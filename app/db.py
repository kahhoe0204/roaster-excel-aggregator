import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spreadsheet_id TEXT UNIQUE NOT NULL,
    label TEXT NOT NULL,
    header_row INTEGER NOT NULL,
    date_col INTEGER NOT NULL,
    date_row_start INTEGER NOT NULL,
    date_row_end INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS known_tabs (
    doc_id INTEGER NOT NULL REFERENCES docs(id),
    gid TEXT NOT NULL,
    title TEXT,
    PRIMARY KEY (doc_id, gid)
);

CREATE TABLE IF NOT EXISTS code_hours (
    code TEXT PRIMARY KEY,
    hours REAL NOT NULL
);
"""

def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(db_path):
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
