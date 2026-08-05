from app import mapping

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
