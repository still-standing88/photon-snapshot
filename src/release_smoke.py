"""Isolated codec/UI smoke checks usable from a packaged executable."""
import json
import tempfile
from pathlib import Path
import traceback

def run(output_folder):
    from PIL import Image
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer, QEventLoop
    from app_db import base_database, db
    from app_config import prefs, key_config
    from utilities.i18n import install_translation
    from core.document import Document, Frame
    from core.image import PhotonImage
    from core.animation_io import decode_document, save_project, load_project
    from core.export import ExportOptions, export_document
    from core.batch_conversion import SourceEntry, BatchSettings, DestinationOptions, run_batch
    from gui.main_window import MainWindow
    from gui.artwork_renderer import render_frame
    import app_info
    output = Path(output_folder).resolve()
    output.mkdir(parents=True, exist_ok=True)
    checks = {'version': app_info.APP_VERSION, 'passed': False}
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    install_translation('en')
    window = None
    try:
        with tempfile.TemporaryDirectory(prefix='photon-release-smoke-') as folder:
            root = Path(folder)
            original_database_path = base_database.get_database_path
            base_database.get_database_path = lambda: str(root / 'app.db')
            db.initialize()
            base_database.get_database_path = original_database_path
            prefs.initialize()
            prefs.prefs['minimize_to_tray_on_close'] = False
            key_config.load_keys()
            window = MainWindow()
            assert window.accessibleName() == 'Photon Snapshot'
            assert [a.text().replace('&', '') for a in window.menuBar().actions()] == ['File', 'Edit', 'View', 'Tools', 'Options']
            document = Document([Frame(PhotonImage(Image.new('RGBA', (48,32), colour)), duration)
                for colour, duration in (('red',40), ('blue',130), ('green',70))], animation=True, total_plays=3)
            for fmt in ('GIF', 'WEBP'):
                path = root / ('animation.'+fmt.lower())
                export_document(path, document, ExportOptions(fmt, lossless=True))
                decoded = decode_document(path)
                assert [f.duration_ms for f in decoded.frames] == [40,130,70]
                assert decoded.total_plays == 3
                checks[fmt] = 'round trip passed'
            document.frames[1].artwork = [{'kind':'rectangle', 'x':5, 'y':5, 'width':10, 'height':10,
                'color':[255,255,255,255], 'fill':[255,255,255,255]}]
            project = root / 'Unicode é project.photonanim'
            save_project(project, document)
            reopened = load_project(project)
            assert reopened.frames[1].artwork == document.frames[1].artwork
            assert render_frame(reopened.frames[1]).getpixel((8,8))[:3] == (255,255,255)
            window.current_file_path = str(project)
            window.editor.load_document(reopened)
            window.editor.apply_invert()
            window.save_file()
            assert not window.editor.is_dirty
            window.open_batch_converter()
            assert [window.batch_dialog.tabs.tabText(i) for i in range(4)] == ['Source','Convert','Processing','Destination']
            inputs, outputs = root / 'inputs', root / 'outputs'
            inputs.mkdir()
            outputs.mkdir()
            for i in range(3):
                Image.new('RGB', (16,16), 'red').save(inputs / f'{i}.png')
            result = run_batch([SourceEntry(str(inputs))], BatchSettings(ExportOptions('JPEG'), destination=DestinationOptions(str(outputs))))
            assert result.counts['converted'] == 3
            checks['batch'] = result.counts
            checks['project_artwork_save'] = 'passed'
            for job in list(window.jobs.jobs):
                job.control.cancel()
                assert job.wait(5000)
            app.processEvents()
            window.hide()
            if window.batch_dialog:
                window.batch_dialog.hide()
            window.deleteLater()
            window = None
            app.processEvents()
            db.close()
        checks['passed'] = True
    except Exception:
        checks['error'] = traceback.format_exc()
    (output / 'release-smoke.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    return 0 if checks['passed'] else 1
