"""Remappable, widget-scoped Qt shortcuts persisted in the app database.

Adapted from playForm, including preservation of custom bindings on upgrade
and enable/disable without forgetting a sequence.
"""
from __future__ import annotations

import re
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from app_constance import default_keys

key_dict = {section: dict(actions) for section, actions in default_keys.key_dict.items()}
bindings: dict[str, dict[str, str]] = {}
_disabled: set[tuple[str, str]] = set()
_bound_targets: dict[tuple[str, str], list] = {}
_change_listeners: list[Callable[[], None]] = []


def _db():
    from app_db import db
    return db


def normalize_sequence(sequence: str) -> str | None:
    """Return Qt portable text for one chord, or None for invalid input."""
    if not isinstance(sequence, str):
        return None
    sequence = sequence.strip()
    if not sequence:
        return ""
    sequence = re.sub(r"\b(win|windows|super|cmd)\s*\+", "Meta+", sequence, flags=re.I)
    sequence = re.sub(r"\bPage\s+Up\b", "PgUp", sequence, flags=re.I)
    sequence = re.sub(r"\bPage\s+Down\b", "PgDown", sequence, flags=re.I)
    keys = QKeySequence.fromString(sequence, QKeySequence.SequenceFormat.PortableText)
    if keys.count() != 1 or keys[0].key() in (
        Qt.Key.Key_unknown, Qt.Key.Key_Control, Qt.Key.Key_Shift,
        Qt.Key.Key_Alt, Qt.Key.Key_Meta, Qt.Key.Key_AltGr,
    ):
        return None
    return keys.toString(QKeySequence.SequenceFormat.PortableText) or None


def is_valid_hotkey(sequence: str) -> bool:
    return normalize_sequence(sequence) is not None


def _check_action(section: str, action: str):
    if action not in key_dict.get(section, {}):
        raise KeyError(f"Unknown shortcut: {section}/{action}")


def get_sequence(section: str, action: str) -> str:
    _check_action(section, action)
    return bindings.get(section, {}).get(action, key_dict[section][action])


def is_hotkey_enabled(section: str, action: str) -> bool:
    _check_action(section, action)
    return (section, action) not in _disabled


def get_active_sequence(section: str, action: str) -> str:
    return get_sequence(section, action) if is_hotkey_enabled(section, action) else ""


def snapshot_configuration() -> tuple[dict, set]:
    return (
        {s: {a: get_sequence(s, a) for a in actions} for s, actions in key_dict.items()},
        set(_disabled),
    )


def save_configuration(new_bindings: dict, disabled=()):
    """Validate and persist a draft before publishing it to live widgets."""
    global bindings, _disabled
    normalized = {}
    for section, actions in key_dict.items():
        normalized[section] = {}
        for action in actions:
            sequence = normalize_sequence(new_bindings[section][action])
            if sequence is None:
                raise ValueError(f"Invalid shortcut for {section}/{action}")
            normalized[section][action] = sequence
    disabled = {(s, a) for s, a in disabled if a in key_dict.get(s, {})}
    _db().save_key_configuration(normalized, sorted(f"{s}::{a}" for s, a in disabled))
    bindings, _disabled = normalized, disabled
    _reapply_all()
    for listener in tuple(_change_listeners):
        listener()


def load_keys():
    """Merge new defaults with saved keys instead of resetting customizations."""
    db = _db()
    stored = db.get_all_key_bindings()
    merged = {}
    for section, actions in key_dict.items():
        merged[section] = {}
        for action, default in actions.items():
            sequence = normalize_sequence(stored.get(section, {}).get(action, default))
            merged[section][action] = default if sequence is None else sequence
    saved_disabled = db.get_pref("disabled_hotkeys", [])
    if not isinstance(saved_disabled, list):
        saved_disabled = []
    disabled = {(s, a) for s, actions in key_dict.items() for a in actions
                if f"{s}::{a}" in saved_disabled}
    save_configuration(merged, disabled)


def keys_to_default():
    save_configuration(key_dict)


def set_sequence(section: str, action: str, sequence: str):
    _check_action(section, action)
    draft, disabled = snapshot_configuration()
    draft[section][action] = sequence
    save_configuration(draft, disabled)


def set_hotkey_enabled(section: str, action: str, enabled: bool):
    _check_action(section, action)
    draft, disabled = snapshot_configuration()
    if enabled:
        disabled.discard((section, action))
    else:
        disabled.add((section, action))
    save_configuration(draft, disabled)


def reset_hotkey(section: str, action: str):
    _check_action(section, action)
    draft, disabled = snapshot_configuration()
    draft[section][action] = key_dict[section][action]
    disabled.discard((section, action))
    save_configuration(draft, disabled)


def find_conflicts(draft: dict, disabled=()) -> list[tuple]:
    """Main-window bindings overlap both panes; separate panes may share keys."""
    active = [(s, a, normalize_sequence(seq)) for s, actions in draft.items()
              for a, seq in actions.items() if seq and (s, a) not in disabled]
    conflicts = []
    for index, (section, action, sequence) in enumerate(active):
        for other_section, other_action, other_sequence in active[index + 1:]:
            overlaps = section == other_section or "Main Window" in (section, other_section)
            if overlaps and sequence and sequence == other_sequence:
                conflicts.append(((section, action), (other_section, other_action), sequence))
    return conflicts


def _forget_target(key, target):
    targets = _bound_targets.get(key, [])
    targets[:] = [item for item in targets if item is not target]
    if not targets:
        _bound_targets.pop(key, None)


def bind_action(section: str, action: str, target):
    """Register a QAction/QShortcut once and unregister when Qt destroys it."""
    _check_action(section, action)
    if not isinstance(target, (QAction, QShortcut)):
        raise TypeError("A shortcut target must be a QAction or QShortcut")
    key = section, action
    targets = _bound_targets.setdefault(key, [])
    if not any(item is target for item in targets):
        targets.append(target)
        target.destroyed.connect(lambda _=None: _forget_target(key, target))
    _apply_sequence(target, get_active_sequence(section, action))
    return target


def make_shortcut(section: str, action: str, parent, callback: Callable,
                  context=Qt.ShortcutContext.WindowShortcut) -> QShortcut:
    shortcut = QShortcut(parent)
    shortcut.setContext(context)
    shortcut.activated.connect(callback)
    return bind_action(section, action, shortcut)


def _apply_sequence(target, sequence: str):
    keys = QKeySequence.fromString(sequence, QKeySequence.SequenceFormat.PortableText)
    if isinstance(target, QShortcut):
        target.setKey(keys)
    else:
        target.setShortcut(keys)


def _reapply_all():
    for (section, action), targets in tuple(_bound_targets.items()):
        sequence = get_active_sequence(section, action)
        for target in tuple(targets):
            _apply_sequence(target, sequence)


def add_change_listener(callback: Callable[[], None]):
    if callback not in _change_listeners:
        _change_listeners.append(callback)


def remove_change_listener(callback: Callable[[], None]):
    if callback in _change_listeners:
        _change_listeners.remove(callback)


def all_sections() -> list[str]:
    return list(key_dict)
