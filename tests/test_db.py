import sqlite3
from app import db

def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = db.init_db(db_path)
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"docs", "known_tabs", "code_hours"} <= tables

def test_get_connection_reopens_existing_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn2 = db.get_connection(db_path)
    assert isinstance(conn2, sqlite3.Connection)

def test_init_db_migrates_global_code_hours_to_per_doc(tmp_path):
    # Regression: code_hours used to be one global table; simulate a
    # pre-migration DB and confirm existing entries carry over to every doc
    # instead of being silently discarded.
    db_path = str(tmp_path / "old.db")
    raw = sqlite3.connect(db_path)
    raw.execute("""CREATE TABLE docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spreadsheet_id TEXT UNIQUE NOT NULL,
        label TEXT NOT NULL,
        header_row INTEGER NOT NULL,
        date_col INTEGER NOT NULL,
        date_row_start INTEGER NOT NULL,
        date_row_end INTEGER NOT NULL
    )""")
    raw.execute(
        "INSERT INTO docs (spreadsheet_id, label, header_row, date_col, date_row_start, date_row_end) "
        "VALUES ('SHEET1', 'Branch A', 0, 0, 1, 1)"
    )
    raw.execute(
        "INSERT INTO docs (spreadsheet_id, label, header_row, date_col, date_row_start, date_row_end) "
        "VALUES ('SHEET2', 'Branch B', 0, 0, 1, 1)"
    )
    raw.execute("CREATE TABLE code_hours (code TEXT PRIMARY KEY, hours REAL NOT NULL)")
    raw.execute("INSERT INTO code_hours (code, hours) VALUES ('F', 12.0)")
    raw.commit()
    raw.close()

    conn = db.init_db(db_path)
    doc_ids = {r["id"] for r in conn.execute("SELECT id FROM docs").fetchall()}
    rows = conn.execute("SELECT doc_id, code, hours FROM code_hours").fetchall()

    assert {r["doc_id"] for r in rows} == doc_ids
    assert all((r["code"], r["hours"]) == ("F", 12.0) for r in rows)

def test_init_db_migration_is_idempotent(tmp_path):
    db_path = str(tmp_path / "test.db")
    db.init_db(db_path)
    conn = db.init_db(db_path)  # second call should not error or duplicate
    assert conn.execute("SELECT * FROM code_hours").fetchall() == []
