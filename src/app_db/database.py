"""peewee-backed application database.

Public API is unchanged from the previous raw-sqlite3 implementation (same
method names/signatures on `AppDatabase`/the module-level `db` singleton),
so nothing in :mod:`core.explorer`, :mod:`app_config.prefs`, or
:mod:`app_config.key_config` needed to change for this rewrite.

Every write goes through :data:`app_db.base_database.write_queue`, which
serializes it onto one background thread (see that module's docstring for
why); every read runs directly on the calling thread, which peewee makes
safe automatically.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from . import base_database
from .base_database import database, write_queue
from .models import ALL_MODELS, FileCategory, KeyBinding, Pref, UserFile, WindowState, UserPreset


class AppDatabase:
    def __init__(self):
        self._initialized = False

    # --------------------------------------------------------- lifecycle ----
    def initialize(self):
        if self._initialized:
            return
        base_database.configure_database()
        database.connect(reuse_if_open=True)
        database.create_tables(ALL_MODELS, safe=True)
        write_queue.start()
        self._initialized = True

    def close(self):
        write_queue.stop()
        if not database.is_closed():
            database.close()
        self._initialized = False

    # ---------------------------------------------------------------- prefs ----
    def get_pref(self, key: str, default: Any = None) -> Any:
        row = Pref.get_or_none(Pref.key == key)
        if row is None:
            return default
        try:
            return json.loads(row.value)
        except (TypeError, json.JSONDecodeError):
            return default

    def set_pref(self, key: str, value: Any):
        write_queue.run(self._set_pref_impl, key, value)

    @staticmethod
    def _set_pref_impl(key: str, value: Any):
        Pref.replace(key=key, value=json.dumps(value)).execute()

    def all_prefs(self) -> dict:
        result = {}
        for row in Pref.select():
            try:
                result[row.key] = json.loads(row.value)
            except (TypeError, json.JSONDecodeError):
                pass
        return result

    # ------------------------------------------------------------ user files ----
    def _get_files(self, category: str, limit: Optional[int] = None) -> list[str]:
        query = (
            UserFile.select(UserFile.path)
            .where(UserFile.category == category)
            .order_by(UserFile.date_added.desc())
        )
        if limit:
            query = query.limit(limit)
        return [row.path for row in query]

    @staticmethod
    def _upsert_file_impl(path: str, category: str):
        now = datetime.now().isoformat()
        UserFile.insert(path=path, category=category, date_added=now).on_conflict(
            conflict_target=[UserFile.path, UserFile.category],
            update={UserFile.date_added: now},
        ).execute()

    @staticmethod
    def _remove_file_impl(path: str, category: str):
        UserFile.delete().where((UserFile.path == path) & (UserFile.category == category)).execute()

    @staticmethod
    def _clear_category_impl(category: str):
        UserFile.delete().where(UserFile.category == category).execute()

    @staticmethod
    def _add_recent_file_impl(path: str, max_count: int):
        AppDatabase._upsert_file_impl(path, FileCategory.RECENT)
        keep_ids = [
            row.id
            for row in UserFile.select(UserFile.id)
            .where(UserFile.category == FileCategory.RECENT)
            .order_by(UserFile.date_added.desc())
            .limit(max_count)
        ]
        if keep_ids:
            UserFile.delete().where(
                (UserFile.category == FileCategory.RECENT) & (UserFile.id.not_in(keep_ids))
            ).execute()

    def add_recent_file(self, path: str, max_count: int = 20):
        write_queue.run(self._add_recent_file_impl, path, max_count)

    def get_recent_files(self, limit: Optional[int] = None) -> list[str]:
        return self._get_files(FileCategory.RECENT, limit)

    def remove_recent_file(self, path: str):
        write_queue.run(self._remove_file_impl, path, FileCategory.RECENT)

    def clear_recent_files(self):
        write_queue.run(self._clear_category_impl, FileCategory.RECENT)

    def add_favorite(self, path: str):
        write_queue.run(self._upsert_file_impl, path, FileCategory.FAVORITE)

    def get_favorites(self) -> list[str]:
        return self._get_files(FileCategory.FAVORITE)

    def remove_favorite(self, path: str):
        write_queue.run(self._remove_file_impl, path, FileCategory.FAVORITE)

    def is_favorite(self, path: str) -> bool:
        return UserFile.select().where(
            (UserFile.path == path) & (UserFile.category == FileCategory.FAVORITE)
        ).exists()

    def add_library_folder(self, path: str):
        write_queue.run(self._upsert_file_impl, path, FileCategory.LIBRARY)

    def get_library_folders(self) -> list[str]:
        return self._get_files(FileCategory.LIBRARY)

    def remove_library_folder(self, path: str):
        write_queue.run(self._remove_file_impl, path, FileCategory.LIBRARY)

    # ---------------------------------------------------------- key bindings ----
    def get_key_bindings(self, section: str) -> dict:
        return {
            row.action: row.sequence
            for row in KeyBinding.select().where(KeyBinding.section == section)
        }

    def get_all_key_bindings(self) -> dict:
        result: dict[str, dict[str, str]] = {}
        for row in KeyBinding.select():
            result.setdefault(row.section, {})[row.action] = row.sequence
        return result

    @staticmethod
    def _set_key_binding_impl(section: str, action: str, sequence: str):
        KeyBinding.insert(section=section, action=action, sequence=sequence).on_conflict(
            conflict_target=[KeyBinding.section, KeyBinding.action],
            update={KeyBinding.sequence: sequence},
        ).execute()

    def set_key_binding(self, section: str, action: str, sequence: str):
        write_queue.run(self._set_key_binding_impl, section, action, sequence)

    def clear_key_bindings(self):
        write_queue.run(lambda: KeyBinding.delete().execute())

    def save_key_configuration(self, bindings: dict, disabled: list[str]):
        """Commit a complete shortcut configuration in one transaction."""
        def save():
            with database.atomic():
                KeyBinding.delete().execute()
                rows = [
                    {"section": section, "action": action, "sequence": sequence}
                    for section, actions in bindings.items()
                    for action, sequence in actions.items()
                ]
                if rows:
                    KeyBinding.insert_many(rows).execute()
                self._set_pref_impl("disabled_hotkeys", disabled)

        write_queue.run(save)

    def has_key_bindings(self) -> bool:
        return KeyBinding.select().limit(1).exists()

    # ------------------------------------------------------------ window state ----
    @staticmethod
    def _save_window_state_impl(key: str, value: str):
        WindowState.replace(key=key, value=value).execute()

    def save_window_state(self, key: str, value: str):
        write_queue.run(self._save_window_state_impl, key, value)

    def load_window_state(self, key: str) -> Optional[str]:
        row = WindowState.get_or_none(WindowState.key == key)
        return row.value if row else None

    def list_presets(self, kind):
        return [row.name for row in UserPreset.select().where(UserPreset.kind == kind).order_by(UserPreset.name)]

    def get_preset(self, kind, name):
        row = UserPreset.get_or_none((UserPreset.kind == kind) & (UserPreset.name == name))
        return json.loads(row.payload) if row else None

    def save_preset(self, kind, name, payload):
        write_queue.run(lambda: UserPreset.insert(kind=kind, name=name, payload=json.dumps(payload)).on_conflict(
            conflict_target=[UserPreset.kind, UserPreset.name], update={UserPreset.payload: json.dumps(payload)}).execute())

    def delete_preset(self, kind, name):
        write_queue.run(lambda: UserPreset.delete().where((UserPreset.kind == kind) & (UserPreset.name == name)).execute())


# Process-wide singleton, mirroring playForm's module-level `prefs`/`media_db`
# pattern so callers can just `from app_db import db`.
db = AppDatabase()
