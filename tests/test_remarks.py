from app import remarks, db


def _conn(tmp_path):
    return db.init_db(str(tmp_path / "roster.db"))


def test_set_and_get(tmp_path):
    conn = _conn(tmp_path)
    remarks.set_remark(conn, "Alice", "1-Aug", "bank in")
    remarks.set_remark(conn, "Alice", "2-Aug", "training")
    assert remarks.get_remarks(conn, "Alice") == {"1-Aug": "bank in", "2-Aug": "training"}


def test_set_conflict_updates_note(tmp_path):
    conn = _conn(tmp_path)
    remarks.set_remark(conn, "Alice", "1-Aug", "old")
    remarks.set_remark(conn, "Alice", "1-Aug", "new")
    assert remarks.get_remarks(conn, "Alice") == {"1-Aug": "new"}


def test_get_scoped_to_name(tmp_path):
    conn = _conn(tmp_path)
    remarks.set_remark(conn, "Alice", "1-Aug", "bank in")
    remarks.set_remark(conn, "Bob", "1-Aug", "training")
    assert remarks.get_remarks(conn, "Alice") == {"1-Aug": "bank in"}
