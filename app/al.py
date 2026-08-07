def add_al_date(conn, name, date, note=""):
    conn.execute(
        """INSERT INTO al_dates (name, date, note) VALUES (?, ?, ?)
           ON CONFLICT(name, date) DO UPDATE SET note=excluded.note""",
        (name, date, note),
    )
    conn.commit()


def list_al_dates(conn, name):
    rows = conn.execute(
        "SELECT id, name, date, note FROM al_dates WHERE name = ? ORDER BY date",
        (name,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_al_date(conn, id):
    conn.execute("DELETE FROM al_dates WHERE id = ?", (id,))
    conn.commit()
