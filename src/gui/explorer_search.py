"""Cancellable filesystem search used by the Explorer's history field."""
import os
from PySide6.QtCore import QThread, Signal
from core.utils import is_image_file


class SearchWorker(QThread):
    results_ready = Signal(str, str, list)
    error = Signal(str, str)

    def start_search(self, root, query):
        self.cancel()
        self.wait()
        self._root, self._query = root, query
        self.start()

    def cancel(self):
        if self.isRunning():
            self.requestInterruption()

    def shutdown(self):
        self.cancel()
        self.wait()

    def run(self):
        root, query = self._root, self._query
        matches = []
        try:
            for directory, _, filenames in os.walk(root):
                if self.isInterruptionRequested():
                    return
                for name in filenames:
                    if self.isInterruptionRequested():
                        return
                    if query.casefold() in name.casefold() and is_image_file(name):
                        path = os.path.join(directory, name)
                        matches.append((os.path.relpath(path, root), False, True, path))
        except OSError as exc:
            if not self.isInterruptionRequested():
                self.error.emit(root, str(exc))
            return
        if not self.isInterruptionRequested():
            matches.sort(key=lambda entry: entry[0].casefold())
            self.results_ready.emit(root, query, matches)
