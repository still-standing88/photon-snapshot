from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QCheckBox, QSlider, QLabel, QLineEdit,
                             QComboBox, QSpinBox, QColorDialog, QInputDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from gui_controls.common_controls import TabableLabel


class OverlayPanel(QWidget):
    """Overlay tools (grid/ruler/pixel-info/shapes/text). Hosted as one
    Accordion section's content (see EditorPanel) - it no longer draws its
    own group-box frame/title, since the accordion header already supplies
    the "Overlays" label."""

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
        
        basic_group = self._create_basic_overlays_group()
        layout.addWidget(basic_group)
        
        shape_group = self._create_shape_drawing_group()
        layout.addWidget(shape_group)
        
        text_group = self._create_text_overlay_group()
        layout.addWidget(text_group)
        
        self.clear_btn = QPushButton(_("Clear All Overlays"))
        self.clear_btn.setAccessibleName(_("Clear all overlays"))
        self.clear_btn.setStyleSheet(self._button_style())
        layout.addWidget(self.clear_btn)
        
        self.setLayout(layout)
    
    def _create_basic_overlays_group(self):
        group = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.grid_checkbox = QCheckBox(_("Grid Overlay"))
        self.grid_checkbox.setAccessibleName(_("Toggle grid overlay"))
        self.grid_checkbox.setStyleSheet(self._checkbox_style())

        self.ruler_checkbox = QCheckBox(_("Ruler Overlay"))
        self.ruler_checkbox.setAccessibleName(_("Toggle ruler overlay"))
        self.ruler_checkbox.setStyleSheet(self._checkbox_style())

        self.pixel_info_checkbox = QCheckBox(_("Pixel Info Mode"))
        self.pixel_info_checkbox.setAccessibleName(_("Toggle pixel info mode"))
        self.pixel_info_checkbox.setStyleSheet(self._checkbox_style())
        
        layout.addWidget(self.grid_checkbox)
        layout.addWidget(self.ruler_checkbox)
        layout.addWidget(self.pixel_info_checkbox)
        
        group.setLayout(layout)
        return group
    
    def _create_shape_drawing_group(self):
        group = QGroupBox(_("Shape Drawing"))
        group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                border: 1px solid #404040;
                border-radius: 3px;
                margin-top: 8px;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """)
        
        layout = QVBoxLayout()
        
        shape_buttons_layout = QHBoxLayout()
        
        self.rectangle_btn = QPushButton(_("Rectangle"))
        self.rectangle_btn.setCheckable(True)
        self.rectangle_btn.setAccessibleName(_("Draw rectangle shape"))
        self.rectangle_btn.setStyleSheet(self._toggle_button_style())

        self.circle_btn = QPushButton(_("Circle"))
        self.circle_btn.setCheckable(True)
        self.circle_btn.setAccessibleName(_("Draw circle shape"))
        self.circle_btn.setStyleSheet(self._toggle_button_style())

        self.line_btn = QPushButton(_("Line"))
        self.line_btn.setCheckable(True)
        self.line_btn.setAccessibleName(_("Draw line shape"))
        self.line_btn.setStyleSheet(self._toggle_button_style())
        
        shape_buttons_layout.addWidget(self.rectangle_btn)
        shape_buttons_layout.addWidget(self.circle_btn)
        shape_buttons_layout.addWidget(self.line_btn)
        
        layout.addLayout(shape_buttons_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_text_overlay_group(self):
        group = QGroupBox(_("Text Overlay"))
        group.setStyleSheet("""
            QGroupBox {
                color: #cccccc;
                border: 1px solid #404040;
                border-radius: 3px;
                margin-top: 8px;
                font-size: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px 0 3px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Text input row
        text_layout = QHBoxLayout()
        
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText(_("Enter text..."))
        self.text_input.setAccessibleName(_("Overlay text"))
        self.text_input.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 3px;
                border-radius: 3px;
            }
        """)
        
        text_layout.addWidget(self.text_input)
        layout.addLayout(text_layout)
        
        # Position and font size row
        pos_font_layout = QHBoxLayout()
        
        # Position dropdown. Item text is translated, but the value read
        # back by _on_add_text_clicked() is the English key stored as
        # itemData - viewer.add_text_overlay()'s position_map is keyed in
        # English, so translating currentText() directly (as before) would
        # silently break placement in every non-English locale.
        pos_font_layout.addWidget(TabableLabel(_("Position:")))
        self.position_combo = QComboBox()
        self.position_combo.setAccessibleName(_("Text overlay position"))
        for key, label in (
            ("Top Left", _("Top Left")), ("Top Center", _("Top Center")), ("Top Right", _("Top Right")),
            ("Left Center", _("Left Center")), ("Center", _("Center")), ("Right Center", _("Right Center")),
            ("Bottom Left", _("Bottom Left")), ("Bottom Center", _("Bottom Center")), ("Bottom Right", _("Bottom Right")),
            ("Click to Place", _("Click to Place")),
        ):
            self.position_combo.addItem(label, key)
        self.position_combo.setCurrentIndex(self.position_combo.count() - 1)
        self.position_combo.setStyleSheet(self._combo_style())
        pos_font_layout.addWidget(self.position_combo)

        # Font size spinner
        pos_font_layout.addWidget(TabableLabel(_("Size:")))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(16)
        self.font_size_spin.setAccessibleName(_("Overlay text font size"))
        self.font_size_spin.setStyleSheet(self._spinbox_style())
        pos_font_layout.addWidget(self.font_size_spin)
        
        layout.addLayout(pos_font_layout)
        
        # Color and background row
        color_layout = QHBoxLayout()
        
        # Text color button
        self.text_color_btn = QPushButton(_("Text Color"))
        self.text_color_btn.setAccessibleName(_("Choose overlay text color"))
        self.text_color_btn.setStyleSheet(self._color_button_style(QColor(255, 255, 255)))
        self.text_color = QColor(255, 255, 255)
        color_layout.addWidget(self.text_color_btn)

        # Background toggle
        self.background_checkbox = QCheckBox(_("Background"))
        self.background_checkbox.setChecked(True)
        self.background_checkbox.setAccessibleName(_("Show text background"))
        self.background_checkbox.setStyleSheet(self._checkbox_style())
        color_layout.addWidget(self.background_checkbox)

        layout.addLayout(color_layout)

        # Add text button
        self.add_text_btn = QPushButton(_("Add Text"))
        self.add_text_btn.setAccessibleName(_("Add text overlay"))
        self.add_text_btn.setStyleSheet(self._button_style())
        layout.addWidget(self.add_text_btn)
        
        group.setLayout(layout)
        return group
    
    def connect_signals(self):
        self.grid_checkbox.toggled.connect(lambda: self.grid_toggled.emit())
        self.ruler_checkbox.toggled.connect(lambda: self.ruler_toggled.emit())
        self.pixel_info_checkbox.toggled.connect(lambda: self.pixel_info_toggled.emit())
        
        # Keyed by the internal shape_type string (never translated) rather
        # than the button's (now-translated) display text, which used to be
        # compared directly against shape_type in _on_shape_toggled() - that
        # broke as soon as the button labels stopped being English.
        self._shape_buttons = {
            "rectangle": self.rectangle_btn,
            "circle": self.circle_btn,
            "line": self.line_btn,
        }
        self.rectangle_btn.toggled.connect(lambda checked: self._on_shape_toggled("rectangle", checked))
        self.circle_btn.toggled.connect(lambda checked: self._on_shape_toggled("circle", checked))
        self.line_btn.toggled.connect(lambda checked: self._on_shape_toggled("line", checked))
        
        self.add_text_btn.clicked.connect(self._on_add_text_clicked)
        self.text_input.returnPressed.connect(self._on_add_text_clicked)
        self.text_color_btn.clicked.connect(self._on_text_color_clicked)
        
        self.clear_btn.clicked.connect(self.overlays_cleared.emit)
    
    def _on_shape_toggled(self, shape_type: str, checked: bool):
        if checked:
            for key, btn in self._shape_buttons.items():
                if key != shape_type:
                    btn.setChecked(False)
            self.shape_mode_changed.emit(shape_type)
        else:
            self.shape_mode_changed.emit("")
    
    def _on_add_text_clicked(self):
        text = self.text_input.text().strip()
        if text:
            position = self.position_combo.currentData()
            font_size = self.font_size_spin.value()
            show_background = self.background_checkbox.isChecked()

            self.text_overlay_requested.emit(text, position, font_size, self.text_color, show_background)
            self.text_input.clear()

    def _on_text_color_clicked(self):
        color = QColorDialog.getColor(self.text_color, self, _("Select Text Color"))
        if color.isValid():
            self.text_color = color
            self.text_color_btn.setStyleSheet(self._color_button_style(color))
    
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
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
            QPushButton:checked {
                background-color: #0078d4;
                border-color: #005a9e;
            }
        """
    
    def _checkbox_style(self):
        return """
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 13px;
                height: 13px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 1px solid #404040;
            }
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border: 1px solid #005a9e;
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
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                selection-background-color: #0078d4;
                border: 1px solid #404040;
            }
        """
    
    def _spinbox_style(self):
        return """
            QSpinBox {
                background-color: #2b2b2b;
                border: 1px solid #404040;
                color: #ffffff;
                padding: 2px;
                border-radius: 3px;
                font-size: 10px;
                max-width: 50px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #404040;
                border: 1px solid #555555;
                width: 12px;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background-color: #505050;
            }
        """
    
    def _color_button_style(self, color: QColor):
        return f"""
            QPushButton {{
                background-color: {color.name()};
                border: 2px solid #555555;
                color: {'#000000' if color.lightness() > 128 else '#ffffff'};
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                border-color: #0078d4;
            }}
            QPushButton:pressed {{
                border-color: #005a9e;
            }}
        """