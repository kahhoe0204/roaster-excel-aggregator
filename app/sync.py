from . import mapping as mapping_mod
from . import sheets as sheets_mod


def check_new_tabs(conn, doc, api_key, list_tabs=None):
    list_tabs = list_tabs or sheets_mod.list_tabs
    remote_tabs = list_tabs(doc["spreadsheet_id"], api_key)
    known = mapping_mod.known_tab_gids(conn, doc["id"])
    new_tabs = [t for t in remote_tabs if t["gid"] not in known]
    for t in new_tabs:
        mapping_mod.mark_tab_known(conn, doc["id"], t["gid"], t["title"])
    return new_tabs


def check_new_tabs_all(conn, api_key, list_tabs=None):
    return {
        doc["spreadsheet_id"]: check_new_tabs(conn, doc, api_key, list_tabs=list_tabs)
        for doc in mapping_mod.list_docs(conn)
    }
