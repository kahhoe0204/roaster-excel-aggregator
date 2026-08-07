from io import BytesIO
from openpyxl import Workbook


def rows_to_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append(["Name", "Date", "Time", "Source"])
    for row in rows:
        ws.append([row["name"], row["date"], row["hours"], row["source"]])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
