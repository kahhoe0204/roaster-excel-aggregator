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

def test_detect_date_range_skips_rows_before_the_dates_start():
    # Regression: some sheets have a blank/instructions row (or several)
    # between the staff-name header and where the actual dates begin.
    grid = [
        ["", "Alice"],
        ["INSTRUCTIONS", ""],
        ["", ""],
        ["1-Aug", "9"],
        ["2-Aug", "8"],
    ]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result == {"date_col": 0, "row_start": 3, "row_end": 4}

def test_detect_date_range_accepts_mid_month_start():
    # Regression: a payroll period starting on the 20th (not the 1st) was
    # never detected because the old code required the run to start at day 1.
    grid = [
        ["", "Alice"],
        ["20-Jul", "9"],
        ["21-Jul", "8"],
        ["22-Jul", "7"],
    ]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result == {"date_col": 0, "row_start": 1, "row_end": 3}

def test_detect_date_range_accepts_month_end_wraparound():
    grid = [
        ["", "Alice"],
        ["30-Jul", "9"],
        ["31-Jul", "8"],
        ["1-Aug", "7"],
    ]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result == {"date_col": 0, "row_start": 1, "row_end": 3}

def test_detect_date_range_rejects_same_month_day_reset():
    # "31-Jul" then "1-Jul" (same month, day resets) is not a real rollover —
    # unlike "31-Jul" then "1-Aug". Must not be treated as a continuing run.
    grid = [
        ["", "Alice"],
        ["31-Jul", "9"],
        ["1-Jul", "8"],
        ["2-Jul", "7"],
    ]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result == {"date_col": 0, "row_start": 2, "row_end": 3}

def test_detect_date_range_rejects_bogus_month_name():
    grid = [["", "Alice"], ["1-Xyz", "9"], ["2-Xyz", "8"]]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result is None

def test_detect_date_range_gives_up_beyond_search_window():
    grid = [["", "Alice"]] + [["", ""]] * 10 + [["1-Aug", "9"], ["2-Aug", "8"]]
    result = mapping.detect_date_range(grid, header_row=0)
    assert result is None

def test_save_and_get_mapping(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    doc = mapping.get_doc(conn, "SHEET1")
    assert doc["id"] == doc_id
    assert doc["label"] == "Branch A"

def test_save_mapping_upserts_on_same_spreadsheet_id(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping.save_mapping(conn, "SHEET1", "Old Label")
    mapping.save_mapping(conn, "SHEET1", "New Label")
    docs = mapping.list_docs(conn)
    assert len(docs) == 1
    assert docs[0]["label"] == "New Label"

def test_delete_doc_removes_doc_and_known_tabs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    mapping.mark_tab_known(conn, doc_id, "111", "August")

    mapping.delete_doc(conn, "SHEET1")

    assert mapping.get_doc(conn, "SHEET1") is None
    assert mapping.known_tab_gids(conn, doc_id) == set()


def test_delete_doc_missing_spreadsheet_id_is_noop(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping.delete_doc(conn, "NOPE")  # should not raise


def test_set_operation_hours(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping.save_mapping(conn, "SHEET1", "Branch A")
    assert mapping.get_doc(conn, "SHEET1")["operation_hours"] is None

    mapping.set_operation_hours(conn, "SHEET1", "10:00 AM - 10:00 PM")

    assert mapping.get_doc(conn, "SHEET1")["operation_hours"] == "10:00 AM - 10:00 PM"


def test_known_tab_gids_includes_pending_and_configured(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    mapping.mark_tab_known(conn, doc_id, "111", "August")
    mapping.mark_tab_known(conn, doc_id, "222", "September")
    mapping.mark_tab_known(conn, doc_id, "111", "August")  # idempotent

    assert mapping.known_tab_gids(conn, doc_id) == {"111", "222"}


def test_known_tabs_excludes_unconfigured_pending_tabs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    mapping.mark_tab_known(conn, doc_id, "111", "August")
    mapping.mark_tab_known(conn, doc_id, "222", "September")
    mapping.configure_tab(conn, doc_id, "111", header_row=0, date_col=0, row_start=1, row_end=31)

    tabs = {t["gid"]: t["title"] for t in mapping.known_tabs(conn, doc_id)}
    assert tabs == {"111": "August"}  # "222" still pending, not returned


def test_default_header_row_uses_a_sibling_configured_tab(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    mapping.mark_tab_known(conn, doc_id, "111", "July")
    mapping.mark_tab_known(conn, doc_id, "222", "August")
    mapping.configure_tab(conn, doc_id, "111", header_row=8, date_col=1, row_start=9, row_end=40)

    assert mapping.default_header_row(conn, doc_id) == 8


def test_default_header_row_none_when_doc_has_no_configured_tabs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    mapping.mark_tab_known(conn, doc_id, "111", "July")

    assert mapping.default_header_row(conn, doc_id) is None


def test_all_known_tabs_includes_pending_and_configured(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping.save_mapping(conn, "SHEET1", "Branch A")
    mapping.mark_tab_known(conn, doc_id, "111", "JUL 26 PH")
    mapping.mark_tab_known(conn, doc_id, "222", "AUG 26 PH")
    mapping.configure_tab(conn, doc_id, "111", header_row=0, date_col=0, row_start=1, row_end=31)

    tabs = {t["gid"]: t["title"] for t in mapping.all_known_tabs(conn, doc_id)}
    assert tabs == {"111": "JUL 26 PH", "222": "AUG 26 PH"}


def test_pending_tabs_lists_unconfigured_tabs_across_docs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_a = mapping.save_mapping(conn, "SHEET1", "Branch A")
    doc_b = mapping.save_mapping(conn, "SHEET2", "Branch B")
    mapping.mark_tab_known(conn, doc_a, "111", "August")
    mapping.mark_tab_known(conn, doc_b, "222", "September")
    mapping.configure_tab(conn, doc_a, "111", header_row=0, date_col=0, row_start=1, row_end=31)

    pending = mapping.pending_tabs(conn)
    assert pending == [
        {"doc_id": doc_b, "gid": "222", "title": "September", "spreadsheet_id": "SHEET2", "label": "Branch B"},
    ]
