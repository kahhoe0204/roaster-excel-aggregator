from app import tab_pattern


def test_matches_month_and_shortyear():
    assert tab_pattern.matches("{month} {shortyear} PH", "AUG 26 PH")
    assert tab_pattern.matches("{month} {shortyear} PH", "aug 26 ph")
    assert not tab_pattern.matches("{month} {shortyear} PH", "AUG 26 OTHER")
    assert not tab_pattern.matches("{month} {shortyear} PH", "26 PH")


def test_matches_rejects_non_month_token():
    assert not tab_pattern.matches("{month} {shortyear} PH", "XYZ 26 PH")


def test_infer_pattern_generalizes_month_and_year():
    assert tab_pattern.infer_pattern("MAY 26 PH") == "{month} {shortyear} PH"
    assert tab_pattern.infer_pattern("may 26 ph") == "{month} {shortyear} ph"


def test_infer_pattern_falls_back_to_literal_without_tokens():
    assert tab_pattern.infer_pattern("STATE PH") == "STATE PH"


def test_infer_pattern_only_replaces_first_month_and_year_token():
    assert tab_pattern.infer_pattern("MAY 26 REVIEW JUN 27") == "{month} {shortyear} REVIEW JUN 27"


def test_infer_pattern_roundtrips_with_matches():
    inferred = tab_pattern.infer_pattern("MAY 26 PH")
    assert tab_pattern.matches(inferred, "JUN 26 PH")
    assert tab_pattern.matches(inferred, "AUG 26 PH")
    assert not tab_pattern.matches(inferred, "AUG 26 OTHER")


def test_tab_month_finds_the_embedded_month():
    assert tab_pattern.tab_month("AUG 26 PH") == 7
    assert tab_pattern.tab_month("jul 26 ph") == 6


def test_tab_month_none_without_a_recognizable_month():
    assert tab_pattern.tab_month("STATE PH") is None


def test_latest_tab_by_parsed_month_year():
    tabs = [
        {"gid": "1", "title": "JUL 25 PH"},
        {"gid": "2", "title": "AUG 26 PH"},
        {"gid": "3", "title": "AUG 26 OTHER"},  # doesn't match, excluded
        {"gid": "4", "title": "JAN 26 PH"},
    ]
    latest = tab_pattern.latest_tab("{month} {shortyear} PH", tabs)
    assert latest == {"gid": "2", "title": "AUG 26 PH"}


def test_latest_tab_returns_none_when_no_match_or_no_pattern():
    tabs = [{"gid": "1", "title": "Instructions"}]
    assert tab_pattern.latest_tab("{month} {shortyear} PH", tabs) is None
    assert tab_pattern.latest_tab(None, tabs) is None
    assert tab_pattern.latest_tab("", tabs) is None
