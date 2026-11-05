# -*- coding: utf-8 -*-
# NEWR Adventure by NEWR LABS — credit marker, do not remove.
"""Data statis game RPG NEWR LABS.

Semua angka sengaja sederhana dan konsisten. Kalau mau rebalance, ubah di sini
saja, jangan ubah rumus di logic.py.
"""

CREDIT = "by NEWR LABS"

# ---------------------------------------------------------------- kelas
CLASSES = {
    "Warrior":  {"hp": 120, "mp": 30,  "atk": 14, "def": 10, "spd": 6,  "skill": "Tebasan Baja",      "skill_mult": 1.8},
    "Mage":     {"hp": 80,  "mp": 120, "atk": 18, "def": 5,  "spd": 7,  "skill": "Ledakan Api",       "skill_mult": 2.2},
    "Archer":   {"hp": 95,  "mp": 60,  "atk": 15, "def": 7,  "spd": 12, "skill": "Panah Beruntun",    "skill_mult": 1.9},
    "Assassin": {"hp": 90,  "mp": 50,  "atk": 17, "def": 6,  "spd": 15, "skill": "Tusukan Bayangan",  "skill_mult": 2.0},
    "Cleric":   {"hp": 100, "mp": 100, "atk": 11, "def": 9,  "spd": 7,  "skill": "Cahaya Suci",       "skill_mult": 1.7},
    "Berserker":{"hp": 140, "mp": 20,  "atk": 19, "def": 6,  "spd": 8,  "skill": "Amukan Liar",       "skill_mult": 2.1},
    "Summoner": {"hp": 85,  "mp": 130, "atk": 16, "def": 5,  "spd": 6,  "skill": "Panggil Roh",       "skill_mult": 2.0},
    "Bard":     {"hp": 90,  "mp": 80,  "atk": 12, "def": 8,  "spd": 10, "skill": "Lagu Perang",       "skill_mult": 1.6},
    "Samurai":  {"hp": 110, "mp": 40,  "atk": 16, "def": 9,  "spd": 11, "skill": "Tebasan Kilat",     "skill_mult": 1.9},
    "Druid":    {"hp": 105, "mp": 90,  "atk": 13, "def": 8,  "spd": 8,  "skill": "Akar Berduri",      "skill_mult": 1.8},
}

# Starter tiers for /register (rolled once per new player, never re-rolled).
# (tier name, probability %, min bonus %, max bonus %, bonus items)
# Bonus % is rolled per player inside the tier range and applied to
# hp/mp/atk/def/spd on top of the class base. The class skill never
# changes; only power is randomised. Tier names stay English.
STARTER_TIERS = [
    ("Common",    60,  0,  5, {}),
    ("Rare",      25,  5, 12, {"potion kecil": 1}),
    ("Epic",      11, 12, 20, {"potion kecil": 2}),
    ("Legendary",  4, 20, 30, {"potion kecil": 2, "potion besar": 1}),
]

# ---------------------------------------------------------------- tier
# ONE unified content tier scheme, reused everywhere (quests, areas,
# monsters, bosses, shop/gacha pools): Common < Rare < Epic < Legendary.
# This is the same scheme as STARTER_TIERS / GACHA_POOL, not a third
# scheme. Guild tiers (Bronze..Diamond) stay separate: they rank guilds,
# not content. Tier is a label + unlock band; it never rebalances
# existing monsters/items (their stats are kept exactly as before).
CONTENT_TIERS = ["Common", "Rare", "Epic", "Legendary"]
CONTENT_TIER_MIN_LEVEL = {"Common": 1, "Rare": 10, "Epic": 20, "Legendary": 30}

# Story shown FIRST on every /register, before the starter roll result.
# REGISTER_PROLOGUE is shared; REGISTER_STORIES adds one opening line
# per class. Existing players never see it again (register rejects them).
REGISTER_PROLOGUE = (
    "Long ago, the NEWR world broke apart. Monsters roam the wilds, "
    "guilds guard the last towns, and a forgotten hero is prophesied "
    "to rise from Beginner Forest. That hero is you."
)
REGISTER_STORIES = {
    "Warrior": "You pick up a battered sword at the forest edge. Its weight feels familiar, like an old promise.",
    "Mage": "A spark jumps from your fingertips before you even try. The old man's eyes widen — you were born for this.",
    "Archer": "Your first arrow splits a falling leaf in mid-air. The forest goes quiet, as if it is watching.",
    "Assassin": "You move without a sound through the trees. Even the rabbits do not notice you until you choose to be seen.",
    "Cleric": "A soft light gathers around your hands and mends a wounded bird. The bird follows you, unafraid.",
    "Berserker": "Your blood sings when danger is near. You grin at the growl in the dark — and walk toward it.",
    "Summoner": "A small spirit flickers into being beside you, curious and loyal. It has been waiting for you.",
    "Bard": "Your song makes the tired travellers stand taller. Even the monsters pause to listen, just for a moment.",
    "Samurai": "You bow to the rising sun, blade steady. Honour is not a word to you — it is the way you walk.",
    "Druid": "Vines curl gently around your wrist like an old friend. The forest itself seems to welcome you home.",
}

