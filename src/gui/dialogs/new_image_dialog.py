"""File -> New: configure a blank canvas (size + background color) that is
loaded straight into the editor - the natural starting point for Canvas
Drawing mode, which paints onto the image's pixels (see
gui.viewer.ImageViewer.set_drawing_mode). Values are read via
:meth:`values` after ``exec()`` returns Accepted - nothing is created
until the caller does so."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox,
    QFormLayout, QPushButton, QSpinBox, QVBoxLayout,
)


class NewImageDialog(QDialog):
    MIN_SIZE = 1
    MAX_SIZE = 10000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("New Image"))
        self.setAccessibleName(_("New image dialog"))
        self.setModal(True)
        self.setMinimumWidth(320)
        self._color = QColor(255, 255, 255)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(self.MIN_SIZE, self.MAX_SIZE)
        self.width_spin.setValue(800)
        self.width_spin.setSuffix(_(" px"))
        self.width_spin.setAccessibleName(_("Canvas width in pixels"))
        form.addRow(_("Width:"), self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(self.MIN_SIZE, self.MAX_SIZE)
        self.height_spin.setValue(600)
        self.height_spin.setSuffix(_(" px"))
        self.height_spin.setAccessibleName(_("Canvas height in pixels"))
        form.addRow(_("Height:"), self.height_spin)

        # The stylesheet here is functional, not decorative: it turns the
        # button into a swatch showing the currently chosen color.
        self.color_btn = QPushButton(_("Background Color"))
        self.color_btn.setAccessibleName(_("Choose background color"))
        self.color_btn.clicked.connect(self._on_color_clicked)
        self._update_color_button()
        form.addRow(_("Background:"), self.color_btn)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.width_spin.setFocus()

    def _on_color_clicked(self):
        color = QColorDialog.getColor(self._color, self, _("Select Background Color"))
        if color.isValid():
            self._color = color
            self._update_color_button()

    def _update_color_button(self):
        color = self._color
        self.color_btn.setStyleSheet(
            f"background-color: {color.name()}; "
            f"color: {'#000000' if color.lightness() > 128 else '#ffffff'};"
        )

    def values(self):
        """(width, height, background QColor)"""
        return (
            self.width_spin.value(),
            self.height_spin.value(),
            self._color,
        )
