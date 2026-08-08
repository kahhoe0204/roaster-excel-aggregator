import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spreadsheet_id TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    header_row INTEGER NOT NULL,
    date_col INTEGER NOT NULL,
    date_row_start INTEGER NOT NULL,
    date_row_end INTEGER NOT NULL,
    operation_hours TEXT,
    tab_pattern TEXT
);

CREATE TABLE IF NOT EXISTS known_tabs (
    doc_id INTEGER NOT NULL REFERENCES docs(id),
    gid TEXT NOT NULL,
    title TEXT,
    PRIMARY KEY (doc_id, gid)
);

CREATE TABLE IF NOT EXISTS code_hours (
    doc_id INTEGER NOT NULL REFERENCES docs(id),
    code TEXT NOT NULL,
    hours REAL NOT NULL,
    PRIMARY KEY (doc_id, code)
);

CREATE TABLE IF NOT EXISTS al_dates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    note TEXT,
    UNIQUE(name, date)
);
"""

class _RemoteCursor:
    """Wraps a libsql cursor so fetchone/fetchall return dict rows, matching
    sqlite3.Row's dict(row)/row["col"] access used throughout this codebase."""

    def __init__(self, cursor):
        self._cursor = cursor

    def _row(self, values):
        if values is None:
            return None
        cols = [d[0] for d in self._cursor.description]
        return dict(zip(cols, values))

    def fetchone(self):
        return self._row(self._cursor.fetchone())

    def fetchall(self):
        return [self._row(v) for v in self._cursor.fetchall()]


class _RemoteConn:
    """libsql (Turso) connection, used when TURSO_DATABASE_URL is set — e.g.
    on Vercel, where the filesystem can't hold a persistent SQLite file."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        return _RemoteCursor(self._conn.execute(sql, params))

    def executescript(self, script):
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                self._conn.execute(stmt)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_connection(db_path):
    turso_url = os.environ.get("TURSO_DATABASE_URL")
    if turso_url:
        import libsql

        return _RemoteConn(
            libsql.connect(database=turso_url, auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""))
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def _migrate_code_hours_to_per_doc(conn):
    """code_hours used to be one global code->hours table; it's now scoped
    per doc_id. Existing global entries are copied to every current doc as
    a starting point, rather than silently discarded."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(code_hours)").fetchall()]
    if "doc_id" in cols:
        return
    old_rows = [(r["code"], r["hours"]) for r in conn.execute("SELECT code, hours FROM code_hours").fetchall()]
    doc_ids = [r["id"] for r in conn.execute("SELECT id FROM docs").fetchall()]
    conn.execute("ALTER TABLE code_hours RENAME TO code_hours_old")
    conn.execute(
        """CREATE TABLE code_hours (
            doc_id INTEGER NOT NULL REFERENCES docs(id),
            code TEXT NOT NULL,
            hours REAL NOT NULL,
            PRIMARY KEY (doc_id, code)
        )"""
    )
    for code, hours in old_rows:
        for doc_id in doc_ids:
            conn.execute(
                "INSERT INTO code_hours (doc_id, code, hours) VALUES (?, ?, ?)",
                (doc_id, code, hours),
            )
    conn.execute("DROP TABLE code_hours_old")
    conn.commit()


def init_db(db_path):
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    for ddl in (
        "ALTER TABLE docs ADD COLUMN operation_hours TEXT",
        "ALTER TABLE docs ADD COLUMN tab_pattern TEXT",
    ):
        try:
            conn.execute(ddl)
            conn.commit()
        except Exception:
            pass  # column already exists on every init_db call after the first
    _migrate_code_hours_to_per_doc(conn)
    return conn
