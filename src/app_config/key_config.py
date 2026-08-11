"""akeyconfig: the app-wide, remappable key-binding system.

Adapted from playForm's ``app_config/key_config.py``. playForm's version
manages OS-wide global hotkeys (for background media control) on top of an
in-app config file; Photon Snapshot only needs in-app shortcuts, so this
version drops the ``keyboard`` package dependency and the global-hotkey
machinery, and persists bindings to the SQLite database (see
:mod:`app_db`) instead of a ``key_config.cfg`` file.

Usage:
    from app_config import key_config
    key_config.load_keys()
    ...
    action = QAction(_("Open file"), window)
    key_config.bind_action("Main Window", "Open file", action)
    ...
    # later, from the hotkeys dialog:
    key_config.set_sequence("Main Window", "Open file", "Ctrl+Shift+O")
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QKeySequence, QShortcut

from app_constance import default_keys

# section -> {action: sequence}
key_dict: dict[str, dict[str, str]] = {
    section: dict(actions) for section, actions in default_keys.key_dict.items()
}

# Live, possibly user-modified bindings. Same shape as key_dict.
bindings: dict[str, dict[str, str]] = {}

# Registered QAction/QShortcut targets, so a remap can immediately update
# every bound widget: {(section, action): [QAction | QShortcut, ...]}
_bound_targets: dict[tuple[str, str], list] = {}

# Callables to invoke when a binding changes, e.g. to refresh a dialog.
_change_listeners: list[Callable[[], None]] = []


def _db():
    from app_db import db

    return db


def is_valid_hotkey(sequence: str) -> bool:
    if not sequence:
        return True
    return not QKeySequence(sequence).isEmpty()


def keys_to_default():
    """Reset the in-memory + persisted bindings to the shipped defaults."""
    global bindings
    bindings = {section: dict(actions) for section, actions in key_dict.items()}
    _save_all()
    _reapply_all()


def _save_all():
    db = _db()
    db.clear_key_bindings()
    for section, actions in bindings.items():
        for action, sequence in actions.items():
            db.set_key_binding(section, action, sequence)


def load_keys():
    """Load bindings from the database, seeding it with defaults on first
    run or if the stored schema no longer matches (e.g. after an app
    update added/removed an action)."""
    global bindings
    db = _db()
    stored = db.get_all_key_bindings()

    if not stored or not _matches_schema(stored):
        keys_to_default()
        return

    bindings = stored


def _matches_schema(stored: dict) -> bool:
    if set(stored.keys()) != set(key_dict.keys()):
        return False
    for section, actions in key_dict.items():
        if set(stored.get(section, {}).keys()) != set(actions.keys()):
            return False
    return True


def get_sequence(section: str, action: str) -> str:
    return bindings.get(section, {}).get(action, key_dict.get(section, {}).get(action, ""))


def set_sequence(section: str, action: str, sequence: str):
    bindings.setdefault(section, {})[action] = sequence
    _db().set_key_binding(section, action, sequence)
    _reapply_one(section, action)
    for listener in _change_listeners:
        listener()


def bind_action(section: str, action: str, target):
    """Attach a QAction or QShortcut to a binding, applying the current
    sequence immediately and keeping it in sync with future remaps."""
    sequence = get_sequence(section, action)
    _apply_sequence(target, sequence)
    _bound_targets.setdefault((section, action), []).append(target)
    return target


def make_shortcut(section: str, action: str, parent, callback: Callable) -> QShortcut:
    sequence = get_sequence(section, action)
    shortcut = QShortcut(QKeySequence(sequence), parent)
    shortcut.activated.connect(callback)
    _bound_targets.setdefault((section, action), []).append(shortcut)
    return shortcut


def _apply_sequence(target, sequence: str):
    try:
        target.setShortcut(QKeySequence(sequence))
    except Exception:
        pass


def _reapply_one(section: str, action: str):
    sequence = get_sequence(section, action)
    for target in _bound_targets.get((section, action), []):
        _apply_sequence(target, sequence)


def _reapply_all():
    for (section, action) in list(_bound_targets.keys()):
        _reapply_one(section, action)


def add_change_listener(callback: Callable[[], None]):
    _change_listeners.append(callback)


def all_sections() -> list[str]:
    return list(key_dict.keys())
