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


_MONTH_TOKEN_RE = re.compile(r"(?i)\b(" + "|".join(_MONTH_ABBR) + r")\b")
_YEAR_TOKEN_RE = re.compile(r"\b\d{2}\b")


def infer_pattern(title):
    """Reverse of compile_pattern: guess a reusable {month}/{shortyear}
    template from one concrete tab title, e.g. "MAY 26 PH" -> "{month}
    {shortyear} PH". Falls back to the literal title if it has no month
    abbreviation or 2-digit year token to generalize from."""
    pattern = _MONTH_TOKEN_RE.sub("{month}", title, count=1)
    pattern = _YEAR_TOKEN_RE.sub("{shortyear}", pattern, count=1)
    return pattern
