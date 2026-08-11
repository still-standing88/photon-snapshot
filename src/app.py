import sys
import app_guard

from PySide6.QtWidgets import QApplication

import app_init
from loading import LoadingSplash
from taskbar_icon import TaskbarIcon


def main():
    app_init.setup_environment()

    cli_args = sys.argv
    instance = app_guard.AppGuard()
    app = QApplication(sys.argv)

    instance.init("photon_snapshot", lambda: None, False)
    if not instance.is_primary_instance() and len(cli_args) > 1:
        instance.send_msg_request("cli-args", cli_args[1])
        instance.release()
        sys.exit(0)

    app.setApplicationName("Photon Snapshot")
    app.setApplicationVersion("1.1.0")

    # Installs `_()` as a builtin using the system locale (or English if
    # nothing matches) *before* anything - including the splash screen
    # below - can call it. app_init.initialize_modules() re-installs it
    # with the user's saved language preference once prefs are loaded;
    # calling it here first is what makes LoadingSplash() safe to
    # construct before that happens.
    from utilities.i18n import install_translation
    install_translation()

    splash = LoadingSplash()
    splash.show()
    app.processEvents()

    db = app_init.initialize_modules(splash)
    app_init.setup_application_style(app)

    window = app_init.create_main_window(splash)
    taskbar_icon = TaskbarIcon(window)

    cli_args_msg = instance.create_ipc_msg("cli-args", window.cli_load_file)
    instance.register_msg(cli_args_msg)

    if len(cli_args) > 1:
        window.load_file(cli_args[1])
        instance.focus_window("Photon Snapshot")

    app_init.setup_cleanup(app, instance, db)

    splash.finish(window)

    from app_config.prefs import prefs
    if not prefs.get("start_minimized_to_tray", False):
        window.show()
    taskbar_icon.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