# (kelas_awal, tahap) -> (nama_evolusi, level_minimal, bonus)
# tahap 0 = kelas awal, tahap 1 = evolusi pertama, tahap 2 = evolusi akhir.
EVOLUTIONS = {
    ("Warrior", 1):  ("Knight", 15, {"hp": 40, "mp": 10, "atk": 6, "def": 5, "spd": 1}),
    ("Warrior", 2):  ("Paladin", 35, {"hp": 60, "mp": 20, "atk": 9, "def": 8, "spd": 2}),
    ("Mage", 1):     ("Wizard", 15, {"hp": 25, "mp": 40, "atk": 8, "def": 2, "spd": 2}),
    ("Mage", 2):     ("Archmage", 35, {"hp": 40, "mp": 60, "atk": 12, "def": 3, "spd": 3}),
    ("Archer", 1):   ("Ranger", 15, {"hp": 30, "mp": 15, "atk": 7, "def": 3, "spd": 4}),
    ("Archer", 2):   ("Sharpshooter", 35, {"hp": 45, "mp": 20, "atk": 11, "def": 4, "spd": 6}),
    ("Assassin", 1): ("Shadow", 15, {"hp": 30, "mp": 15, "atk": 8, "def": 3, "spd": 5}),
    ("Assassin", 2): ("Nightblade", 35, {"hp": 45, "mp": 25, "atk": 12, "def": 4, "spd": 7}),
    ("Cleric", 1):   ("Priest", 15, {"hp": 35, "mp": 35, "atk": 5, "def": 4, "spd": 2}),
    ("Cleric", 2):   ("Saint", 35, {"hp": 55, "mp": 55, "atk": 8, "def": 6, "spd": 3}),
    ("Berserker", 1):("Ravager", 15, {"hp": 50, "mp": 5, "atk": 8, "def": 3, "spd": 3}),
    ("Berserker", 2):("Warlord", 35, {"hp": 70, "mp": 10, "atk": 12, "def": 5, "spd": 4}),
    ("Summoner", 1): ("Conjurer", 15, {"hp": 25, "mp": 45, "atk": 8, "def": 2, "spd": 2}),
    ("Summoner", 2): ("Grand Summoner", 35, {"hp": 40, "mp": 65, "atk": 12, "def": 3, "spd": 3}),
    ("Bard", 1):     ("Minstrel", 15, {"hp": 30, "mp": 20, "atk": 6, "def": 4, "spd": 4}),
    ("Bard", 2):     ("Maestro", 35, {"hp": 45, "mp": 30, "atk": 9, "def": 6, "spd": 6}),
    ("Samurai", 1):  ("Ronin", 15, {"hp": 35, "mp": 10, "atk": 8, "def": 4, "spd": 4}),
    ("Samurai", 2):  ("Shogun", 35, {"hp": 55, "mp": 15, "atk": 12, "def": 6, "spd": 6}),
    ("Druid", 1):    ("Warden", 15, {"hp": 35, "mp": 25, "atk": 7, "def": 4, "spd": 3}),
    ("Druid", 2):    ("Archdruid", 35, {"hp": 50, "mp": 40, "atk": 11, "def": 6, "spd": 4}),
}

# ---------------------------------------------------------------- area
AREAS = {
    "Hutan Pemula":     {"min_level": 1,  "tier": "Common",    "monsters": ["Slime Hijau", "Kelinci Liar", "Goblin Kecil"]},
    "Gua Gelap":        {"min_level": 5,  "tier": "Common",    "monsters": ["Kelelawar Gua", "Skeleton", "Laba-laba Raksasa"]},
    "Gunung Berapi":    {"min_level": 12, "tier": "Rare",      "monsters": ["Golem Lava", "Salamander Api", "Kadal Magma"]},
    "Kastil Kegelapan": {"min_level": 20, "tier": "Epic",      "monsters": ["Ksatria Hitam", "Penyihir Gelap", "Gargoyle"]},
    "Langit Terlarang": {"min_level": 30, "tier": "Legendary", "monsters": ["Naga Langit", "Phoenix Bayangan", "Raksasa Awan"]},
    "Desa Tenang":      {"min_level": 1,  "tier": "Common",    "monsters": ["Ayam Liar", "Tikus Ladang", "Kupu-kupu Raksasa"]},
    "Pantai Karang":    {"min_level": 8,  "tier": "Common",    "monsters": ["Kepiting Raksasa", "Ubur-ubur Listrik", "Penyu Karang"]},
    "Hutan Beracun":    {"min_level": 14, "tier": "Rare",      "monsters": ["Jamur Beracun", "Ular Berbisa", "Katak Racun"]},
    "Gurun Pasir":      {"min_level": 18, "tier": "Rare",      "monsters": ["Kalajengking Pasir", "Mumi Kuno", "Cacing Gurun"]},
    "Pegunungan Salju": {"min_level": 24, "tier": "Epic",      "monsters": ["Serigala Salju", "Yeti Muda", "Roh Es"]},
    "Menara Void":      {"min_level": 38, "tier": "Legendary", "monsters": ["Mata Void", "Bayangan Void", "Naga Void"]},
}

