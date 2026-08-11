"""Centralized light/dark palette application, factored out of what used
to be inline in ``app.py``'s ``setup_application_style()``. Selected from
:mod:`app_config.prefs` (``theme`` key, "dark" or "light") - see the
Options menu / preferences dialog for how the user changes it.
"""

from PySide6.QtGui import QColor, QPalette


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(66, 66, 66))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(64, 64, 64))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    return palette


def _light_palette() -> QPalette:
    # Qt's own default QPalette already reads as a normal light theme -
    # returning a fresh, unmodified instance is enough.
    return QPalette()


def apply_theme(app, theme: str = "dark"):
    if theme == "light":
        app.setPalette(_light_palette())
    else:
        app.setPalette(_dark_palette())
