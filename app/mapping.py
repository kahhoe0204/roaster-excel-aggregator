import re

_DAY_RE = re.compile(r"^(\d{1,2})-[A-Za-z]{3,9}$")

def _day_matches(cell, expected_day):
    m = _DAY_RE.match(cell.strip())
    return bool(m) and int(m.group(1)) == expected_day

def detect_date_range(grid, header_row):
    num_cols = max((len(r) for r in grid), default=0)
    best = None
    for col in range(num_cols):
        run_start = None
        expected = 1
        row = header_row + 1
        while row < len(grid):
            cell = grid[row][col] if col < len(grid[row]) else ""
            if _day_matches(cell, expected):
                if run_start is None:
                    run_start = row
                expected += 1
                row += 1
            else:
                break
        run_len = expected - 1
        if run_start is not None and run_len >= 2:
            if best is None or run_len > best[3]:
                best = (col, run_start, row - 1, run_len)
    if best is None:
        return None
    col, start, end, _ = best
    return {"date_col": col, "row_start": start, "row_end": end}


def save_mapping(conn, spreadsheet_id, label, header_row, date_col, row_start, row_end):
    conn.execute(
        """INSERT INTO docs
             (spreadsheet_id, label, header_row, date_col, date_row_start, date_row_end)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(spreadsheet_id) DO UPDATE SET
             label=excluded.label,
             header_row=excluded.header_row,
             date_col=excluded.date_col,
             date_row_start=excluded.date_row_start,
             date_row_end=excluded.date_row_end""",
        (spreadsheet_id, label, header_row, date_col, row_start, row_end),
    )
    conn.commit()
    return get_doc(conn, spreadsheet_id)["id"]


def get_doc(conn, spreadsheet_id):
    row = conn.execute(
        "SELECT * FROM docs WHERE spreadsheet_id = ?", (spreadsheet_id,)
    ).fetchone()
    return dict(row) if row else None


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
