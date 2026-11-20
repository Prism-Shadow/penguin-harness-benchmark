"""Read-only database observations must not retain a lock on the application."""
from contextlib import closing
import sqlite3


def table_names(path):
    # A Connection context manager commits/rolls back but does not close it.
    # A remaining WAL reader can block EF's next EnsureDeletedAsync startup.
    with closing(sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro', uri=True)) as connection:
        return {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
