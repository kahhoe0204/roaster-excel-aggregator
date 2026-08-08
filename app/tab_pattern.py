import re

_MONTH_ABBR = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MONTH_RE = "(?:" + "|".join(_MONTH_ABBR) + ")"


def compile_pattern(template):
    """Compile a `{month}`/`{shortyear}` template into a case-insensitive regex.

    Literal characters are matched as-is; `{month}` matches a 3-letter month
    abbreviation, `{shortyear}` matches 2 digits.
    """
    parts = re.split(r"(\{month\}|\{shortyear\})", template)
    pattern = "".join(
        f"(?P<month>{_MONTH_RE})" if part == "{month}"
        else r"(?P<shortyear>\d{2})" if part == "{shortyear}"
        else re.escape(part)
        for part in parts
    )
    return re.compile(f"^{pattern}$", re.IGNORECASE)


def _sort_key(match):
    groups = match.groupdict()
    year = int(groups["shortyear"]) if groups.get("shortyear") else 0
    month = _MONTH_ABBR.index(groups["month"].upper()) + 1 if groups.get("month") else 0
    return (year, month)


def matches(template, title):
    return bool(compile_pattern(template).match(title.strip()))


def pick_latest(template, tabs):
    """Return the tab dict (must have a "title") that parses to the latest
    month/year among those matching `template`, or None if none match."""
    regex = compile_pattern(template)
    ranked = []
    for tab in tabs:
        m = regex.match(tab["title"].strip())
        if m:
            ranked.append((_sort_key(m), tab))
    if not ranked:
        return None
    return max(ranked, key=lambda pair: pair[0])[1]
