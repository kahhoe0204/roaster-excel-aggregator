import requests

from app import aggregate, db as db_mod
from app import mapping as mapping_mod


def test_resolve_cell_numeric():
    assert aggregate.resolve_cell("9.5", {}) == (9.5, None)
    assert aggregate.resolve_cell("12", {}) == (12.0, None)


def test_resolve_cell_blank_is_no_hours():
    assert aggregate.resolve_cell("", {}) == (None, None)
    assert aggregate.resolve_cell("   ", {}) == (None, None)


def test_resolve_cell_mapped_code():
    assert aggregate.resolve_cell("SJ", {"SJ": 12.0}) == (12.0, None)
    assert aggregate.resolve_cell("FULL", {"FULL": 9.0}) == (9.0, None)


def test_resolve_cell_code_with_explicit_number_wins():
    assert aggregate.resolve_cell("P14 12.5", {"P14": 12.0}) == (12.5, None)


def test_resolve_cell_code_with_suffix():
    assert aggregate.resolve_cell("SJ(BANK)", {"SJ": 12.0}) == (12.0, None)


def test_resolve_cell_unmapped_code_is_flagged_not_guessed():
    assert aggregate.resolve_cell("SJ", {}) == (None, "SJ")
    assert aggregate.resolve_cell("XYZ", {"SJ": 12.0}) == (None, "XYZ")


def test_resolve_cell_leave_shortforms_are_ignored():
    for code in ("AL", "RL", "MC", "PH", "Leave"):
        assert aggregate.resolve_cell(code, {}) == (None, None)
        assert aggregate.resolve_cell(code, {code.upper(): 8.0}) == (None, None)


def test_resolve_cell_digit_bearing_unmapped_code():
    # Regression: "P14" unmapped should be flagged, not guessed as 14 hours
    assert aggregate.resolve_cell("P14", {}) == (None, "P14")


def test_resolve_cell_digit_bearing_mapped_code():
    # Regression: "P14" mapped should use lookup value, not embedded digit
    assert aggregate.resolve_cell("P14", {"P14": 12.0}) == (12.0, None)


