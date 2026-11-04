# -*- coding: utf-8 -*-
"""Database tables owned by the /info cog.

This module ONLY creates its own tables. It never modifies the tables or
functions in database.py; it only relies on the existing player / guild
helpers in database.py, which the cog reads through.

Why this table exists: the current raid flow (battle.py) marks a defeated
raid 'done' and rewards participants, but it never records WHO landed
the killing blow. Until the parent adds the hook lines from the /info
report to battle.py, this table stays empty and /info boss says so
plainly instead of inventing history.

Call ensure_tables(conn) once per handler before using any table here.
All timestamps are Unix seconds.
"""
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS boss_kills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss TEXT NOT NULL,
    raid_id INTEGER,
    killer_id INTEGER NOT NULL,
    killer_power INTEGER NOT NULL DEFAULT 0,
    killer_damage INTEGER NOT NULL DEFAULT 0,
    killed_at INTEGER NOT NULL DEFAULT 0
);
"""


def ensure_tables(conn):
    """Create this module's tables if they do not exist yet."""
    conn.executescript(SCHEMA)
    conn.commit()


def now():
    return int(time.time())


def record_boss_kill(conn, boss, raid_id, killer_id, killer_power,
                     killer_damage):
    """Record one boss kill.

    Called from the raid flow (see the hook lines in the /info report):
    boss is the internal boss key, killer_id the player who landed the
    killing blow, killer_power their power at kill time (same formula as
    friends_db.member_power), killer_damage the killing hit's damage.
    """
    ensure_tables(conn)
    conn.execute(
        "INSERT INTO boss_kills (boss, raid_id, killer_id, killer_power,"
        " killer_damage, killed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (boss, raid_id, killer_id, killer_power, killer_damage, now()))
    conn.commit()


def recent_boss_kills(conn, boss=None, limit=10):
    """Latest boss kills, newest first; optionally filtered to one boss."""
    if boss:
        rows = conn.execute(
            "SELECT * FROM boss_kills WHERE boss = ? "
            "ORDER BY killed_at DESC, id DESC LIMIT ?",
            (boss, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM boss_kills ORDER BY killed_at DESC, id DESC "
            "LIMIT ?",
            (limit,)).fetchall()
    return [dict(r) for r in rows]


def boss_kill_count(conn, boss=None):
    """Total recorded kills, optionally for one boss."""
    if boss:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM boss_kills WHERE boss = ?",
            (boss,)).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM boss_kills").fetchone()
    return row["c"]
