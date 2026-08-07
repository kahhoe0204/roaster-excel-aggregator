import csv
import io
import requests


def fetch_csv(spreadsheet_id, gid, timeout=15):
    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return list(csv.reader(io.StringIO(resp.text)))
