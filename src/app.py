import sys
import os
import app_guard

from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor

from gui.main_window import MainWindow
from taskbar_icon import TaskbarIcon


def setup_application_style(app: QApplication):
    app.setStyle('Fusion')
    
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(64, 64, 64))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))    
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))

    app.setPalette(dark_palette)


def main():
    if getattr(sys, 'frozen', False):
        BASE_DIR = Path(sys.executable).parent
        os.environ['QT_PLUGIN_PATH'] = str(BASE_DIR / "PySide6" / "qt-plugins")
    else:
        BASE_DIR = Path(__file__).parent

    cli_args = sys.argv
    instance = app_guard.AppGuard()
    app = QApplication(sys.argv)

    instance.init("photon_snapshot", lambda: None, False)
    if not instance.is_primary_instance() and cli_args:
        instance.send_msg_request("cli-args", cli_args[1])
        instance.release()
        exit(0)

    app.setApplicationName("Photon Snapshot")
    app.setApplicationVersion("1.0.0")
    setup_application_style(app)

    window = MainWindow()
    taskbar_icon = TaskbarIcon(window)
    cli_args_msg:app_guard.IPCMsg = instance.create_ipc_msg("cli-args",
        window.cli_load_file
    )
    instance.register_msg(cli_args_msg)

    if len(cli_args) > 1:
        window.load_file(cli_args[1])
        instance.focus_window("Photon Snapshot")

    window.show()
    taskbar_icon.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()