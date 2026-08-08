from io import BytesIO
from openpyxl import load_workbook
from app import excel_export


def test_rows_to_xlsx_roundtrip():
    rows = [
        {"name": "Alice", "date": "1-Aug", "hours": 9.5, "source": "Branch A / August", "operation_hours": 12.0},
        {"name": "Alice", "date": "3-Aug", "hours": 12.0, "source": "Branch A / August", "operation_hours": 12.0},
    ]
    data = excel_export.rows_to_xlsx(rows)

    wb = load_workbook(BytesIO(data))
    assert wb.sheetnames == ["August"]
    ws = wb.active
    values = [[cell.value for cell in row] for row in ws.iter_rows()]

    assert values[0] == ["Name", "Date", "Time", "Source", "Operation Hours"]
    assert values[1] == ["Alice", "1-Aug", 9.5, "Branch A / August", 12.0]
    assert values[2] == ["Alice", "3-Aug", 12.0, "Branch A / August", 12.0]


def test_rows_to_xlsx_empty_rows_still_has_header():
    data = excel_export.rows_to_xlsx([])
    wb = load_workbook(BytesIO(data))
    ws = wb.active
    values = [[cell.value for cell in row] for row in ws.iter_rows()]
    assert values == [["Name", "Date", "Time", "Source", "Operation Hours"]]


def test_rows_to_xlsx_splits_months_into_separate_tabs():
    rows = [
        {"name": "Alice", "date": "20-Jul", "hours": 9.0, "source": "Branch A / July", "operation_hours": None},
        {"name": "Alice", "date": "1-Aug", "hours": 9.5, "source": "Branch A / August", "operation_hours": None},
    ]
    data = excel_export.rows_to_xlsx(rows)
    wb = load_workbook(BytesIO(data))

    assert wb.sheetnames == ["July", "August"]
    assert [c.value for c in wb["July"][2]] == ["Alice", "20-Jul", 9.0, "Branch A / July", None]
    assert [c.value for c in wb["August"][2]] == ["Alice", "1-Aug", 9.5, "Branch A / August", None]


def test_rows_to_xlsx_colors_rows_by_branch():
    rows = [
        {"name": "Alice", "date": "1-Aug", "hours": 9.0, "source": "Branch A / August"},
        {"name": "Bob", "date": "1-Aug", "hours": 9.0, "source": "Branch B / August"},
        {"name": "Alice", "date": "2-Aug", "hours": 9.0, "source": "Branch A / August"},
    ]
    data = excel_export.rows_to_xlsx(rows)
    wb = load_workbook(BytesIO(data))
    ws = wb["August"]

    row_a1 = ws[2][0].fill.start_color.rgb
    row_b = ws[3][0].fill.start_color.rgb
    row_a2 = ws[4][0].fill.start_color.rgb

    assert row_a1 == row_a2
    assert row_a1 != row_b
