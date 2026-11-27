from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QSlider, QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
                             QComboBox, QFrame, QSizePolicy, QButtonGroup, QCheckBox,
                             QScrollArea, QColorDialog, QMenu)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from core.editor import Editor
from gui_controls.accordion import Accordion
from gui_controls.common_controls import TabableLabel
from .overlay_panel import OverlayPanel
from .dialogs.effect_dialog import CropRegionDialog, EffectDialog
from .effect_labels import effect_label


class SliderGroup(QWidget):
    """A slider paired with a ranged QDoubleSpinBox showing/editing the same
    float value - the spinbox is the accessible, keyboard-precise entry
    point (screen readers announce QSlider values far less reliably), and
    it's hard-capped to [min_val, max_val] so it can never be typed out of
    range."""

    value_changed = Signal(float)

    def __init__(self, title: str, min_val: float = 0.0, max_val: float = 2.0,
                 default_val: float = 1.0, decimals: int = 2, step: float = 0.05):
        super().__init__()
        self.min_val = min_val
        self.max_val = max_val
        self.decimals = decimals
        self.multiplier = 10 ** decimals
        self._syncing = False

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        self.title_label = TabableLabel(title, accessible_name=title)
        self.title_label.setStyleSheet("font-weight: bold;")

        slider_layout = QHBoxLayout()

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(int(min_val * self.multiplier))
        self.slider.setMaximum(int(max_val * self.multiplier))
        self.slider.setValue(int(default_val * self.multiplier))
        self.slider.setAccessibleName(title)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(min_val, max_val)
        self.value_spin.setDecimals(decimals)
        self.value_spin.setSingleStep(step)
        self.value_spin.setValue(default_val)
        self.value_spin.setMinimumWidth(70)
        self.value_spin.setAccessibleName(_("{title} value").format(title=title))
        self.value_spin.valueChanged.connect(self._on_spin_changed)

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.value_spin)

        layout.addWidget(self.title_label)
        layout.addLayout(slider_layout)

        self.setLayout(layout)

    def _on_slider_changed(self, value):
        if self._syncing:
            return
        real_value = value / self.multiplier
        self._syncing = True
        self.value_spin.setValue(real_value)
        self._syncing = False
        self.value_changed.emit(real_value)

    def _on_spin_changed(self, value: float):
        if self._syncing:
            return
        self._syncing = True
        self.slider.setValue(int(value * self.multiplier))
        self._syncing = False
        self.value_changed.emit(value)

    def set_value(self, value: float):
        """Programmatic set (e.g. resetting controls after loading an
        image). Must NOT emit value_changed - the old version did, which
        executed a phantom 'Brightness 1.0' action on the freshly loaded
        image and polluted its undo history."""
        value = max(self.min_val, min(self.max_val, value))
        self._syncing = True
        try:
            self.value_spin.setValue(value)
            self.slider.setValue(int(value * self.multiplier))
        finally:
            self._syncing = False


class EffectsPanel(QWidget):
    brightness_changed = Signal(float)
    contrast_changed = Signal(float)
    grayscale_applied = Signal()
    sepia_applied = Signal()
    invert_applied = Signal()

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Effects and adjustments"))

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.brightness_slider = SliderGroup(_("Brightness"), 0.0, 3.0, 1.0)
        self.contrast_slider = SliderGroup(_("Contrast"), 0.0, 3.0, 1.0)

        self.brightness_slider.value_changed.connect(self.brightness_changed.emit)
        self.contrast_slider.value_changed.connect(self.contrast_changed.emit)

        # Long translated labels must fit the narrow editing pane.
        effects_layout = QVBoxLayout()

        self.grayscale_btn = QPushButton(_("Grayscale"))
        self.grayscale_btn.setAccessibleName(_("Apply grayscale effect"))
        self.sepia_btn = QPushButton(_("Sepia"))
        self.sepia_btn.setAccessibleName(_("Apply sepia effect"))
        self.invert_btn = QPushButton(_("Invert"))
        self.invert_btn.setAccessibleName(_("Invert colors"))

        self.grayscale_btn.clicked.connect(self.grayscale_applied.emit)
        self.sepia_btn.clicked.connect(self.sepia_applied.emit)
        self.invert_btn.clicked.connect(self.invert_applied.emit)

        effects_layout.addWidget(self.grayscale_btn)
        effects_layout.addWidget(self.sepia_btn)
        effects_layout.addWidget(self.invert_btn)

        layout.addWidget(self.brightness_slider)
        layout.addWidget(self.contrast_slider)
        layout.addLayout(effects_layout)
        self.more_effects_btn = QPushButton(_("Image Effects"))
        layout.addWidget(self.more_effects_btn)

        self.setLayout(layout)

    def reset_sliders(self):
        self.brightness_slider.set_value(1.0)
        self.contrast_slider.set_value(1.0)