MONSTERS = {
    "Slime Hijau":      {"hp": 40,  "atk": 6,  "def": 2,  "exp": 25,  "gold": (8, 20),   "loot": ["lendir slime", "potion kecil"], "tier": "Common"},
    "Kelinci Liar":     {"hp": 30,  "atk": 5,  "def": 1,  "exp": 20,  "gold": (5, 15),   "loot": ["daging", "bulu kelinci"], "tier": "Common"},
    "Goblin Kecil":     {"hp": 55,  "atk": 8,  "def": 3,  "exp": 35,  "gold": (10, 25),  "loot": ["koin goblin", "pedang kayu"], "tier": "Common"},
    "Kelelawar Gua":    {"hp": 70,  "atk": 11, "def": 4,  "exp": 50,  "gold": (15, 35),  "loot": ["sayap kelelawar", "potion kecil"], "tier": "Common"},
    "Skeleton":         {"hp": 90,  "atk": 13, "def": 5,  "exp": 65,  "gold": (20, 45),  "loot": ["tulang", "armor kulit"], "tier": "Common"},
    "Laba-laba Raksasa":{"hp": 100, "atk": 14, "def": 5,  "exp": 70,  "gold": (20, 50),  "loot": ["jaring laba-laba", "bisa laba-laba"], "tier": "Common"},
    "Golem Lava":       {"hp": 160, "atk": 20, "def": 10, "exp": 110, "gold": (35, 70),  "loot": ["batu lava", "bijih besi"], "tier": "Rare"},
    "Salamander Api":   {"hp": 140, "atk": 22, "def": 8,  "exp": 120, "gold": (40, 80),  "loot": ["sisik api", "kristal api"], "tier": "Rare"},
    "Kadal Magma":      {"hp": 150, "atk": 21, "def": 9,  "exp": 115, "gold": (35, 75),  "loot": ["kulit magma", "batu lava"], "tier": "Rare"},
    "Ksatria Hitam":    {"hp": 240, "atk": 30, "def": 15, "exp": 180, "gold": (60, 120), "loot": ["pedang hitam", "armor baja"], "tier": "Epic"},
    "Penyihir Gelap":   {"hp": 210, "atk": 34, "def": 10, "exp": 190, "gold": (65, 130), "loot": ["tongkat gelap", "kristal api"], "tier": "Epic"},
    "Gargoyle":         {"hp": 260, "atk": 28, "def": 18, "exp": 200, "gold": (70, 140), "loot": ["batu gargoyle", "armor baja"], "tier": "Epic"},
    "Naga Langit":      {"hp": 400, "atk": 45, "def": 22, "exp": 320, "gold": (120, 250),"loot": ["sisik naga", "pedang naga"], "tier": "Legendary"},
    "Phoenix Bayangan": {"hp": 360, "atk": 48, "def": 18, "exp": 330, "gold": (130, 260),"loot": ["bulu phoenix", "tongkat phoenix"], "tier": "Legendary"},
    "Raksasa Awan":     {"hp": 450, "atk": 42, "def": 25, "exp": 350, "gold": (140, 280),"loot": ["awan padat", "armor langit"], "tier": "Legendary"},
    "Ayam Liar":        {"hp": 25,  "atk": 4,  "def": 1,  "exp": 15,  "gold": (4, 12),   "loot": ["daging", "telur ayam"], "tier": "Common"},
    "Tikus Ladang":     {"hp": 35,  "atk": 6,  "def": 2,  "exp": 22,  "gold": (6, 16),   "loot": ["daging", "kayu"], "tier": "Common"},
    "Kupu-kupu Raksasa":{"hp": 45,  "atk": 7,  "def": 2,  "exp": 30,  "gold": (8, 20),   "loot": ["bulu kupu", "potion kecil"], "tier": "Common"},
    "Kepiting Raksasa": {"hp": 80,  "atk": 12, "def": 8,  "exp": 55,  "gold": (15, 35),  "loot": ["cangkang karang", "daging"], "tier": "Common"},
    "Ubur-ubur Listrik":{"hp": 75,  "atk": 15, "def": 3,  "exp": 60,  "gold": (18, 40),  "loot": ["cangkang karang", "potion kecil"], "tier": "Common"},
    "Penyu Karang":     {"hp": 110, "atk": 10, "def": 12, "exp": 65,  "gold": (20, 45),  "loot": ["cangkang karang", "armor kulit"], "tier": "Common"},
    "Jamur Beracun":    {"hp": 120, "atk": 18, "def": 6,  "exp": 95,  "gold": (30, 60),  "loot": ["racun ular", "sup jamur"], "tier": "Rare"},
    "Ular Berbisa":     {"hp": 130, "atk": 24, "def": 7,  "exp": 105, "gold": (35, 70),  "loot": ["racun ular", "kulit monster"], "tier": "Rare"},
    "Katak Racun":      {"hp": 110, "atk": 20, "def": 5,  "exp": 90,  "gold": (28, 55),  "loot": ["racun ular", "lendir slime"], "tier": "Rare"},
    "Kalajengking Pasir":{"hp": 150, "atk": 23, "def": 9,  "exp": 115, "gold": (35, 75), "loot": ["racun ular", "bijih besi"], "tier": "Rare"},
    "Mumi Kuno":        {"hp": 190, "atk": 26, "def": 12, "exp": 140, "gold": (50, 100), "loot": ["tulang", "koin goblin"], "tier": "Rare"},
    "Cacing Gurun":     {"hp": 220, "atk": 24, "def": 8,  "exp": 150, "gold": (55, 110), "loot": ["kulit monster", "batu lava"], "tier": "Rare"},
    "Serigala Salju":   {"hp": 250, "atk": 32, "def": 14, "exp": 190, "gold": (65, 130), "loot": ["bulu salju", "daging"], "tier": "Epic"},
    "Yeti Muda":        {"hp": 300, "atk": 34, "def": 16, "exp": 210, "gold": (70, 140), "loot": ["bulu salju", "armor kulit kuat"], "tier": "Epic"},
    "Roh Es":           {"hp": 230, "atk": 38, "def": 10, "exp": 200, "gold": (70, 140), "loot": ["sisik es", "kristal api"], "tier": "Epic"},
    "Mata Void":        {"hp": 420, "atk": 48, "def": 20, "exp": 340, "gold": (130, 260),"loot": ["pasir void", "kristal void"], "tier": "Legendary"},
    "Bayangan Void":    {"hp": 460, "atk": 52, "def": 18, "exp": 360, "gold": (140, 280),"loot": ["pasir void", "belati bayangan"], "tier": "Legendary"},
    "Naga Void":        {"hp": 600, "atk": 58, "def": 28, "exp": 450, "gold": (180, 350),"loot": ["pasir void", "sisik naga"], "tier": "Legendary"},
}

