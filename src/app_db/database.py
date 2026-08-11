"""SQLite-backed application database.

Replaces the old ``~/.photon_snapshot/config.json`` explorer config with a
single ``photon_snapshot.db`` file holding:

* ``prefs``        - arbitrary JSON-encoded preference values (key/value)
* ``user_files``    - recent / favorite / library-folder paths
* ``key_bindings``  - the akeyconfig hotkey table (section, action, sequence)
* ``window_state``  - saved geometry/dock layout blobs, hex-encoded
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from utilities.functions import get_database_path


SCHEMA = """
CREATE TABLE IF NOT EXISTS prefs (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    category TEXT CHECK(category IN ('RECENT', 'FAVORITE', 'LIBRARY')) NOT NULL,
    date_added TEXT NOT NULL,
    UNIQUE(path, category)
);
CREATE INDEX IF NOT EXISTS idx_user_files_category ON user_files(category);

CREATE TABLE IF NOT EXISTS key_bindings (
    section TEXT NOT NULL,
    action TEXT NOT NULL,
    sequence TEXT NOT NULL,
    PRIMARY KEY (section, action)
);

CREATE TABLE IF NOT EXISTS window_state (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
);
"""


@dataclass
class FileCategory:
    RECENT = "RECENT"
    FAVORITE = "FAVORITE"
    LIBRARY = "LIBRARY"


class AppDatabase:
    """Thread-safe-enough wrapper: one sqlite3 connection per thread
    (Qt apps mostly touch this from the GUI thread, but background image
    loading workers may not)."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or get_database_path()
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._initialized = False

    def _connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def initialize(self):
        with self._init_lock:
            if self._initialized:
                return
            conn = self._connection()
            conn.executescript(SCHEMA)
            conn.commit()
            self._initialized = True

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ---------------------------------------------------------- prefs ----
    def get_pref(self, key: str, default: Any = None) -> Any:
        cur = self._connection().execute("SELECT value FROM prefs WHERE key = ?", (key,))
        row = cur.fetchone()
        if row is None:
            return default
        try:
            return json.loads(row[0])
        except (TypeError, json.JSONDecodeError):
            return default

    def set_pref(self, key: str, value: Any):
        conn = self._connection()
        conn.execute(
            "INSERT INTO prefs (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )
        conn.commit()

    def all_prefs(self) -> dict:
        cur = self._connection().execute("SELECT key, value FROM prefs")
        result = {}
        for key, value in cur.fetchall():
            try:
                result[key] = json.loads(value)
            except (TypeError, json.JSONDecodeError):
                pass
        return result

    # ------------------------------------------------------ user files ----
    def _add_file(self, path: str, category: str):
        conn = self._connection()
        conn.execute(
            "INSERT INTO user_files (path, category, date_added) VALUES (?, ?, ?) "
            "ON CONFLICT(path, category) DO UPDATE SET date_added = excluded.date_added",
            (path, category, datetime.now().isoformat()),
        )
        conn.commit()

    def _get_files(self, category: str, limit: Optional[int] = None) -> list[str]:
        sql = "SELECT path FROM user_files WHERE category = ? ORDER BY date_added DESC"
        params: tuple = (category,)
        if limit:
            sql += " LIMIT ?"
            params = (category, limit)
        cur = self._connection().execute(sql, params)
        return [row[0] for row in cur.fetchall()]

    def _remove_file(self, path: str, category: str):
        conn = self._connection()
        conn.execute("DELETE FROM user_files WHERE path = ? AND category = ?", (path, category))
        conn.commit()

    def _clear_category(self, category: str):
        conn = self._connection()
        conn.execute("DELETE FROM user_files WHERE category = ?", (category,))
        conn.commit()

    def add_recent_file(self, path: str, max_count: int = 20):
        self._add_file(path, FileCategory.RECENT)
        conn = self._connection()
        conn.execute(
            "DELETE FROM user_files WHERE category = ? AND id NOT IN "
            "(SELECT id FROM user_files WHERE category = ? ORDER BY date_added DESC LIMIT ?)",
            (FileCategory.RECENT, FileCategory.RECENT, max_count),
        )
        conn.commit()

    def get_recent_files(self, limit: Optional[int] = None) -> list[str]:
        return self._get_files(FileCategory.RECENT, limit)

    def remove_recent_file(self, path: str):
        self._remove_file(path, FileCategory.RECENT)

    def clear_recent_files(self):
        self._clear_category(FileCategory.RECENT)

    def add_favorite(self, path: str):
        self._add_file(path, FileCategory.FAVORITE)

    def get_favorites(self) -> list[str]:
        return self._get_files(FileCategory.FAVORITE)

    def remove_favorite(self, path: str):
        self._remove_file(path, FileCategory.FAVORITE)

    def is_favorite(self, path: str) -> bool:
        cur = self._connection().execute(
            "SELECT 1 FROM user_files WHERE path = ? AND category = ?", (path, FileCategory.FAVORITE)
        )
        return cur.fetchone() is not None

    def add_library_folder(self, path: str):
        self._add_file(path, FileCategory.LIBRARY)

    def get_library_folders(self) -> list[str]:
        return self._get_files(FileCategory.LIBRARY)

    def remove_library_folder(self, path: str):
        self._remove_file(path, FileCategory.LIBRARY)

    # ---------------------------------------------------- key bindings ----
    def get_key_bindings(self, section: str) -> dict:
        cur = self._connection().execute(
            "SELECT action, sequence FROM key_bindings WHERE section = ?", (section,)
        )
        return {action: sequence for action, sequence in cur.fetchall()}

    def get_all_key_bindings(self) -> dict:
        cur = self._connection().execute("SELECT section, action, sequence FROM key_bindings")
        result: dict[str, dict[str, str]] = {}
        for section, action, sequence in cur.fetchall():
            result.setdefault(section, {})[action] = sequence
        return result

    def set_key_binding(self, section: str, action: str, sequence: str):
        conn = self._connection()
        conn.execute(
            "INSERT INTO key_bindings (section, action, sequence) VALUES (?, ?, ?) "
            "ON CONFLICT(section, action) DO UPDATE SET sequence = excluded.sequence",
            (section, action, sequence),
        )
        conn.commit()

    def clear_key_bindings(self):
        conn = self._connection()
        conn.execute("DELETE FROM key_bindings")
        conn.commit()

    def has_key_bindings(self) -> bool:
        cur = self._connection().execute("SELECT 1 FROM key_bindings LIMIT 1")
        return cur.fetchone() is not None

    # ----------------------------------------------------- window state ----
    def save_window_state(self, key: str, value: str):
        conn = self._connection()
        conn.execute(
            "INSERT INTO window_state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()

    def load_window_state(self, key: str) -> Optional[str]:
        cur = self._connection().execute("SELECT value FROM window_state WHERE key = ?", (key,))
        row = cur.fetchone()
        return row[0] if row else None


# Process-wide singleton, mirroring playForm's module-level `prefs`/`media_db`
# pattern so callers can just `from app_db import db`.
db = AppDatabase()
