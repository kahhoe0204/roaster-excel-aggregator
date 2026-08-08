import re
from datetime import datetime

import requests

from . import mapping as mapping_mod
from . import csv_fetch as csv_fetch_mod
from . import tab_pattern as tab_pattern_mod

_CODE_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")

# Leave shortforms — not hours worked, not an unmapped code either.
_IGNORED_CODES = {"AL", "RL", "MC", "PH", "LEAVE"}

# A bracket-only header ("[Pharmacist Name]", "[]", "[any]") is a floating
# covering slot for whoever's own column is blank that day, not a named column.
_PLACEHOLDER_HEADER_RE = re.compile(r"^\[.*\]$")

_WEEKDAYS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}


def resolve_cell(cell, code_hours):
    """Resolve a cell value to hours or an unmapped code.

    Args:
        cell: Cell value (string or None)
        code_hours: Dict mapping code strings to hours (float), or to None
            for a code that's mapped but explicitly ignored (not a working-
            hour code — e.g. a code someone marked "not applicable")

    Returns:
        Tuple of (hours, unmapped_code) where exactly one is non-None,
        or both are None for blank cells and for codes mapped to None.
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
    if code in _IGNORED_CODES:
        return None, None
    if code in code_hours:
        return code_hours[code], None

    return None, code


def _date_sort_key(date_str):
    # No year in "1-Aug" style cells — sort by month/day only, unparseable
    # dates keep their original relative order at the end.
    try:
        return (0, datetime.strptime(f"{date_str} 2000", "%d-%b %Y"))
    except ValueError:
        return (1, date_str)


def get_code_hours(conn, doc_id):
    """Get this doc's code->hours mappings from the database."""
    rows = conn.execute("SELECT code, hours FROM code_hours WHERE doc_id = ?", (doc_id,)).fetchall()
    return {r["code"]: r["hours"] for r in rows}


def set_code_hours(conn, doc_id, code, hours):
    """Set or update a code->hours mapping for one doc. hours=None marks the
    code as ignored — not a working-hour code, excluded from reports."""
    conn.execute(
        """INSERT INTO code_hours (doc_id, code, hours) VALUES (?, ?, ?)
           ON CONFLICT(doc_id, code) DO UPDATE SET hours=excluded.hours""",
        (doc_id, code, hours),
    )
    conn.commit()


def get_branch_operation_hours(conn, doc_id):
    """Code -> operation period, for codes that appear in a floating source
    column (a relief pharmacist's covering branch) and have their own
    operation period configured, distinct from this doc's own."""
    rows = conn.execute(
        "SELECT code, operation_hours FROM code_hours WHERE doc_id = ? AND operation_hours IS NOT NULL",
        (doc_id,),
    ).fetchall()
    return {r["code"]: r["operation_hours"] for r in rows}


def set_branch_operation_hours(conn, doc_id, code, operation_hours):
    """Set the operation period for a branch code, independent of its hours
    mapping (a code can have hours, an operation period, both, or neither)."""
    conn.execute(
        """INSERT INTO code_hours (doc_id, code, operation_hours) VALUES (?, ?, ?)
           ON CONFLICT(doc_id, code) DO UPDATE SET operation_hours=excluded.operation_hours""",
        (doc_id, code, operation_hours),
    )
    conn.commit()


def generate_report(conn, name, fetch_csv=None):
    """Aggregate hours for `name` across all known docs/tabs via live CSV fetch.

    Returns (rows, unmapped) where rows are {"name", "date", "hours",
    "source"} dicts and unmapped is a sorted list of
    {"code", "spreadsheet_id", "label"} dicts — codes with no hours mapping
    for the specific doc they appeared in (mappings are scoped per doc).
    """
    fetch = fetch_csv or csv_fetch_mod.fetch_csv
    rows = []
    unmapped = {}
    name_lower = name.strip().lower()

    for doc in mapping_mod.list_docs(conn):
        code_hours = get_code_hours(conn, doc["id"])
        branch_hours = get_branch_operation_hours(conn, doc["id"])
        for tab in mapping_mod.known_tabs(conn, doc["id"]):
            try:
                grid = fetch(doc["spreadsheet_id"], tab["gid"])
            except requests.exceptions.HTTPError:
                continue
            header = grid[tab["header_row"]] if tab["header_row"] < len(grid) else []
            name_col = next(
                (i for i, cell in enumerate(header) if name_lower in cell.strip().lower()),
                None,
            )
            if name_col is None:
                continue
            placeholder_col = name_col + 1
            has_placeholder = (
                placeholder_col < len(header)
                and _PLACEHOLDER_HEADER_RE.match(header[placeholder_col].strip())
            )
            tab_month = tab_pattern_mod.tab_month(tab["title"])
            for r in range(tab["date_row_start"], tab["date_row_end"] + 1):
                if r >= len(grid):
                    break
                row = grid[r]
                date_cell = row[tab["date_col"]] if tab["date_col"] < len(row) else ""
                # Sheets often carry a few leftover days from the adjacent
                # month for scheduling convenience (e.g. the "AUG" tab also
                # shows late July and early September) — only trust rows
                # that actually belong to this tab's own month, so the same
                # calendar date isn't double-counted from two tabs.
                if tab_month is not None:
                    parsed = mapping_mod.parse_day_month(date_cell)
                    if parsed is not None and parsed[1] != tab_month:
                        continue
                day_col = tab["date_col"] + 1
                day_cell = row[day_col].strip() if day_col < len(row) else ""
                day = day_cell if day_cell.upper() in _WEEKDAYS else ""
                value_cell = row[name_col] if name_col < len(row) else ""
                placeholder_text = ""
                if has_placeholder:
                    placeholder_cell = row[placeholder_col] if placeholder_col < len(row) else ""
                    placeholder_text = placeholder_cell.strip()
                hours, unmapped_code = resolve_cell(value_cell, code_hours)
                if hours is None and unmapped_code is None and placeholder_text:
                    hours, unmapped_code = resolve_cell(placeholder_cell, code_hours)
                if unmapped_code:
                    unmapped[(unmapped_code, doc["spreadsheet_id"])] = doc["label"]
                if hours is None:
                    continue
                # A relief pharmacist's own column stays hers, but the
                # floating slot next to it records which branch she actually
                # covered that day — that code wins over the doc's own label.
                branch = placeholder_text or doc["label"]
                branch_code = placeholder_text.upper() if placeholder_text else None
                operation_hours = branch_hours.get(branch_code) if branch_code else None
                rows.append({
                    "name": name,
                    "date": date_cell.strip(),
                    "day": day,
                    "hours": hours,
                    "source": f"{branch} / {tab['title']}",
                    "operation_hours": operation_hours or doc["operation_hours"],
                    "spreadsheet_id": doc["spreadsheet_id"],
                    "branch_code": branch_code,
                })
    rows.sort(key=lambda r: _date_sort_key(r["date"]))
    unmapped_list = sorted(
        (
            {"code": code, "spreadsheet_id": spreadsheet_id, "label": label}
            for (code, spreadsheet_id), label in unmapped.items()
        ),
        key=lambda u: (u["code"], u["label"]),
    )
    return rows, unmapped_list
