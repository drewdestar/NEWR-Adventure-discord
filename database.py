# -*- coding: utf-8 -*-
"""Lapisan database SQLite untuk bot RPG.

Satu file database (rpg.db). Semua fungsi menerima path database supaya
test offline bisa memakai database sementara tanpa menyentuh data asli.
Tidak ada token/kredensial di sini.
"""
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    user_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    class TEXT NOT NULL,
    evo_stage INTEGER NOT NULL DEFAULT 0,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    gold INTEGER NOT NULL DEFAULT 100,
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    mp INTEGER NOT NULL,
    max_mp INTEGER NOT NULL,
    atk INTEGER NOT NULL,
    def INTEGER NOT NULL,
    spd INTEGER NOT NULL,
    hunger INTEGER NOT NULL DEFAULT 100,
    thirst INTEGER NOT NULL DEFAULT 100,
    stamina INTEGER NOT NULL DEFAULT 100,
    stamina_date TEXT NOT NULL DEFAULT '',
    last_daily TEXT NOT NULL DEFAULT '',
    streak INTEGER NOT NULL DEFAULT 0,
    vip INTEGER NOT NULL DEFAULT 0,
    vip_until INTEGER NOT NULL DEFAULT 0,
    guild_id INTEGER,
    party_id INTEGER,
    story_chapter INTEGER NOT NULL DEFAULT 0,
    house_level INTEGER NOT NULL DEFAULT 0,
    kills INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    gold_earned INTEGER NOT NULL DEFAULT 0,
    crafts INTEGER NOT NULL DEFAULT 0,
    jobs_done INTEGER NOT NULL DEFAULT 0,
    casino_lost INTEGER NOT NULL DEFAULT 0,
    casino_date TEXT NOT NULL DEFAULT '',
    meteor_date TEXT NOT NULL DEFAULT '',
    starter_tier TEXT NOT NULL DEFAULT 'Common',
    starter_bonus_pct INTEGER NOT NULL DEFAULT 0,
    last_seen INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    equipped INTEGER NOT NULL DEFAULT 0,
    durability INTEGER NOT NULL DEFAULT 100
);
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    species TEXT NOT NULL,
    name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    gear_weapon TEXT,
    gear_armor TEXT
);
CREATE TABLE IF NOT EXISTS guilds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    leader_id INTEGER NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_members (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    leader_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS party_members (
    party_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (party_id, user_id)
);
CREATE TABLE IF NOT EXISTS quests_progress (
    user_id INTEGER NOT NULL,
    quest_id TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    claimed INTEGER NOT NULL DEFAULT 0,
    progress_date TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, quest_id)
);
CREATE TABLE IF NOT EXISTS raids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss TEXT NOT NULL,
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS raid_members (
    raid_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    damage INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (raid_id, user_id)
);
CREATE TABLE IF NOT EXISTS pvp_rank (
    user_id INTEGER PRIMARY KEY,
    points INTEGER NOT NULL DEFAULT 1000,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    offer_item TEXT NOT NULL,
    offer_qty INTEGER NOT NULL,
    want_item TEXT NOT NULL,
    want_qty INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS wars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_a INTEGER NOT NULL,
    guild_b INTEGER NOT NULL,
    declarer_id INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    score_a INTEGER NOT NULL DEFAULT 0,
    score_b INTEGER NOT NULL DEFAULT 0,
    winner_id INTEGER,
    resolves_at INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    crop TEXT NOT NULL,
    planted_at INTEGER NOT NULL DEFAULT 0,
    ready_at INTEGER NOT NULL DEFAULT 0,
    harvested INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS animals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    animal TEXT NOT NULL,
    last_collect INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS jobs_cd (
    user_id INTEGER NOT NULL,
    job TEXT NOT NULL,
    last_work INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, job)
);
CREATE TABLE IF NOT EXISTS bm_stock (
    date TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty_left INTEGER NOT NULL,
    PRIMARY KEY (date, item_id)
);
CREATE TABLE IF NOT EXISTS guild_quest_progress (
    guild_id INTEGER NOT NULL,
    quest_id TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    period TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (guild_id, quest_id)
);
CREATE TABLE IF NOT EXISTS guild_quest_claims (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    claimed_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, period)
);
CREATE TABLE IF NOT EXISTS ranking_claims (
    user_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    claimed_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, period)
);
CREATE TABLE IF NOT EXISTS user_prefs (
    user_id INTEGER PRIMARY KEY,
    language TEXT NOT NULL DEFAULT 'en'
);
CREATE TABLE IF NOT EXISTS translations_cache (
    source TEXT NOT NULL,
    lang TEXT NOT NULL,
    translated TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    PRIMARY KEY (source, lang)
);
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

