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
