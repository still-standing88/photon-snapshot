from PySide6.QtWidgets import QSpinBox, QLabel, QCheckBox
from .new_image_dialog import NewImageDialog

class NewAnimationDialog(NewImageDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('New Animation'))
        self.transparent = QCheckBox(_('Transparent background'))
        self.transparent.setChecked(True)
        self.layout().insertWidget(self.layout().count()-1, self.transparent)
        self.duration = QSpinBox()
        self.duration.setRange(1, 3600000)
        self.duration.setValue(100)
        self.duration.setSuffix(_(' ms'))
        self.duration.setAccessibleName(_('Initial frame duration'))
        self.plays = QSpinBox()
        self.plays.setRange(0, 65535)
        self.plays.setSpecialValueText(_('Infinite'))
        self.plays.setAccessibleName(_('Total plays'))
        self.layout().insertWidget(self.layout().count()-1, QLabel(_('Initial duration and total plays (0 = infinite):')))
        self.layout().insertWidget(self.layout().count()-1, self.duration)
        self.layout().insertWidget(self.layout().count()-1, self.plays)
