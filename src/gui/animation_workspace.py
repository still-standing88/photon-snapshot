"""Application integration for animation, project saves and batch jobs."""
from pathlib import Path
import re
from PIL import Image
from PySide6.QtWidgets import QSplitter, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QFileDialog, QMessageBox, QProgressDialog, QDialog, QDialogButtonBox, QListWidget, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QColorDialog, QPushButton, QMenu
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QAction, QColor
from core.document import Document, Frame
from core.image import PhotonImage
from core.formats import file_filter, format_for_path, get_format
from core.export import ExportOptions, export_document
from core.animation_io import decode_document, save_project
from core.processing import resize
from app_config import key_config
from .managers.job_manager import JobManager, FunctionJob
from .animation_panel import AnimationPanel
from .animation_playback import AnimationPlayback
from .artwork_renderer import render_frame
from .dialogs.export_dialog import ExportDialog


class AnimationWorkspace:
    def initialize_workspace(self):
        self.jobs = JobManager(self)
        self.playback = AnimationPlayback(self.editor, self)
        self.batch_dialog = None
        self.export_options = ExportOptions()
        self._load_generation = 0
        self._pending_exit = False
        self._exit_authorized = False
        self._last_document_id = None
        self._last_content_revision = None
        self._display_cache = {}
        self.editor.state.on_before_edit = self.playback.stop
        self.editor.state.processing_runner = self._process_large_edit

    def build_canvas_workspace(self):
        self.canvas_splitter = QSplitter(Qt.Orientation.Vertical)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scope_row = QWidget()
        row = QHBoxLayout(self.scope_row)
        row.addWidget(QLabel(_('Apply to:')))
        self.frame_scope = QComboBox()
        self.frame_scope.addItem(_('Current frame'), 'current')
        self.frame_scope.addItem(_('Selected frames'), 'selected')
        self.frame_scope.addItem(_('All frames'), 'all')
        self.frame_scope.setAccessibleName(_('Frame edit scope'))
        row.addWidget(self.frame_scope)
        note = QLabel(_('Crop, resize and rotation apply to every frame.'))
        note.setWordWrap(True)
        row.addWidget(note)
        row.addStretch()
        layout.addWidget(self.scope_row)
        layout.addWidget(self.viewer, 1)
        self.scope_row.hide()
        self.canvas_splitter.addWidget(container)
        self.animation_panel = AnimationPanel(self.editor, self.playback, self.jobs, self)
        self.canvas_splitter.addWidget(self.animation_panel)
        self.canvas_splitter.setStretchFactor(0, 1)
        self.animation_panel.hide()
        self.frame_scope.currentIndexChanged.connect(self._scope_changed)
        self.animation_panel.import_requested.connect(self.import_frames)
        self.animation_panel.blank_requested.connect(self.add_blank_frame)
        self.animation_panel.onion_changed.connect(lambda checked: self.refresh_document_view())
        self.playback.frame_changed.connect(lambda frame_id: self.refresh_document_view(playback=True))
        self.playback.state_changed.connect(self._playback_changed)
        self.viewer.shape_finished.connect(self._shape_finished)
        self.viewer.image_clicked.connect(self._place_pending_text)
        return self.canvas_splitter

    def add_workspace_actions(self):
        file_menu, edit_menu, view_menu = self.file_menu, self.edit_menu, self.view_menu
        tools_menu = self.menuBar().addMenu(_('Tools'))
        self.tools_menu = tools_menu
        self.menuBar().insertAction(self.options_menu.menuAction(), tools_menu.menuAction())
        specs = (
            (self.new_menu, 'New Animation', _('New Animation...'), self.new_animation),
            (file_menu, 'Import Frames', _('Import Frames...'), self.import_frames),
            (file_menu, 'Export Animation', _('Export Animation...'), self.export_animation),
            (file_menu, 'Export Current Frame', _('Export Current Frame...'), self.export_current_frame),
            (file_menu, 'Export Frames', _('Export Frames...'), self.export_frames),
            (edit_menu, 'Reset Current Frame', _('Reset Current Frame'), lambda: self.editor.reset_current_frame()),
            (edit_menu, 'Edit Artwork', _('Edit Text and Shapes...'), self.edit_artwork),
            (tools_menu, 'Batch Image Converter', _('Batch Image Converter...'), self.open_batch_converter),
        )
        self.workspace_actions = {}
        for menu, name, label, callback in specs:
            action = QAction(label, self)
            action.setEnabled(name in ('New Animation', 'Batch Image Converter'))
            action.triggered.connect(callback)
            key_config.bind_action('Main Window', name, action)
            menu.addAction(action)
            self.workspace_actions[name] = action
        file_menu.insertAction(self.save_action, self.workspace_actions['Import Frames'])
        for name in ('Export Animation', 'Export Current Frame', 'Export Frames'):
            file_menu.insertAction(self.recent_files_menu.menuAction(), self.workspace_actions[name])
        file_menu.insertSeparator(self.recent_files_menu.menuAction())
        file_menu.removeAction(self.exit_action)
        file_menu.addAction(self.exit_action)
        self.animation_visible_action = QAction(_('Animation Panel'), self)
        self.animation_visible_action.setCheckable(True)
        self.animation_visible_action.toggled.connect(self.animation_panel.setVisible)
        key_config.bind_action('Main Window', 'Show Animation Panel', self.animation_visible_action)
        view_menu.addAction(self.animation_visible_action)
        self.frames_menu = edit_menu.addMenu(_('Frames'))
        for action in self.animation_panel.frame_actions.values():
            self.frames_menu.addAction(action)
        self.frames_menu.aboutToShow.connect(self.animation_panel.update_context_actions)
        self.viewer.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.viewer.customContextMenuRequested.connect(self.show_canvas_menu)
        self.jobs.idle.connect(self._jobs_idle)
        # Slider focus/mouse release ends a gesture; moving frames does too.
        for slider_group in (self.editor_panel.effects_panel.brightness_slider, self.editor_panel.effects_panel.contrast_slider):
            slider_group.slider.sliderPressed.connect(self._begin_edit)
            slider_group.slider.sliderReleased.connect(self.editor.state.end_gesture)
            slider_group.value_spin.editingFinished.connect(self.editor.state.end_gesture)

    def create_canvas_menu(self):
        menu = QMenu(self.viewer)
        has_image = self.editor.document is not None
        for action in (self.undo_action, self.redo_action):
            menu.addAction(action)
        menu.addSeparator()
        for action in (self.zoom_fit_action, self.zoom_actual_action, self.zoom_in_action, self.zoom_out_action):
            menu.addAction(action)
        menu.addSeparator()
        artwork = self.workspace_actions['Edit Artwork']
        artwork.setEnabled(has_image and bool(self.editor.document.frame(self.editor.state.active_frame_id).artwork))
        menu.addAction(artwork)
        menu.addAction(self.workspace_actions['Reset Current Frame'])
        for name in ('Export Current Frame', 'Export Animation', 'Export Frames'):
            menu.addAction(self.workspace_actions[name])
        menu.addSeparator()
        for action in (self.toggle_grid_action, self.toggle_ruler_action, self.toggle_pixel_info_action):
            menu.addAction(action)
        return menu

    def show_canvas_menu(self, position):
        menu = self.create_canvas_menu()
        menu.exec(self.viewer.mapToGlobal(position))
        menu.deleteLater()

    def _begin_edit(self):
        self.playback.stop()
        self.editor.state.end_gesture()

    def _process_large_edit(self, document, mutate, ids):
        from core.export import CancelledError
        def process(control, progress):
            control.checkpoint()
            mutate(document, control.checkpoint)
            control.checkpoint()
            return True
        if not self._run_worker(_('Applying Frame Edits'), process):
            raise CancelledError()

    def _scope_changed(self):
        self.playback.stop()
        self.editor.state.set_scope(self.frame_scope.currentData())

    def _playback_changed(self, playing):
        self.status_label.setText(_('Playback started') if playing else _('Playback stopped'))
        self.refresh_document_view(playback=playing)

    def refresh_document_view(self, playback=False):
        document = self.editor.document
        if not document:
            return
        replaced = document.id != self._last_document_id
        if replaced:
            self.playback.stop()
            self._last_document_id = document.id
            self._display_cache.clear()
            self.animation_visible_action.setChecked(document.animation)
            self.scope_row.setVisible(document.animation)
        if not playback and document.revision != self._last_content_revision:
            self.playback.stop()
            self._display_cache.clear()
        self._last_content_revision = document.revision
        frame = document.frame(self.editor.state.active_frame_id)
        cache_key = frame.id, document.revision
        pixels = self._display_cache.get(cache_key)
        if pixels is None:
            pixels = render_frame(frame) if frame.artwork else frame.image.current
            # Bound cached rendered canvases to roughly 64 MiB.
            if sum(i.width*i.height*4 for i in self._display_cache.values()) + pixels.width*pixels.height*4 > 64*1024**2:
                self._display_cache.clear()
            self._display_cache[cache_key] = pixels
        if self.animation_panel.onion.isChecked() and not self.playback.playing:
            index = document.frames.index(frame)
            if index > 0:
                previous = render_frame(document.frames[index-1]).convert('RGBA')
                previous.putalpha(previous.getchannel('A').point(lambda value: int(value*.2)))
                pixels = Image.alpha_composite(pixels.convert('RGBA'), previous)
        self.viewer.set_pixmap(__import__('core.utils', fromlist=['pil_to_qpixmap']).pil_to_qpixmap(pixels))
        if not playback:
            self.animation_panel.refresh()
        else:
            self.animation_panel.sync_playback()
        for name, action in self.workspace_actions.items():
            if name in ('New Animation', 'Batch Image Converter'):
                continue
            action.setEnabled(bool(document) and (document.animation if name == 'Export Animation' else True))
        self._update_image_info()
        self._update_window_title()

    def _run_worker(self, title, function):
        dialog = QProgressDialog(title, _('Cancel'), 0, 0, self)
        dialog.setWindowTitle(title)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        result = {'value': None, 'error': None, 'cancelled': False, 'finished': False}
        job = FunctionJob(function, self)
        def cancel():
            job.control.cancel()
            dialog.setLabelText(_('Cancelling... Waiting for the current operation to finish.'))
        dialog.canceled.connect(cancel)
        job.progress.connect(lambda a, b: (dialog.setRange(0, b), dialog.setValue(a)))
        job.succeeded.connect(lambda value: result.update(value=value))
        job.failed.connect(lambda message: result.update(error=message))
        job.cancelled.connect(lambda: result.update(cancelled=True))
        job.finished.connect(lambda: result.update(finished=True))
        job.finished.connect(dialog.accept)
        self.jobs.start(job)
        dialog.exec()
        # A cancelled dialog may hide before the worker's codec returns.
        # Keep its owner alive; do not expose a partially completed result.
        if not result['finished']:
            from PySide6.QtCore import QEventLoop
            loop = QEventLoop()
            job.finished.connect(loop.quit)
            if not result['finished']:
                loop.exec()
        dialog.deleteLater()
        if result['error']:
            QMessageBox.warning(self, _('Operation Failed'), result['error'])
        return None if result['error'] or result['cancelled'] else result['value']

    def new_animation(self):
        from .dialogs.new_animation_dialog import NewAnimationDialog
        dialog = NewAnimationDialog(self)
        if not dialog.exec() or not self._confirm_close():
            return
        width, height, colour = dialog.values()
        pixels = Image.new('RGBA', (width, height), (colour.red(), colour.green(), colour.blue(), 0 if dialog.transparent.isChecked() else colour.alpha()))
        image = PhotonImage(pixels)
        document = Document([Frame(image, dialog.duration.value())], 'PNG', dialog.plays.value(), True, store=image.store)
        self.current_file_path = None
        self.editor.load_document(document, True)
        self.editor_panel.reset_controls()

    def import_frames(self):
        if not self.editor.document:
            self.new_animation()
            if not self.editor.document:
                return
        paths, selected = QFileDialog.getOpenFileNames(self, _('Import Frames'), '', file_filter())
        if not paths:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Import Frame Sizing'))
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(_('Import order follows file selection. Choose sizing for the existing canvas.')))
        sizing = QComboBox()
        sizing.addItem(_('Fit with transparent padding'), 'contain')
        sizing.addItem(_('Fill with cropping'), 'fill')
        sizing.addItem(_('Stretch'), 'exact')
        layout.addWidget(sizing)
        natural = QCheckBox(_('Sort naturally by filename'))
        layout.addWidget(natural)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if not dialog.exec():
            return
        if natural.isChecked():
            paths.sort(key=lambda path: [int(part) if part.isdigit() else part.lower() for part in re.split(r'(\d+)', Path(path).name)])
        document_id, revision, canvas = self.editor.document.id, self.editor.document.revision, self.editor.document.canvas_size
        mode = sizing.currentData()
        def imported(control, progress):
            frames = []
            for index, path in enumerate(paths):
                control.checkpoint()
                document = decode_document(path, control.cancelled.is_set)
                for frame in document.frames:
                    control.checkpoint()
                    frame.image.current = resize(frame.image.current, canvas, mode)
                    frames.append(frame)
                progress(index+1, len(paths))
            return frames
        frames = self._run_worker(_('Importing Frames'), imported)
        if frames is not None and self.editor.document.id == document_id and self.editor.document.revision == revision:
            self.editor.add_frames(frames)

    def add_blank_frame(self):
        if self.editor.document:
            frame = Frame(PhotonImage(Image.new('RGBA', self.editor.document.canvas_size), self.editor.document.store))
            self.editor.add_frames([frame])
            self.editor.set_active_frame(self.editor.document.frames[-1].id)

    def load_document_file(self, path):
        if not self._confirm_close():
            return
        self.playback.stop()
        self._load_generation += 1
        generation = self._load_generation
        try:
            # Tiny static previews preserve the existing immediate Explorer API.
            if Path(path).suffix.lower() in ('.gif', '.webp', '.photonanim') or Path(path).stat().st_size > 1024**2:
                document = self._run_worker(_('Opening Image'), lambda c, p: decode_document(path, c.cancelled.is_set, p))
            else:
                document = decode_document(path)
            if document is None or generation != self._load_generation:
                return
            self.current_file_path = path
            self.export_options = ExportOptions(format_id=document.source_format if document.source_format in ('JPEG', 'PNG', 'BMP', 'TIFF', 'GIF', 'WEBP') else 'PNG')
            self.editor.load_document(document)
            self.editor_panel.reset_controls()
            self.status_label.setText(_('Loaded: ') + Path(path).name)
            self.explorer_widget.explorer.add_recent_file(path)
        except Exception as exc:
            QMessageBox.warning(self, _('Cannot Open Image'), str(exc))

    def save_document(self, save_as=False):
        document = self.editor.document
        if not document:
            return
        path = self.current_file_path
        project = bool(document.has_artwork or (document.animation and (save_as or not path or Path(path).suffix.lower() == '.photonanim')))
        if save_as or not path or (document.has_artwork and Path(path).suffix.lower() != '.photonanim'):
            filters = 'Photon Animation Project (*.photonanim)' if project else file_filter(save=True)
            suggested = str(Path(path).with_suffix('.photonanim')) if project and path else path or ''
            path, selected = QFileDialog.getSaveFileName(self, _('Save Animation Project') if project else _('Save Image As'), suggested, filters)
            if not path:
                return
            if not Path(path).suffix:
                fmt = 'PHOTONANIM' if project else selected.split()[0].upper()
                path += '.photonanim' if project else get_format(fmt).extension
            project = Path(path).suffix.lower() == '.photonanim'
        if document.animation and not project and not get_format(format_for_path(path).id).animation:
            QMessageBox.warning(self, _('Choose an Animation Format'), _('Save an editable .photonanim project or export GIF/WebP. Use Export Current Frame for still images.'))
            return
        options = self.export_options
        if not project:
            fmt = format_for_path(path).id
            if save_as or fmt != options.format_id:
                dialog = ExportDialog(self, document=document)
                dialog.options.load({**__import__('dataclasses').asdict(options), 'format_id': fmt, 'quality': min(options.quality, 95)})
                if not dialog.exec():
                    return
                options = dialog.options.values()
                if options.format_id != fmt:
                    path = str(Path(path).with_suffix(get_format(options.format_id).extension))
        snapshot, state_id = document.snapshot(), self.editor.state.state_id
        def save(control, progress):
            if project:
                save_project(path, snapshot, cancel=control.cancelled.is_set)
            else:
                export_document(path, snapshot, options, render_frame, cancel=control.cancelled.is_set)
            return path
        saved = self._run_worker(_('Saving Document'), save)
        if saved is not None and self.editor.document.id == snapshot.id:
            self.current_file_path = str(saved)
            self.export_options = options
            self.editor.current_image.format = options.format_id
            self.editor.mark_saved(state_id)
            self._update_window_title()
            self.status_label.setText(_('Saved: ') + Path(saved).name)
            self.explorer_widget.explorer.add_recent_file(str(saved))

    def export_animation(self):
        self._export_frames(False, True)

    def export_current_frame(self):
        self._export_frames(False, False)

    def export_frames(self):
        self._export_frames(True, False)

    def _export_frames(self, separate, animated):
        document = self.editor.document
        if not document:
            return
        dialog = ExportDialog(self, animated, document)
        if not dialog.exec():
            return
        options = dialog.options.values()
        snapshot = document.snapshot()
        if separate:
            folder = QFileDialog.getExistingDirectory(self, _('Export Frames Folder'))
            if not folder:
                return
            def export(control, progress):
                for index, frame in enumerate(snapshot.frames):
                    control.checkpoint()
                    path = Path(folder) / f'frame_{index+1:06d}{get_format(options.format_id).extension}'
                    export_document(path, snapshot, options, render_frame, overwrite=False, cancel=control.cancelled.is_set, frame_ids={frame.id})
                    progress(index+1, len(snapshot.frames))
                return folder
        else:
            path, selected = QFileDialog.getSaveFileName(self, _('Export Animation') if animated else _('Export Current Frame'), '',
                f'{get_format(options.format_id).label} (*{get_format(options.format_id).extension})')
            if not path:
                return
            if Path(path).suffix.lower() not in get_format(options.format_id).extensions:
                path = str(Path(path).with_suffix(get_format(options.format_id).extension))
            ids = None if animated else {self.editor.state.active_frame_id}
            def export(control, progress):
                export_document(path, snapshot, options, render_frame, cancel=control.cancelled.is_set, frame_ids=ids)
                return path
        if self._run_worker(_('Exporting Images'), export) is not None:
            self.status_label.setText(_('Export complete'))

    def open_batch_converter(self):
        if self.batch_dialog is None:
            from tools.image_batch_converter.ui import BatchConverterDialog
            self.batch_dialog = BatchConverterDialog(self.jobs, self)
        self.batch_dialog.show()
        self.batch_dialog.raise_()
        self.batch_dialog.activateWindow()

    def add_document_text(self, text, position='Click to Place', font_size=16, colour=None, background=True):
        if not self.editor.document:
            return
        width, height = self.editor.document.canvas_size
        colour = colour or QColor(255, 255, 255)
        item = {'kind': 'text', 'text': text, 'font_size': font_size, 'x': 10, 'y': 10,
                'width': min(width, max(font_size*len(text), font_size)), 'height': min(height, font_size*3),
                'color': [colour.red(), colour.green(), colour.blue(), colour.alpha()], 'background': background, 'opacity': 1}
        if position == 'Click to Place':
            self._pending_text = item
            self.status_label.setText(_('Click the canvas to place text'))
            return
        item['x'] = (width-item['width'])/2 if 'Center' in position or position == 'Center' else width-item['width'] if 'Right' in position else 10
        item['y'] = height-item['height'] if 'Bottom' in position else (height-item['height'])/2 if position in ('Center', 'Left Center', 'Right Center') else 10
        self.editor.add_artwork(item)

    def _place_pending_text(self, x, y):
        item = getattr(self, '_pending_text', None)
        if item:
            item['x'], item['y'] = x, y
            self._pending_text = None
            self.editor.add_artwork(item)

    def _shape_finished(self, kind, x1, y1, x2, y2):
        if self.editor.document:
            kind = 'ellipse' if kind == 'circle' else kind
            self.editor.add_artwork({'kind': kind, 'x': min(x1, x2) if kind != 'line' else x1,
                'y': min(y1, y2) if kind != 'line' else y1, 'width': abs(x2-x1) if kind != 'line' else x2-x1,
                'height': abs(y2-y1) if kind != 'line' else y2-y1, 'color': [self.viewer.pen_color.red(), self.viewer.pen_color.green(), self.viewer.pen_color.blue(), self.viewer.pen_color.alpha()],
                'stroke_width': self.viewer.pen_width, 'opacity': 1})

    def edit_artwork(self):
        if not self.editor.document:
            return
        artwork = self.editor.document.frame(self.editor.state.active_frame_id).artwork
        if not artwork:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(_('Edit Text and Shapes'))
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        for item in artwork:
            listing.addItem(item.get('text', item['kind']))
        layout.addWidget(listing)
        form = QFormLayout()
        fields = {}
        for key, label in (('text', _('Text:')), ('x', _('X:')), ('y', _('Y:')), ('width', _('Width:')), ('height', _('Height:')),
                           ('font_size', _('Font size:')), ('stroke_width', _('Stroke width:')), ('opacity', _('Opacity:'))):
            control = QLineEdit() if key == 'text' else QDoubleSpinBox()
            if key != 'text':
                control.setRange(0 if key == 'opacity' else -100000, 1 if key == 'opacity' else 100000)
            form.addRow(label, control)
            fields[key] = control
        visible = QCheckBox(_('Visible'))
        form.addRow(visible)
        colour_button = QPushButton(_('Colour...'))
        form.addRow(colour_button)
        colour_value = [255, 255, 255, 255]
        def choose_colour():
            value = QColorDialog.getColor(QColor(*colour_value), dialog, _('Artwork Colour'), QColorDialog.ColorDialogOption.ShowAlphaChannel)
            if value.isValid():
                colour_value[:] = [value.red(), value.green(), value.blue(), value.alpha()]
        colour_button.clicked.connect(choose_colour)
        layout.addLayout(form)
        def selected(index):
            if index < 0:
                return
            item = artwork[index]
            for key, control in fields.items():
                control.setText(item.get(key, '')) if key == 'text' else control.setValue(item.get(key, 1 if key == 'opacity' else 0))
            visible.setChecked(item.get('visible', True))
            colour_value[:] = item.get('color', [255, 255, 255, 255])
        listing.currentRowChanged.connect(selected)
        listing.setCurrentRow(0)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            index = listing.currentRow()
            item = dict(artwork[index])
            for key, control in fields.items():
                item[key] = control.text() if key == 'text' else control.value()
            item['visible'] = visible.isChecked()
            item['color'] = list(colour_value)
            self.editor.update_artwork(index, item)

    def _jobs_idle(self):
        if self._pending_exit:
            self._pending_exit = False
            self._force_exit = True
            self._exit_authorized = True
            self.close()
