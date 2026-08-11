"""Shared base for QDockWidgets that can be floated into their own window.
Ported verbatim from playForm's ``gui_controls/floatable_dock_widget.py``.
"""

from PySide6.QtWidgets import QDockWidget


class FloatableDockWidget(QDockWidget):
    """Closing a floated window (its close button, Alt+F4, etc.) must never
    destroy the dock - visibility is only meant to be controlled through the
    View menu / toolbar toggle. Closing instead re-docks and hides it."""

    def closeEvent(self, event):
        if self.isFloating():
            self.setFloating(False)
        self.hide()
        event.accept()
