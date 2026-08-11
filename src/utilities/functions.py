"""General-purpose helper functions shared across the app. Adapted from
playForm's ``utilities/functions.py``, trimmed to what an image viewer/
editor actually needs (no media/VLC/YouTube helpers).
"""

import os
import sys
import shlex
import subprocess as sp
import tempfile
from pathlib import Path

import app_info


def is_frozen() -> bool:
    """True when running from a Nuitka/PyInstaller-built executable."""
    return getattr(sys, "frozen", False) or "__compiled__" in globals()


def is_dev_mode() -> bool:
    return not is_frozen()


def get_app_path() -> str:
    """Directory the running code lives in (install dir when frozen, the
    ``src`` directory's parent when run from source)."""
    if is_frozen():
        base_dir = Path(sys.argv[0]).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent
    return str(base_dir)


def get_script_parent_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_exe_parent_dir() -> Path:
    return Path(sys.argv[0]).resolve().parent if is_frozen() else Path(sys.executable).parent


def get_parent_dir() -> str:
    return str(get_exe_parent_dir() if is_frozen() else get_script_parent_dir())


def get_user_data_dir() -> str:
    """Per-user, per-app data directory: ``~/.photon-snapshot``.

    This is where the SQLite database, logs, screenshots and any user
    overrides live - never inside the (possibly read-only / admin-owned)
    install directory.
    """
    data_dir = Path.home() / app_info.APP_DATA_DIRNAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir)


def get_logs_dir() -> str:
    candidates = [Path(get_user_data_dir()) / "logs"]
    local_appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if local_appdata:
        candidates.append(Path(local_appdata) / "Photon Snapshot" / "logs")
    candidates.append(Path(tempfile.gettempdir()) / "PhotonSnapshot" / "logs")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_test"
            with open(probe, "a", encoding="utf-8"):
                pass
            probe.unlink(missing_ok=True)
            return str(candidate)
        except OSError:
            continue

    fallback = Path(tempfile.gettempdir()) / "PhotonSnapshot" / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return str(fallback)


def get_screenshots_dir() -> str:
    path = Path(get_user_data_dir()) / "Screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_database_path() -> str:
    return str(Path(get_user_data_dir()) / "photon_snapshot.db")


def get_lang_dir() -> str:
    """Compiled .mo catalogs shipped with the app (``<app_path>/lang``),
    falling back to the source tree's ``lang`` directory in dev mode."""
    shipped = Path(get_parent_dir()) / "lang"
    if shipped.is_dir():
        return str(shipped)
    return str(Path(__file__).resolve().parent.parent.parent / "lang")


def user_path() -> str:
    return os.path.expanduser("~")


def set_restart_flag(flag: bool):
    os.environ["APP_RESTART"] = "1" if flag else "0"


def get_restart_flag() -> bool:
    return os.environ.get("APP_RESTART", "0") == "1"


def restart_app():
    if is_frozen():
        os.execl(sys.executable, sys.executable, *sys.argv[1:])
    else:
        python = sys.executable
        os.execl(python, python, *sys.argv)


def is_local_file(path: str) -> bool:
    if not path:
        return False
    try:
        return os.path.isfile(path)
    except OSError:
        return False


def open_file_location(path: str):
    """Reveal a file in the platform's file manager, selecting it."""
    if not is_local_file(path):
        return
    if sys.platform == "win32":
        sp.Popen(f'explorer /select,"{path}"')
    elif sys.platform == "darwin":
        sp.Popen(["open", "-R", path])
    else:
        sp.Popen(["xdg-open", os.path.dirname(path)])


def get_file_size_str(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def is_valid_shell_text(text: str) -> bool:
    try:
        shlex.split(text, posix=True)
        return True
    except ValueError:
        return False
