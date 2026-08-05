from app import aggregate, db as db_mod


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
    assert aggregate.resolve_cell("AL", {}) == (None, "AL")
    assert aggregate.resolve_cell("PH", {"SJ": 12.0}) == (None, "PH")


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
