-- schema.sql — struktur database bot RPG Adventure (by NEWR LABS).
-- Dibuat dari database.py. Berisi skema SAJA, tanpa data pemain.
-- Dibuat ulang dengan: bash scripts/export_db.sh
CREATE TABLE animals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    animal TEXT NOT NULL,
    last_collect INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE bm_stock (
    date TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty_left INTEGER NOT NULL,
    PRIMARY KEY (date, item_id)
);
CREATE TABLE crops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    crop TEXT NOT NULL,
    planted_at INTEGER NOT NULL DEFAULT 0,
    ready_at INTEGER NOT NULL DEFAULT 0,
    harvested INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE guild_members (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE guild_quest_claims (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    claimed_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, period)
);
CREATE TABLE guild_quest_progress (
    guild_id INTEGER NOT NULL,
    quest_id TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    period TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (guild_id, quest_id)
);
CREATE TABLE guilds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    leader_id INTEGER NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 1,
    equipped INTEGER NOT NULL DEFAULT 0,
    durability INTEGER NOT NULL DEFAULT 100
);
CREATE TABLE jobs_cd (
    user_id INTEGER NOT NULL,
    job TEXT NOT NULL,
    last_work INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, job)
);
CREATE TABLE listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    leader_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE party_members (
    party_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    PRIMARY KEY (party_id, user_id)
);
CREATE TABLE pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    species TEXT NOT NULL,
    name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    gear_weapon TEXT,
    gear_armor TEXT
);
CREATE TABLE players (
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
    last_seen INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE pvp_rank (
    user_id INTEGER PRIMARY KEY,
    points INTEGER NOT NULL DEFAULT 1000,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE quests_progress (
    user_id INTEGER NOT NULL,
    quest_id TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    claimed INTEGER NOT NULL DEFAULT 0,
    progress_date TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, quest_id)
);
CREATE TABLE raid_members (
    raid_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    damage INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (raid_id, user_id)
);
CREATE TABLE raids (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    boss TEXT NOT NULL,
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    state TEXT NOT NULL DEFAULT 'active',
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE ranking_claims (
    user_id INTEGER NOT NULL,
    period TEXT NOT NULL,
    claimed_at INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, period)
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE trades (
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
CREATE TABLE wars (
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
