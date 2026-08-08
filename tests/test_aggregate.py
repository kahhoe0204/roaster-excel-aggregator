import requests

from app import aggregate, db as db_mod
from app import mapping as mapping_mod
from tests.conftest import configure_doc


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


def test_resolve_cell_code_mapped_to_none_is_ignored():
    # A code someone explicitly marked "Ignore" — mapped, but not a
    # working-hour code, so it's excluded like the leave shortforms.
    assert aggregate.resolve_cell("KDM", {"KDM": None}) == (None, None)


def test_resolve_cell_digit_bearing_unmapped_code():
    # Regression: "P14" unmapped should be flagged, not guessed as 14 hours
    assert aggregate.resolve_cell("P14", {}) == (None, "P14")


def test_resolve_cell_digit_bearing_mapped_code():
    # Regression: "P14" mapped should use lookup value, not embedded digit
    assert aggregate.resolve_cell("P14", {"P14": 12.0}) == (12.0, None)


def test_code_hours_roundtrip(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    assert aggregate.get_code_hours(conn, doc_id) == {}
    aggregate.set_code_hours(conn, doc_id, "SJ", 12.0)
    aggregate.set_code_hours(conn, doc_id, "P14", 12.0)
    aggregate.set_code_hours(conn, doc_id, "SJ", 8.0)  # overwrite
    assert aggregate.get_code_hours(conn, doc_id) == {"SJ": 8.0, "P14": 12.0}


def test_code_hours_scoped_per_doc(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_a = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    doc_b = mapping_mod.save_mapping(conn, "SHEET2", "Branch B")
    aggregate.set_code_hours(conn, doc_a, "SJ", 12.0)
    aggregate.set_code_hours(conn, doc_b, "SJ", 8.0)

    assert aggregate.get_code_hours(conn, doc_a) == {"SJ": 12.0}
    assert aggregate.get_code_hours(conn, doc_b) == {"SJ": 8.0}


def test_code_hours_can_be_marked_ignored_with_none(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    aggregate.set_code_hours(conn, doc_id, "KDM", None)

    assert aggregate.get_code_hours(conn, doc_id) == {"KDM": None}


def test_branch_operation_hours_roundtrip(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    assert aggregate.get_branch_operation_hours(conn, doc_id) == {}

    aggregate.set_branch_operation_hours(conn, doc_id, "P14", "8:00 AM - 8:00 PM")
    assert aggregate.get_branch_operation_hours(conn, doc_id) == {"P14": "8:00 AM - 8:00 PM"}


def test_branch_operation_hours_independent_of_code_hours(tmp_path):
    # A code can have hours, an operation period, both, or neither — setting
    # one must not clobber the other.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    aggregate.set_code_hours(conn, doc_id, "P14", 12.0)
    aggregate.set_branch_operation_hours(conn, doc_id, "P14", "8:00 AM - 8:00 PM")

    assert aggregate.get_code_hours(conn, doc_id) == {"P14": 12.0}
    assert aggregate.get_branch_operation_hours(conn, doc_id) == {"P14": "8:00 AM - 8:00 PM"}


def test_generate_report_matches_name_across_docs(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    aggregate.set_code_hours(conn, doc_id, "SJ", 12.0)

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
        {"name": "Alice", "date": "1-Aug", "day": "Friday", "hours": 9.5, "source": "Branch A / August",
         "operation_hours": None, "spreadsheet_id": "SHEET1", "branch_code": None},
    ]
    assert unmapped == []

def test_generate_report_ignores_non_weekday_adjacent_column(tmp_path):
    # The column right after date_col is only trusted as "day" when it's
    # actually a weekday name — a sheet without that column (or with
    # something else there) should just get a blank day, not garbage.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)

    grid = [["", "Alice"], ["1-Aug", "9.5"]]
    rows, _ = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )
    assert rows[0]["day"] == ""


def test_generate_report_flags_unmapped_codes(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)

    grid = [["", "Alice"], ["1-Aug", "XYZ"]]
    rows, unmapped = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )
    assert rows == []
    assert unmapped == [{"code": "XYZ", "spreadsheet_id": "SHEET1", "label": "Branch A"}]

def test_generate_report_excludes_code_marked_ignored(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    aggregate.set_code_hours(conn, doc_id, "KDM", None)

    grid = [["", "Alice"], ["1-Aug", "KDM"]]
    rows, unmapped = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )
    assert rows == []
    assert unmapped == []  # ignored, not flagged as unmapped either


def test_generate_report_skips_docs_without_matching_name(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)

    grid = [["", "Bob"], ["1-Aug", "9"]]
    rows, unmapped = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )
    assert rows == []
    assert unmapped == []


def test_generate_report_filters_leftover_days_from_adjacent_month(tmp_path):
    # Regression: a month's tab often carries a few leftover days from the
    # tab before/after (e.g. "AUG 26 PH" also lists late July) — those must
    # not be double-counted against the tab that actually owns that month.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    mapping_mod.mark_tab_known(conn, doc_id, "1", "JUL 26 PH")
    mapping_mod.mark_tab_known(conn, doc_id, "2", "AUG 26 PH")
    mapping_mod.configure_tab(conn, doc_id, "1", header_row=0, date_col=0, row_start=1, row_end=4)
    mapping_mod.configure_tab(conn, doc_id, "2", header_row=0, date_col=0, row_start=1, row_end=8)

    jul_grid = [
        ["", "Javerin"],
        ["28-Jul", "12"], ["29-Jul", "12"], ["30-Jul", "12"], ["31-Jul", "12"],
    ]
    aug_grid = [
        ["", "Javerin"],
        ["28-Jul", "12"], ["29-Jul", "12"], ["30-Jul", "12"], ["31-Jul", "12"],  # leftover, not August's
        ["1-Aug", "12"], ["2-Aug", "12"], ["3-Aug", "12"], ["4-Aug", "12"],
    ]
    grids = {"1": jul_grid, "2": aug_grid}
    rows, _ = aggregate.generate_report(
        conn, "Javerin", fetch_csv=lambda sid, gid, timeout=15: grids[gid]
    )

    dates = [r["date"] for r in rows]
    assert dates == ["28-Jul", "29-Jul", "30-Jul", "31-Jul", "1-Aug", "2-Aug", "3-Aug", "4-Aug"]
    assert len(dates) == len(set(dates))  # no duplicates


def test_generate_report_uses_floating_column_code_as_source(tmp_path):
    # Regression: a relief pharmacist's own column holds her hours (a bare
    # number), but which branch she actually covered that day is recorded
    # as a code in the "[Pharmacist Name]" floating slot next to it — that
    # code should win over this doc's own branch label.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 3)

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
        {"name": "Tan Min", "date": "1-Aug", "day": "", "hours": 12.0, "source": "P14 / August",
         "operation_hours": None, "spreadsheet_id": "SHEET1", "branch_code": "P14"},
        {"name": "Tan Min", "date": "3-Aug", "day": "", "hours": 12.0, "source": "Branch A / August",
         "operation_hours": None, "spreadsheet_id": "SHEET1", "branch_code": None},
    ]
    assert unmapped == []


