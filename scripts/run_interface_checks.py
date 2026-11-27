"""Launch a real-window QA session using an isolated preferences database."""
import sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtWidgets import QApplication
from app_db import base_database, db
from app_config import prefs, key_config
from utilities.i18n import install_translation
from gui.main_window import MainWindow
from taskbar_icon import TaskbarIcon
import resources_rc

def main():
    folder = ROOT / 'qa-artifacts'
    folder.mkdir(exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName('Photon Snapshot QA')
    install_translation('en')
    with patch.object(base_database, 'get_database_path', return_value=str(folder / 'interface.db')):
        db.initialize()
    prefs.initialize()
    from utilities.theme_manager import setup_theme
    setup_theme(app)
    prefs.prefs['minimize_to_tray_on_close'] = False
    prefs.prefs['last_explorer_path'] = str(folder)
    key_config.load_keys()
    window = MainWindow()
    window.taskbar_icon = TaskbarIcon(window)
    window.taskbar_icon.show()
    window.show()
    if len(sys.argv) > 1:
        window.load_image_file(sys.argv[1])
    code = app.exec()
    db.close()
    return code

if __name__ == '__main__':
    raise SystemExit(main())