# ---------------------------------------------------------------- item
# type: weapon | armor | potion | material | seed | petgear | food | rare | misc
ITEMS = {
    # senjata
    "pedang kayu":    {"type": "weapon", "atk": 3,  "price": 50},
    "pedang besi":    {"type": "weapon", "atk": 8,  "price": 250},
    "pedang baja":    {"type": "weapon", "atk": 14, "price": 600},
    "pedang hitam":   {"type": "weapon", "atk": 20, "price": 1200},
    "pedang naga":    {"type": "weapon", "atk": 30, "price": 3000},
    "tongkat kayu":   {"type": "weapon", "atk": 4,  "price": 60},
    "tongkat api":    {"type": "weapon", "atk": 12, "price": 500},
    "tongkat gelap":  {"type": "weapon", "atk": 19, "price": 1100},
    "tongkat phoenix":{"type": "weapon", "atk": 29, "price": 2800},
    "busur kayu":     {"type": "weapon", "atk": 4,  "price": 60},
    "busur elang":    {"type": "weapon", "atk": 13, "price": 550},
    "belati kayu":    {"type": "weapon", "atk": 4,  "price": 60},
    "belati bayangan":{"type": "weapon", "atk": 16, "price": 800},
    # armor
    "armor kulit":    {"type": "armor", "def": 3,  "price": 50},
    "armor kulit kuat":{"type": "armor", "def": 7,  "price": 280},
    "armor baja":     {"type": "armor", "def": 12, "price": 650},
    "armor langit":   {"type": "armor", "def": 20, "price": 2500},
    # potion & makanan
    "potion kecil":   {"type": "potion", "heal": 50,  "price": 30},
    "potion besar":   {"type": "potion", "heal": 150, "price": 90},
    "elixir":         {"type": "potion", "heal": 9999, "price": 300, "mp": 9999},
    "roti":           {"type": "food", "hunger": 30, "price": 20},
    "daging panggang":{"type": "food", "hunger": 50, "price": 45},
    "air minum":      {"type": "food", "thirst": 40, "price": 15},
    "jus buah":       {"type": "food", "thirst": 60, "hunger": 10, "price": 35},
    "telur ayam":     {"type": "food", "hunger": 15, "price": 10},
    "susu":           {"type": "food", "thirst": 20, "hunger": 10, "price": 15},
    # material
    "kayu":           {"type": "material", "price": 10},
    "bijih besi":     {"type": "material", "price": 25},
    "kulit monster":  {"type": "material", "price": 20},
    "daging":         {"type": "material", "price": 15},
    "lendir slime":   {"type": "material", "price": 8},
    "tulang":         {"type": "material", "price": 18},
    "batu lava":      {"type": "material", "price": 40},
    "kristal api":    {"type": "material", "price": 80},
    "sisik api":      {"type": "material", "price": 70},
    "bulu elang":     {"type": "material", "price": 45},
    "bulu kelinci":   {"type": "material", "price": 12},
    "koin goblin":    {"type": "material", "price": 30},
    "sayap kelelawar":{"type": "material", "price": 22},
    "jaring laba-laba":{"type": "material", "price": 28},
    "bisa laba-laba": {"type": "material", "price": 35},
    "kulit magma":    {"type": "material", "price": 60},
    "batu gargoyle":  {"type": "material", "price": 90},
    "sisik naga":     {"type": "material", "price": 200},
    "bulu phoenix":   {"type": "material", "price": 220},
    "awan padat":     {"type": "material", "price": 180},
    # benih
    "benih gandum":   {"type": "seed", "crop": "gandum", "grow_minutes": 60,  "price": 25},
    "benih tomat":    {"type": "seed", "crop": "tomat",  "grow_minutes": 120, "price": 40},
    "benih labu":     {"type": "seed", "crop": "labu",   "grow_minutes": 240, "price": 70},
    # pet gear
    "kalung pet":     {"type": "petgear", "atk": 3, "price": 150},
    "zirah pet":      {"type": "petgear", "def": 4, "price": 200},
    "mahkota pet":    {"type": "petgear", "atk": 6, "def": 3, "price": 500},
    # langka (black market / gacha / event)
    "jimat keberuntungan": {"type": "rare", "price": 1500},
    "kristal void":   {"type": "rare", "price": 2500},
    "telur naga":     {"type": "rare", "price": 5000},
    "topi labu":      {"type": "rare", "price": 800},
    "tongkat permen": {"type": "weapon", "atk": 18, "price": 1000},
    "lonceng tahun baru": {"type": "rare", "price": 900},
    # expansion weapons
    "tongkat suci":   {"type": "weapon", "atk": 10, "price": 400},
    "kapak kayu":     {"type": "weapon", "atk": 5,  "price": 70},
    "kitab roh":      {"type": "weapon", "atk": 11, "price": 450},
    "seruling kayu":  {"type": "weapon", "atk": 5,  "price": 70},
    "katana kayu":    {"type": "weapon", "atk": 6,  "price": 80},
    "tongkat alam":   {"type": "weapon", "atk": 9,  "price": 350},
    "pedang es":      {"type": "weapon", "atk": 22, "price": 1400},
    "tombak petir":   {"type": "weapon", "atk": 24, "price": 1600},
    "pedang void":    {"type": "weapon", "atk": 32, "price": 3200},
    "busur bulan":    {"type": "weapon", "atk": 26, "price": 2200},
    # expansion armor
    "armor salju":    {"type": "armor", "def": 14, "price": 900},
    "armor void":     {"type": "armor", "def": 22, "price": 2800},
    "jubah penyihir": {"type": "armor", "def": 8,  "price": 400},
    "zirah druid":    {"type": "armor", "def": 10, "price": 600},
    # expansion potion & food
    "potion sedang":  {"type": "potion", "heal": 90,  "price": 55},
    "sup jamur":      {"type": "food", "hunger": 45, "price": 40},
    "sup hangat":     {"type": "food", "hunger": 40, "thirst": 20, "price": 50},
    "roti gandum":    {"type": "food", "hunger": 35, "price": 25},
    # expansion materials
    "sisik es":       {"type": "material", "price": 120},
    "bulu salju":     {"type": "material", "price": 90},
    "pasir void":     {"type": "material", "price": 160},
    "racun ular":     {"type": "material", "price": 55},
    "cangkang karang":{"type": "material", "price": 50},
    "bulu kupu":      {"type": "material", "price": 30},
}

