import re

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
