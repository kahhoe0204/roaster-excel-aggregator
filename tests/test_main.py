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
    resp = client.post("/login", data={"username": "manager", "password": "wrong"})
    assert resp.status_code == 401


def test_login_then_index(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.post("/login", data={"username": "manager", "password": "secret"})
    assert resp.status_code == 200
    assert "Roster report" in resp.text
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
