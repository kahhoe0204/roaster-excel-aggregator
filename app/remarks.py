def set_remark(conn, name, date, note):
    conn.execute(
        """INSERT INTO remarks (name, date, note) VALUES (?, ?, ?)
           ON CONFLICT(name, date) DO UPDATE SET note=excluded.note""",
        (name, date, note),
    )
    conn.commit()


def get_remarks(conn, name):
    """date -> note, for every remark this person has on record."""
    rows = conn.execute(
        "SELECT date, note FROM remarks WHERE name = ?", (name,)
    ).fetchall()
    return {r["date"]: r["note"] for r in rows}
