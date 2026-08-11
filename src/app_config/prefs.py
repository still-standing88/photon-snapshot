"""Dict-like preferences facade over the SQLite ``prefs`` table.

Mirrors playForm's ``app_config.prefs.prefs`` usage pattern (``prefs.get(key,
default)`` / ``prefs[key] = value``) so callers don't need to think about the
database directly, but nothing is cached in a JSON file - every read/write
goes straight to :mod:`app_db`.
"""

from __future__ import annotations

from typing import Any, Iterator

DEFAULTS: dict[str, Any] = {
    "language": "",  # "" = follow system locale
    "theme": "dark",
    "ui_zoom_level": 0,
    "last_explorer_path": "",
    "window_geometry": "",
    "window_state": "",
    "explorer_dock_visible": True,
    "toolbar_visible": True,
    "statusbar_visible": True,
    "menubar_visible": True,
    "confirm_on_overwrite": True,
    "check_for_updates_on_startup": True,
    "start_minimized_to_tray": False,
    "minimize_to_tray_on_close": False,
    "max_recent_files": 20,
    "should_restart": False,
}


class Prefs:
    def _db(self):
        from app_db import db

        return db

    def get(self, key: str, default: Any = None) -> Any:
        if default is None and key in DEFAULTS:
            default = DEFAULTS[key]
        return self._db().get_pref(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __setitem__(self, key: str, value: Any):
        self._db().set_pref(key, value)

    def __contains__(self, key: str) -> bool:
        return self._db().get_pref(key, _MISSING) is not _MISSING

    def keys(self) -> Iterator[str]:
        return iter(self._db().all_prefs().keys())

    def as_dict(self) -> dict:
        merged = dict(DEFAULTS)
        merged.update(self._db().all_prefs())
        return merged

    def save(self):
        # No-op: every set() already persists immediately. Kept for API
        # parity with playForm's prefs.save() call sites.
        pass

    def reset(self):
        db = self._db()
        for key, value in DEFAULTS.items():
            db.set_pref(key, value)


_MISSING = object()

prefs = Prefs()


def initialize():
    """Seed any missing defaults on first run / after an update that added
    new preference keys."""
    db_prefs = prefs._db().all_prefs()
    for key, value in DEFAULTS.items():
        if key not in db_prefs:
            prefs[key] = value