SHOP_STOCK = [
    "pedang kayu", "tongkat kayu", "busur kayu", "belati kayu", "armor kulit",
    "potion kecil", "potion besar", "elixir",
    "roti", "daging panggang", "air minum", "jus buah",
    "benih gandum", "benih tomat", "benih labu",
    "kalung pet", "zirah pet",
    "tongkat suci", "kapak kayu", "kitab roh", "seruling kayu", "katana kayu",
    "tongkat alam", "potion sedang", "jubah penyihir", "sup jamur", "roti gandum",
]

BLACKMARKET_POOL = [
    "pedang hitam", "tongkat gelap", "belati bayangan", "armor baja",
    "jimat keberuntungan", "kristal void", "telur naga", "mahkota pet",
    "pedang void", "armor void", "busur bulan", "tombak petir",
]

RECIPES = {
    "pedang besi":      {"needs": {"pedang kayu": 1, "bijih besi": 2}, "gold": 50},
    "pedang baja":      {"needs": {"pedang besi": 1, "bijih besi": 3}, "gold": 150},
    "armor kulit kuat": {"needs": {"armor kulit": 1, "kulit monster": 3}, "gold": 60},
    "tongkat api":      {"needs": {"tongkat kayu": 1, "kristal api": 1}, "gold": 100},
    "busur elang":      {"needs": {"busur kayu": 1, "bulu elang": 2}, "gold": 100},
    "potion besar":     {"needs": {"potion kecil": 2, "lendir slime": 2}, "gold": 20},
    "pedang es":        {"needs": {"pedang baja": 1, "sisik es": 2}, "gold": 200},
    "armor salju":      {"needs": {"armor baja": 1, "bulu salju": 2}, "gold": 200},
    "tongkat suci":     {"needs": {"tongkat kayu": 1, "kristal api": 2}, "gold": 150},
    "busur bulan":      {"needs": {"busur elang": 1, "bulu phoenix": 1}, "gold": 300},
    "zirah druid":      {"needs": {"armor kulit kuat": 1, "kulit magma": 1}, "gold": 150},
    "tombak petir":     {"needs": {"pedang besi": 1, "kristal api": 2}, "gold": 250},
}

