from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import PatternFill

_PALETTE = [
    "FFF2CC", "D9EAD3", "CFE2F3", "F4CCCC",
    "EAD1DC", "D0E0E3", "FCE5CD", "D9D2E9",
]


def _month_tab(date_str):
    try:
        return datetime.strptime(f"{date_str} 2000", "%d-%b %Y").strftime("%B")
    except ValueError:
        return "Other"


def _branch(source):
    return source.split(" / ", 1)[0]


def rows_to_xlsx(rows):
    wb = Workbook()
    wb.remove(wb.active)

    branch_colors = {}

    def fill_for(branch):
        color = branch_colors.setdefault(branch, _PALETTE[len(branch_colors) % len(_PALETTE)])
        return PatternFill(start_color=color, end_color=color, fill_type="solid")

    sheets = {}
    for row in rows:
        month = _month_tab(row["date"])
        ws = sheets.get(month)
        if ws is None:
            ws = wb.create_sheet(title=month)
            ws.append(["Name", "Date", "Time", "Source", "Operation Period"])
            sheets[month] = ws
        ws.append([row["name"], row["date"], row["hours"], row["source"], row.get("operation_hours")])
        for cell in ws[ws.max_row]:
            cell.fill = fill_for(_branch(row["source"]))

    if not sheets:
        wb.create_sheet(title="Report").append(["Name", "Date", "Time", "Source", "Operation Period"])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
