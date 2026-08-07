from app import al, db


def _conn(tmp_path):
    return db.init_db(str(tmp_path / "roster.db"))


def test_add_and_list(tmp_path):
    conn = _conn(tmp_path)
    al.add_al_date(conn, "Alice", "2026-09-01", "trip")
    al.add_al_date(conn, "Alice", "2026-08-15")
    rows = al.list_al_dates(conn, "Alice")
    assert [r["date"] for r in rows] == ["2026-08-15", "2026-09-01"]
    assert rows[1]["note"] == "trip"


def test_add_conflict_updates_note(tmp_path):
    conn = _conn(tmp_path)
    al.add_al_date(conn, "Alice", "2026-09-01", "old")
    al.add_al_date(conn, "Alice", "2026-09-01", "new")
    rows = al.list_al_dates(conn, "Alice")
    assert len(rows) == 1
    assert rows[0]["note"] == "new"


def test_list_scoped_to_name(tmp_path):
    conn = _conn(tmp_path)
    al.add_al_date(conn, "Alice", "2026-09-01")
    al.add_al_date(conn, "Bob", "2026-09-02")
    assert len(al.list_al_dates(conn, "Alice")) == 1


def test_delete(tmp_path):
    conn = _conn(tmp_path)
    al.add_al_date(conn, "Alice", "2026-09-01")
    row_id = al.list_al_dates(conn, "Alice")[0]["id"]
    al.delete_al_date(conn, row_id)
    assert al.list_al_dates(conn, "Alice") == []
