"""App-data persistence layer.

Everything the app needs to remember between runs - preferences, recent /
favorite / library files, window geometry, and key bindings - lives in a
single SQLite database under the user's home directory
(``~/.photon-snapshot/photon_snapshot.db``, see
:func:`utilities.functions.get_database_path`). No JSON/pickle/cfg files are
used for persistence; this satisfies item 5 of the snapshot-rewrite task.

Backed by the ``peewee`` ORM (see :mod:`app_db.models` for the schema and
:mod:`app_db.base_database` for the shared ``Database`` object). Writes are
serialized onto a single background thread via ``base_database.write_queue``
so concurrent writers can't hit SQLite's "database is locked" error; reads
run on the calling thread, which peewee's per-thread connection handling
makes safe without any extra locking here.
"""

from .database import AppDatabase, db

__all__ = ["AppDatabase", "db"]