GACHA_POOL = {
    "common":    ["potion kecil", "roti", "air minum", "kayu", "daging",
                  "potion sedang", "roti gandum", "bulu kupu", "cangkang karang"],
    "rare":      ["potion besar", "bijih besi", "armor kulit", "pedang kayu", "kalung pet",
                  "tongkat suci", "jubah penyihir", "racun ular", "sisik es"],
    "epic":      ["pedang besi", "tongkat api", "armor kulit kuat", "zirah pet", "kristal api",
                  "pedang es", "armor salju", "zirah druid", "tombak petir"],
    "legendary": ["pedang naga", "tongkat phoenix", "armor langit", "telur naga", "jimat keberuntungan",
                  "pedang void", "armor void", "busur bulan", "pasir void"],
}

# ---------------------------------------------------------------- quest
# counter: kills | wins | gold_earned | crafts | jobs_done | level
QUESTS = {
    # utama (berurutan, harus klaim satu-satu)
    "mq1": {"name": "Pertarungan Pertama", "kind": "main", "counter": "kills", "target": 3, "gold": 100, "exp": 50, "tier": "Common", "desc": "Kalahkan 3 monster."},
    "mq2": {"name": "Naik Level", "kind": "main", "counter": "level", "target": 5, "gold": 250, "exp": 150, "tier": "Common", "desc": "Capai level 5."},
    "mq3": {"name": "Pemburu Gua", "kind": "main", "counter": "kills", "target": 15, "gold": 500, "exp": 300, "tier": "Rare", "desc": "Kalahkan total 15 monster."},
    "mq4": {"name": "Pahlawan Sejati", "kind": "main", "counter": "level", "target": 15, "gold": 1500, "exp": 800, "tier": "Epic", "desc": "Capai level 15 dan berevolusi."},
    # sampingan
    "sq1": {"name": "Tukang Kumpul Gold", "kind": "side", "counter": "gold_earned", "target": 1000, "gold": 200, "exp": 100, "tier": "Common", "desc": "Kumpulkan total 1000 gold dari semua sumber."},
    "sq2": {"name": "Perajin Pemula", "kind": "side", "counter": "crafts", "target": 3, "gold": 300, "exp": 150, "tier": "Rare", "desc": "Craft 3 item."},
    "sq3": {"name": "Pekerja Keras", "kind": "side", "counter": "jobs_done", "target": 5, "gold": 300, "exp": 150, "tier": "Common", "desc": "Selesaikan 5 pekerjaan."},
    # harian (reset tiap hari)
    "dq1": {"name": "Harian: Berburu", "kind": "daily", "counter": "kills", "target": 2, "gold": 80, "exp": 40, "tier": "Common", "desc": "Kalahkan 2 monster hari ini."},
    "dq2": {"name": "Harian: Kerja", "kind": "daily", "counter": "jobs_done", "target": 1, "gold": 60, "exp": 30, "tier": "Common", "desc": "Kerja 1 kali hari ini."},
    # expansion: every quest below carries a tier, like every quest above
    "mq5": {"name": "Penjelajah Dunia Baru", "kind": "main", "counter": "kills", "target": 40, "gold": 1200, "exp": 700, "tier": "Epic", "desc": "Kalahkan total 40 monster."},
    "mq6": {"name": "Legenda NEWR", "kind": "main", "counter": "level", "target": 30, "gold": 3000, "exp": 2000, "tier": "Legendary", "desc": "Capai level 30."},
    "sq4": {"name": "Duelis", "kind": "side", "counter": "wins", "target": 10, "gold": 800, "exp": 400, "tier": "Rare", "desc": "Menangkan 10 duel PvP."},
    "sq5": {"name": "Juragan Gold", "kind": "side", "counter": "gold_earned", "target": 10000, "gold": 1000, "exp": 500, "tier": "Epic", "desc": "Kumpulkan total 10000 gold dari semua sumber."},
    "sq6": {"name": "Perajin Mahir", "kind": "side", "counter": "crafts", "target": 10, "gold": 800, "exp": 400, "tier": "Rare", "desc": "Craft 10 item."},
    "sq7": {"name": "Buruh Legendaris", "kind": "side", "counter": "jobs_done", "target": 20, "gold": 700, "exp": 350, "tier": "Rare", "desc": "Selesaikan 20 pekerjaan."},
    "sq8": {"name": "Pemburu Monster", "kind": "side", "counter": "kills", "target": 100, "gold": 2000, "exp": 1000, "tier": "Legendary", "desc": "Kalahkan total 100 monster."},
    "sq9": {"name": "Master Petualang", "kind": "side", "counter": "level", "target": 40, "gold": 2500, "exp": 1500, "tier": "Legendary", "desc": "Capai level 40."},
    "dq3": {"name": "Harian: Berburu Berat", "kind": "daily", "counter": "kills", "target": 5, "gold": 150, "exp": 75, "tier": "Rare", "desc": "Kalahkan 5 monster hari ini."},
    "dq4": {"name": "Harian: Kerja Keras", "kind": "daily", "counter": "jobs_done", "target": 3, "gold": 120, "exp": 60, "tier": "Common", "desc": "Kerja 3 kali hari ini."},
}

