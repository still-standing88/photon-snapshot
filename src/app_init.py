"""Startup orchestration, adapted from playForm's ``app_init.py``: resolves
base paths, wires the SQLite database, akeyconfig, and gettext translations
before any GUI module is imported, and builds the main window.
"""

import os
import sys
from pathlib import Path

from PySide6.QtGui import QFont


def setup_environment() -> Path:
    import app_info
    app_info.setup_env()

    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).parent
        os.environ["QT_PLUGIN_PATH"] = str(base_dir / "PySide6" / "qt-plugins")
    else:
        base_dir = Path(__file__).parent
    return base_dir


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
    from utilities.theme_manager import apply_theme
    from app_config.prefs import prefs

    app.setStyle("Fusion")
    apply_ui_zoom(app)
    apply_theme(app, prefs.get("theme", "dark"))


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


def create_main_window(splash=None):
    if splash:
        splash.update_message(_("Building interface..."))
    from gui.main_window import MainWindow
    window = MainWindow()

    if prefs_check_updates_on_startup():
        from update_checker import UpdateChecker
        UpdateChecker.instance(parent=window)

    return window


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

    app.aboutToQuit.connect(release)
