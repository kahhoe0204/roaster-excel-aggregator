import pytest

from app import mapping


def configure_doc(conn, spreadsheet_id, label, header_row, date_col, row_start, row_end,
                   gid="111", title="August", tab_pattern=None):
    """Create a doc and fully configure one of its tabs in one call — most
    tests just need "a doc with a working tab" and don't care that
    header_row/date_col live on the tab, not the doc."""
    doc_id = mapping.save_mapping(conn, spreadsheet_id, label, tab_pattern=tab_pattern)
    mapping.mark_tab_known(conn, doc_id, gid, title)
    mapping.configure_tab(conn, doc_id, gid, header_row, date_col, row_start, row_end)
    return doc_id


@pytest.fixture(autouse=True)
def _no_leaked_env(monkeypatch):
    """Importing app.main runs load_dotenv(override=True), which leaks real
    secrets from .env into the test process: TURSO_DATABASE_URL/TOKEN route
    unrelated tests (test_db.py, test_al.py, ...) to the real remote database
    instead of their tmp_path sqlite file, and ACCOUNTS_JSON shadows the
    per-test accounts file set up in tests/test_main.py's _client() fixture.
    Strip them for every test regardless of what app code does at import
    time — config.* values are read into module constants at import and are
    unaffected (tests already override those directly), but these three are
    read from os.environ at call time."""
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("TURSO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ACCOUNTS_JSON", raising=False)
