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
