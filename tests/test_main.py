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
