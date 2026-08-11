"""Text-overlay configuration, split out of OverlayPanel into its own
modal dialog so the accordion panel itself stays compact - the panel now
just has an "Add Text Overlay..." button that opens this."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)


class TextOverlayDialog(QDialog):
    """Collects text/position/size/color/background for one text overlay.
    Values are read via :meth:`values` after ``exec()`` returns Accepted -
    nothing is applied until the caller does so."""

    # (internal key, translated label) - the key is what
    # viewer.add_text_overlay()'s position_map expects, and must never be
    # translated (see the note in the old inline version this replaced).
    _POSITIONS = (
        ("Top Left", "Top Left"), ("Top Center", "Top Center"), ("Top Right", "Top Right"),
        ("Left Center", "Left Center"), ("Center", "Center"), ("Right Center", "Right Center"),
        ("Bottom Left", "Bottom Left"), ("Bottom Center", "Bottom Center"), ("Bottom Right", "Bottom Right"),
        ("Click to Place", "Click to Place"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Add Text Overlay"))
        self.setAccessibleName(_("Add text overlay dialog"))
        self.setModal(True)
        self.setMinimumWidth(360)
        self._color = QColor(255, 255, 255)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText(_("Enter text..."))
        self.text_input.setAccessibleName(_("Overlay text"))
        form.addRow(_("Text:"), self.text_input)

        self.position_combo = QComboBox()
        self.position_combo.setAccessibleName(_("Text overlay position"))
        for key, label in self._POSITIONS:
            self.position_combo.addItem(_(label), key)
        self.position_combo.setCurrentIndex(self.position_combo.count() - 1)
        form.addRow(_("Position:"), self.position_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(16)
        self.font_size_spin.setAccessibleName(_("Overlay text font size"))
        form.addRow(_("Size:"), self.font_size_spin)

        self.text_color_btn = QPushButton(_("Text Color"))
        self.text_color_btn.setAccessibleName(_("Choose overlay text color"))
        self.text_color_btn.clicked.connect(self._on_color_clicked)
        self._update_color_button()
        form.addRow(_("Color:"), self.text_color_btn)

        self.background_checkbox = QCheckBox(_("Show background behind text"))
        self.background_checkbox.setChecked(True)
        self.background_checkbox.setAccessibleName(_("Show text background"))
        form.addRow("", self.background_checkbox)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setEnabled(False)
        self.text_input.textChanged.connect(lambda t: self._ok_button.setEnabled(bool(t.strip())))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.text_input.setFocus()

    def _on_color_clicked(self):
        color = QColorDialog.getColor(self._color, self, _("Select Text Color"))
        if color.isValid():
            self._color = color
            self._update_color_button()

    def _update_color_button(self):
        color = self._color
        self.text_color_btn.setStyleSheet(
            f"background-color: {color.name()}; "
            f"color: {'#000000' if color.lightness() > 128 else '#ffffff'};"
        )

    def values(self):
        """(text, position_key, font_size, color, show_background)"""
        return (
            self.text_input.text().strip(),
            self.position_combo.currentData(),
            self.font_size_spin.value(),
            self._color,
            self.background_checkbox.isChecked(),
        )