PLAYER_COLUMNS = [
    "user_id", "name", "class", "evo_stage", "level", "exp", "gold",
    "hp", "max_hp", "mp", "max_mp", "atk", "def", "spd", "hunger",
    "thirst", "stamina", "stamina_date", "last_daily", "streak", "vip",
    "vip_until", "guild_id", "party_id", "story_chapter", "house_level",
    "kills", "wins", "gold_earned", "crafts", "jobs_done", "casino_lost",
    "casino_date", "meteor_date", "starter_tier", "starter_bonus_pct",
    "last_seen", "created_at",
]


def connect(db_path):
    """Buka koneksi dan pastikan schema ada."""
    path = Path(db_path)
    if path.parent and str(path.parent):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Migration for databases created before the starter-tier columns
    # existed: CREATE TABLE IF NOT EXISTS never adds columns, so add
    # them explicitly. Existing players keep their stats untouched.
    _cols = {r[1] for r in conn.execute("PRAGMA table_info(players)")}
    if "starter_tier" not in _cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN starter_tier TEXT NOT NULL DEFAULT 'Common'")
    if "starter_bonus_pct" not in _cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN starter_bonus_pct INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    return conn


def row_to_dict(row):
    return dict(row) if row is not None else None


def get_player(conn, user_id):
    row = conn.execute(
        "SELECT * FROM players WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row_to_dict(row)


def save_player(conn, player):
    """Simpan dict player (harus berisi semua kolom)."""
    cols = [c for c in PLAYER_COLUMNS if c in player]
    sets = ", ".join(f"{c} = ?" for c in cols)
    vals = [player[c] for c in cols] + [player["user_id"]]
    conn.execute(f"UPDATE players SET {sets} WHERE user_id = ?", vals)
    conn.commit()


def create_player(conn, user_id, name, cls, stats, starter_tier="Common",
                  starter_bonus_pct=0):
    now = int(time.time())
    conn.execute(
        """INSERT INTO players (user_id, name, class, hp, max_hp, mp, max_mp,
               atk, def, spd, starter_tier, starter_bonus_pct,
               last_seen, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, cls, stats["hp"], stats["hp"], stats["mp"],
         stats["mp"], stats["atk"], stats["def"], stats["spd"],
         starter_tier, starter_bonus_pct, now, now),
    )
    conn.commit()
    return get_player(conn, user_id)


# ------------------------------------------------------------- inventory
def get_inventory(conn, user_id):
    rows = conn.execute(
        "SELECT * FROM inventory WHERE user_id = ? ORDER BY item_id",
        (user_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def item_qty(conn, user_id, item_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(qty), 0) AS q FROM inventory "
        "WHERE user_id = ? AND item_id = ?",
        (user_id, item_id),
    ).fetchone()
    return row["q"]


def add_item(conn, user_id, item_id, qty=1, durability=100):
    row = conn.execute(
        "SELECT * FROM inventory WHERE user_id = ? AND item_id = ? "
        "AND equipped = 0 ORDER BY id LIMIT 1",
        (user_id, item_id),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE inventory SET qty = qty + ? WHERE id = ?",
            (qty, row["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO inventory (user_id, item_id, qty, durability) "
            "VALUES (?, ?, ?, ?)",
            (user_id, item_id, qty, durability),
        )
    conn.commit()


def remove_item(conn, user_id, item_id, qty=1):
    """Kembalikan True kalau berhasil, False kalau stok kurang."""
    rows = conn.execute(
        "SELECT * FROM inventory WHERE user_id = ? AND item_id = ? "
        "ORDER BY equipped ASC, id",
        (user_id, item_id),
    ).fetchall()
    total = sum(r["qty"] for r in rows)
    if total < qty:
        return False
    remaining = qty
    for r in rows:
        if remaining <= 0:
            break
        take = min(r["qty"], remaining)
        if r["qty"] - take <= 0:
            conn.execute("DELETE FROM inventory WHERE id = ?", (r["id"],))
        else:
            conn.execute(
                "UPDATE inventory SET qty = qty - ? WHERE id = ?",
                (take, r["id"]),
            )
        remaining -= take
    conn.commit()
    return True


def equipped_items(conn, user_id):
    rows = conn.execute(
        "SELECT * FROM inventory WHERE user_id = ? AND equipped = 1",
        (user_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def set_equipped(conn, inv_id, equipped):
    conn.execute(
        "UPDATE inventory SET equipped = ? WHERE id = ?", (equipped, inv_id)
    )
    conn.commit()


# ------------------------------------------------------------------ pets
def get_pets(conn, user_id):
    rows = conn.execute(
        "SELECT * FROM pets WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()
    return [row_to_dict(r) for r in rows]


def add_pet(conn, user_id, species, name):
    conn.execute(
        "INSERT INTO pets (user_id, species, name) VALUES (?, ?, ?)",
        (user_id, species, name),
    )
    conn.commit()


def save_pet(conn, pet):
    conn.execute(
        "UPDATE pets SET level = ?, exp = ?, gear_weapon = ?, gear_armor = ? "
        "WHERE id = ?",
        (pet["level"], pet["exp"], pet["gear_weapon"], pet["gear_armor"],
         pet["id"]),
    )
    conn.commit()


# ---------------------------------------------------------------- quests
def quest_row(conn, user_id, quest_id):
    row = conn.execute(
        "SELECT * FROM quests_progress WHERE user_id = ? AND quest_id = ?",
        (user_id, quest_id),
    ).fetchone()
    return row_to_dict(row)


def bump_quest(conn, user_id, quest_id, amount, period_date=""):
    """Tambah progress quest (buat baris kalau belum ada)."""
    row = quest_row(conn, user_id, quest_id)
    if row is None:
        conn.execute(
            "INSERT INTO quests_progress (user_id, quest_id, progress, progress_date)"
            " VALUES (?, ?, ?, ?)",
            (user_id, quest_id, amount, period_date),
        )
    else:
        # Quest harian: kalau tanggal sudah beda, progress di-reset.
        if period_date and row["progress_date"] not in ("", period_date):
            conn.execute(
                "UPDATE quests_progress SET progress = ?, progress_date = ? "
                "WHERE user_id = ? AND quest_id = ?",
                (amount, period_date, user_id, quest_id),
            )
        else:
            conn.execute(
                "UPDATE quests_progress SET progress = progress + ?, progress_date = ? "
                "WHERE user_id = ? AND quest_id = ?",
                (amount, period_date or row["progress_date"], user_id, quest_id),
            )
    conn.commit()


def claim_quest(conn, user_id, quest_id):
    conn.execute(
        "UPDATE quests_progress SET claimed = 1 WHERE user_id = ? AND quest_id = ?",
        (user_id, quest_id),
    )
    conn.commit()


# ------------------------------------------------------------------ guild
def get_guild(conn, guild_id):
    row = conn.execute(
        "SELECT * FROM guilds WHERE id = ?", (guild_id,)
    ).fetchone()
    return row_to_dict(row)


def get_guild_by_name(conn, name):
    row = conn.execute(
        "SELECT * FROM guilds WHERE LOWER(name) = LOWER(?)", (name,)
    ).fetchone()
    return row_to_dict(row)


def guild_member_count(conn, guild_id):
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM guild_members WHERE guild_id = ?",
        (guild_id,),
    ).fetchone()
    return row["c"]


def guild_member_ids(conn, guild_id):
    rows = conn.execute(
        "SELECT user_id FROM guild_members WHERE guild_id = ?", (guild_id,)
    ).fetchall()
    return [r["user_id"] for r in rows]


# ------------------------------------------------------------------- raid
def active_raid(conn):
    row = conn.execute(
        "SELECT * FROM raids WHERE state = 'active' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row_to_dict(row)


def raid_members(conn, raid_id):
    rows = conn.execute(
        "SELECT * FROM raid_members WHERE raid_id = ? ORDER BY damage DESC",
        (raid_id,),
    ).fetchall()
    return [row_to_dict(r) for r in rows]


# -------------------------------------------------------------------- pvp
def pvp_row(conn, user_id):
    row = conn.execute(
        "SELECT * FROM pvp_rank WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO pvp_rank (user_id) VALUES (?)", (user_id,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM pvp_rank WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row_to_dict(row)


def save_pvp(conn, row):
    conn.execute(
        "UPDATE pvp_rank SET points = ?, wins = ?, losses = ? WHERE user_id = ?",
        (row["points"], row["wins"], row["losses"], row["user_id"]),
    )
    conn.commit()
