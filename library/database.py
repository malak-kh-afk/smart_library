"""Persistence layer: a thin wrapper around sqlite3.
All data is stored in one local file, so it survives application restarts."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


class Database:
    def __init__(self, path="data/library.db"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        self._depth = 0

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def query_all(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    @contextmanager
    def transaction(self):
        """All-or-nothing block. Can be nested: only the outermost block commits,
        and any error rolls everything back (data stays consistent)."""
        self._depth += 1
        try:
            yield
            if self._depth == 1:
                self.conn.commit()
        except Exception:
            if self._depth == 1:
                self.conn.rollback()
            raise
        finally:
            self._depth -= 1

    def close(self):
        self.conn.close()
