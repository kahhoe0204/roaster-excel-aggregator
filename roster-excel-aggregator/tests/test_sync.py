from app import sync, mapping as mapping_mod, db as db_mod


def test_check_new_tabs_marks_and_returns_only_new(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    doc_id = mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
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


def test_check_new_tabs_all_covers_every_doc(tmp_path):
    conn = db_mod.init_db(str(tmp_path / "t.db"))
    mapping_mod.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
    mapping_mod.save_mapping(conn, "SHEET2", "Branch B", 0, 0, 1, 31)

    def fake_list_tabs(spreadsheet_id, api_key):
        return [{"gid": "1", "title": "August"}]

    result = sync.check_new_tabs_all(conn, "fake-key", list_tabs=fake_list_tabs)

    assert result == {
        "SHEET1": [{"gid": "1", "title": "August"}],
        "SHEET2": [{"gid": "1", "title": "August"}],
    }
