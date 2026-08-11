"""App-data persistence layer.

Everything the app needs to remember between runs - preferences, recent /
favorite / library files, window geometry, and key bindings - lives in a
single SQLite database under the user's home directory
(``~/.photon-snapshot/photon_snapshot.db``, see
:func:`utilities.functions.get_database_path`). No JSON/pickle/cfg files are
used for persistence; this satisfies item 5 of the snapshot-rewrite task.

Only the stdlib ``sqlite3`` module is used (no extra ORM dependency such as
peewee/SQLAlchemy), keeping the dependency footprint identical to what was
already declared in requirements.txt.
"""

from .database import AppDatabase, db

__all__ = ["AppDatabase", "db"]
