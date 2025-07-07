from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                             QSlider, QLabel, QPushButton, QSpinBox, QComboBox,
                             QFrame, QSizePolicy, QButtonGroup, QCheckBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from core.editor import Editor
from .overlay_panel import OverlayPanel


class SliderGroup(QWidget):
    value_changed = Signal(float)
    
    def __init__(self, title: str, min_val: float = 0.0, max_val: float = 2.0, 
                 default_val: float = 1.0, decimals: int = 2):
        super().__init__()
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals
        self.multiplier = 10 ** decimals
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        
        slider_layout = QHBoxLayout()
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(int(min_val * self.multiplier))
        self.slider.setMaximum(int(max_val * self.multiplier))
        self.slider.setValue(int(default_val * self.multiplier))
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        self.value_label = QLabel(f"{default_val:.{decimals}f}")
        self.value_label.setMinimumWidth(50)
        self.value_label.setStyleSheet("color: #cccccc;")
        
        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.value_label)
        
        layout.addWidget(self.title_label)
        layout.addLayout(slider_layout)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #404040;
                height: 8px;
                background: #2b2b2b;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 1px solid #005a9e;
                width: 18px;
                border-radius: 9px;
                margin: -5px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #106ebe;
            }
        """)
    
    def _on_slider_changed(self, value):
        real_value = value / self.multiplier
        self.value_label.setText(f"{real_value:.{self.decimals}f}")
        self.value_changed.emit(real_value)
    
    def set_value(self, value: float):
        self.slider.setValue(int(value * self.multiplier))


class EffectsPanel(QGroupBox):
    brightness_changed = Signal(float)
    contrast_changed = Signal(float)
    grayscale_applied = Signal()
    sepia_applied = Signal()
    invert_applied = Signal()
    
    def __init__(self):
        super().__init__("Effects & Adjustments")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.brightness_slider = SliderGroup("Brightness", 0.0, 3.0, 1.0)
        self.contrast_slider = SliderGroup("Contrast", 0.0, 3.0, 1.0)
        
        self.brightness_slider.value_changed.connect(self.brightness_changed.emit)
        self.contrast_slider.value_changed.connect(self.contrast_changed.emit)
        
        effects_layout = QHBoxLayout()
        
        self.grayscale_btn = QPushButton("Grayscale")
        self.sepia_btn = QPushButton("Sepia")
        self.invert_btn = QPushButton("Invert")
        
        for btn in [self.grayscale_btn, self.sepia_btn, self.invert_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    color: #ffffff;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #303030;
                }
            """)
        
        self.grayscale_btn.clicked.connect(self.grayscale_applied.emit)
        self.sepia_btn.clicked.connect(self.sepia_applied.emit)
        self.invert_btn.clicked.connect(self.invert_applied.emit)
        
        effects_layout.addWidget(self.grayscale_btn)
        effects_layout.addWidget(self.sepia_btn)
        effects_layout.addWidget(self.invert_btn)
        
        layout.addWidget(self.brightness_slider)
        layout.addWidget(self.contrast_slider)
        layout.addLayout(effects_layout)
        
        self.setLayout(layout)
    
    def reset_sliders(self):
        self.brightness_slider.set_value(1.0)
        self.contrast_slider.set_value(1.0)


class TransformPanel(QGroupBox):
    rotate_90_cw = Signal()
    rotate_90_ccw = Signal()
    flip_horizontal = Signal()
    flip_vertical = Signal()
    
    def __init__(self):
        super().__init__("Transform")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        rotate_layout = QHBoxLayout()
        
        self.rotate_cw_btn = QPushButton("↻ 90°")
        self.rotate_ccw_btn = QPushButton("↺ 90°")
        
        flip_layout = QHBoxLayout()
        
        self.flip_h_btn = QPushButton("↔ Flip H")
        self.flip_v_btn = QPushButton("↕ Flip V")
        
        for btn in [self.rotate_cw_btn, self.rotate_ccw_btn, 
                   self.flip_h_btn, self.flip_v_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #404040;
                    border: 1px solid #555555;
                    color: #ffffff;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #505050;
                }
                QPushButton:pressed {
                    background-color: #303030;
                }
            """)
        
        self.rotate_cw_btn.clicked.connect(self.rotate_90_cw.emit)
        self.rotate_ccw_btn.clicked.connect(self.rotate_90_ccw.emit)
        self.flip_h_btn.clicked.connect(self.flip_horizontal.emit)
        self.flip_v_btn.clicked.connect(self.flip_vertical.emit)
        
        rotate_layout.addWidget(self.rotate_cw_btn)
        rotate_layout.addWidget(self.rotate_ccw_btn)
        
        flip_layout.addWidget(self.flip_h_btn)
        flip_layout.addWidget(self.flip_v_btn)
        
        layout.addLayout(rotate_layout)
        layout.addLayout(flip_layout)
        
        self.setLayout(layout)


class CropPanel(QGroupBox):
    crop_mode_toggled = Signal(bool)
    crop_applied = Signal()
    
    def __init__(self):
        super().__init__("Crop")
        self.setStyleSheet("""
            QGroupBox {
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.crop_mode_checkbox = QCheckBox("Crop Mode")
        self.crop_mode_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
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
        """)
        
        self.apply_crop_btn = QPushButton("Apply Crop")
        self.apply_crop_btn.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                border: 1px solid #555555;
                color: #ffffff;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #303030;
            }
            QPushButton:disabled {
                background-color: #2b2b2b;
                color: #666666;
            }
        """)
        self.apply_crop_btn.setEnabled(False)
        
        self.crop_mode_checkbox.toggled.connect(self._on_crop_mode_toggled)
        self.apply_crop_btn.clicked.connect(self.crop_applied.emit)
        
        layout.addWidget(self.crop_mode_checkbox)
        layout.addWidget(self.apply_crop_btn)
        
        self.setLayout(layout)
    
    def _on_crop_mode_toggled(self, checked):
        self.apply_crop_btn.setEnabled(checked)
        self.crop_mode_toggled.emit(checked)


class EditorPanel(QWidget):
    def __init__(self, editor: Editor):
        super().__init__()
        self.editor = editor
        self.setup_ui()
        self.connect_signals()
    
    def setup_ui(self):
        self.setFixedWidth(250)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.effects_panel = EffectsPanel()
        self.transform_panel = TransformPanel()
        self.crop_panel = CropPanel()
        self.overlay_panel = OverlayPanel()
        
        layout.addWidget(self.effects_panel)
        layout.addWidget(self.transform_panel)
        layout.addWidget(self.crop_panel)
        layout.addWidget(self.overlay_panel)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def connect_signals(self):
        self.effects_panel.brightness_changed.connect(self.editor.apply_brightness)
        self.effects_panel.contrast_changed.connect(self.editor.apply_contrast)
        self.effects_panel.grayscale_applied.connect(self.editor.apply_grayscale)
        self.effects_panel.sepia_applied.connect(self.editor.apply_sepia)
        self.effects_panel.invert_applied.connect(self.editor.apply_invert)
        
        self.transform_panel.rotate_90_cw.connect(lambda: self.editor.rotate(90))
        self.transform_panel.rotate_90_ccw.connect(lambda: self.editor.rotate(-90))
        self.transform_panel.flip_horizontal.connect(self.editor.flip_horizontal)
        self.transform_panel.flip_vertical.connect(self.editor.flip_vertical)
    
    def reset_controls(self):
        self.effects_panel.reset_sliders()
        self.crop_panel.crop_mode_checkbox.setChecked(False)
