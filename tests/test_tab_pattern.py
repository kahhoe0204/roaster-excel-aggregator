from app import tab_pattern


def test_matches_month_and_shortyear():
    assert tab_pattern.matches("{month} {shortyear} PH", "AUG 26 PH")
    assert tab_pattern.matches("{month} {shortyear} PH", "aug 26 ph")
    assert not tab_pattern.matches("{month} {shortyear} PH", "AUG 26 OTHER")
    assert not tab_pattern.matches("{month} {shortyear} PH", "26 PH")


def test_matches_rejects_non_month_token():
    assert not tab_pattern.matches("{month} {shortyear} PH", "XYZ 26 PH")


def test_pick_latest_by_parsed_month_year():
    tabs = [
        {"gid": "1", "title": "JUL 25 PH"},
        {"gid": "2", "title": "AUG 26 PH"},
        {"gid": "3", "title": "AUG 26 OTHER"},  # doesn't match, excluded
        {"gid": "4", "title": "JAN 26 PH"},
    ]
    latest = tab_pattern.pick_latest("{month} {shortyear} PH", tabs)
    assert latest == {"gid": "2", "title": "AUG 26 PH"}


def test_pick_latest_returns_none_when_no_match():
    tabs = [{"gid": "1", "title": "Instructions"}]
    assert tab_pattern.pick_latest("{month} {shortyear} PH", tabs) is None