def test_code_hours_roundtrip(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    assert aggregate.get_code_hours(conn) == {}
    aggregate.set_code_hours(conn, "SJ", 12.0)
    aggregate.set_code_hours(conn, "P14", 12.0)
    aggregate.set_code_hours(conn, "SJ", 8.0)  # overwrite
    assert aggregate.get_code_hours(conn) == {"SJ": 8.0, "P14": 12.0}


def test_codes_used_by_doc_collects_every_code_token(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 2)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")
    doc = mapping_mod.get_doc(conn, "SHEET1")

    grid = [["", "Alice"], ["1-Aug", "SJ"], ["2-Aug", "12"]]
    codes = aggregate.codes_used_by_doc(conn, doc, fetch_csv=lambda sid, gid, timeout=15: grid)

    assert codes == {"SJ"}


def test_remove_codes_unique_to_doc_keeps_codes_used_elsewhere(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_a = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    doc_b = mapping_mod.save_mapping(conn, "SHEET2", "Branch B", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_a, "111", "August")
    mapping_mod.mark_tab_known(conn, doc_b, "222", "August")
    aggregate.set_code_hours(conn, "SJ", 12.0)
    aggregate.set_code_hours(conn, "PMT", 12.0)

    grids = {
        "SHEET1": [["", "Alice"], ["1-Aug", "SJ"]],
        "SHEET2": [["", "Bob"], ["1-Aug", "SJ"], ["2-Aug", "PMT"]],
    }
    aggregate.remove_codes_unique_to_doc(
        conn, "SHEET1", fetch_csv=lambda sid, gid, timeout=15: grids[sid]
    )

    remaining = aggregate.get_code_hours(conn)
    assert remaining == {"SJ": 12.0, "PMT": 12.0}  # both still used by SHEET2


def test_remove_codes_unique_to_doc_drops_codes_used_nowhere_else(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_a = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    doc_b = mapping_mod.save_mapping(conn, "SHEET2", "Branch B", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_a, "111", "August")
    mapping_mod.mark_tab_known(conn, doc_b, "222", "August")
    aggregate.set_code_hours(conn, "PMT", 12.0)
    aggregate.set_code_hours(conn, "SJ", 12.0)

    grids = {
        "SHEET1": [["", "Alice"], ["1-Aug", "PMT"]],
        "SHEET2": [["", "Bob"], ["1-Aug", "SJ"]],
    }
    aggregate.remove_codes_unique_to_doc(
        conn, "SHEET1", fetch_csv=lambda sid, gid, timeout=15: grids[sid]
    )

    remaining = aggregate.get_code_hours(conn)
    assert remaining == {"SJ": 12.0}  # PMT was only used by SHEET1, dropped


def test_generate_report_matches_name_across_docs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")
    aggregate.set_code_hours(conn, "SJ", 12.0)

    grid = [
        ["", "", "Alice", "Bob"],
        ["1-Aug", "Friday", "9.5", "SJ"],
        ["2-Aug", "Saturday", "AL", ""],
    ]
    def fake_fetch_csv(spreadsheet_id, gid, timeout=15):
        assert spreadsheet_id == "SHEET1"
        assert gid == "111"
        return grid

    rows, unmapped = aggregate.generate_report(conn, "Alice", fetch_csv=fake_fetch_csv)

    assert rows == [
        {"name": "Alice", "date": "1-Aug", "hours": 9.5, "source": "Branch A / August", "operation_hours": None},
    ]
    assert unmapped == []

def test_generate_report_flags_unmapped_codes(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")

    grid = [["", "Alice"], ["1-Aug", "XYZ"]]
    rows, unmapped = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )
    assert rows == []
    assert unmapped == ["XYZ"]

def test_generate_report_skips_docs_without_matching_name(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")

    grid = [["", "Bob"], ["1-Aug", "9"]]
    rows, unmapped = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )
    assert rows == []
    assert unmapped == []


def test_generate_report_uses_floating_column_code_as_source(tmp_path):
    # Regression: a relief pharmacist's own column holds her hours (a bare
    # number), but which branch she actually covered that day is recorded
    # as a code in the "[Pharmacist Name]" floating slot next to it — that
    # code should win over this doc's own branch label.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 3)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")

    grid = [
        ["", "MEGAN", "TAN MIN (PRP)", "[Pharmacist Name]"],
        ["1-Aug", "", "12", "P14"],
        ["2-Aug", "", "", ""],
        ["3-Aug", "", "12", ""],
    ]
    rows, unmapped = aggregate.generate_report(
        conn, "Tan Min", fetch_csv=lambda sid, gid, timeout=15: grid
    )

    assert rows == [
        {"name": "Tan Min", "date": "1-Aug", "hours": 12.0, "source": "P14 / August", "operation_hours": None},
        {"name": "Tan Min", "date": "3-Aug", "hours": 12.0, "source": "Branch A / August", "operation_hours": None},
    ]
    assert unmapped == []


def test_generate_report_credits_floating_column_when_own_cell_blank(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")
    aggregate.set_code_hours(conn, "SJ", 12.0)

    grid = [
        ["", "TAN MIN (PRP)", "[Pharmacist Name]"],
        ["1-Aug", "", "SJ"],
    ]
    rows, unmapped = aggregate.generate_report(
        conn, "Tan Min", fetch_csv=lambda sid, gid, timeout=15: grid
    )

    assert rows == [
        {"name": "Tan Min", "date": "1-Aug", "hours": 12.0, "source": "SJ / August", "operation_hours": None},
    ]
    assert unmapped == []


def test_generate_report_carries_doc_operation_hours(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")
    mapping_mod.set_operation_hours(conn, "SHEET1", "10:00 AM - 10:00 PM")

    grid = [["", "Alice"], ["1-Aug", "9.5"]]
    rows, _ = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )

    assert rows == [
        {"name": "Alice", "date": "1-Aug", "hours": 9.5, "source": "Branch A / August", "operation_hours": "10:00 AM - 10:00 PM"},
    ]


def test_generate_report_sorts_rows_by_date_ascending(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_a = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 2)
    doc_b = mapping_mod.save_mapping(conn, "SHEET2", "Branch B", 0, 0, 1, 2)
    mapping_mod.mark_tab_known(conn, doc_a, "111", "August")
    mapping_mod.mark_tab_known(conn, doc_b, "222", "July")

    grids = {
        "SHEET1": [["", "Alice"], ["10-Aug", "9"], ["2-Aug", "9"]],
        "SHEET2": [["", "Alice"], ["31-Jul", "9"], ["20-Jul", "9"]],
    }
    rows, _ = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grids[sid]
    )

    assert [r["date"] for r in rows] == ["20-Jul", "31-Jul", "2-Aug", "10-Aug"]


def test_generate_report_skips_tab_with_stale_gid(tmp_path):
    # Regression: a deleted/renamed tab's gid causes Google to 400 on export;
    # that tab should be skipped, not crash the whole report.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.mark_tab_known(conn, doc_id, "1", "Stale")
    mapping_mod.mark_tab_known(conn, doc_id, "2", "Live")

    good_grid = [["", "Alice"], ["1-Aug", "9.5"]]

    def fake_fetch_csv(spreadsheet_id, gid, timeout=15):
        if gid == "1":
            raise requests.exceptions.HTTPError("400 Client Error")
        return good_grid

    rows, unmapped = aggregate.generate_report(conn, "Alice", fetch_csv=fake_fetch_csv)

    assert rows == [
        {"name": "Alice", "date": "1-Aug", "hours": 9.5, "source": "Branch A / Live", "operation_hours": None},
    ]
    assert unmapped == []