class TransformPanel(QWidget):
    rotate_90_cw = Signal()
    rotate_90_ccw = Signal()
    flip_horizontal = Signal()
    flip_vertical = Signal()

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Transform tools"))

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        rotate_layout = QHBoxLayout()
        self.rotate_cw_btn = QPushButton(_("↻ 90°"))
        self.rotate_cw_btn.setAccessibleName(_("Rotate 90 degrees clockwise"))
        self.rotate_ccw_btn = QPushButton(_("↺ 90°"))
        self.rotate_ccw_btn.setAccessibleName(_("Rotate 90 degrees counterclockwise"))

        flip_layout = QHBoxLayout()
        self.flip_h_btn = QPushButton(_("↔ Flip H"))
        self.flip_h_btn.setAccessibleName(_("Flip image horizontally"))
        self.flip_v_btn = QPushButton(_("↕ Flip V"))
        self.flip_v_btn.setAccessibleName(_("Flip image vertically"))

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


class CropPanel(QWidget):
    crop_mode_toggled = Signal(bool)
    crop_applied = Signal()

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Crop tools"))

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.crop_mode_checkbox = QCheckBox(_("Crop Mode"))
        self.crop_mode_checkbox.setAccessibleName(_("Toggle crop mode"))

        self.apply_crop_btn = QPushButton(_("Apply Crop"))
        self.apply_crop_btn.setAccessibleName(_("Apply crop selection"))
        self.apply_crop_btn.setEnabled(False)

        self.crop_mode_checkbox.toggled.connect(self._on_crop_mode_toggled)
        self.apply_crop_btn.clicked.connect(self.crop_applied.emit)

        layout.addWidget(self.crop_mode_checkbox)
        layout.addWidget(self.apply_crop_btn)
        self.coordinates_btn = QPushButton(_("Crop by Coordinates..."))
        layout.addWidget(self.coordinates_btn)

        self.setLayout(layout)

    def _on_crop_mode_toggled(self, checked):
        self.apply_crop_btn.setEnabled(checked)
        self.crop_mode_toggled.emit(checked)


class DrawPanel(QWidget):
    """Canvas drawing mode controls: freehand pen tool that paints directly
    onto the image's pixels (see gui.viewer.ImageViewer.set_drawing_mode /
    core.editor.Editor.draw_stroke)."""

    drawing_mode_toggled = Signal(bool)
    pen_color_changed = Signal(QColor)
    pen_width_changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setAccessibleName(_("Canvas drawing tools"))
        self.pen_color = QColor(255, 0, 0)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.draw_mode_checkbox = QCheckBox(_("Drawing Mode"))
        self.draw_mode_checkbox.setAccessibleName(_("Toggle canvas drawing mode"))
        self.draw_mode_checkbox.toggled.connect(self.drawing_mode_toggled.emit)
        layout.addWidget(self.draw_mode_checkbox)

        color_row = QHBoxLayout()
        self.pen_color_btn = QPushButton(_("Pen Color"))
        self.pen_color_btn.setAccessibleName(_("Choose pen color"))
        self.pen_color_btn.setStyleSheet(self._color_button_style(self.pen_color))
        self.pen_color_btn.clicked.connect(self._on_pen_color_clicked)
        color_row.addWidget(self.pen_color_btn)
        layout.addLayout(color_row)

        width_row = QHBoxLayout()
        width_row.addWidget(TabableLabel(_("Pen Width:")))
        self.pen_width_spin = QSpinBox()
        self.pen_width_spin.setRange(1, 50)
        self.pen_width_spin.setValue(3)
        self.pen_width_spin.setSuffix(_(" px"))
        self.pen_width_spin.setAccessibleName(_("Pen width in pixels"))
        self.pen_width_spin.valueChanged.connect(self.pen_width_changed.emit)
        width_row.addWidget(self.pen_width_spin)
        layout.addLayout(width_row)

        hint = TabableLabel(_("Click and drag on the image to draw. This permanently edits the pixels."))
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 11px;")
        layout.addWidget(hint)

        self.setLayout(layout)

    def _on_pen_color_clicked(self):
        color = QColorDialog.getColor(self.pen_color, self, _("Select Pen Color"))
        if color.isValid():
            self.pen_color = color
            self.pen_color_btn.setStyleSheet(self._color_button_style(color))
            self.pen_color_changed.emit(color)

    def _color_button_style(self, color: QColor):
        return f"""
            QPushButton {{
                background-color: {color.name()};
                border: 2px solid #555555;
                color: {'#000000' if color.lightness() > 128 else '#ffffff'};
                padding: 4px 8px;
                border-radius: 3px;
                font-weight: bold;
            }}
            QPushButton:hover {{ border-color: #0078d4; }}
        """

    def reset(self):
        self.draw_mode_checkbox.setChecked(False)


