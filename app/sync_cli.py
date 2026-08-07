from . import config, db, sync


def main():
    conn = db.init_db(config.DB_PATH)
    result = sync.check_new_tabs_all(conn, config.GOOGLE_API_KEY)
    total = sum(len(v) for v in result.values())
    print(f"Sync complete: {total} new tab(s) found.")
    for spreadsheet_id, new_tabs in result.items():
        for t in new_tabs:
            print(f"  {spreadsheet_id}: {t['title']} ({t['gid']})")


if __name__ == "__main__":
    main()
