import re

_MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_DAY_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3,9})$")

def _day_month(cell):
    """Parse "20-Jul" into (day, month_index), or None if it doesn't match
    a real day-of-month / real month abbreviation."""
    m = _DAY_RE.match(cell.strip())
    if not m:
        return None
    day = int(m.group(1))
    month_abbr = m.group(2)[:3].upper()
    if month_abbr not in _MONTH_ABBR or not 1 <= day <= 31:
        return None
    return day, _MONTH_ABBR.index(month_abbr)

def _is_next_day(prev, curr):
    prev_day, prev_month = prev
    day, month = curr
    if month == prev_month:
        return day == prev_day + 1
    return day == 1 and month == (prev_month + 1) % 12

def detect_date_range(grid, header_row, search_rows=10):
    """Find the date column/range below header_row.

    The date sequence doesn't always start right below the header (some
    sheets have a blank/instructions row first), and doesn't always start
    on the 1st of the month (payroll periods can start mid-month) — so try
    every possible start within `search_rows` rows below the header, and
    follow the actual month names so a run only continues into the next
    calendar month, never wraps on a coincidental day-of-month match.
    """
    num_cols = max((len(r) for r in grid), default=0)
    search_end = min(len(grid), header_row + 1 + search_rows)
    best = None
    for col in range(num_cols):
        for start in range(header_row + 1, search_end):
            cell = grid[start][col] if col < len(grid[start]) else ""
            prev = _day_month(cell)
            if prev is None:
                continue
            row = start + 1
            while row < len(grid):
                cell = grid[row][col] if col < len(grid[row]) else ""
                curr = _day_month(cell)
                if curr is None or not _is_next_day(prev, curr):
                    break
                prev = curr
                row += 1
            run_len = row - start
            if run_len >= 2 and (best is None or run_len > best[3]):
                best = (col, start, row - 1, run_len)
    if best is None:
        return None
    col, start, end, _ = best
    return {"date_col": col, "row_start": start, "row_end": end}


def save_mapping(conn, spreadsheet_id, label, header_row, date_col, row_start, row_end, tab_pattern=None):
    conn.execute(
        """INSERT INTO docs
             (spreadsheet_id, label, header_row, date_col, date_row_start, date_row_end, tab_pattern)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(spreadsheet_id) DO UPDATE SET
             label=excluded.label,
             header_row=excluded.header_row,
             date_col=excluded.date_col,
             date_row_start=excluded.date_row_start,
             date_row_end=excluded.date_row_end,
             tab_pattern=excluded.tab_pattern""",
        (spreadsheet_id, label, header_row, date_col, row_start, row_end, tab_pattern),
    )
    conn.commit()
    return get_doc(conn, spreadsheet_id)["id"]


def get_doc(conn, spreadsheet_id):
    row = conn.execute(
        "SELECT * FROM docs WHERE spreadsheet_id = ?", (spreadsheet_id,)
    ).fetchone()
    return dict(row) if row else None


def set_operation_hours(conn, spreadsheet_id, hours):
    conn.execute(
        "UPDATE docs SET operation_hours = ? WHERE spreadsheet_id = ?",
        (hours, spreadsheet_id),
    )
    conn.commit()


def delete_doc(conn, spreadsheet_id):
    doc = get_doc(conn, spreadsheet_id)
    if doc is None:
        return
    conn.execute("DELETE FROM known_tabs WHERE doc_id = ?", (doc["id"],))
    conn.execute("DELETE FROM code_hours WHERE doc_id = ?", (doc["id"],))
    conn.execute("DELETE FROM docs WHERE id = ?", (doc["id"],))
    conn.commit()


def list_docs(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM docs").fetchall()]


def mark_tab_known(conn, doc_id, gid, title):
    conn.execute(
        "INSERT OR IGNORE INTO known_tabs (doc_id, gid, title) VALUES (?, ?, ?)",
        (doc_id, gid, title),
    )
    conn.commit()


def known_tab_gids(conn, doc_id):
    rows = conn.execute(
        "SELECT gid FROM known_tabs WHERE doc_id = ?", (doc_id,)
    ).fetchall()
    return {r["gid"] for r in rows}


def known_tabs(conn, doc_id):
    rows = conn.execute(
        "SELECT gid, title FROM known_tabs WHERE doc_id = ?", (doc_id,)
    ).fetchall()
    return [dict(r) for r in rows]
