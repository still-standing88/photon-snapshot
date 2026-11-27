"""Photon implementation of the referenced four-tab conversion workflow."""
from dataclasses import asdict
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QComboBox, QPushButton, QLabel, QTreeWidget, QTreeWidgetItem, QFileDialog, QMessageBox, QCheckBox, QLineEdit, QRadioButton, QButtonGroup, QListWidget, QListWidgetItem, QDialogButtonBox, QMenu, QAbstractItemView
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from core.formats import file_filter, FORMATS
from core.effects_catalog import EFFECTS, validate_effect
from core.batch_conversion import SourceEntry, BatchSettings, DestinationOptions
from gui.dialogs.effect_dialog import EffectDialog
from gui.dialogs.export_dialog import ExportOptionsWidget
from gui_controls.job_progress_dialog import JobProgressDialog
from .job import BatchJob
from app_db import db
from gui.effect_labels import effect_label, category_label


class BatchConverterDialog(QDialog):
    def __init__(self, jobs, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.job = None
        self.progress_dialog = None
        self.preset_error = ''
        self.setWindowTitle(_('Batch Image Converter'))
        self.resize(780, 580)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel(_('Preset:')))
        self.preset = QComboBox()
        self.preset.setEditable(True)
        self.preset.setAccessibleName(_('Batch preset name'))
        row.addWidget(self.preset, 1)
        self.preset.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preset.customContextMenuRequested.connect(self.preset_menu)
        self.preset.lineEdit().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preset.lineEdit().customContextMenuRequested.connect(self.preset_menu)
        layout.addLayout(row)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._source_tab()
        self._convert_tab()
        self._processing_tab()
        self._destination_tab()
        self.validation = QLabel()
        self.validation.setWordWrap(True)
        layout.addWidget(self.validation)
        row = QHBoxLayout()
        row.addStretch()
        self.begin = QPushButton(_('Begin'))
        self.begin.clicked.connect(self.start)
        row.addWidget(self.begin)
        layout.addLayout(row)
        self.refresh_presets()
        self.preset.activated.connect(self.load_preset)
        self.encoding.format.currentIndexChanged.connect(self._clear_preset_error)
        self.effects.model().rowsRemoved.connect(self._clear_preset_error)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.dialog_menu)
        self._shortcuts = []
        for widget, callback in ((self.sources, self.remove_sources), (self.effects, self.remove_effects)):
            shortcut = QShortcut(QKeySequence('Delete'), widget)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _tab(self, label):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.tabs.addTab(widget, label)
        return layout

    def _source_tab(self):
        layout = self._tab(_('Source'))
        layout.addWidget(QLabel(_('Right-click to add files or folders. Shift+F10 opens the context menu.')))
        self.sources = QTreeWidget()
        self.sources.setHeaderLabels([_('Path'), _('Formats')])
        self.sources.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.sources.setAccessibleName(_('Batch source files and folders'))
        self.sources.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sources.customContextMenuRequested.connect(self.source_menu)
        layout.addWidget(self.sources)

    def add_source(self, entry):
        import os
        canonical = os.path.normcase(os.path.realpath(entry.path))
        for i in range(self.sources.topLevelItemCount()):
            existing = self.sources.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
            if os.path.normcase(os.path.realpath(existing.path)) == canonical:
                return
        item = QTreeWidgetItem([entry.path, ', '.join(entry.formats) or _('All supported images')])
        item.setData(0, Qt.ItemDataRole.UserRole, entry)
        item.setToolTip(0, entry.path)
        if entry.recursive:
            item.addChild(QTreeWidgetItem([_('Subfolders discovered when Begin is pressed'), '']))
        self.sources.addTopLevelItem(item)
        self.sources.resizeColumnToContents(0)

    def add_files(self):
        paths, selected = QFileDialog.getOpenFileNames(self, _('Add Image Files'), '', file_filter())
        for path in paths:
            self.add_source(SourceEntry(path))

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, _('Add Image Folder'))
        if not path:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Folder Options'))
        layout = QVBoxLayout(dialog)
        recursive = QCheckBox(_('Include all subfolders'))
        layout.addWidget(recursive)
        formats = QComboBox()
        formats.addItem(_('All supported image formats'), ())
        for fmt in FORMATS:
            if fmt.readable:
                formats.addItem(fmt.label, (fmt.id,))
        layout.addWidget(formats)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            self.add_source(SourceEntry(path, recursive.isChecked(), formats.currentData()))

    def remove_sources(self):
        for item in self.sources.selectedItems():
            index = self.sources.indexOfTopLevelItem(item)
            if index >= 0:
                self.sources.takeTopLevelItem(index)

    def create_source_menu(self):
        menu = QMenu(self)
        for label, callback in ((_('Add Files...'), self.add_files), (_('Add Folder...'), self.add_folder),
                                (_('Remove'), self.remove_sources), (_('Clear'), self.sources.clear)):
            action = menu.addAction(label, callback)
            if callback == self.remove_sources:
                action.setEnabled(any(self.sources.indexOfTopLevelItem(i) >= 0 for i in self.sources.selectedItems()))
            elif callback == self.sources.clear:
                action.setEnabled(self.sources.topLevelItemCount() > 0)
        return menu

    def source_menu(self, position):
        menu = self.create_source_menu()
        menu.exec(self.sources.mapToGlobal(position))
        menu.deleteLater()

    def _convert_tab(self):
        layout = self._tab(_('Convert'))
        self.encoding = ExportOptionsWidget()
        layout.addWidget(self.encoding)
        self.animation = QComboBox()
        for label, value in ((_('Preserve animation'), 'preserve'), (_('First frame'), 'first'), (_('Separate frames'), 'separate')):
            self.animation.addItem(label, value)
        form = QFormLayout()
        form.addRow(_('Animation handling:'), self.animation)
        layout.addLayout(form)
        layout.addStretch()

    def _processing_tab(self):
        layout = self._tab(_('Processing'))
        layout.addWidget(QLabel(_('Right-click to add, edit or reorder effects.')))
        self.effects = QListWidget()
        self.effects.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.effects.setAccessibleName(_('Applied image effects in order'))
        self.effects.itemDoubleClicked.connect(lambda item: self.edit_effect())
        self.effects.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.effects.customContextMenuRequested.connect(self.effect_menu)
        layout.addWidget(self.effects)

    def pick_effect(self, filters):
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Choose Image Filter') if filters else _('Choose Image Edit'))
        layout = QVBoxLayout(dialog)
        tree = QTreeWidget()
        tree.setHeaderLabels([_('Effect')])
        categories = {}
        for effect in EFFECTS.values():
            if (effect.category in ('Colour', 'Filters')) != filters:
                continue
            if effect.category not in categories:
                categories[effect.category] = QTreeWidgetItem(tree, [category_label(effect.category)])
            item = QTreeWidgetItem(categories[effect.category], [effect_label(effect.id)])
            item.setData(0, Qt.ItemDataRole.UserRole, effect.id)
        tree.expandAll()
        if tree.topLevelItemCount():
            tree.setCurrentItem(tree.topLevelItem(0).child(0))
        layout.addWidget(tree)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        tree.itemDoubleClicked.connect(lambda item, column: dialog.accept() if item.data(0, Qt.ItemDataRole.UserRole) else None)
        layout.addWidget(buttons)
        if dialog.exec() and tree.currentItem():
            effect_id = tree.currentItem().data(0, Qt.ItemDataRole.UserRole)
            if effect_id:
                parameters = EffectDialog(effect_id, parent=self)
                if parameters.exec():
                    self.add_effect(effect_id, parameters.values())

    def add_effect(self, effect_id, values):
        values = validate_effect(effect_id, values)
        item = QListWidgetItem(effect_label(effect_id) + ': ' + str(values))
        item.setData(Qt.ItemDataRole.UserRole, (effect_id, values))
        self.effects.addItem(item)

    def edit_effect(self):
        item = self.effects.currentItem()
        if item:
            effect_id, values = item.data(Qt.ItemDataRole.UserRole)
            dialog = EffectDialog(effect_id, values, self)
            if dialog.exec():
                values = dialog.values()
                item.setData(Qt.ItemDataRole.UserRole, (effect_id, values))
                item.setText(effect_label(effect_id) + ': ' + str(values))

    def remove_effects(self):
        for item in self.effects.selectedItems():
            self.effects.takeItem(self.effects.row(item))

    def move_effect(self, step):
        row = self.effects.currentRow()
        if row >= 0 and 0 <= row+step < self.effects.count():
            self.effects.insertItem(row+step, self.effects.takeItem(row))
            self.effects.setCurrentRow(row+step)

    def create_effect_menu(self):
        menu = QMenu(self)
        menu.addAction(_('Add Edit...'), lambda: self.pick_effect(False))
        menu.addAction(_('Add Filter...'), lambda: self.pick_effect(True))
        menu.addSeparator()
        selected = self.effects.selectedItems()
        single = len(selected) == 1 and self.effects.currentItem() in selected
        row = self.effects.currentRow()
        for label, callback, enabled in ((_('Edit'), self.edit_effect, single), (_('Remove'), self.remove_effects, bool(selected)),
                                (_('Move Up'), lambda: self.move_effect(-1), single and row > 0),
                                (_('Move Down'), lambda: self.move_effect(1), single and row < self.effects.count()-1),
                                (_('Clear All'), self.effects.clear, self.effects.count() > 0)):
            menu.addAction(label, callback).setEnabled(enabled)
        return menu

    def effect_menu(self, position):
        menu = self.create_effect_menu()
        menu.exec(self.effects.mapToGlobal(position))
        menu.deleteLater()

    def create_preset_menu(self):
        menu = self.preset.lineEdit().createStandardContextMenu()
        menu.addSeparator()
        name = self.preset.currentText().strip()
        saved = bool(name and name in db.list_presets('image_batch'))
        menu.addAction(_('Save Preset'), self.save_preset).setEnabled(bool(name) and not self.preset_error)
        menu.addAction(_('Load Preset'), lambda: self.load_preset(self.preset.currentIndex())).setEnabled(saved)
        menu.addAction(_('Delete Preset'), self.delete_preset).setEnabled(saved)
        return menu

    def preset_menu(self, position):
        menu = self.create_preset_menu()
        menu.exec(self.preset.lineEdit().mapToGlobal(position))
        menu.deleteLater()

    def dialog_menu(self, position):
        menu = QMenu(self)
        menu.addAction(_('Show Progress'), self.reopen_progress).setEnabled(self.progress_dialog is not None)
        menu.addAction(_('Hide'), self.hide)
        menu.exec(self.mapToGlobal(position))
        menu.deleteLater()

    def _destination_tab(self):
        layout = self._tab(_('Destination'))
        self.original = QRadioButton(_('Original folders'))
        self.selected = QRadioButton(_('Selected folder'))
        self.original.setChecked(True)
        self.folder_group = QButtonGroup(self)
        self.folder_group.addButton(self.original)
        self.folder_group.addButton(self.selected)
        layout.addWidget(self.original)
        layout.addWidget(self.selected)
        row = QHBoxLayout()
        self.destination = QLineEdit()
        self.destination.setAccessibleName(_('Destination folder'))
        browse = QPushButton(_('Browse...'))
        browse.clicked.connect(lambda: self.destination.setText(QFileDialog.getExistingDirectory(self, _('Destination Folder')) or self.destination.text()))
        row.addWidget(self.destination, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        self.subfolders = QCheckBox(_('Preserve subfolders'))
        self.overwrite = QCheckBox(_('Overwrite existing files'))
        self.delete_originals = QCheckBox(_('Delete original files after verified conversion'))
        self.create_log = QCheckBox(_('Create log file'))
        for control in (self.subfolders, self.overwrite, self.delete_originals, self.create_log):
            layout.addWidget(control)
        row = QHBoxLayout()
        self.log_path = QLineEdit()
        self.log_path.setAccessibleName(_('Log file path'))
        log_button = QPushButton(_('Set Log File...'))
        log_button.clicked.connect(lambda: self.log_path.setText(QFileDialog.getSaveFileName(self, _('Conversion Log'), '', 'JSON (*.json)')[0] or self.log_path.text()))
        row.addWidget(self.log_path, 1)
        row.addWidget(log_button)
        layout.addLayout(row)
        def enabled():
            self.destination.setEnabled(self.selected.isChecked())
            browse.setEnabled(self.selected.isChecked())
            self.subfolders.setEnabled(self.selected.isChecked())
            self.log_path.setEnabled(self.create_log.isChecked())
            log_button.setEnabled(self.create_log.isChecked())
        self.selected.toggled.connect(enabled)
        self.create_log.toggled.connect(enabled)
        enabled()
        layout.addStretch()

    def processing_values(self):
        return tuple(self.effects.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.effects.count()))

    def refresh_presets(self):
        self.preset.clear()
        self.preset.addItems(db.list_presets('image_batch'))
        self.preset.setCurrentIndex(-1)

    def save_preset(self):
        name = self.preset.currentText().strip()
        if not name:
            return
        db.save_preset('image_batch', name, {'version': 1, 'convert': asdict(self.encoding.values()),
                       'animation_handling': self.animation.currentData(), 'processing': self.processing_values()})
        self.refresh_presets()
        self.preset.setCurrentText(name)

    def delete_preset(self):
        name = self.preset.currentText().strip()
        if name:
            db.delete_preset('image_batch', name)
            self.refresh_presets()

    def load_preset(self, index):
        try:
            payload = db.get_preset('image_batch', self.preset.currentText())
            if not payload or payload.get('version') != 1:
                raise ValueError('Unsupported preset version')
            # Validate before replacing current controls; never omit an effect.
            from core.export import ExportOptions
            ExportOptions(**payload['convert']).validate()
            for effect_id, values in payload['processing']:
                validate_effect(effect_id, values)
            policy_index = self.animation.findData(payload['animation_handling'])
            if policy_index < 0:
                raise ValueError('Invalid animation handling policy')
            self.encoding.load(payload['convert'])
            self.animation.setCurrentIndex(policy_index)
            self.effects.clear()
            for effect_id, values in payload['processing']:
                self.add_effect(effect_id, values)
            self._clear_preset_error()
        except Exception as exc:
            self.preset_error = str(exc)
            self.validation.setText(_('Preset needs correction: ') + str(exc))
            self.begin.setEnabled(False)

    def _clear_preset_error(self, *args):
        self.preset_error = ''
        self.validation.clear()
        if hasattr(self, 'begin'):
            self.begin.setEnabled(not (self.job and self.job.isRunning()))

    def start(self):
        try:
            sources = tuple(self.sources.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) for i in range(self.sources.topLevelItemCount()))
            if not sources:
                raise ValueError('Add image files or a folder first')
            if self.selected.isChecked() and not self.destination.text().strip():
                raise ValueError('Select a destination folder')
            if self.create_log.isChecked() and not self.log_path.text().strip():
                raise ValueError('Select a log file')
            settings = BatchSettings(self.encoding.values(), self.processing_values(), DestinationOptions(
                self.destination.text() if self.selected.isChecked() else '', self.subfolders.isChecked(),
                self.overwrite.isChecked(), self.delete_originals.isChecked(), self.log_path.text() if self.create_log.isChecked() else ''),
                self.animation.currentData())
            if self.progress_dialog:
                self.progress_dialog.deleteLater()
            if self.job:
                self.job.deleteLater()
            self.job = BatchJob(sources, settings, self)
            self.progress_dialog = JobProgressDialog(self.job, self)
            self.job.finished.connect(lambda: self.begin.setEnabled(True))
            self.begin.setEnabled(False)
            self.jobs.start(self.job)
            self.reopen_progress()
        except Exception as exc:
            QMessageBox.warning(self, _('Cannot Begin'), str(exc))

    def reopen_progress(self):
        if self.progress_dialog:
            self.progress_dialog.show()
            self.progress_dialog.raise_()
            self.progress_dialog.activateWindow()

    def reject(self):
        self.close()

    def closeEvent(self, event):
        if self.job and self.job.isRunning():
            reply = QMessageBox.question(self, _('Conversion Still Running'), _('Continue conversion in the background? Choose No to cancel the job.'),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if reply == QMessageBox.StandardButton.No:
                self.job.control.cancel()
        self.hide()
        event.ignore()
