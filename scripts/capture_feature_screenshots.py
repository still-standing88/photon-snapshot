"""Render isolated Qt windows for documentation and layout review."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtCore import QEvent
from app_init import setup_application_style
from app_db import base_database, db
from app_config import prefs, key_config
from utilities.i18n import install_translation
from core.animation_io import decode_document
from core.batch_conversion import SourceEntry
from gui.main_window import MainWindow
import resources_rc


def close_window(window, app):
    window.jobs.cancel_all()
    for job in list(window.jobs.jobs):
        job.wait(5000)
    app.processEvents()
    window.hide()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def main():
    language = sys.argv[1] if len(sys.argv) > 1 else 'en'
    output = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'assets' / 'screenshots'
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    # Windows' offscreen backend does not discover installed fonts itself.
    if sys.platform == 'win32':
        for name in ('segoeui.ttf', 'segoeuib.ttf'):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name))
    app.setQuitOnLastWindowClosed(False)
    install_translation(language)
    with tempfile.TemporaryDirectory(prefix='photon-layout-') as folder, ExitStack() as cleanup:
        with patch.object(base_database, 'get_database_path', return_value=str(Path(folder) / 'app.db')):
            db.initialize()
        cleanup.callback(db.close)
        prefs.initialize()
        prefs.prefs['minimize_to_tray_on_close'] = False
        key_config.load_keys()
        setup_application_style(app)
        window = MainWindow()
        cleanup.callback(close_window, window, app)
        window.editor.load_document(decode_document(ROOT / 'qa-artifacts' / 'desktop-saved.photonanim'))
        window.resize(900, 700)
        window.show()
        QTest.qWait(200)
        for job in list(window.jobs.jobs):
            job.wait(5000)
        app.processEvents()
        print('Main layout:', window.size(), window.minimumSizeHint(), 'canvas:', window.canvas_splitter.minimumSizeHint(),
              'frames:', window.animation_panel.minimumSizeHint(), 'editor:', window.editor_panel.minimumSizeHint())
        assert window.minimumSizeHint().width() <= 900
        assert window.minimumSizeHint().height() <= 700
        window.grab().save(str(output / f'animation-{language}.png'))
        window.open_batch_converter()
        tool = window.batch_dialog
        tool.add_source(SourceEntry(str(ROOT / 'qa-artifacts' / 'demo-photo.jpg')))
        tool.add_effect('resize', {'width': 320, 'height': 240, 'mode': 'exact'})
        tool.add_effect('grayscale', {})
        tool.preset.setCurrentText('Demo')
        tool.resize(780, 580)
        for index in range(4):
            tool.tabs.setCurrentIndex(index)
            app.processEvents()
            print('Batch tab:', index, tool.size(), tool.minimumSizeHint())
            assert tool.minimumSizeHint().width() <= 900
            assert tool.minimumSizeHint().height() <= 700
            tool.grab().save(str(output / f'batch-{index}-{language}.png'))
        tool.hide()
    print(f'Rendered {language} layouts to {output}')


if __name__ == '__main__':
    main()
