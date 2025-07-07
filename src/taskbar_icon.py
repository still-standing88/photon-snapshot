from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QObject
import resources_rc


class TaskbarIcon(QObject):


    def __init__(self, window):
        super().__init__(window)
        self.window = window
        
        self.tray_icon = QSystemTrayIcon(self)
        
        icon = QIcon(":icons/photon-snapshot.png")
        self.tray_icon.setIcon(icon)
        
        self.create_menu()
        self.tray_icon.setToolTip("Photon Snapshot")
        self.tray_icon.activated.connect(self.on_tray_activated)
    
    def create_menu(self):
        menu = QMenu()
        
        self.show_action = QAction("Show", self)
        self.show_action.triggered.connect(self.on_show_window)
        menu.addAction(self.show_action)
        
        menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.window.close)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()
    
    def on_show_window(self):
        if self.window.isVisible():
            self.show_action.setText("Show")
            self.hide_window()
        else:
            self.show_action.setText("Hide")
            self.show_window()

    def show_window(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()
    
    def hide_window(self):
        self.window.hide()
    
    def show(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon.show()
            return True
        return False
