"""
Database connection factory.
All other modules use the connection() context manager; nothing else opens
a sqlite3 connection directly.
"""

import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH


@contextmanager
def connection():
    """
    Yield a sqlite3.Connection with row_factory and foreign-key enforcement.
    Commits on clean exit, rolls back on any exception, always closes.
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