class EditorPanel(QWidget):
    """The whole editing tool panel: each category of edit (Adjustments,
    Transform, Crop, Overlays, Draw) lives in its own Accordion section, per
    the snapshot-rewrite GUI spec. No fixed width - it lives in a resizable
    QSplitter pane in MainWindow, so panels can shrink/grow with the window
    (responsive layout requirement)."""

    edit_dialog_opening = Signal()

    def __init__(self, editor: Editor):
        super().__init__()
        self.editor = editor
        self.setAccessibleName(_("Editing tools"))
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setup_ui()
        self.connect_signals()
        self.set_document_available(False)

    def setup_ui(self):
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setAccessibleName(_("Editing tool panels"))

        self.accordion = Accordion()

        self.effects_panel = EffectsPanel()
        self.effect_menu = QMenu(_("Image Effects"), self)
        for effect_id in ('saturation', 'auto_contrast', 'sharpen', 'gaussian_blur',
                          'speckle_reduction', 'levels', 'duotone'):
            self.effect_menu.addAction(effect_label(effect_id),
                                       lambda checked=False, key=effect_id: self.open_effect(key))
        self.effects_panel.more_effects_btn.setMenu(self.effect_menu)
        self.transform_panel = TransformPanel()
        self.crop_panel = CropPanel()
        self.overlay_panel = OverlayPanel()
        self.draw_panel = DrawPanel()

        self.accordion.add_section(_("Adjustments"), self.effects_panel)
        self.accordion.add_section(_("Transform"), self.transform_panel)
        self.accordion.add_section(_("Crop"), self.crop_panel)
        self.accordion.add_section(_("Overlays"), self.overlay_panel)
        self.accordion.add_section(_("Draw"), self.draw_panel)
        self.accordion.open_section(0)

        scroll.setWidget(self.accordion)
        outer_layout.addWidget(scroll)

        self.setLayout(outer_layout)

    def connect_signals(self):
        self.effects_panel.brightness_changed.connect(self.editor.apply_brightness)
        self.effects_panel.contrast_changed.connect(self.editor.apply_contrast)
        self.effects_panel.grayscale_applied.connect(self.editor.apply_grayscale)
        self.effects_panel.sepia_applied.connect(self.editor.apply_sepia)
        self.effects_panel.invert_applied.connect(self.editor.apply_invert)
        self.crop_panel.coordinates_btn.clicked.connect(self.crop_by_coordinates)

        self.transform_panel.rotate_90_cw.connect(lambda: self.editor.rotate(90))
        self.transform_panel.rotate_90_ccw.connect(lambda: self.editor.rotate(-90))
        self.transform_panel.flip_horizontal.connect(self.editor.flip_horizontal)
        self.transform_panel.flip_vertical.connect(self.editor.flip_vertical)

    def set_document_available(self, available):
        self.effect_menu.setEnabled(available)
        self.effects_panel.more_effects_btn.setEnabled(available)
        self.crop_panel.coordinates_btn.setEnabled(available)

    def open_effect(self, effect_id):
        image = self.editor.current_image
        if image is None:
            return
        self.edit_dialog_opening.emit()
        document = self.editor.document
        dialog = EffectDialog(effect_id, parent=self.window(), canvas_size=image.size)
        if dialog.exec() and self.editor.document is document:
            self.editor.apply_effect(effect_id, dialog.values(), region=dialog.region())

    def crop_by_coordinates(self):
        image = self.editor.current_image
        if image is None:
            return
        self.edit_dialog_opening.emit()
        document = self.editor.document
        dialog = CropRegionDialog(image.size, self.window())
        if dialog.exec() and self.editor.document is document:
            self.editor.crop(dialog.box())
            self.crop_panel.crop_mode_checkbox.setChecked(False)

    def reset_controls(self):
        self.effects_panel.reset_sliders()
        self.crop_panel.crop_mode_checkbox.setChecked(False)
        self.draw_panel.reset()
