# -*- coding: utf-8 -*-
"""Discord role sync for NEWR Adventure: roles mirror the database.

Design:
- Role names are derived purely from DB state, so granting AND removing
  are both safe: anything in the managed set that is not desired gets
  removed, and anything desired that is missing gets added.
- This module never touches roles outside the managed set, and never
  assigns a role at or above the bot's own highest role (Discord would
  reject it anyway; the pre-check just keeps the logs clean).
- All role operations are best-effort: a missing permission (403) is
  logged and skipped, never raised into a command handler. The periodic
  reconciler repairs any drift later.
- Seasons and achievements live in the shared rpg.db. The same DDL is
  repeated in database.py SCHEMA and in the admin bot's db.py (all
  CREATE TABLE IF NOT EXISTS, so the copies can never conflict).

No tokens or credentials live here.
"""
import json
import logging
import time

import discord

import database as db
import friends_db

log = logging.getLogger("rpg.rolesync")

# Season 1 starts at bot launch day: 2026-11-05 00:00 WIB (UTC+7).
SEASON_1_START = 1793811600

# Level roles are milestones only, never one role per level.
LEVEL_MILESTONES = [10, 15, 25, 35, 50]

CLASSES = ["Warrior", "Mage", "Archer", "Assassin"]
STARTER_TIERS = ["Common", "Rare", "Epic", "Legendary"]
# NOTE: there is NO SSS tier in the game today. These are the only tier
# roles; an SSS tier would be a separate game-design change.
ACHIEVEMENT_NAMES = ["Boss Slayer", "War Champion"]

GAME_TABLES = """
CREATE TABLE IF NOT EXISTS announce_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS achievements (
    user_id INTEGER NOT NULL,
    achievement TEXT NOT NULL,
    granted_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, achievement)
);
CREATE TABLE IF NOT EXISTS seasons (
    number INTEGER PRIMARY KEY,
    starts_at INTEGER NOT NULL,
    ended_at INTEGER
);
"""


def ensure_tables(conn):
    """Create seasons/achievements/announce_state + seed Season 1."""
    conn.executescript(GAME_TABLES)
    conn.execute(
        "INSERT INTO seasons (number, starts_at, ended_at) "
        "SELECT 1, ?, NULL WHERE NOT EXISTS (SELECT 1 FROM seasons)",
        (SEASON_1_START,))
    conn.commit()


