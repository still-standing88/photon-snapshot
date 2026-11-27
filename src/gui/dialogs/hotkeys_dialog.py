"""Accessible shortcut editor adapted from the updated playForm dialog.

Changes stay in a draft until Apply/OK. Cancel also discards pending resets
and enabled-state changes. The editor is a normal panel in the focus tree.
"""
from PySide6.QtCore import QEvent, Qt, Signal, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu,
    QMessageBox, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app_config import key_config


class ShortcutEdit(QLineEdit):
    captured = Signal(str)
    captureCancelled = Signal()
    _MODIFIERS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                  Qt.Key.Key_Meta, Qt.Key.Key_AltGr}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._armed = False
        self._captured_key = None
        self._captured_sequence = ""
        self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)

    def set_capture_armed(self, armed):
        self._armed = armed
        self._captured_key = None
        self.setReadOnly(armed)
        self.setAccessibleDescription(
            _("Press a key combination and release it to accept. Escape cancels recording.")
            if armed else _("Type a shortcut or use Capture key. Leave empty to unbind.")
        )

    def event(self, event):
        if event.type() == QEvent.Type.ShortcutOverride and self._armed:
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if not self._armed:
            super().keyPressEvent(event)
            return
        event.accept()
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.captureCancelled.emit()
        elif key not in self._MODIFIERS and key != Qt.Key.Key_unknown:
            self._captured_key = key
            self._captured_sequence = QKeySequence(event.keyCombination()).toString(
                QKeySequence.SequenceFormat.PortableText)
            self.setText(self._captured_sequence)

    def keyReleaseEvent(self, event):
        if not self._armed:
            super().keyReleaseEvent(event)
            return
        event.accept()
        if not event.isAutoRepeat() and event.key() == self._captured_key:
            self.captured.emit(self._captured_sequence)


class HotkeysTree(QTreeWidget):
    enter_pressed = Signal(object)
    toggle_requested = Signal(object)

    def keyPressEvent(self, event):
        item = self.currentItem()
        if item is not None and item.parent() is not None:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.enter_pressed.emit(item)
                event.accept()
                return
            if event.key() == Qt.Key.Key_Space:
                self.toggle_requested.emit(item)
                event.accept()
                return
        super().keyPressEvent(event)


class HotkeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._draft, self._disabled = key_config.snapshot_configuration()
        self._edit_item = None
        self._dirty = False
        self.setWindowTitle(_("Hotkeys Configuration"))
        self.setAccessibleName(_("Hotkeys Configuration Dialog"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(700, 550)
        self.setMinimumSize(600, 400)
        self.setup_ui()
        self.populate_tree()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(_("Search hotkeys"))
        self.search_edit.setAccessibleName(_("Search hotkeys"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.filter_hotkeys)
        layout.addWidget(self.search_edit)

        self.tree = HotkeysTree()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([_("Action"), _("Shortcut")])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionsMovable(False)
        self.tree.header().setSectionsClickable(False)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.currentItemChanged.connect(self.on_current_item_changed)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_item_clicked)
        self.tree.enter_pressed.connect(self.focus_editor)
        self.tree.toggle_requested.connect(self.toggle_item_enabled)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        layout.addWidget(self.tree, 1)

        self.edit_panel = QWidget()
        edit_layout = QVBoxLayout(self.edit_panel)
        edit_layout.setContentsMargins(0, 4, 0, 0)
        self.edit_label = QLabel()
        self.edit_label.setWordWrap(True)
        edit_layout.addWidget(self.edit_label)
        row = QHBoxLayout()
        self.edit_field = ShortcutEdit()
        self.edit_label.setBuddy(self.edit_field)
        self.edit_field.textEdited.connect(self.on_field_edited)
        self.edit_field.captured.connect(self.on_shortcut_captured)
        self.edit_field.captureCancelled.connect(self.disarm_capture)
        row.addWidget(self.edit_field, 1)
        self.capture_button = QPushButton(_("Capture key"))
        self.capture_button.setCheckable(True)
        self.capture_button.toggled.connect(self.on_capture_toggled)
        row.addWidget(self.capture_button)
        edit_layout.addLayout(row)
        layout.addWidget(self.edit_panel)
        self.edit_panel.hide()

        row = QHBoxLayout()
        self.reset_button = QPushButton(_("Reset to Default"))
        self.reset_button.setAccessibleName(_("Reset all shortcuts to default"))
        self.reset_button.clicked.connect(self.reset_to_default)
        row.addWidget(self.reset_button)
        row.addStretch()
        self.apply_button = QPushButton(_("Apply"))
        self.apply_button.clicked.connect(self.apply_changes)
        self.ok_button = QPushButton(_("OK"))
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        for button in (self.capture_button, self.reset_button, self.apply_button,
                       self.ok_button, self.cancel_button):
            button.setAutoDefault(False)
        for button in (self.apply_button, self.ok_button, self.cancel_button):
            row.addWidget(button)
        layout.addLayout(row)

    @staticmethod
    def _item_key(item):
        return (item.data(0, Qt.ItemDataRole.UserRole),
                item.data(0, Qt.ItemDataRole.UserRole + 1))

    def _refresh_item(self, item):
        section, action = self._item_key(item)
        sequence = self._draft[section][action]
        was_blocked = self.tree.blockSignals(True)
        item.setText(1, sequence)
        item.setCheckState(0, Qt.CheckState.Unchecked if (section, action) in self._disabled
                          else Qt.CheckState.Checked)
        self.tree.blockSignals(was_blocked)

    def populate_tree(self):
        self.disarm_capture()
        self._edit_item = None
        self._dirty = False
        self.edit_panel.hide()
        self.tree.blockSignals(True)
        self.tree.clear()
        for section, actions in self._draft.items():
            category = QTreeWidgetItem(self.tree, [_(section), ""])  # i18n-dynamic: ok
            for action in actions:
                item = QTreeWidgetItem(category, [_(action), ""])  # i18n-dynamic: ok
                item.setData(0, Qt.ItemDataRole.UserRole, section)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, action)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                self._refresh_item(item)
        self.tree.blockSignals(False)
        self.filter_hotkeys(self.search_edit.text())

    @Slot(object, int)
    def on_item_changed(self, item, column):
        if column == 0 and item.parent() is not None:
            key = self._item_key(item)
            if item.checkState(0) == Qt.CheckState.Checked:
                self._disabled.discard(key)
            else:
                self._disabled.add(key)

    @Slot(object)
    def toggle_item_enabled(self, item):
        item.setCheckState(0, Qt.CheckState.Unchecked
                          if item.checkState(0) == Qt.CheckState.Checked else Qt.CheckState.Checked)

    @Slot(object, int)
    def on_item_clicked(self, item, column):
        if column == 1 and item.parent() is not None:
            self.focus_editor(item)

    @Slot(object, object)
    def on_current_item_changed(self, current, previous):
        if not self.commit_pending():
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(previous)
            self.tree.blockSignals(False)
            return
        self.load_panel(current)

    @Slot(object)
    def focus_editor(self, item):
        if not self.commit_pending():
            return
        if self.tree.currentItem() is not item:
            self.tree.setCurrentItem(item)
        self.load_panel(item)
        self.edit_field.setFocus()

    def load_panel(self, item):
        self.disarm_capture()
        self._edit_item = item if item is not None and item.parent() is not None else None
        self._dirty = False
        self.edit_panel.setVisible(self._edit_item is not None)
        if self._edit_item is not None:
            section, action = self._item_key(item)
            self.edit_field.setText(self._draft[section][action])
            label = _("Editing: {action} in {section}").format(
                action=_(action), section=_(section))  # i18n-dynamic: ok
            self.edit_label.setText(label)
            self.edit_field.setAccessibleName(label)
            self.edit_field.set_capture_armed(False)

    @Slot(str)
    def on_field_edited(self, text):
        self._dirty = True

    def commit_pending(self):
        if self.edit_field._armed:
            return False
        if self._edit_item is None or not self._dirty:
            return True
        sequence = key_config.normalize_sequence(self.edit_field.text())
        if sequence is None:
            QMessageBox.warning(self, _("Invalid shortcut"),
                                _("Enter one key combination, such as Ctrl+Shift+P."))
            self.edit_field.setFocus()
            return False
        section, action = self._item_key(self._edit_item)
        self._draft[section][action] = sequence
        self._dirty = False
        self.edit_field.setText(sequence)
        self._refresh_item(self._edit_item)
        return True

    @Slot(bool)
    def on_capture_toggled(self, armed):
        if armed:
            self.edit_field.set_capture_armed(True)
            self.edit_field.setFocus()
        else:
            self.disarm_capture()

    @Slot()
    def disarm_capture(self):
        was_armed = self.edit_field._armed
        self.edit_field.set_capture_armed(False)
        was_blocked = self.capture_button.blockSignals(True)
        self.capture_button.setChecked(False)
        self.capture_button.blockSignals(was_blocked)
        if was_armed and self._edit_item is not None:
            section, action = self._item_key(self._edit_item)
            self.edit_field.setText(self._draft[section][action])
            self._dirty = False

    @Slot(str)
    def on_shortcut_captured(self, sequence):
        self.disarm_capture()
        self.edit_field.setText(sequence)
        self._dirty = True
        self.commit_pending()

    @Slot(str)
    def filter_hotkeys(self, query):
        query = query.strip().casefold()
        for index in range(self.tree.topLevelItemCount()):
            category = self.tree.topLevelItem(index)
            matches = False
            for row in range(category.childCount()):
                item = category.child(row)
                text = f"{category.text(0)} {item.text(0)} {item.text(1)}".casefold()
                visible = not query or query in text
                item.setHidden(not visible)
                matches |= visible
            category.setHidden(not matches)
            category.setExpanded(bool(query) and matches)

    @Slot(object)
    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item is None or item.parent() is None or not self.commit_pending():
            return
        self.tree.setCurrentItem(item)
        section, action = self._item_key(item)
        menu = QMenu(self)
        toggle = menu.addAction(_("Enable") if (section, action) in self._disabled else _("Disable"))
        unbind = menu.addAction(_("Unbind shortcut"))
        reset = menu.addAction(_("Reset hotkey"))
        selected = menu.exec(self.tree.viewport().mapToGlobal(position))
        if selected is toggle:
            self.toggle_item_enabled(item)
        elif selected is unbind:
            self._draft[section][action] = ""
        elif selected is reset:
            self._draft[section][action] = key_config.key_dict[section][action]
            self._disabled.discard((section, action))
        self._refresh_item(item)
        self.load_panel(item)
        menu.deleteLater()

    @Slot()
    def reset_to_default(self):
        reply = QMessageBox.question(
            self, _("Reset to Default"), _("Are you sure you want to reset all hotkeys to default?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._draft = {section: dict(actions) for section, actions in key_config.key_dict.items()}
            self._disabled = set()
            self.populate_tree()

    @Slot()
    def apply_changes(self):
        if not self.commit_pending():
            return False
        conflicts = key_config.find_conflicts(self._draft, self._disabled)
        if conflicts:
            first, second, sequence = conflicts[0]
            QMessageBox.warning(self, _("Shortcut conflict"),
                _("{shortcut} is assigned to both {first} and {second}. Change or disable one binding.").format(
                    shortcut=sequence, first=_(first[1]), second=_(second[1])))  # i18n-dynamic: ok
            return False
        try:
            key_config.save_configuration(self._draft, self._disabled)
        except Exception as exc:
            QMessageBox.warning(self, _("Error"), _("Could not save shortcuts: {error}").format(error=exc))
            return False
        return True

    def accept(self):
        if self.apply_changes():
            super().accept()

    def done(self, result):
        self.disarm_capture()
        super().done(result)
