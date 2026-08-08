import requests

from app import sync, mapping as mapping_mod, db as db_mod


def test_check_new_tabs_marks_and_returns_only_new(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", tab_pattern="September")
    mapping_mod.mark_tab_known(conn, doc_id, "111", "August")
    doc = mapping_mod.get_doc(conn, "SHEET1")

    remote_tabs = [
        {"gid": "111", "title": "August"},
        {"gid": "222", "title": "September"},
    ]
    new_tabs = sync.check_new_tabs(
        conn, doc, "fake-key", list_tabs=lambda sid, key: remote_tabs
    )

    assert new_tabs == [{"gid": "222", "title": "September"}]
    assert mapping_mod.known_tab_gids(conn, doc_id) == {"111", "222"}


def test_check_new_tabs_ignores_titles_that_dont_match_pattern(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", tab_pattern="September")
    doc = mapping_mod.get_doc(conn, "SHEET1")

    remote_tabs = [{"gid": "222", "title": "Random Notes"}]
    new_tabs = sync.check_new_tabs(
        conn, doc, "fake-key", list_tabs=lambda sid, key: remote_tabs
    )

    assert new_tabs == []
    assert mapping_mod.known_tab_gids(conn, doc_id) == set()


def test_check_new_tabs_without_pattern_imports_nothing(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping_mod.save_mapping(conn, "SHEET1", "Branch A")
    doc = mapping_mod.get_doc(conn, "SHEET1")

    remote_tabs = [{"gid": "222", "title": "September"}]
    new_tabs = sync.check_new_tabs(
        conn, doc, "fake-key", list_tabs=lambda sid, key: remote_tabs
    )

    assert new_tabs == []


def test_check_new_tabs_all_covers_every_doc(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping_mod.save_mapping(conn, "SHEET1", "Branch A", tab_pattern="August")
    mapping_mod.save_mapping(conn, "SHEET2", "Branch B", tab_pattern="August")

    def fake_list_tabs(spreadsheet_id, api_key):
        return [{"gid": "1", "title": "August"}]

    result = sync.check_new_tabs_all(conn, "fake-key", list_tabs=fake_list_tabs)

    assert result == {
        "SHEET1": [{"gid": "1", "title": "August"}],
        "SHEET2": [{"gid": "1", "title": "August"}],
    }


def test_check_new_tabs_all_skips_doc_that_errors(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping_mod.save_mapping(conn, "SHEET1", "Branch A", tab_pattern="August")
    mapping_mod.save_mapping(conn, "SHEET2", "Branch B", tab_pattern="August")

    def fake_list_tabs(spreadsheet_id, api_key):
        if spreadsheet_id == "SHEET1":
            raise requests.exceptions.HTTPError("404 Client Error: Not Found")
        return [{"gid": "1", "title": "August"}]

    result = sync.check_new_tabs_all(conn, "fake-key", list_tabs=fake_list_tabs)

    assert result["SHEET1"] == {"error": "404 Client Error: Not Found"}
    assert result["SHEET2"] == [{"gid": "1", "title": "August"}]
