"""peewee model definitions for the app database. See
:mod:`app_db.base_database` for the shared ``Database`` object and the
write-serialization worker these models are used through (via
:mod:`app_db.database`'s ``AppDatabase`` - nothing outside this package
should query these models directly, to keep every write funneled through
the write queue).
"""

from peewee import CharField, CompositeKey, Model, TextField

from .base_database import database


class BaseModel(Model):
    class Meta:
        database = database


class Pref(BaseModel):
    """Arbitrary JSON-encoded preference values."""

    key = CharField(primary_key=True)
    value = TextField()


class UserFile(BaseModel):
    """Recent / favorite / pinned-library-folder paths."""

    path = CharField()
    category = CharField()  # "RECENT" | "FAVORITE" | "LIBRARY"
    date_added = CharField()

    class Meta:
        indexes = (
            (("path", "category"), True),  # unique together
        )


class KeyBinding(BaseModel):
    """akeyconfig hotkey table: one row per (section, action)."""

    section = CharField()
    action = CharField()
    sequence = CharField()

    class Meta:
        primary_key = CompositeKey("section", "action")


class WindowState(BaseModel):
    """Saved geometry/dock-layout blobs (hex-encoded) and misc UI state."""

    key = CharField(primary_key=True)
    value = TextField()


ALL_MODELS = [Pref, UserFile, KeyBinding, WindowState]


class FileCategory:
    RECENT = "RECENT"
    FAVORITE = "FAVORITE"
    LIBRARY = "LIBRARY"
