from app import sheets


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_list_tabs_returns_gid_and_title(monkeypatch):
    payload = {
        "sheets": [
            {"properties": {"sheetId": 0, "title": "August"}},
            {"properties": {"sheetId": 883413209, "title": "September"}},
        ]
    }
    captured = {}

    def fake_get(url, params=None, timeout=15):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse(payload)

    monkeypatch.setattr(sheets.requests, "get", fake_get)

    tabs = sheets.list_tabs("SHEET123", "fake-api-key")

    assert tabs == [
        {"gid": "0", "title": "August"},
        {"gid": "883413209", "title": "September"},
    ]
    assert captured["params"]["key"] == "fake-api-key"
    assert "SHEET123" in captured["url"]
