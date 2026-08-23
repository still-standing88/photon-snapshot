"""Startup orchestration, adapted from playForm's ``app_init.py``: resolves
base paths, wires the SQLite database, akeyconfig, and gettext translations
before any GUI module is imported, and builds the main window.
"""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont

# Single-instance identity. APP_GUARD_ID is the cross-process lock/IPC name;
# WINDOW_TITLE is what app_guard's focus_window() looks for on the desktop, so
# it has to match MainWindow's actual window title.
APP_GUARD_ID = "photon_snapshot"
WINDOW_TITLE = "Photon Snapshot"
IPC_CLI_ARGS = "cli-args"


def _log(msg: str) -> None:
    """Write to stdout if there is one (None in windowed frozen builds).

    Same guard as playForm's ``app_init._log`` - a bare print() here raises
    AttributeError under ``--windows-console-mode=disable``.
    """
    out = sys.__stdout__
    if out is not None:
        try:
            out.write(msg if msg.endswith("\n") else msg + "\n")
            out.flush()
        except Exception:
            pass


def clean_path_arg(raw_arg: str) -> str:
    """Normalise a path handed to us on the command line or over IPC.

    Explorer passes quoted absolute paths, but a shell, a shortcut with
    arguments, or a drag-and-drop onto the exe can produce surrounding quotes
    and relative paths. playForm normalises the same way in
    ``_clean_path_arg``; previously Photon passed ``sys.argv[1]`` through
    completely raw, so a relative path resolved against whatever working
    directory the launcher happened to have.
    """
    if not raw_arg:
        return ""
    arg = raw_arg.strip().strip('"').strip("'").strip()
    if not arg:
        return ""
    try:
        return os.path.abspath(arg)
    except (OSError, ValueError):
        return arg


def setup_environment() -> Path:
    import app_info
    app_info.setup_env()

    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
        os.environ["QT_PLUGIN_PATH"] = str(base_dir / "PySide6" / "qt-plugins")
    else:
        base_dir = Path(__file__).parent
    return base_dir


def initialize_app_guard(cli_args):
    """Claim the single-instance lock. Returns ``(instance, should_exit)``.

    A secondary instance always exits - this is the fix for the case that was
    broken before: the old check in ``app.py`` was

        if not instance.is_primary_instance() and len(cli_args) > 1:

    so launching with *no* arguments (double-clicking the shortcut or the tray
    icon while the app was already running) fell straight through and built a
    whole second main window, with a second SQLite connection on the same
    database. playForm's equivalent returns ``should_exit=True`` for any
    secondary, which is what this now does.

    ``focus_window`` is also called from the secondary rather than the primary.
    The primary calling it on itself (as before) did nothing useful, and meant
    opening an image by file association while the app was running loaded the
    image into a window that stayed buried behind whatever had focus.
    """
    import app_guard

    instance = app_guard.AppGuard()
    instance.init(APP_GUARD_ID, lambda: None, False)

    if instance.is_primary_instance():
        return instance, False

    if len(cli_args) > 1:
        path = clean_path_arg(cli_args[1])
        if path:
            _log(f"[Photon Snapshot IPC] secondary handing off: {path}")
            instance.send_msg_request(IPC_CLI_ARGS, path)

    instance.focus_window(WINDOW_TITLE)
    instance.release()
    return None, True


def setup_ipc_handlers(instance, window):
    """Register the primary's handler for paths sent by later launches."""
    if instance is None:
        return None
    msg = instance.create_ipc_msg(IPC_CLI_ARGS, window.cli_load_file)
    instance.register_msg(msg)
    return msg


BASE_FONT_POINT_SIZE = 9
MIN_UI_ZOOM_LEVEL = -4
MAX_UI_ZOOM_LEVEL = 10


def apply_ui_zoom(app, zoom_level=None):
    from app_config.prefs import prefs
    if zoom_level is None:
        zoom_level = prefs.get("ui_zoom_level", 0)
    zoom_level = max(MIN_UI_ZOOM_LEVEL, min(MAX_UI_ZOOM_LEVEL, zoom_level))
    app.setFont(QFont("Segoe UI", BASE_FONT_POINT_SIZE + zoom_level))
    return zoom_level


def setup_application_style(app):
    from utilities.theme_manager import setup_theme

    app.setStyle("Fusion")
    apply_ui_zoom(app)
    setup_theme(app)


def initialize_modules(splash=None):
    """Bring up persistence + config + translations, in dependency order.
    Must run before any GUI module (main_window, editor_panel, ...) is
    imported, since those modules call ``_()`` at class-definition time."""
    if splash:
        splash.update_message("Loading database...")
    from app_db import db
    db.initialize()

    if splash:
        splash.update_message("Loading configuration...")
    from app_config import prefs as prefs_module
    prefs_module.initialize()

    from utilities.i18n import install_translation
    install_translation(prefs_module.prefs.get("language") or None)

    if splash:
        splash.update_message(_("Loading key bindings..."))
    from app_config import key_config
    key_config.load_keys()

    return db


def create_main_window(splash=None, cli_args=None):
    if splash:
        splash.update_message(_("Building interface..."))
    from gui.main_window import MainWindow
    window = MainWindow()

    # Deferred like playForm's: loading during construction runs before the
    # window is shown, so an error dialog from a bad path would have no parent
    # on screen yet.
    if cli_args and len(cli_args) > 1:
        path = clean_path_arg(cli_args[1])
        if path:
            QTimer.singleShot(100, lambda: window.load_external_path(path))

    if prefs_check_updates_on_startup():
        start_update_checker(window)

    return window


def start_update_checker(window):
    """Construct the update checker, tolerating a build without QtNetwork.

    ``update_checker`` imports ``PySide6.QtNetwork``. The MSI build script used
    to strip Qt6Network.dll from the distribution, so this import raised
    ImportError and - because it was unguarded and runs on the default startup
    path - took the whole application down before the main window appeared.
    The DLL is no longer stripped (see installer/windows/build-msi.ps1), but a
    missing optional component must not be able to block startup again.
    """
    try:
        from update_checker import UpdateChecker
    except ImportError as e:
        from log_handler import get_logger
        get_logger().warning("Update checker unavailable (QtNetwork missing?): %s", e)
        return None
    return UpdateChecker.instance(parent=window, background=True)


def prefs_check_updates_on_startup() -> bool:
    from app_config.prefs import prefs
    return bool(prefs.get("check_for_updates_on_startup", True))


def setup_cleanup(app, app_guard_instance, db):
    def release():
        try:
            db.close()
        except Exception:
            pass
        try:
            if app_guard_instance is not None:
                app_guard_instance.release()
        except Exception:
            pass
        try:
            from log_handler import LoggingSetup
            LoggingSetup().cleanup()
        except Exception:
            pass

    app.aboutToQuit.connect(release)
