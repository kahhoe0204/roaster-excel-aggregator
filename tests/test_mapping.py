from app import mapping
from app import db as db_mod

REAL_SAMPLE_GRID = [
    ["", "", "JOSEY", "TAN MIN", "NANTHINI"],
    ["1-Aug", "Saturday", "SJ", "", "P14 12.5"],
    ["2-Aug", "Sunday", "", "SJ", ""],
    ["3-Aug", "Monday", "", "", "SJ"],
    ["4-Aug", "Tuesday", "SJ(BANK)", "P14", "P14 12.5"],
]

def test_detect_date_range_finds_date_col_0():
    result = mapping.detect_date_range(REAL_SAMPLE_GRID, header_row=0)
    assert result == {"date_col": 0, "row_start": 1, "row_end": 4}

def test_detect_date_range_returns_none_when_no_pattern():
    grid = [["", "Alice", "Bob"], ["not-a-date", "x", "y"]]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result is None

def test_detect_date_range_stops_at_broken_sequence():
    grid = [
        ["", "Alice"],
        ["1-Aug", "9"],
        ["2-Aug", "8"],
        ["not-a-date", "7"],
        ["4-Aug", "6"],
    ]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result == {"date_col": 0, "row_start": 1, "row_end": 2}

def test_save_and_get_mapping(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
    doc = mapping.get_doc(conn, "SHEET1")
    assert doc["id"] == doc_id
    assert doc["label"] == "Branch A"
    assert doc["date_row_end"] == 31

def test_save_mapping_upserts_on_same_spreadsheet_id(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping.save_mapping(conn, "SHEET1", "Old Label", 0, 0, 1, 31)
    mapping.save_mapping(conn, "SHEET1", "New Label", 0, 0, 1, 30)
    docs = mapping.list_docs(conn)
    assert len(docs) == 1
    assert docs[0]["label"] == "New Label"

def test_delete_doc_removes_doc_and_known_tabs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
    mapping.mark_tab_known(conn, doc_id, "111", "August")

    mapping.delete_doc(conn, "SHEET1")

    assert mapping.get_doc(conn, "SHEET1") is None
    assert mapping.known_tab_gids(conn, doc_id) == set()


def test_delete_doc_missing_spreadsheet_id_is_noop(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping.delete_doc(conn, "NOPE")  # should not raise


def test_mark_and_list_known_tabs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
    mapping.mark_tab_known(conn, doc_id, "111", "August")
    mapping.mark_tab_known(conn, doc_id, "222", "September")
    mapping.mark_tab_known(conn, doc_id, "111", "August")  # idempotent

    gids = mapping.known_tab_gids(conn, doc_id)
    assert gids == {"111", "222"}

    tabs = {t["gid"]: t["title"] for t in mapping.known_tabs(conn, doc_id)}
    assert tabs == {"111": "August", "222": "September"}
