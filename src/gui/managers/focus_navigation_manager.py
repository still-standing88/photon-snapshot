"""F6/Shift+F6 pane-cycling logic, ported from playForm's
``gui/managers/focus_navigation_manager.py`` (same algorithm: derive the
current position from ``QApplication.focusWidget()`` rather than trusting a
stale index, so it stays correct even after the user clicked or Tabbed
somewhere else - e.g. into a floated dock - since the last F6 press).
"""

from PySide6.QtWidgets import QApplication


class FocusNavigationManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def _current_focus_list_index(self) -> int:
        mw = self.main_window
        focus_widget = QApplication.focusWidget()
        if focus_widget is None:
            return -1
        for i, widget in enumerate(mw.focusable_widgets):
            if widget is focus_widget or widget.isAncestorOf(focus_widget):
                return i
        return -1

    def focus_next_widget(self):
        mw = self.main_window
        mw.dock_manager.update_focusable_widgets()
        if not mw.focusable_widgets:
            return
        current = self._current_focus_list_index()
        mw.current_focus_index = (current + 1) % len(mw.focusable_widgets)
        self._focus_navigation_target(mw.focusable_widgets[mw.current_focus_index])

    def focus_previous_widget(self):
        mw = self.main_window
        mw.dock_manager.update_focusable_widgets()
        if not mw.focusable_widgets:
            return
        current = self._current_focus_list_index()
        mw.current_focus_index = (current - 1) % len(mw.focusable_widgets)
        self._focus_navigation_target(mw.focusable_widgets[mw.current_focus_index])

    def _focus_navigation_target(self, widget):
        mw = self.main_window
        if widget is None:
            return

        target_window = widget.window()
        if target_window is not None:
            target_window.activateWindow()
            target_window.raise_()
            # Window activation isn't always synchronous - without pumping
            # the event loop here, the setFocus() calls below can land
            # before the window manager actually hands over activation.
            QApplication.processEvents()

        if widget is mw.toolbar:
            widget.setFocus()
            toolbar_actions = [a for a in widget.actions() if a.isVisible() and not a.isSeparator()]
            if toolbar_actions:
                toolbar_widget = widget.widgetForAction(toolbar_actions[0])
                if toolbar_widget is not None:
                    toolbar_widget.setFocus()
            return

        if widget is mw.status_bar:
            widget.setFocus()
            mw.status_label.setFocus()
            return

        widget.setFocus()
