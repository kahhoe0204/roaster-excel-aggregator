from app import csv_fetch


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_fetch_csv_parses_grid(monkeypatch):
    csv_text = "a,b,c\r\n1,2,3\r\n"
    captured = {}

    def fake_get(url, timeout=15):
        captured["url"] = url
        captured["timeout"] = timeout
        return FakeResponse(csv_text)

    monkeypatch.setattr(csv_fetch.requests, "get", fake_get)

    grid = csv_fetch.fetch_csv("SHEET123", "999")

    assert grid == [["a", "b", "c"], ["1", "2", "3"]]
    assert "SHEET123" in captured["url"]
    assert "gid=999" in captured["url"]
    assert "format=csv" in captured["url"]
