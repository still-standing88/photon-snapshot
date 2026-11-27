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
        from app_config.prefs import prefs
        self.sort_mode = prefs.get("explorer_sort_mode", "name_asc")
        self.filter_mode = prefs.get("explorer_filter_mode", "all")
        self.filter_extension = prefs.get("explorer_filter_format", "")
        # Standard history model: history holds every visited path
        # (including the current one) and history_index points at the
        # current entry. The previous scheme pointed one entry behind,
        # which made Forward a dead click after going back twice.
        self.history = [self.current_path]
        self.history_index = 0

    # -------------------------------------------------------------- nav ----
    def navigate_to(self, path: str):
        path = "drives" if path.casefold() == "drives" else os.path.abspath(path)
        if path == "drives" or os.path.isdir(path):
            if path == self.current_path:
                return True
            # Navigating after going back discards the forward entries.
            if self.history_index < len(self.history) - 1:
                del self.history[self.history_index + 1:]
            self.history.append(path)
            if len(self.history) > self.max_history:
                del self.history[0:len(self.history) - self.max_history]
            self.history_index = len(self.history) - 1
            self.current_path = path
            self._save_last_path()
            self.path_changed.emit(self.current_path)
            return True
        return False

    def go_back(self) -> bool:
        if self.can_go_back():
            self.history_index -= 1
            self.current_path = self.history[self.history_index]
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
        return self.history_index > 0

    def can_go_forward(self) -> bool:
        return self.history_index < len(self.history) - 1

    def go_up(self) -> bool:
        if self.current_path == "drives":
            return False
        parent = str(Path(self.current_path).parent)
        if parent != self.current_path:
            self.navigate_to(parent)
            return True
        if os.name == "nt":
            return self.navigate_to("drives")
        return False

    def get_drives(self) -> List[str]:
        if os.name == "nt":
            return [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{letter}:\\")]
        return ["/"]

    # ------------------------------------------------------------ listing ----
    def get_all_files(self, path: str = None) -> List[tuple]:
        path = path or self.current_path
        if path == "drives":
            return [(drive, True, False, drive) for drive in self.get_drives()]
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                is_image = is_image_file(item) if not is_dir else False
                items.append((item, is_dir, is_image, item_path))
            return self.filter_entries(items)
        except (PermissionError, OSError):
            return []

    def filter_entries(self, entries):
        entries = [entry for entry in entries if entry[1] or self.filter_mode == "all"
                   or (self.filter_mode == "images" and entry[2])
                   or (self.filter_mode == "custom" and
                       os.path.splitext(entry[3])[1].lstrip('.').casefold() == self.filter_extension)]
        def modified(entry):
            try:
                return os.path.getmtime(entry[3])
            except OSError:
                return 0
        key = modified if self.sort_mode.startswith("date_") else lambda entry: entry[0].casefold()
        reverse = self.sort_mode in ("name_desc", "date_newest")
        folders = sorted((entry for entry in entries if entry[1]), key=key, reverse=reverse)
        files = sorted((entry for entry in entries if not entry[1]), key=key, reverse=reverse)
        return folders + files

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

    def get_recent_files(self, limit: int = None) -> List[str]:
        max_count = limit or self.max_recent_files
        # Over-fetch from the DB, then drop entries whose files no longer
        # exist and trim - otherwise deleted files permanently shrink the
        # list below max even though older valid entries are still stored.
        raw = self._db().get_recent_files(max_count * 3)
        files = [f for f in raw if os.path.exists(f)]
        return files[:max_count]

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
        if path and (path == "drives" or os.path.isdir(path)):
            self.current_path = path
        self.recent_files = self.get_recent_files()