# ---------------------------------------------------------------- pet
PETS = {
    "Serigala Api":    {"skill": "Gigitan Membara", "skill_mult": 1.5, "atk": 5,  "forms": ["Anak Serigala Api", "Serigala Api", "Serigala Inferno"]},
    "Kucing Bayangan": {"skill": "Cakaran Senyap",  "skill_mult": 1.4, "atk": 4,  "forms": ["Anak Kucing Bayangan", "Kucing Bayangan", "Macan Bayangan"]},
    "Naga Mini":       {"skill": "Napas Api Kecil", "skill_mult": 1.8, "atk": 7,  "forms": ["Bayi Naga", "Naga Mini", "Naga Muda"]},
    "Kelinci Bulan":   {"skill": "Tendangan Lunar", "skill_mult": 1.3, "atk": 3,  "forms": ["Kelinci Kecil", "Kelinci Bulan", "Kelinci Dewa Bulan"]},
    "Rubah Es":        {"skill": "Gigitan Beku",     "skill_mult": 1.5, "atk": 5,  "forms": ["Anak Rubah Es", "Rubah Es", "Rubah Badai Es"]},
    "Burung Guntur":   {"skill": "Sambar Petir",     "skill_mult": 1.7, "atk": 6,  "forms": ["Anak Burung Guntur", "Burung Guntur", "Burung Badai"]},
    "Kura-kura Karang":{"skill": "Hantaman Karang",  "skill_mult": 1.3, "atk": 4,  "forms": ["Tukik Karang", "Kura-kura Karang", "Kura-kura Purba"]},
    "Lebah Madu":      {"skill": "Sengatan Manis",   "skill_mult": 1.2, "atk": 3,  "forms": ["Lebah Kecil", "Lebah Madu", "Ratu Lebah"]},
    "Harimau Gurun":   {"skill": "Cakaran Pasir",    "skill_mult": 1.6, "atk": 6,  "forms": ["Anak Harimau Gurun", "Harimau Gurun", "Harimau Badai Pasir"]},
    "Roh Void":        {"skill": "Sentuhan Void",    "skill_mult": 1.9, "atk": 8,  "forms": ["Wisp Void", "Roh Void", "Roh Void Agung"]},
}
PET_ADOPT_COST = 200

# ---------------------------------------------------------------- job
JOBS = {
    "tukang kayu": {"gold": (30, 60),  "items": ["kayu"],       "cooldown": 3600},
    "penambang":   {"gold": (40, 80),  "items": ["bijih besi"], "cooldown": 3600},
    "pemburu":     {"gold": (35, 70),  "items": ["daging", "kulit monster"], "cooldown": 3600},
    "nelayan":     {"gold": (35, 70),  "items": ["cangkang karang", "daging"], "cooldown": 3600},
    "petani":      {"gold": (30, 60),  "items": ["benih gandum", "roti gandum"], "cooldown": 3600},
    "penjaga salju":{"gold": (50, 90), "items": ["bulu salju", "sisik es"], "cooldown": 3600},
}

