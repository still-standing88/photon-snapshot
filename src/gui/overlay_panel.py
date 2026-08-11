from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QToolButton, QComboBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from gui_controls.common_controls import TabableLabel
from .dialogs.text_overlay_dialog import TextOverlayDialog


class OverlayPanel(QWidget):
    """Overlay tools (grid/ruler/pixel-info/shapes/text), hosted as one
    Accordion section's content (see EditorPanel).

    Compacted from the original stacked-groupboxes layout (checkboxes,
    then a 3-button shape row, then a 4-row text-overlay form) down to 4
    rows total: the three toggles share one row, shape selection is a
    single combo box instead of three buttons, and the whole text-overlay
    form moved into :class:`TextOverlayDialog` - opened on demand instead
    of permanently eating vertical space in the panel.
    """

    grid_toggled = Signal()
    ruler_toggled = Signal()
    pixel_info_toggled = Signal()
    text_overlay_requested = Signal(str, str, int, QColor, bool)  # text, position, font_size, color, show_background
    shape_mode_changed = Signal(str)
    overlays_cleared = Signal()

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Overlay tools"))
        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        toggles_row = QHBoxLayout()
        self.grid_btn = QToolButton()
        self.grid_btn.setText(_("Grid"))
        self.grid_btn.setCheckable(True)
        self.grid_btn.setAccessibleName(_("Toggle grid overlay"))
        self.grid_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        self.ruler_btn = QToolButton()
        self.ruler_btn.setText(_("Ruler"))
        self.ruler_btn.setCheckable(True)
        self.ruler_btn.setAccessibleName(_("Toggle ruler overlay"))
        self.ruler_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        self.pixel_info_btn = QToolButton()
        self.pixel_info_btn.setText(_("Pixel Info"))
        self.pixel_info_btn.setCheckable(True)
        self.pixel_info_btn.setAccessibleName(_("Toggle pixel info mode"))
        self.pixel_info_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        for btn in (self.grid_btn, self.ruler_btn, self.pixel_info_btn):
            btn.setStyleSheet(self._toggle_button_style())
            toggles_row.addWidget(btn)
        layout.addLayout(toggles_row)

        shape_row = QHBoxLayout()
        shape_row.addWidget(TabableLabel(_("Shape:")))
        self.shape_combo = QComboBox()
        self.shape_combo.setAccessibleName(_("Shape drawing tool"))
        self.shape_combo.setStyleSheet(self._combo_style())
        # Each addItem() call below must keep _("...") as a literal string
        # argument, not a variable - scripts/extract_strings.py's AST-based
        # extractor only recognizes _() calls whose argument is a plain
        # string constant, so looping over a (key, label) list and calling
        # _(label) would silently never get translated (verified: this
        # exact mistake shipped once already and was caught by testing all
        # 4 languages, not by the extractor itself).
        self.shape_combo.addItem(_("None"), "")
        self.shape_combo.addItem(_("Rectangle"), "rectangle")
        self.shape_combo.addItem(_("Circle"), "circle")
        self.shape_combo.addItem(_("Line"), "line")
        shape_row.addWidget(self.shape_combo, 1)
        layout.addLayout(shape_row)

        self.add_text_btn = QPushButton(_("Add Text Overlay..."))
        self.add_text_btn.setAccessibleName(_("Open add text overlay dialog"))
        self.add_text_btn.setStyleSheet(self._button_style())
        layout.addWidget(self.add_text_btn)

        self.clear_btn = QPushButton(_("Clear All Overlays"))
        self.clear_btn.setAccessibleName(_("Clear all overlays"))
        self.clear_btn.setStyleSheet(self._button_style())
        layout.addWidget(self.clear_btn)

        self.setLayout(layout)

    def connect_signals(self):
        self.grid_btn.toggled.connect(lambda: self.grid_toggled.emit())
        self.ruler_btn.toggled.connect(lambda: self.ruler_toggled.emit())
        self.pixel_info_btn.toggled.connect(lambda: self.pixel_info_toggled.emit())

        self.shape_combo.currentIndexChanged.connect(self._on_shape_changed)

        self.add_text_btn.clicked.connect(self._on_add_text_clicked)
        self.clear_btn.clicked.connect(self.overlays_cleared.emit)

    def _on_shape_changed(self, index: int):
        self.shape_mode_changed.emit(self.shape_combo.itemData(index) or "")

    def reset_shape_tool(self):
        """Called externally (e.g. on Escape) to drop back to "None"
        without re-emitting through the normal toggled-button dance."""
        self.shape_combo.setCurrentIndex(0)

    def _on_add_text_clicked(self):
        dialog = TextOverlayDialog(self)
        if dialog.exec():
            text, position, font_size, color, show_background = dialog.values()
            if text:
                self.text_overlay_requested.emit(text, position, font_size, color, show_background)

    def _button_style(self):
        return """
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
        """

    def _toggle_button_style(self):
        return """
            QToolButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 4px 6px;
                border-radius: 3px;
                font-size: 10px;
            }
            QToolButton:hover {
                background-color: #505050;
            }
            QToolButton:checked {
                background-color: #0078d4;
                border-color: #005a9e;
            }
        """

    def _combo_style(self):
        return """
            QComboBox {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 2px 5px;
                border-radius: 3px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                selection-background-color: #0078d4;
                border: 1px solid #404040;
            }
        """