def test_generate_report_uses_branch_specific_operation_hours(tmp_path):
    # The floating column can send a relief pharmacist's hours to a branch
    # with its own operation period, distinct from this doc's own — that
    # period should show up on the row, falling back to the doc's own when
    # the detected branch code has no period configured.
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 3)
    mapping_mod.set_operation_hours(conn, "SHEET1", "9:00 AM - 9:00 PM")
    aggregate.set_branch_operation_hours(conn, doc_id, "P14", "8:00 AM - 8:00 PM")

    grid = [
        ["", "MEGAN", "TAN MIN (PRP)", "[Pharmacist Name]"],
        ["1-Aug", "", "12", "P14"],  # P14 has its own configured period
        ["2-Aug", "", "", ""],
        ["3-Aug", "", "12", "SJ"],  # SJ has none — falls back to doc's own
    ]
    rows, _ = aggregate.generate_report(
        conn, "Tan Min", fetch_csv=lambda sid, gid, timeout=15: grid
    )

    assert rows == [
        {"name": "Tan Min", "date": "1-Aug", "day": "", "hours": 12.0, "source": "P14 / August",
         "operation_hours": "8:00 AM - 8:00 PM", "spreadsheet_id": "SHEET1", "branch_code": "P14"},
        {"name": "Tan Min", "date": "3-Aug", "day": "", "hours": 12.0, "source": "SJ / August",
         "operation_hours": "9:00 AM - 9:00 PM", "spreadsheet_id": "SHEET1", "branch_code": "SJ"},
    ]


def test_generate_report_credits_floating_column_when_own_cell_blank(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    aggregate.set_code_hours(conn, doc_id, "SJ", 12.0)

    grid = [
        ["", "TAN MIN (PRP)", "[Pharmacist Name]"],
        ["1-Aug", "", "SJ"],
    ]
    rows, unmapped = aggregate.generate_report(
        conn, "Tan Min", fetch_csv=lambda sid, gid, timeout=15: grid
    )

    assert rows == [
        {"name": "Tan Min", "date": "1-Aug", "day": "", "hours": 12.0, "source": "SJ / August",
         "operation_hours": None, "spreadsheet_id": "SHEET1", "branch_code": "SJ"},
    ]
    assert unmapped == []


def test_generate_report_carries_doc_operation_hours(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    mapping_mod.set_operation_hours(conn, "SHEET1", "10:00 AM - 10:00 PM")

    grid = [["", "Alice"], ["1-Aug", "9.5"]]
    rows, _ = aggregate.generate_report(
        conn, "Alice", fetch_csv=lambda sid, gid, timeout=15: grid
    )

    assert rows == [
        {"name": "Alice", "date": "1-Aug", "day": "", "hours": 9.5, "source": "Branch A / August",
         "operation_hours": "10:00 AM - 10:00 PM", "spreadsheet_id": "SHEET1", "branch_code": None},
    ]


def test_generate_report_sorts_rows_by_date_ascending(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    configure_doc(conn, "SHEET1", "Branch A", 0, 0, 1, 2, gid="111", title="August")
    configure_doc(conn, "SHEET2", "Branch B", 0, 0, 1, 2, gid="222", title="July")

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
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    mapping_mod.mark_tab_known(conn, doc_id, "1", "Stale")
    mapping_mod.mark_tab_known(conn, doc_id, "2", "Live")
    mapping_mod.configure_tab(conn, doc_id, "1", 0, 0, 1, 1)
    mapping_mod.configure_tab(conn, doc_id, "2", 0, 0, 1, 1)

    good_grid = [["", "Alice"], ["1-Aug", "9.5"]]

    def fake_fetch_csv(spreadsheet_id, gid, timeout=15):
        if gid == "1":
            raise requests.exceptions.HTTPError("400 Client Error")
        return good_grid

    rows, unmapped = aggregate.generate_report(conn, "Alice", fetch_csv=fake_fetch_csv)

    assert rows == [
        {"name": "Alice", "date": "1-Aug", "day": "", "hours": 9.5, "source": "Branch A / Live",
         "operation_hours": None, "spreadsheet_id": "SHEET1", "branch_code": None},
    ]
    assert unmapped == []
