import os
from typing import List, Optional
from pathlib import Path
from PySide6.QtCore import QObject, Signal
from .utils import is_image_file


class FileExplorer(QObject):
    """Filesystem browsing model for the Explorer dock: current path,
    back/forward history, recent files, favorites and pinned "library"
    folders. Persistence moved from a ``~/.photon_snapshot/config.json``
    file to the SQLite app database (see :mod:`app_db`) - this is a plain
    filesystem browser, not a media catalog/indexer, so no scan/database
    implementation lives here (per the snapshot-rewrite scope: "library,
    file list, path, and search - no database implementations").
    """

    path_changed = Signal(str)
    selection_changed = Signal(str)
    recent_files_updated = Signal(list)
    library_updated = Signal(list)

    def __init__(self):
        super().__init__()
        self.current_path = str(Path.home())
        self.history: List[str] = []
        self.history_index = -1
        self.max_history = 100
        self.recent_files: List[str] = []
        self.max_recent_files = 20

        self._load_state()

    # -------------------------------------------------------------- nav ----
    def navigate_to(self, path: str):
        if os.path.exists(path) and os.path.isdir(path):
            if self.history_index < len(self.history) - 1:
                self.history = self.history[: self.history_index + 1]

            self.history.append(self.current_path)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            else:
                self.history_index += 1

            self.current_path = path
            self._save_last_path()
            self.path_changed.emit(self.current_path)

    def go_back(self) -> bool:
        if self.can_go_back():
            self.current_path = self.history[self.history_index]
            self.history_index -= 1
            self.path_changed.emit(self.current_path)
            return True
        return False

    def go_forward(self) -> bool:
        if self.can_go_forward():
            self.history_index += 1
            self.current_path = self.history[self.history_index]
            self.path_changed.emit(self.current_path)
            return True
        return False

    def can_go_back(self) -> bool:
        return self.history_index >= 0

    def can_go_forward(self) -> bool:
        return self.history_index < len(self.history) - 1

    def go_up(self) -> bool:
        parent = str(Path(self.current_path).parent)
        if parent != self.current_path:
            self.navigate_to(parent)
            return True
        return False

    def get_drives(self) -> List[str]:
        if os.name == "nt":
            return [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{letter}:\\")]
        return ["/"]

    # ------------------------------------------------------------ listing ----
    def get_all_files(self, path: str = None) -> List[tuple]:
        path = path or self.current_path
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                is_image = is_image_file(item) if not is_dir else False
                items.append((item, is_dir, is_image, item_path))
            items.sort(key=lambda x: (not x[1], x[0].lower()))
            return items
        except (PermissionError, OSError):
            return []

    def search(self, query: str, path: str = None, recursive: bool = False) -> List[tuple]:
        """Filename search. Non-recursive by default (searches the current
        folder only, matching the "Search current folder" scope used
        elsewhere in the app); pass ``recursive=True`` to walk subfolders
        too."""
        path = path or self.current_path
        query_lower = query.lower()
        results: List[tuple] = []
        try:
            if recursive:
                for root, dirs, files in os.walk(path):
                    for name in dirs + files:
                        if query_lower in name.lower():
                            full_path = os.path.join(root, name)
                            is_dir = os.path.isdir(full_path)
                            is_image = is_image_file(name) if not is_dir else False
                            results.append((name, is_dir, is_image, full_path))
            else:
                for name, is_dir, is_image, full_path in self.get_all_files(path):
                    if query_lower in name.lower():
                        results.append((name, is_dir, is_image, full_path))
        except (PermissionError, OSError):
            pass
        results.sort(key=lambda x: (not x[1], x[0].lower()))
        return results

    def get_full_path(self, filename: str) -> str:
        return os.path.join(self.current_path, filename)

    # ------------------------------------------------------------ recents ----
    def add_recent_file(self, file_path: str):
        if not os.path.exists(file_path) or not is_image_file(file_path):
            return
        self._db().add_recent_file(file_path, self.max_recent_files)
        self.recent_files = self.get_recent_files()
        self.recent_files_updated.emit(self.recent_files)

    def get_recent_files(self) -> List[str]:
        files = [f for f in self._db().get_recent_files(self.max_recent_files) if os.path.exists(f)]
        return files

    def remove_recent_file(self, file_path: str):
        self._db().remove_recent_file(file_path)
        self.recent_files = self.get_recent_files()
        self.recent_files_updated.emit(self.recent_files)

    def clear_recent_files(self):
        self._db().clear_recent_files()
        self.recent_files = []
        self.recent_files_updated.emit([])

    # ------------------------------------------------------------ library ----
    def get_library_folders(self) -> List[str]:
        return [f for f in self._db().get_library_folders() if os.path.isdir(f)]

    def add_library_folder(self, path: str):
        if os.path.isdir(path):
            self._db().add_library_folder(path)
            self.library_updated.emit(self.get_library_folders())

    def remove_library_folder(self, path: str):
        self._db().remove_library_folder(path)
        self.library_updated.emit(self.get_library_folders())

    # ----------------------------------------------------------- favorites ----
    def add_favorite(self, path: str):
        self._db().add_favorite(path)

    def get_favorites(self) -> List[str]:
        return [f for f in self._db().get_favorites() if os.path.exists(f)]

    def remove_favorite(self, path: str):
        self._db().remove_favorite(path)

    def is_favorite(self, path: str) -> bool:
        return self._db().is_favorite(path)

    # ------------------------------------------------------------- state ----
    def _db(self):
        from app_db import db

        return db

    def _save_last_path(self):
        from app_config.prefs import prefs

        prefs["last_explorer_path"] = self.current_path

    def _load_state(self):
        from app_config.prefs import prefs

        path = prefs.get("last_explorer_path", "")
        if path and os.path.exists(path) and os.path.isdir(path):
            self.current_path = path
        self.recent_files = self.get_recent_files()