# ---------------------------------------------------------------- event
EVENTS = {
    "Halloween":  {"months_days": [(10, 20), (10, 31)], "boss": "Labu Raksasa", "boss_hp": 3000,
                   "shop": ["topi labu", "tongkat permen"], "desc": "Labu-labu bangkit! Boss Labu Raksasa muncul di raid."},
    "Natal":      {"months_days": [(12, 20), (12, 26)], "boss": "Rusa Kutub Jahat", "boss_hp": 3500,
                   "shop": ["tongkat permen"], "desc": "Salju turun, Rusa Kutub Jahat mengamuk di raid."},
    "Tahun Baru": {"months_days": [(12, 30), (1, 2)], "boss": "Kembang Api Hidup", "boss_hp": 4000,
                   "shop": ["lonceng tahun baru"], "desc": "Langit berpesta! Boss Kembang Api Hidup muncul di raid."},
    "Festival Musim Panas": {"months_days": [(7, 1), (7, 31)], "boss": "Raja Ombak", "boss_hp": 4500,
                   "shop": ["tombak petir"], "desc": "Ombak mengamuk! Boss Raja Ombak muncul di raid."},
    "Festival Panen": {"months_days": [(9, 1), (9, 30)], "boss": "Dewi Panen", "boss_hp": 4200,
                   "shop": ["sup jamur"], "desc": "Panen raya! Boss Dewi Panen muncul di raid."},
}
WEEKLY_BOSS = {"name": "Raja Iblis", "hp": 5000}
# Raid bosses that rotate weekly when no seasonal event is active.
# WEEKLY_BOSS stays first (and stays the default fallback) so the
# rotation never removes the original weekly boss.
WEEKLY_BOSSES = [
    WEEKLY_BOSS,
    {"name": "Raja Void", "hp": 6500},
    {"name": "Ratu Salju", "hp": 5500},
]

# ---------------------------------------------------------------- story
STORY = [
    {"chapter": 1, "title": "Bangun di Hutan Pemula", "min_level": 1, "gold": 100, "exp": 50,
     "text": "Kamu terbangun di Hutan Pemula tanpa ingatan. Seorang kakek misterius memberimu pedang kayu dan berkata: 'Kalahkan 3 monster, dan ingatanmu akan kembali sedikit demi sedikit.'"},
    {"chapter": 2, "title": "Jejak di Gua Gelap", "min_level": 5, "gold": 250, "exp": 150,
     "text": "Di Gua Gelap kamu menemukan peta tua menuju Kastil Kegelapan. Tapi jalan ditutup monster. Kamu harus jadi lebih kuat dulu."},
    {"chapter": 3, "title": "Api Gunung Berapi", "min_level": 12, "gold": 500, "exp": 300,
     "text": "Gunung Berapi menyimpan kristal api legendaris. Golem Lava menjaganya. Kalau kamu bisa lewat, kekuatanmu diakui para tetua."},
    {"chapter": 4, "title": "Gerbang Kastil Kegelapan", "min_level": 20, "gold": 1000, "exp": 600,
     "text": "Kastil Kegelapan akhirnya terbuka. Di dalamnya, Raja Iblis menunggu. Tapi ingatanmu masih belum utuh..."},
    {"chapter": 5, "title": "Langit Terlarang", "min_level": 30, "gold": 2500, "exp": 1500,
     "text": "Naga Langit membawamu ke Langit Terlarang, tempat kebenaran terakhir disimpan. Siapkah kamu menghadapi takdirmu?"},
    {"chapter": 6, "title": "Menara Void", "min_level": 38, "gold": 4000, "exp": 2500,
     "text": "Sebuah menara hitam muncul dari kehampaan. Raja Void menantimu di puncaknya — dan ingatanmu yang hilang ternyata tersimpan di sana."},
    {"chapter": 7, "title": "Ratu Salju", "min_level": 45, "gold": 6000, "exp": 4000,
     "text": "Pegunungan Salju membeku lebih dingin dari biasanya. Ratu Salju menjaga kunci terakhir menuju takdirmu."},
    {"chapter": 8, "title": "Takdir Terakhir", "min_level": 50, "gold": 10000, "exp": 8000,
     "text": "Semua potongan ingatan kembali. Kamu bukan sekadar petualang — kamulah penjaga dunia NEWR. Cerita ini baru permulaan."},
]

# ---------------------------------------------------------------- dungeon
DUNGEON_PUZZLES = [
    {"q": "Aku berjalan tanpa kaki, bersuara tanpa mulut. Siapakah aku? (jawab: angin)", "a": "angin"},
    {"q": "Berapa hasil 7 x 8 + 6? (jawab angka saja)", "a": "62"},
    {"q": "Benda apa yang makin diambil makin besar? (jawab: lubang)", "a": "lubang"},
    {"q": "Aku punya kota tapi tak ada rumah, hutan tapi tak ada pohon, sungai tapi tak ada air. Siapakah aku? (jawab: peta)", "a": "peta"},
    {"q": "Urutan berikutnya: 2, 6, 12, 20, 30, ...? (jawab angka saja)", "a": "42"},
    {"q": "Aku selalu di depanmu tapi tak pernah bisa kau sentuh. Siapakah aku? (jawab: bayangan)", "a": "bayangan"},
    {"q": "Aku mengulang semua yang kau katakan, tapi aku bukan dirimu. Siapakah aku? (jawab: gema)", "a": "gema"},
    {"q": "Berapa hasil 12 x 12 - 44? (jawab angka saja)", "a": "100"},
    {"q": "Apa yang naik tapi tidak pernah turun? (jawab: usia)", "a": "usia"},
    {"q": "Benda apa yang punya jarum tapi tidak bisa menjahit? (jawab: jam)", "a": "jam"},
]
DUNGEON_REWARD_GOLD = (150, 400)
