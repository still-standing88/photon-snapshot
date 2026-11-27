import os
import sys

from PySide6.QtWidgets import QApplication

import app_init
from loading import LoadingSplash
from taskbar_icon import TaskbarIcon

if sys.platform.startswith("linux"):
    from local_app_guard import LocalAppGuard
else:
    import app_guard


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from release_smoke import run
        raise SystemExit(run(sys.argv[2]))
    app_init.setup_environment()

    cli_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else None
    app = QApplication(sys.argv)

    if sys.platform.startswith("linux"):
        instance = LocalAppGuard("photon-snapshot")
        if not instance.start_or_forward(cli_path):
            sys.exit(0)
    else:
        instance = app_guard.AppGuard()
        instance.init("photon_snapshot", lambda: None, False)
        if not instance.is_primary_instance():
            if cli_path:
                instance.send_msg_request("cli-args", cli_path)
            instance.focus_window("Photon Snapshot")
            instance.release()
            sys.exit(0)

    app.setApplicationName("Photon Snapshot")
    import app_info
    app.setApplicationVersion(app_info.APP_VERSION)

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

    if sys.platform.startswith("linux"):
        def open_forwarded_path(path):
            taskbar_icon.show_window()
            if path:
                window.load_file(path)

        instance.set_handler(open_forwarded_path)
    else:
        cli_args_msg = instance.create_ipc_msg("cli-args", window.cli_load_file)
        instance.register_msg(cli_args_msg)

    if cli_path:
        window.load_file(cli_path)
        if not sys.platform.startswith("linux"):
            instance.focus_window("Photon Snapshot")

    app_init.setup_cleanup(app, instance, db)

    from app_config.prefs import prefs
    tray_available = taskbar_icon.show()
    if not prefs.get("start_minimized_to_tray", False) or not tray_available:
        window.show()
        splash.finish(window)
    else:
        # finish(window) waits for the window to be exposed. A startup
        # intentionally hidden in the tray must close the splash directly.
        splash.close()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
