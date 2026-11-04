# -*- coding: utf-8 -*-
"""Database tables owned by the friends / guild-power / leaderboard cogs.

This module ONLY creates its own tables. It never modifies the tables or
functions in database.py; it only imports database (read-only) for the
existing player / guild / item helpers used by the cogs.

Call ensure_tables(conn) once per handler before using any table here.
All timestamps are Unix seconds.
"""
import time

import database as db

SCHEMA = """
CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS friends (
    user_id INTEGER NOT NULL,
    friend_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, friend_id)
);
CREATE TABLE IF NOT EXISTS transfers_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    gold INTEGER NOT NULL DEFAULT 0,
    item_id TEXT,
    qty INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lender_id INTEGER NOT NULL,
    borrower_id INTEGER NOT NULL,
    principal INTEGER NOT NULL,
    interest_pct INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'offered',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS borrows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    borrower_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    fee INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'requested',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS boss_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inviter_id INTEGER NOT NULL,
    invitee_id INTEGER NOT NULL,
    raid_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_invites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    inviter_id INTEGER NOT NULL,
    invitee_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_trophies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    war_id INTEGER NOT NULL UNIQUE,
    awarded_at INTEGER NOT NULL DEFAULT 0
);
"""


def ensure_tables(conn):
    """Create this module's tables if they do not exist yet."""
    conn.executescript(SCHEMA)
    conn.commit()


def now():
    return int(time.time())


# -------------------------------------------------------------- friendship
def is_friend(conn, user_id, other_id):
    row = conn.execute(
        "SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?",
        (user_id, other_id)).fetchone()
    return row is not None


def pending_friend_request(conn, user_id, other_id):
    """Pending request in either direction between the two users, or None."""
    row = conn.execute(
        "SELECT * FROM friend_requests WHERE status = 'pending' AND "
        "((from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?)) "
        "ORDER BY id DESC LIMIT 1",
        (user_id, other_id, other_id, user_id)).fetchone()
    return dict(row) if row else None


def add_friendship(conn, user_id, other_id):
    ts = now()
    conn.execute(
        "INSERT OR IGNORE INTO friends (user_id, friend_id, created_at) "
        "VALUES (?, ?, ?)", (user_id, other_id, ts))
    conn.execute(
        "INSERT OR IGNORE INTO friends (user_id, friend_id, created_at) "
        "VALUES (?, ?, ?)", (other_id, user_id, ts))
    conn.commit()


def remove_friendship(conn, user_id, other_id):
    conn.execute(
        "DELETE FROM friends WHERE (user_id = ? AND friend_id = ?) "
        "OR (user_id = ? AND friend_id = ?)",
        (user_id, other_id, other_id, user_id))
    conn.execute(
        "DELETE FROM friend_requests WHERE "
        "((from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?))",
        (user_id, other_id, other_id, user_id))
    conn.commit()


def friend_ids(conn, user_id):
    rows = conn.execute(
        "SELECT friend_id FROM friends WHERE user_id = ? ORDER BY friend_id",
        (user_id,)).fetchall()
    return [r["friend_id"] for r in rows]


# ------------------------------------------------------------- guild power
def member_power(player):
    """Power contributed by one member: level, stats, and wins."""
    return (player["level"] * 10 + player["atk"] + player["def"]
            + player["wins"] * 5)


def guild_power(conn, guild_id):
    """Total guild power = sum of member power + guild level bonus."""
    guild = db.get_guild(conn, guild_id)
    if not guild:
        return 0, 0
    total = 0
    member_ids = db.guild_member_ids(conn, guild_id)
    for mid in member_ids:
        mp = db.get_player(conn, mid)
        if mp:
            total += member_power(mp)
    total += guild["level"] * 50
    return total, len(member_ids)


# ------------------------------------------------------------ war trophies
def sync_war_trophies(conn):
    """Award one trophy per finished war that has no trophy yet.

    The existing war flow (battle.py) is never modified: this scans wars
    with state='done' and a winner, and records a trophy for each war id
    not yet recorded. Returns the list of newly awarded (guild_id, war_id).
    Call it at the start of guild-power / leaderboard handlers so trophies
    appear shortly after a war resolves.
    """
    rows = conn.execute(
        "SELECT id, guild_a, guild_b, winner_id FROM wars "
        "WHERE state = 'done' AND winner_id IS NOT NULL").fetchall()
    awarded = []
    for war in rows:
        exists = conn.execute(
            "SELECT 1 FROM guild_trophies WHERE war_id = ?",
            (war["id"],)).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO guild_trophies (guild_id, war_id, awarded_at) "
            "VALUES (?, ?, ?)",
            (war["winner_id"], war["id"], now()))
        awarded.append((war["winner_id"], war["id"]))
    if awarded:
        conn.commit()
    return awarded


def guild_trophy_count(conn, guild_id):
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM guild_trophies WHERE guild_id = ?",
        (guild_id,)).fetchone()
    return row["c"]


def latest_trophy(conn, guild_id):
    """Most recent trophy with its war row, or (None, None)."""
    row = conn.execute(
        "SELECT * FROM guild_trophies WHERE guild_id = ? "
        "ORDER BY awarded_at DESC, id DESC LIMIT 1",
        (guild_id,)).fetchone()
    if not row:
        return None, None
    war = conn.execute(
        "SELECT * FROM wars WHERE id = ?", (row["war_id"],)).fetchone()
    return dict(row), (dict(war) if war else None)
