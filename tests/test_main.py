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
    assert resp.json() == {"tabs": [{"gid": "111", "title": "August"}]}


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
    main.mapping.save_mapping(conn, "SHEET1", "Branch A", 0, 0, 1, 31)
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

    resp = client.get("/codes")
    assert resp.status_code == 200
    assert "No codes configured" in resp.text

    resp2 = client.post(
        "/codes", data={"code": "sj", "hours": "12.0"}, follow_redirects=False
    )
    assert resp2.status_code == 303
    assert resp2.headers["location"] == "/codes"

    resp3 = client.get("/codes")
    assert resp3.status_code == 200
    assert "SJ" in resp3.text
    assert "12.0" in resp3.text
