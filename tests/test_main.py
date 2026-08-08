import json

from fastapi.testclient import TestClient

from app import auth, config, main


def _client(tmp_path, monkeypatch):
    accounts = tmp_path / "accounts.json"
    accounts.write_text(json.dumps({"manager": auth.hash_password("secret")}))
    monkeypatch.setattr(config, "ACCOUNTS_FILE", str(accounts))
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "roster.db"))
    return TestClient(main.app)


def test_index_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_bad_credentials_rejected(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post(
        "/login", data={"username": "manager", "password": "wrong"}, follow_redirects=False
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login?error=1"

    resp2 = client.get(resp.headers["location"])
    assert resp2.status_code == 200
    assert "Invalid credentials" in resp2.text


def test_login_then_index(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/login", data={"username": "manager", "password": "secret"})
    assert resp.status_code == 200
    assert "Roster Ledger" in resp.text
    # session persists on the client; direct index access now allowed
    assert client.get("/", follow_redirects=False).status_code == 200


def test_api_report_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/report", params={"name": "Alice"})
    assert resp.status_code == 401


def test_api_report_empty_name_returns_empty(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})
    resp = client.get("/api/report")
    assert resp.status_code == 200
    assert resp.json() == {"rows": [], "unmapped": [], "al_dates": []}


def test_api_add_and_delete_al(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    resp = client.post(
        "/api/al", json={"name": "Alice", "date": "2026-09-01", "note": "trip"}
    )
    assert resp.status_code == 200
    assert resp.json()["al_dates"] == [
        {"id": 1, "name": "Alice", "date": "2026-09-01", "note": "trip"}
    ]

    al_id = resp.json()["al_dates"][0]["id"]
    resp2 = client.post(f"/api/al/{al_id}/delete", json={"name": "Alice"})
    assert resp2.status_code == 200
    assert resp2.json()["al_dates"] == []


def test_api_add_al_empty_name_returns_empty(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    resp = client.post("/api/al", json={"name": "", "date": "2026-09-01", "note": "trip"})
    assert resp.status_code == 200
    assert resp.json() == {"al_dates": []}

    # Verify AL date was not persisted by checking a subsequent add with a real name
    resp_alice = client.post(
        "/api/al", json={"name": "Alice", "date": "2026-09-01", "note": "trip"}
    )
    assert resp_alice.status_code == 200
    assert resp_alice.json()["al_dates"] == [
        {"id": 1, "name": "Alice", "date": "2026-09-01", "note": "trip"}
    ]


def test_api_delete_al_empty_name_returns_empty(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    # First add an AL date with a real name
    resp_add = client.post(
        "/api/al", json={"name": "Alice", "date": "2026-09-01", "note": "trip"}
    )
    al_id = resp_add.json()["al_dates"][0]["id"]

    # Try to delete with empty name; should return empty shape and NOT delete the AL date
    resp_delete = client.post(f"/api/al/{al_id}/delete", json={"name": ""})
    assert resp_delete.status_code == 200
    assert resp_delete.json() == {"al_dates": []}

    # Verify AL date was NOT deleted by checking with the real name
    resp_check = client.get("/api/report", params={"name": "Alice"})
    assert resp_check.status_code == 200
    assert len(resp_check.json()["al_dates"]) == 1
    assert resp_check.json()["al_dates"][0]["id"] == al_id
    assert resp_check.json()["al_dates"][0]["date"] == "2026-09-01"


def test_sheets_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/sheets", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_api_sheets_tabs_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/api/sheets/tabs", json={"spreadsheet_id": "SHEET1"})
    assert resp.status_code == 401


def test_api_sheets_tabs_returns_tabs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    monkeypatch.setattr(
        main.sheets, "list_tabs",
        lambda spreadsheet_id, api_key, timeout=15: [{"gid": "111", "title": "August"}],
    )

    resp = client.post("/api/sheets/tabs", json={"spreadsheet_id": "SHEET1"})
    assert resp.status_code == 200
    assert resp.json() == {"tabs": [{"gid": "111", "title": "August", "pattern": "August"}]}


def test_api_sheets_tabs_infers_pattern_per_tab(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    monkeypatch.setattr(
        main.sheets, "list_tabs",
        lambda spreadsheet_id, api_key, timeout=15: [
            {"gid": "1", "title": "JUL 26 PH"},
            {"gid": "2", "title": "AUG 26 PH"},
            {"gid": "3", "title": "AUG 26 OTHER"},
        ],
    )

    resp = client.post("/api/sheets/tabs", json={"spreadsheet_id": "SHEET1"})
    assert resp.status_code == 200
    assert resp.json()["tabs"] == [
        {"gid": "1", "title": "JUL 26 PH", "pattern": "{month} {shortyear} PH"},
        {"gid": "2", "title": "AUG 26 PH", "pattern": "{month} {shortyear} PH"},
        {"gid": "3", "title": "AUG 26 OTHER", "pattern": "{month} {shortyear} OTHER"},
    ]


def test_delete_doc_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sheets/SHEET1/delete")
    assert resp.status_code == 401


def test_delete_doc_removes_it_from_list(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    conn = main.db.init_db(config.DB_PATH)
    main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
    conn.close()

    resp = client.post("/sheets/SHEET1/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/sheets"

    resp2 = client.get("/sheets")
    assert "SHEET1" not in resp2.text


def test_delete_doc_drops_its_own_codes_but_not_other_docs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    conn = main.db.init_db(config.DB_PATH)
    doc_a = main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    doc_b = main.mapping.save_mapping(conn, "SHEET2", "Branch B", 0, 0, 1, 1)
    main.aggregate.set_code_hours(conn, doc_a, "SJ", 12.0)
    main.aggregate.set_code_hours(conn, doc_b, "SJ", 8.0)
    conn.close()

    client.post("/sheets/SHEET1/delete")

    conn = main.db.init_db(config.DB_PATH)
    assert main.aggregate.get_code_hours(conn, doc_a) == {}
    assert main.aggregate.get_code_hours(conn, doc_b) == {"SJ": 8.0}
    conn.close()


def test_set_operation_hours_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/sheets/SHEET1/operation-hours", data={"hours": "12"})
    assert resp.status_code == 401


def test_set_operation_hours_saves_and_redirects(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    conn = main.db.init_db(config.DB_PATH)
    main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
    conn.close()

    resp = client.post(
        "/sheets/SHEET1/operation-hours",
        data={"hours": "10:00 AM - 10:00 PM"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/sheets"

    conn = main.db.init_db(config.DB_PATH)
    assert main.mapping.get_doc(conn, "SHEET1")["operation_hours"] == "10:00 AM - 10:00 PM"
    conn.close()


def test_configure_saves_mapping_and_lists_doc(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    grid = [
        ["", "", "Alice", "Bob"],
        ["1-Aug", "Friday", "9.5", "SJ"],
        ["2-Aug", "Saturday", "FULL", ""],
    ]
    monkeypatch.setattr(main.csv_fetch, "fetch_csv", lambda spreadsheet_id, gid, timeout=15: grid)
    monkeypatch.setattr(
        main.sheets, "list_tabs",
        lambda spreadsheet_id, api_key, timeout=15: [{"gid": "111", "title": "August"}],
    )

    resp = client.get("/sheets")
    assert resp.status_code == 200
    assert "No docs configured" in resp.text

    resp2 = client.post(
        "/sheets/SHEET1/configure",
        data={"gid": "111", "label": "Branch A", "header_row": "0"},
        follow_redirects=False,
    )
    assert resp2.status_code == 303
    assert resp2.headers["location"] == "/sheets"

    resp3 = client.get("/sheets")
    assert resp3.status_code == 200
    assert "Branch A" in resp3.text
    assert "SHEET1" in resp3.text


def test_configure_form_carries_tab_pattern_into_hidden_field(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    grid = [["", "Alice"], ["1-Aug", "9.5"]]
    monkeypatch.setattr(main.csv_fetch, "fetch_csv", lambda spreadsheet_id, gid, timeout=15: grid)

    resp = client.get(
        "/sheets/SHEET1/configure",
        params={"gid": "111", "tab_pattern": "{month} {shortyear} PH"},
    )
    assert resp.status_code == 200
    assert 'value="{month} {shortyear} PH"' in resp.text


def test_configure_submit_persists_tab_pattern(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    grid = [["", "Alice"], ["1-Aug", "9.5"], ["2-Aug", "9.5"]]
    monkeypatch.setattr(main.csv_fetch, "fetch_csv", lambda spreadsheet_id, gid, timeout=15: grid)
    monkeypatch.setattr(
        main.sheets, "list_tabs",
        lambda spreadsheet_id, api_key, timeout=15: [{"gid": "111", "title": "August"}],
    )

    resp = client.post(
        "/sheets/SHEET1/configure",
        data={
            "gid": "111",
            "label": "Branch A",
            "header_row": "0",
            "tab_pattern": "{month} {shortyear} PH",
        },
    )
    assert resp.status_code == 200

    conn = main.db.init_db(config.DB_PATH)
    assert main.mapping.get_doc(conn, "SHEET1")["tab_pattern"] == "{month} {shortyear} PH"
    conn.close()


def test_configure_rejects_ungenerated_date_range(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    grid = [["", "Alice"], ["not-a-date", "9"]]
    monkeypatch.setattr(main.csv_fetch, "fetch_csv", lambda spreadsheet_id, gid, timeout=15: grid)

    resp = client.post(
        "/sheets/SHEET1/configure",
        data={"gid": "111", "label": "Branch A", "header_row": "0"},
    )
    assert resp.status_code == 400


def test_api_sync_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/api/sync")
    assert resp.status_code == 401


def test_api_sync_returns_new_tabs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    conn = main.db.init_db(config.DB_PATH)
    main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31, tab_pattern="August")
    conn.close()

    monkeypatch.setattr(
        main.sync.sheets_mod, "list_tabs",
        lambda spreadsheet_id, api_key, timeout=15: [{"gid": "111", "title": "August"}],
    )

    resp = client.post("/api/sync")
    assert resp.status_code == 200
    assert resp.json() == {"new_tabs": {"SHEET1": [{"gid": "111", "title": "August"}]}}


def test_codes_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/codes", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_codes_page_lists_and_saves(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    conn = main.db.init_db(config.DB_PATH)
    main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    conn.close()

    resp = client.get("/codes")
    assert resp.status_code == 200
    assert "No codes configured" in resp.text
    assert "Branch A" in resp.text

    resp2 = client.post(
        "/codes",
        data={"spreadsheet_id": "SHEET1", "code": "sj", "hours": "12.0"},
        follow_redirects=False,
    )
    assert resp2.status_code == 303
    assert resp2.headers["location"] == "/codes"

    resp3 = client.get("/codes")
    assert resp3.status_code == 200
    assert "SJ" in resp3.text
    assert "12.0" in resp3.text


def test_api_set_code_hours_requires_login(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/api/codes", json={"spreadsheet_id": "SHEET1", "code": "f", "hours": 9.0})
    assert resp.status_code == 401


def test_api_set_code_hours_saves(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    conn = main.db.init_db(config.DB_PATH)
    doc_id = main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 1)
    conn.close()

    resp = client.post("/api/codes", json={"spreadsheet_id": "SHEET1", "code": "f", "hours": 9.0})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    conn = main.db.init_db(config.DB_PATH)
    assert main.aggregate.get_code_hours(conn, doc_id) == {"F": 9.0}
    conn.close()


def test_api_set_code_hours_unknown_spreadsheet_id_404s(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/login", data={"username": "manager", "password": "secret"})

    resp = client.post("/api/codes", json={"spreadsheet_id": "NOPE", "code": "f", "hours": 9.0})
    assert resp.status_code == 404
