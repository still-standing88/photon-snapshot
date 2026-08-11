"""Explorer dock lifecycle + window/layout persistence, adapted (heavily
simplified - one dock, not playform's half-dozen media panes) from
playForm's ``gui/managers/dock_manager.py``. Geometry/state are persisted
to the SQLite database (see :mod:`app_db`) instead of QSettings/JSON.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDockWidget

from gui_controls.floatable_dock_widget import FloatableDockWidget


class DockManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self._hidden_floating_docks = []

    @staticmethod
    def _make_float_a_real_window(dock: QDockWidget):
        """A floated QDockWidget defaults to Qt::Tool, which most window
        managers (including Windows) exclude from Alt-Tab/taskbar
        switching. Force Qt::Window so it behaves like a normal top-level
        window once floated."""
        def on_top_level_changed(floating: bool):
            if floating:
                was_visible = dock.isVisible()
                dock.setWindowFlags(dock.windowFlags() | Qt.WindowType.Window)
                if was_visible:
                    dock.show()

        dock.topLevelChanged.connect(on_top_level_changed)

    def _floatable_features(self):
        return (
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )

    def setup_dock_widgets(self):
        mw = self.main_window
        self.explorer_dock = FloatableDockWidget(_("Explorer"), mw)
        self.explorer_dock.setObjectName("explorerDock")
        self.explorer_dock.setWidget(mw.explorer_widget)
        self.explorer_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.explorer_dock.setFeatures(self._floatable_features())
        self._make_float_a_real_window(self.explorer_dock)
        self.explorer_dock.visibilityChanged.connect(mw.on_explorer_visibility_changed)
        mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)
        mw.explorer_dock = self.explorer_dock
        self.update_focusable_widgets()

    def toggle_explorer(self, checked: bool):
        mw = self.main_window
        self.explorer_dock.setVisible(checked)
        if checked:
            mw.explorer_widget.setFocus()
        self.update_focusable_widgets()

    def save_window_state(self):
        from app_db import db
        mw = self.main_window
        db.save_window_state("geometry", mw.saveGeometry().data().hex())
        db.save_window_state("state", mw.saveState().data().hex())
        db.save_window_state("explorer_visible", "1" if self.explorer_dock.isVisible() else "0")

    def restore_window_state(self):
        from app_db import db
        mw = self.main_window

        geometry = db.load_window_state("geometry")
        if geometry:
            try:
                mw.restoreGeometry(bytes.fromhex(geometry))
            except (ValueError, TypeError):
                pass

        state = db.load_window_state("state")
        if state:
            try:
                mw.restoreState(bytes.fromhex(state))
            except (ValueError, TypeError):
                pass

        explorer_visible = db.load_window_state("explorer_visible")
        visible = explorer_visible != "0" if explorer_visible is not None else False
        self.explorer_dock.setVisible(visible)
        mw.show_explorer_action.setChecked(visible)

        QTimer.singleShot(0, self.clamp_to_screen)

    def clamp_to_screen(self):
        mw = self.main_window
        if mw.isFullScreen() or mw.isMaximized():
            return
        screen = mw.screen()
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = mw.frameGeometry()
        x = min(frame.x(), available.right() - frame.width() + 1)
        y = min(frame.y(), available.bottom() - frame.height() + 1)
        x = max(x, available.left())
        y = max(y, available.top())
        if (x, y) != (frame.x(), frame.y()):
            mw.move(x, y)

    def hide_floating_docks(self):
        """Floated docks are separate top-level windows - hiding the main
        window (e.g. to the tray) doesn't hide them too."""
        self._hidden_floating_docks = [
            d for d in (self.explorer_dock,) if d.isFloating() and d.isVisible()
        ]
        for dock in self._hidden_floating_docks:
            dock.hide()

    def restore_floating_docks(self):
        for dock in self._hidden_floating_docks:
            dock.show()
        self._hidden_floating_docks = []

    def update_focusable_widgets(self):
        mw = self.main_window
        mw.focusable_widgets = []

        if hasattr(mw, "toolbar") and mw.toolbar.isVisible():
            mw.focusable_widgets.append(mw.toolbar)

        if self.explorer_dock.isVisible():
            mw.focusable_widgets.append(mw.explorer_widget)

        mw.focusable_widgets.append(mw.viewer)
        mw.focusable_widgets.append(mw.editor_panel)

        if hasattr(mw, "status_bar") and mw.status_bar.isVisible():
            mw.focusable_widgets.append(mw.status_bar)
