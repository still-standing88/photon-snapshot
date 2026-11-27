"""The shared peewee ``Database`` object plus the write-serialization
worker that gives the app_db layer its multithreading story.

Two separate concerns, both handled here:

1. **Reads are thread-safe for free.** Peewee's ``Database`` keeps its
   connection in thread-local storage - the first query issued from any
   given thread transparently opens *that thread's own* real sqlite3
   connection against the same database file, so calling a model's
   ``.select()`` directly from a background thread (e.g. a future
   thumbnail-loading worker) just works without any extra plumbing here.

2. **Writes are serialized through one dedicated thread.** SQLite only
   ever allows one writer at a time even in WAL mode - if two threads both
   try to write concurrently, one of them gets a transient "database is
   locked" error. Rather than making every call site retry/handle that,
   every write in :mod:`app_db.database` is routed through
   :class:`WriteQueueWorker`, which owns a single background thread and
   runs writes one at a time. Callers still get synchronous,
   read-your-own-write consistency (``run()`` blocks until the write
   completes) - the app's existing "write, then immediately re-read the
   same row" call sites (e.g. ``core.explorer.FileExplorer.add_recent_file``
   re-reading the list right after adding to it) keep working correctly,
   while the actual disk I/O and lock contention are still fully isolated
   from whichever thread called in.

Adapted from playForm's ``app_db/base_database.py`` (which spins up a
second, independent ``SqliteDatabase`` object for its worker thread); this
version instead relies on peewee's built-in per-thread connection handling
against the *same* ``Database`` object, which is the pattern peewee's own
documentation recommends for multithreaded use.
"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Any, Callable

from peewee import SqliteDatabase

from utilities.functions import get_database_path

logger = logging.getLogger(__name__)

# Deferred initialization (peewee idiom: bind the real path later via
# .init()) since get_database_path() touches the filesystem and we don't
# want that as an import-time side effect.
database = SqliteDatabase(None)


def configure_database(db_path: str | None = None) -> None:
    """Binds `database` to the on-disk file, creating its parent directory
    if needed. Safe to call more than once (peewee closes any existing
    connections first)."""
    path = db_path or get_database_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    database.init(
        path,
        pragmas={
            "journal_mode": "wal",   # readers don't block the writer, and vice versa
            "cache_size": -4096,     # ~4MB page cache, per connection
            "foreign_keys": 1,
            "synchronous": 1,        # NORMAL - safe under WAL, faster than FULL
        },
    )


class WriteQueueWorker:
    """Owns one background thread that executes queued write callables
    one at a time against the shared `database`."""

    def __init__(self):
        self._queue: "queue.Queue[tuple | None]" = queue.Queue()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="AppDatabaseWriter", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            while True:
                item = self._queue.get()
                if item is None:  # shutdown sentinel
                    self._queue.task_done()
                    break
                func, args, kwargs, result_box, done_event = item
                try:
                    result_box["value"] = func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - re-raised by run()
                    result_box["error"] = exc
                    logger.exception("AppDatabase write failed: %s", func)
                finally:
                    done_event.set()
                    self._queue.task_done()
        finally:
            # Peewee connections are thread-local; the UI thread's close()
            # cannot release the writer's connection on Windows.
            if not database.is_closed():
                database.close()

    def run(self, func: Callable, *args, **kwargs) -> Any:
        """Execute `func` on the writer thread and block the calling
        thread until it finishes, returning its result (or re-raising
        whatever it raised). Safe to call from any thread."""
        if self._thread is None:
            self.start()
        result_box: dict[str, Any] = {}
        done_event = threading.Event()
        self._queue.put((func, args, kwargs, result_box, done_event))
        done_event.wait()
        if "error" in result_box:
            raise result_box["error"]
        return result_box.get("value")

    def run_async(self, func: Callable, *args, **kwargs) -> None:
        """Fire-and-forget variant for writes nothing needs to wait on
        (e.g. periodic window-state autosave)."""
        if self._thread is None:
            self.start()
        self._queue.put((func, args, kwargs, {}, threading.Event()))

    def stop(self, timeout: float = 2.0) -> None:
        if self._thread is None:
            return
        self._queue.put(None)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise RuntimeError("Database writer did not finish shutting down")
        self._thread = None


write_queue = WriteQueueWorker()