# ------------------------------------------------------------------ state
def get_state(conn, key):
    row = conn.execute(
        "SELECT value FROM announce_state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_state(conn, key, value):
    conn.execute(
        "INSERT INTO announce_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value))
    conn.commit()


# --------------------------------------------------------------- seasons
def current_season(conn):
    row = conn.execute(
        "SELECT * FROM seasons ORDER BY number DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def season_for_ts(conn, ts):
    """Season active at a registration timestamp.

    Timestamps of 0 (legacy rows) and anything before Season 1 belong
    to Season 1: every player so far joined at launch.
    """
    if ts:
        row = conn.execute(
            "SELECT number FROM seasons WHERE starts_at <= ? "
            "ORDER BY starts_at DESC LIMIT 1", (ts,)).fetchone()
        if row:
            return row[0]
    return 1


def season_role_name(number):
    return f"Season S{number}"


def start_season(conn):
    """Close the current season and open a new one starting now.

    Seasons advance ONLY when an admin starts one, never automatically.
    Returns the new season number.
    """
    now = int(time.time())
    cur = current_season(conn)
    if cur is not None:
        conn.execute("UPDATE seasons SET ended_at = ? WHERE number = ?",
                     (now, cur["number"]))
        new_number = cur["number"] + 1
    else:
        new_number = 1
    conn.execute(
        "INSERT INTO seasons (number, starts_at, ended_at) VALUES (?, ?, NULL)",
        (new_number, now))
    conn.commit()
    return new_number


def list_seasons(conn):
    rows = conn.execute(
        "SELECT * FROM seasons ORDER BY number").fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------ achievements
def grant_achievement(conn, user_id, key):
    """Record an achievement (idempotent). Returns True if newly granted."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO achievements (user_id, achievement, granted_at)"
        " VALUES (?, ?, ?)", (user_id, key, int(time.time())))
    conn.commit()
    return cur.rowcount > 0


def player_achievements(conn, user_id):
    rows = conn.execute(
        "SELECT achievement FROM achievements WHERE user_id = ?",
        (user_id,)).fetchall()
    return [r[0] for r in rows]


# ------------------------------------------------------------ role mapping
def _managed_names(conn):
    """Every role name this sync is allowed to add or remove."""
    names = set(CLASSES)
    names.update(f"Tier {t}" for t in STARTER_TIERS)
    names.update(f"Level {m}" for m in LEVEL_MILESTONES)
    names.update(["Guild Leader", "Guild Member"])
    names.update(ACHIEVEMENT_NAMES)
    names.update(["Top 10 Power", "Top 10 Wealth", "Top 10 Level"])
    for r in conn.execute("SELECT DISTINCT achievement FROM achievements"):
        names.add(r[0])
    for r in conn.execute("SELECT name FROM guilds"):
        names.add(r[0])
    return names


def desired_roles(conn, player, top10=None):
    """Role names a player should currently hold (top-10 optional).

    When top10 is None (immediate syncs after one event), top-10 roles
    are left untouched; the periodic reconciler owns them.
    """
    out = set()
    if player["class"]:
        out.add(player["class"])
    if player.get("starter_tier"):
        out.add(f"Tier {player['starter_tier']}")
    out.add(season_role_name(season_for_ts(conn, player.get("created_at") or 0)))
    reached = [m for m in LEVEL_MILESTONES if player["level"] >= m]
    if reached:
        out.add(f"Level {max(reached)}")
    if player.get("guild_id"):
        g = db.get_guild(conn, player["guild_id"])
        if g:
            out.add(g["name"])
            out.add("Guild Leader" if g["leader_id"] == player["user_id"]
                    else "Guild Member")
    out.update(player_achievements(conn, player["user_id"]))
    if top10 is not None:
        uid = player["user_id"]
        if uid in top10["power"]:
            out.add("Top 10 Power")
        if uid in top10["wealth"]:
            out.add("Top 10 Wealth")
        if uid in top10["level"]:
            out.add("Top 10 Level")
    return out


def compute_top10(conn):
    """Current top-10 user-id sets for power, wealth (gold), level."""
    players = [dict(r) for r in
               conn.execute("SELECT * FROM players").fetchall()]
    by_power = sorted(players,
                      key=lambda p: friends_db.member_power(p),
                      reverse=True)[:10]
    by_wealth = sorted(players, key=lambda p: p["gold"], reverse=True)[:10]
    by_level = sorted(players,
                      key=lambda p: (p["level"], p["exp"]), reverse=True)[:10]
    return {
        "power": {p["user_id"] for p in by_power},
        "wealth": {p["user_id"] for p in by_wealth},
        "level": {p["user_id"] for p in by_level},
    }


# ------------------------------------------------------------ discord ops
async def get_or_create_role(guild, name):
    """Reuse an exact-name match, else create the role (or None)."""
    for role in guild.roles:
        if role.name == name:
            return role
    try:
        return await guild.create_role(name=name,
                                       reason="NEWR Adventure role sync")
    except discord.Forbidden:
        log.warning("Cannot create role %r: missing Manage Roles", name)
    except discord.HTTPException as exc:
        log.warning("Cannot create role %r: %s", name, exc)
    return None


async def sync_member_roles(guild, member, player, conn, top10=None):
    """Grant desired roles, remove stale managed roles. Best-effort."""
    ensure_tables(conn)
    desired = desired_roles(conn, player, top10=top10)
    managed = _managed_names(conn)
    current = {r.name: r for r in member.roles if r.name in managed}
    top_pos = guild.me.top_role.position if guild.me else 0
    for name in sorted(desired - set(current)):
        role = await get_or_create_role(guild, name)
        if role is None or role.position >= top_pos:
            if role is not None:
                log.warning("Role %r sits above the bot role; skipped", name)
            continue
        try:
            await member.add_roles(role, reason="NEWR Adventure role sync")
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Cannot grant role %r: %s", name, exc)
    for name in sorted(set(current) - desired):
        role = current[name]
        if role.position >= top_pos:
            continue
        try:
            await member.remove_roles(role, reason="NEWR Adventure role sync")
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Cannot remove role %r: %s", name, exc)


async def reconcile_guild(guild, conn):
    """Re-sync every registered player (drift repair + top-10).

    Members who left the server are skipped: roles only exist for
    current members, and their DB state is untouched.
    """
    ensure_tables(conn)
    top10 = compute_top10(conn)
    synced = skipped = 0
    for row in conn.execute("SELECT * FROM players").fetchall():
        player = dict(row)
        try:
            member = guild.get_member(player["user_id"])
            if member is None:
                member = await guild.fetch_member(player["user_id"])
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            member = None
        if member is None:
            skipped += 1
            continue
        try:
            await sync_member_roles(guild, member, player, conn, top10=top10)
            synced += 1
        except Exception as exc:  # never break the loop on one member
            log.warning("Reconcile failed for %s: %s", player["user_id"], exc)
            skipped += 1
    log.info("Role reconcile done: %d synced, %d skipped", synced, skipped)
    return synced, skipped


def state_json_load(raw, default):
    try:
        val = json.loads(raw) if raw else default
        return val if isinstance(val, type(default)) else default
    except (ValueError, TypeError):
        return default
