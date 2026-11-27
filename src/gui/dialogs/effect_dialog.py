from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLineEdit, QMessageBox, QSpinBox, QVBoxLayout, QWidget,
)

from core.effects_catalog import EFFECTS, ColorParameter, defaults, validate_effect
from gui_controls.common_controls import TabableLabel
from ..effect_labels import effect_label, parameter_label, resize_mode_label


class ImageRegionFields(QWidget):
    def __init__(self, canvas_size, parent=None):
        super().__init__(parent)
        width, height = canvas_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        hint = TabableLabel(_('Positions are measured in image pixels from the top-left corner.'))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        layout.addLayout(form)
        self.left = self._add_field(form, 'left', 0, width - 1, 0)
        self.top = self._add_field(form, 'top', 0, height - 1, 0)
        self.width = self._add_field(form, 'width', 1, width, width)
        self.height = self._add_field(form, 'height', 1, height, height)
        self.left.valueChanged.connect(lambda left: self.width.setMaximum(width - left))
        self.top.valueChanged.connect(lambda top: self.height.setMaximum(height - top))

    @staticmethod
    def _add_field(form, key, minimum, maximum, default):
        control = QSpinBox()
        control.setRange(minimum, maximum)
        control.setValue(default)
        label = parameter_label(key)
        control.setAccessibleName(label)
        form.addRow(label, control)
        return control

    def box(self):
        left, top = self.left.value(), self.top.value()
        return left, top, left + self.width.value(), top + self.height.value()


class CropRegionDialog(QDialog):
    def __init__(self, canvas_size, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('Crop by Coordinates'))
        layout = QVBoxLayout(self)
        self.fields = ImageRegionFields(canvas_size)
        layout.addWidget(self.fields)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_('Apply'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.fields.left.setFocus()

    def box(self):
        return self.fields.box()


class EffectDialog(QDialog):
    def __init__(self, effect_id, values=None, parent=None, *, canvas_size=None):
        super().__init__(parent)
        self.effect_id = effect_id
        self.setWindowTitle(effect_label(effect_id))
        self.controls = {}
        self.region_mode = self.region_fields = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        values = validate_effect(effect_id, values) if values is not None else defaults(effect_id)
        for key, spec in EFFECTS[effect_id].parameters.items():
            control = self._parameter_control(spec, values[key])
            label = parameter_label(key)
            control.setAccessibleName(label)
            form.addRow(label, control)
            self.controls[key] = control

        if effect_id == 'gaussian_blur' and canvas_size is not None:
            self.region_mode = QComboBox()
            self.region_mode.addItem(_('Entire image'), False)
            self.region_mode.addItem(_('Rectangle by coordinates'), True)
            self.region_mode.setAccessibleName(_('Blur area'))
            form.addRow(_('Blur area'), self.region_mode)
            self.region_fields = ImageRegionFields(canvas_size)
            self.region_fields.hide()
            layout.addWidget(self.region_fields)
            self.region_mode.currentIndexChanged.connect(
                lambda: self.region_fields.setVisible(self.region_mode.currentData())
            )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if canvas_size is not None:
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_('Apply'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _parameter_control(spec, value):
        if isinstance(spec, ColorParameter):
            control = QLineEdit(value)
            control.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            control.setAccessibleDescription(_('Enter a colour in #RRGGBB format, such as #204060.'))
        elif isinstance(spec[0], str):
            control = QComboBox()
            for choice in spec:
                control.addItem(resize_mode_label(choice), choice)
            control.setCurrentIndex(control.findData(value))
        else:
            control = QSpinBox() if isinstance(spec[2], int) else QDoubleSpinBox()
            control.setRange(spec[0], spec[1])
            control.setValue(value)
        return control

    def values(self):
        values = {}
        for key, control in self.controls.items():
            if isinstance(control, QComboBox):
                values[key] = control.currentData()
            elif isinstance(control, QLineEdit):
                values[key] = control.text().strip()
            else:
                values[key] = control.value()
        return validate_effect(self.effect_id, values)

    def accept(self):
        try:
            self.values()
        except ValueError:
            message = (_('Black point must be below white point.') if self.effect_id == 'levels'
                       else _('Enter a colour in #RRGGBB format, such as #204060.'))
            QMessageBox.warning(self, self.windowTitle(), message)
            return
        super().accept()

    def region(self):
        if self.region_mode is not None and self.region_mode.currentData():
            return self.region_fields.box()
        return None
