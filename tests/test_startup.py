"""Exercise the real entry point in isolated Qt processes and databases."""
import os
import subprocess
import sys
import unittest
from pathlib import Path

STARTUP_CHECK = r'''
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

available = sys.argv[1] == 'True'
sys.argv = ['photon']
import app as photon_app
import app_init
from app_db import base_database, db
from app_config.prefs import prefs
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

original_create = app_init.create_main_window
guard = MagicMock()
guard.is_primary_instance.return_value = True
guard.start_or_forward.return_value = True
guard_patch = (
    patch.object(photon_app, 'LocalAppGuard', return_value=guard)
    if sys.platform.startswith('linux')
    else patch.object(photon_app.app_guard, 'AppGuard', return_value=guard)
)
errors = []
reviewed = []

def create_window(splash=None):
    window = original_create(splash)
    prefs['start_minimized_to_tray'] = True
    def check():
        try:
            assert window.isVisible() == (not available)
            assert not splash.isVisible()
            reviewed.append(True)
        except Exception as exc:
            errors.append(exc)
        finally:
            QApplication.instance().quit()
    QTimer.singleShot(50, check)
    return window

with tempfile.TemporaryDirectory() as directory:
    with patch.object(base_database, 'get_database_path', return_value=str(Path(directory) / 'app.db')), \
         guard_patch, \
         patch.object(photon_app.TaskbarIcon, 'show', return_value=available), \
         patch.object(app_init, 'prefs_check_updates_on_startup', return_value=False), \
         patch.object(app_init, 'create_main_window', side_effect=create_window):
        try:
            photon_app.main()
        except SystemExit as result:
            assert result.code == 0
        assert reviewed and not errors, errors
        assert not db._initialized
        guard.release.assert_called_once()
'''


class StartupTests(unittest.TestCase):
    def test_start_minimized_with_and_without_a_tray(self):
        root = Path(__file__).resolve().parents[1]
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=str(root / 'src'))
        for available in (True, False):
            with self.subTest(tray_available=available):
                result = subprocess.run(
                    [sys.executable, '-c', STARTUP_CHECK, str(available)],
                    cwd=root, env=environment, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux instance guard')
    def test_linux_secondary_forwards_file_and_focus_requests(self):
        import tempfile
        from unittest.mock import patch

        from PySide6.QtCore import QCoreApplication, QTimer

        root = Path(__file__).resolve().parents[1]
        script = """
import sys
from PySide6.QtCore import QCoreApplication
from local_app_guard import LocalAppGuard

app = QCoreApplication([])
guard = LocalAppGuard("photon-test")
assert not guard.start_or_forward(sys.argv[1] or None)
"""
        with tempfile.TemporaryDirectory() as runtime, patch.dict(os.environ, XDG_RUNTIME_DIR=runtime):
            sys.path.insert(0, str(root / 'src'))
            try:
                from local_app_guard import LocalAppGuard
            finally:
                sys.path.pop(0)

            app = QCoreApplication.instance() or QCoreApplication([])
            primary = LocalAppGuard('photon-test')
            self.assertTrue(primary.start_or_forward(None))
            try:
                path = str(Path(runtime) / 'Unicode é image.png')
                environment = dict(os.environ, PYTHONPATH=str(root / 'src'))
                for argument in (path, ''):
                    result = subprocess.run(
                        [sys.executable, '-c', script, argument],
                        env=environment, capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

                received = []

                def handle_request(request):
                    received.append(request)
                    if len(received) == 2:
                        app.quit()

                primary.set_handler(handle_request)
                timeout = QTimer()
                timeout.setSingleShot(True)
                timeout.timeout.connect(app.quit)
                timeout.start(1000)
                app.exec()
                self.assertEqual(received, [path, ''])
            finally:
                primary.release()


if __name__ == '__main__':
    unittest.main()
