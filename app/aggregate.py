import re

import requests

from . import mapping as mapping_mod
from . import csv_fetch as csv_fetch_mod

_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def resolve_cell(cell, code_hours):
    """Resolve a cell value to hours or an unmapped code.

    Args:
        cell: Cell value (string or None)
        code_hours: Dict mapping code strings to hours (float)

    Returns:
        Tuple of (hours, unmapped_code) where exactly one is non-None,
        or both are None for blank cells.
    """
    text = (cell or "").strip()
    if not text:
        return None, None

    # Try parsing as pure number
    try:
        return float(text), None
    except ValueError:
        pass

    # Look for explicit number after whitespace (space-separated pattern like "P14 12.5")
    num_match = re.search(r"\s+(\d+(?:\.\d+)?)", text)
    if num_match:
        return float(num_match.group(1)), None

    # Extract code and lookup
    code_match = _CODE_RE.match(text)
    code = code_match.group().upper() if code_match else text.upper()
    if code in code_hours:
        return code_hours[code], None

    return None, code


def get_code_hours(conn):
    """Get all code->hours mappings from the database."""
    rows = conn.execute("SELECT code, hours FROM code_hours").fetchall()
    return {r["code"]: r["hours"] for r in rows}


def set_code_hours(conn, code, hours):
    """Set or update a code->hours mapping."""
    conn.execute(
        """INSERT INTO code_hours (code, hours) VALUES (?, ?)
           ON CONFLICT(code) DO UPDATE SET hours=excluded.hours""",
        (code, hours),
    )
    conn.commit()


def generate_report(conn, name, fetch_csv=None):
    """Aggregate hours for `name` across all known docs/tabs via live CSV fetch.

    Returns (rows, unmapped_codes) where rows are
    {"name", "date", "hours", "source"} dicts and unmapped_codes is a
    sorted list of distinct codes with no hours mapping.
    """
    fetch = fetch_csv or csv_fetch_mod.fetch_csv
    code_hours = get_code_hours(conn)
    rows = []
    unmapped = set()
    name_lower = name.strip().lower()

    for doc in mapping_mod.list_docs(conn):
        for tab in mapping_mod.known_tabs(conn, doc["id"]):
            try:
                grid = fetch(doc["spreadsheet_id"], tab["gid"])
            except requests.exceptions.HTTPError:
                continue
            header = grid[doc["header_row"]] if doc["header_row"] < len(grid) else []
            name_col = next(
                (i for i, cell in enumerate(header) if name_lower in cell.strip().lower()),
                None,
            )
            if name_col is None:
                continue
            for r in range(doc["date_row_start"], doc["date_row_end"] + 1):
                if r >= len(grid):
                    break
                row = grid[r]
                date_cell = row[doc["date_col"]] if doc["date_col"] < len(row) else ""
                value_cell = row[name_col] if name_col < len(row) else ""
                hours, unmapped_code = resolve_cell(value_cell, code_hours)
                if unmapped_code:
                    unmapped.add(unmapped_code)
                if hours is None:
                    continue
                rows.append({
                    "name": name,
                    "date": date_cell.strip(),
                    "hours": hours,
                    "source": f"{doc['label']} / {tab['title']}",
                })
    return rows, sorted(unmapped)
