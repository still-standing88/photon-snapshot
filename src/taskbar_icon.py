from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject, QEvent
import resources_rc

import app_info


class TaskbarIcon(QObject):
    """System tray icon: shows/hides the main window and exits the app.
    Ported/expanded from the pre-rewrite ``taskbar_icon.py`` - now
    i18n-marked and synced correctly with the window's actual visibility
    (the previous version could get out of sync since the menu label was
    updated from the click handler rather than from the window's real
    show/hide events)."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.window.taskbar_icon = self

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(":icons/photon-snapshot.png"))
        self.tray_icon.setToolTip(app_info.APP_NAME)

        self.create_menu()
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.window.installEventFilter(self)
        self._sync_label()

    def create_menu(self):
        # The menu must be parented (and kept as an attribute): Qt's
        # setContextMenu() does NOT take ownership, so a parentless local
        # QMenu would be garbage-collected once this method returns,
        # leaving the tray icon with a dangling pointer.
        self.tray_menu = QMenu(self.window)
        menu = self.tray_menu

        self.show_action = QAction(_("Hide"), self)
        self.show_action.triggered.connect(self.on_toggle_window)
        menu.addAction(self.show_action)

        menu.addSeparator()

        quit_action = QAction(_("Quit"), self)
        quit_action.triggered.connect(self.window.close_application)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        menu.aboutToShow.connect(self._sync_label)

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() in (
            QEvent.Type.Show, QEvent.Type.Hide, QEvent.Type.WindowStateChange,
        ):
            self._sync_label()
        return super().eventFilter(watched, event)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.on_toggle_window()

    def on_toggle_window(self):
        if self.window.isVisible() and not self.window.isMinimized():
            self.hide_window()
        else:
            self.show_window()

    def _sync_label(self):
        visible = self.window.isVisible() and not self.window.isMinimized()
        self.show_action.setText(_("Hide") if visible else _("Show"))

    def show_window(self):
        if self.window.isMinimized():
            self.window.showNormal()
        else:
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        if hasattr(self.window, "dock_manager"):
            self.window.dock_manager.restore_floating_docks()
        self._sync_label()

    def hide_window(self):
        if hasattr(self.window, 'playback'):
            self.window.playback.stop()
        if hasattr(self.window, "dock_manager"):
            self.window.dock_manager.hide_floating_docks()
        self.window.hide()
        self._sync_label()

    def show(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
            return True
        return False

    def show_message(self, title: str, message: str, duration_ms: int = 2000):
        if self.tray_icon.supportsMessages():
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms)
