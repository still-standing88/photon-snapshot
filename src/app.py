"""Application entry point.

Startup order mirrors playForm's ``app.py``: parse argv flags, install crash
and logging handlers *before* anything can fail, claim the single-instance
lock, then bring up the GUI inside a try/except that closes the splash and
logs rather than leaving an orphaned splash screen on a failed start.
"""

import os
import sys

from PySide6.QtWidgets import QApplication

import app_init
from app_info import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_PUBLISHER,
    APP_VERSION,
    APP_WEBSITE,
)

_USAGE = """\
{name} {version} - {description}

Usage:
  PhotonSnapshot [options] [image-file]

Options:
  -h, --help       Show this message and exit.
  -v, --version    Show the version and exit.
  --debug          Verbose fault dumps (all threads) for this run.

If an image file is given and {name} is already running, the file is opened
in the existing window instead of starting a second copy.
"""


def _print_and_exit(text: str) -> None:
    """Emit a CLI message, falling back to a dialog in a windowed build.

    The Windows binary is built with --windows-console-mode=disable, so
    sys.stdout is None when launched from Explorer and there is nothing to
    print to. Running it from a terminal *does* give a usable stdout, which is
    the case that matters for --help/--version.
    """
    out = sys.__stdout__
    if out is not None:
        out.write(text if text.endswith("\n") else text + "\n")
        out.flush()
    else:
        from PySide6.QtWidgets import QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
        QMessageBox.information(None, APP_NAME, text)
    sys.exit(0)


def parse_cli_args(argv):
    """Split argv into (remaining_args, debug_mode), handling --help/--version.

    ``--debug`` is a plain argv flag rather than an environment variable so it
    behaves identically for a compiled binary and for ``python app.py`` -
    playForm makes the same choice. It is stripped out before the rest of
    startup sees argv, since everything downstream treats argv[1] as a path.
    """
    if any(a in ("-h", "--help", "/?") for a in argv[1:]):
        _print_and_exit(
            _USAGE.format(name=APP_NAME, version=APP_VERSION, description=APP_DESCRIPTION)
        )
    if any(a in ("-v", "--version") for a in argv[1:]):
        _print_and_exit(f"{APP_NAME} {APP_VERSION}")

    debug_mode = "--debug" in argv
    if debug_mode:
        argv = [a for a in argv if a != "--debug"]
        os.environ["PHOTON_DEBUG"] = "1"
    return argv, debug_mode


def main():
    cli_args, _debug_mode = parse_cli_args(sys.argv)

    # setup_environment() populates the PHOTON_APP_* environment from
    # app_info, so it has to run before anything reads those.
    app_init.setup_environment()

    # Logging and crash capture first: everything after this point is covered,
    # including a failure inside module import or window construction. Before,
    # get_logs_dir() existed but was never called by anything and an uncaught
    # exception in a windowed build vanished with no trace at all.
    from log_handler import LoggingSetup, get_logger
    from utilities.crash_handler import install_crash_handler
    from utilities.functions import get_logs_dir

    logs_dir = get_logs_dir()
    LoggingSetup(logs_dir)
    install_crash_handler(logs_dir)
    logger = get_logger()
    logger.info("Starting %s %s", APP_NAME, APP_VERSION)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    # Was missing entirely; Qt uses these for QSettings paths and for the
    # window-manager identity, and they should come from app_info rather than
    # being hardcoded here as the name/version previously were.
    app.setOrganizationName(APP_PUBLISHER)
    app.setOrganizationDomain(APP_WEBSITE)

    # Installs `_()` as a builtin using the system locale (or English if
    # nothing matches) *before* anything - including the splash screen below -
    # can call it. app_init.initialize_modules() re-installs it with the user's
    # saved language preference once prefs are loaded; calling it here first is
    # what makes LoadingSplash() safe to construct before that happens.
    from utilities.i18n import install_translation
    install_translation()

    instance, should_exit = app_init.initialize_app_guard(cli_args)
    if should_exit:
        # Another copy is already running; it has been handed any file
        # argument and raised to the front.
        logger.info("Secondary instance handed off to the running copy; exiting")
        sys.exit(0)

    from loading import LoadingSplash
    splash = LoadingSplash()
    splash.show()
    app.processEvents()

    try:
        db = app_init.initialize_modules(splash)
        app_init.setup_application_style(app)

        window = app_init.create_main_window(splash, cli_args)
        from taskbar_icon import TaskbarIcon
        taskbar_icon = TaskbarIcon(window)

        app_init.setup_ipc_handlers(instance, window)
        app_init.setup_cleanup(app, instance, db)

        splash.update_message(_("Starting application..."))
        splash.finish(window)

        from app_config.prefs import prefs
        if not prefs.get("start_minimized_to_tray", False):
            window.show()
        taskbar_icon.show()
    except Exception:
        # Previously an exception anywhere in here propagated with the splash
        # still on screen: no main window, no log, no message - just a stuck
        # splash. Log it, take the splash down, then re-raise so the installed
        # excepthook records it too.
        logger.exception("Fatal error during startup")
        try:
            splash.close()
        except Exception:
            pass
        try:
            if instance is not None:
                instance.release()
        except Exception:
            pass
        raise

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
