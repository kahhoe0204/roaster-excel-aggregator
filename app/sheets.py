import requests


def list_tabs(spreadsheet_id, api_key, timeout=15):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    resp = requests.get(
        url,
        params={"key": api_key, "fields": "sheets.properties"},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return [
        {"gid": str(s["properties"]["sheetId"]), "title": s["properties"]["title"]}
        for s in data.get("sheets", [])
    ]
