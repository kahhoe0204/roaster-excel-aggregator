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
