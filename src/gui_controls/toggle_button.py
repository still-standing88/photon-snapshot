"""Animated two-state push button used as an Accordion section header.
Ported from playForm's ``gui_controls/toggle_button.py`` verbatim (it has no
media-app-specific dependencies).
"""

import shiboken6
from PySide6.QtWidgets import QPushButton, QGraphicsOpacityEffect, QGraphicsDropShadowEffect
from PySide6.QtCore import Signal, QPropertyAnimation, QEasingCurve, Qt, QParallelAnimationGroup
from PySide6.QtGui import QColor


class ToggleButton(QPushButton):
    actuated = Signal(bool)

    def __init__(self, text=None, parent=None):
        super().__init__(parent)

        self.activated = False

        self.setupAnimations()
        self.setupStyle()

        self.clicked.connect(self.onActuate)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if text and text.strip():
            self.setText(text)

        self.updateAccessibility()
        self.updateStyle()

        self.setMinimumSize(100, 35)

    def setupAnimations(self):
        self.animationGroup = QParallelAnimationGroup(self)

        self.opacityEffect = QGraphicsOpacityEffect()

        self.opacityAnimation = QPropertyAnimation(self.opacityEffect, b"opacity")
        self.opacityAnimation.setDuration(200)
        self.opacityAnimation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.sizeAnimation = QPropertyAnimation(self, b"minimumSize")
        self.sizeAnimation.setDuration(250)
        self.sizeAnimation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.animationGroup.addAnimation(self.opacityAnimation)
        self.animationGroup.addAnimation(self.sizeAnimation)

        self.shadowEffect = QGraphicsDropShadowEffect()
        self.shadowEffect.setBlurRadius(8)
        self.shadowEffect.setOffset(0, 4)
        self.shadowEffect.setColor(QColor(66, 133, 244, 90))
        self.shadowEffect.setEnabled(False)

        self.shadowAnimation = QPropertyAnimation(self.shadowEffect, b"blurRadius")
        self.shadowAnimation.setDuration(200)
        self.shadowAnimation.setEasingCurve(QEasingCurve.Type.OutQuad)

    def _ensure_opacity_effect(self):
        if not shiboken6.isValid(self.opacityEffect):
            self.opacityEffect = QGraphicsOpacityEffect()
            self.opacityAnimation.setTargetObject(self.opacityEffect)

    def _ensure_shadow_effect(self):
        if not shiboken6.isValid(self.shadowEffect):
            self.shadowEffect = QGraphicsDropShadowEffect()
            self.shadowEffect.setBlurRadius(8)
            self.shadowEffect.setOffset(0, 4)
            self.shadowEffect.setColor(QColor(66, 133, 244, 90))
            self.shadowEffect.setEnabled(False)
            self.shadowAnimation.setTargetObject(self.shadowEffect)

    def setupStyle(self):
        self.base_style = """
            QPushButton {
                background-color: #333333;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: 600;
                color: #e8e8e8;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        self.activated_style = """
            QPushButton {
                background-color: #0078d4;
                border: 1px solid #106ebe;
                border-radius: 4px;
                padding: 8px 12px;
                font-weight: 600;
                color: white;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """

    def updateStyle(self):
        if self.activated:
            self.setStyleSheet(self.activated_style)
            self.setProperty("toggled", True)
        else:
            self.setStyleSheet(self.base_style)
            self.setProperty("toggled", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def updateAccessibility(self):
        if self.activated:
            self.setAccessibleDescription(_("Section expanded - activate to collapse"))
            self.setAccessibleName(_("{name} - expanded").format(name=self.text()))
        else:
            self.setAccessibleDescription(_("Section collapsed - activate to expand"))
            self.setAccessibleName(_("{name} - collapsed").format(name=self.text()))

    def setActuated(self, state):
        if isinstance(state, bool) and state != self.activated:
            self.activated = state
            self.actuatedChange()
            self.updateStyle()
            self.updateAccessibility()
            self.actuated.emit(self.activated)
        elif not isinstance(state, bool):
            raise TypeError("State must be boolean")

    def isActuated(self):
        return self.activated

    def onActuate(self):
        self.activated = not self.activated
        self.actuatedChange()
        self.updateStyle()
        self.updateAccessibility()
        self.actuated.emit(self.activated)

    def actuatedChange(self):
        if self.animationGroup.state() == QParallelAnimationGroup.State.Running:
            self.animationGroup.stop()

        self._ensure_opacity_effect()
        self.opacityAnimation.setStartValue(1.0)
        self.opacityAnimation.setKeyValueAt(0.5, 0.7)
        self.opacityAnimation.setEndValue(1.0)

        # A not-yet-laid-out widget has a 640x480 default size. Animating
        # minimumSize toward it permanently enlarged accordion headers.
        # Keep layout constraints stable through every expand/collapse.
        self.sizeAnimation.setStartValue(self.minimumSize())
        self.sizeAnimation.setEndValue(self.minimumSize())
        self.animationGroup.start()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.activated:
            self._ensure_shadow_effect()
            if self.graphicsEffect() != self.shadowEffect:
                self.setGraphicsEffect(self.shadowEffect)
            self.shadowEffect.setEnabled(True)
            self.shadowAnimation.stop()
            self.shadowAnimation.setStartValue(self.shadowEffect.blurRadius())
            self.shadowAnimation.setEndValue(12)
            self.shadowAnimation.start()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._ensure_shadow_effect()
        if self.shadowEffect.isEnabled():
            self.shadowAnimation.stop()
            self.shadowAnimation.setStartValue(self.shadowEffect.blurRadius())
            self.shadowAnimation.setEndValue(0)
            self.shadowAnimation.finished.connect(self._restoreOpacityEffect)
            self.shadowAnimation.start()

    def _restoreOpacityEffect(self):
        self._ensure_shadow_effect()
        self.shadowEffect.setEnabled(False)
        self._ensure_opacity_effect()
        self.setGraphicsEffect(self.opacityEffect)
        try:
            self.shadowAnimation.finished.disconnect(self._restoreOpacityEffect)
        except (RuntimeError, TypeError):
            pass

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setWidth(max(hint.width(), 100))
        hint.setHeight(max(hint.height(), 35))
        return hint

    def setText(self, text):
        super().setText(text)
        self.updateAccessibility()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        if not enabled and hasattr(self, "animationGroup"):
            self.animationGroup.stop()

    def __del__(self):
        try:
            if hasattr(self, "animationGroup") and shiboken6.isValid(self.animationGroup):
                self.animationGroup.stop()
        except Exception:
            pass
