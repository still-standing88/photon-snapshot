"""akeyconfig editor UI: lets the user remap every action in
:mod:`app_config.key_config` through a category tree, adapted from
playForm's ``gui/dialogs/hotkeys_dialog.py``.
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QKeySequenceEdit, QMessageBox,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from app_config import key_config


class HotkeysDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_editor = None
        self.current_editor_item = None
        self.setWindowTitle(_("Hotkeys Configuration"))
        self.setAccessibleName(_("Hotkeys Configuration Dialog"))
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(700, 500)
        self.setMinimumSize(600, 400)
        self.setup_ui()
        self.populate_tree()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([_("Action"), _("Shortcut")])
        self.tree.setAccessibleName(_("Action shortcuts"))
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionsMovable(False)
        self.tree.header().setSectionsClickable(False)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.keyPressEvent = self._tree_key_press_event
        layout.addWidget(self.tree)

        button_layout = QHBoxLayout()
        self.reset_button = QPushButton(_("Reset to Default"))
        self.reset_button.setAccessibleName(_("Reset all shortcuts to default"))
        self.reset_button.clicked.connect(self.reset_to_default)
        self.apply_button = QPushButton(_("Apply"))
        self.apply_button.clicked.connect(self.apply_changes)
        self.cancel_button = QPushButton(_("Cancel"))
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button = QPushButton(_("OK"))
        self.ok_button.setDefault(True)
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)

    def _tree_key_press_event(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current_item = self.tree.currentItem()
            if current_item and current_item.parent() is not None:
                self.start_editing(current_item, 1)
                return
        QTreeWidget.keyPressEvent(self.tree, event)

    def populate_tree(self):
        self.tree.clear()
        for section in key_config.all_sections():
            category_item = QTreeWidgetItem(self.tree, [_(section), ""])
            category_item.setFlags(category_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            category_item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, _("Category: {name}").format(name=_(section)))
            for action in key_config.key_dict[section]:
                sequence = key_config.get_sequence(section, action)
                action_item = QTreeWidgetItem(category_item, [_(action), sequence])
                action_item.setData(0, Qt.ItemDataRole.UserRole, section)
                action_item.setData(0, Qt.ItemDataRole.UserRole + 1, action)
                desc = _("{action} in {section}, current shortcut: {shortcut}").format(
                    action=_(action), section=_(section), shortcut=sequence or _("none")
                )
                action_item.setData(0, Qt.ItemDataRole.AccessibleDescriptionRole, desc)
                action_item.setData(1, Qt.ItemDataRole.AccessibleDescriptionRole, desc)
                action_item.setFlags(action_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tree.addTopLevelItem(category_item)
            category_item.setExpanded(False)

    @Slot(object, int)
    def on_item_clicked(self, item, column):
        if item.parent() is not None and column == 1:
            self.start_editing(item, column)

    @Slot(object, int)
    def on_item_double_clicked(self, item, column):
        if item.parent() is not None and column == 1:
            self.start_editing(item, column)

    def start_editing(self, item, column):
        if column != 1 or item.parent() is None:
            return
        if self.current_editor is not None:
            self.finish_editing()

        editor = QKeySequenceEdit(QKeySequence(item.text(1)))
        editor.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        tooltip = _("Press the desired key combination; press Enter or change focus to accept.")
        editor.setAccessibleDescription(tooltip)
        editor.setToolTip(tooltip)
        editor.editingFinished.connect(self.finish_editing)

        self.current_editor = editor
        self.current_editor_item = item
        self.tree.setItemWidget(item, 1, editor)
        editor.setFocus()

    def finish_editing(self):
        if self.current_editor is None or self.current_editor_item is None:
            return

        new_seq = self.current_editor.keySequence().toString()
        item = self.current_editor_item
        parent = item.parent()

        if parent is not None:
            section = item.data(0, Qt.ItemDataRole.UserRole)
            action = item.data(0, Qt.ItemDataRole.UserRole + 1)
            item.setText(1, new_seq)
            self._pending_changes = getattr(self, "_pending_changes", {})
            self._pending_changes[(section, action)] = new_seq

        try:
            self.tree.setItemWidget(item, 1, None)
        except RuntimeError:
            pass

        self.current_editor.deleteLater()
        self.current_editor = None
        self.current_editor_item = None

    @Slot()
    def reset_to_default(self):
        reply = QMessageBox.question(
            self,
            _("Reset to Default"),
            _("Are you sure you want to reset all hotkeys to default?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            key_config.keys_to_default()
            self._pending_changes = {}
            self.populate_tree()

    @Slot()
    def apply_changes(self):
        for (section, action), sequence in getattr(self, "_pending_changes", {}).items():
            key_config.set_sequence(section, action, sequence)
        self._pending_changes = {}

    def accept(self):
        if self.current_editor:
            self.finish_editing()
        self.apply_changes()
        super().accept()

    def reject(self):
        if self.current_editor:
            try:
                if self.current_editor_item is not None:
                    self.tree.setItemWidget(self.current_editor_item, 1, None)
            except RuntimeError:
                pass
            self.current_editor.deleteLater()
            self.current_editor = None
            self.current_editor_item = None
        self._pending_changes = {}
        super().reject()
