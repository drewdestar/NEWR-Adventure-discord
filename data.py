# -*- coding: utf-8 -*-
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
}

# ---------------------------------------------------------------- area
AREAS = {
    "Hutan Pemula":     {"min_level": 1,  "monsters": ["Slime Hijau", "Kelinci Liar", "Goblin Kecil"]},
    "Gua Gelap":        {"min_level": 5,  "monsters": ["Kelelawar Gua", "Skeleton", "Laba-laba Raksasa"]},
    "Gunung Berapi":    {"min_level": 12, "monsters": ["Golem Lava", "Salamander Api", "Kadal Magma"]},
    "Kastil Kegelapan": {"min_level": 20, "monsters": ["Ksatria Hitam", "Penyihir Gelap", "Gargoyle"]},
    "Langit Terlarang": {"min_level": 30, "monsters": ["Naga Langit", "Phoenix Bayangan", "Raksasa Awan"]},
}

MONSTERS = {
    "Slime Hijau":      {"hp": 40,  "atk": 6,  "def": 2,  "exp": 25,  "gold": (8, 20),   "loot": ["lendir slime", "potion kecil"]},
    "Kelinci Liar":     {"hp": 30,  "atk": 5,  "def": 1,  "exp": 20,  "gold": (5, 15),   "loot": ["daging", "bulu kelinci"]},
    "Goblin Kecil":     {"hp": 55,  "atk": 8,  "def": 3,  "exp": 35,  "gold": (10, 25),  "loot": ["koin goblin", "pedang kayu"]},
    "Kelelawar Gua":    {"hp": 70,  "atk": 11, "def": 4,  "exp": 50,  "gold": (15, 35),  "loot": ["sayap kelelawar", "potion kecil"]},
    "Skeleton":         {"hp": 90,  "atk": 13, "def": 5,  "exp": 65,  "gold": (20, 45),  "loot": ["tulang", "armor kulit"]},
    "Laba-laba Raksasa":{"hp": 100, "atk": 14, "def": 5,  "exp": 70,  "gold": (20, 50),  "loot": ["jaring laba-laba", "bisa laba-laba"]},
    "Golem Lava":       {"hp": 160, "atk": 20, "def": 10, "exp": 110, "gold": (35, 70),  "loot": ["batu lava", "bijih besi"]},
    "Salamander Api":   {"hp": 140, "atk": 22, "def": 8,  "exp": 120, "gold": (40, 80),  "loot": ["sisik api", "kristal api"]},
    "Kadal Magma":      {"hp": 150, "atk": 21, "def": 9,  "exp": 115, "gold": (35, 75),  "loot": ["kulit magma", "batu lava"]},
    "Ksatria Hitam":    {"hp": 240, "atk": 30, "def": 15, "exp": 180, "gold": (60, 120), "loot": ["pedang hitam", "armor baja"]},
    "Penyihir Gelap":   {"hp": 210, "atk": 34, "def": 10, "exp": 190, "gold": (65, 130), "loot": ["tongkat gelap", "kristal api"]},
    "Gargoyle":         {"hp": 260, "atk": 28, "def": 18, "exp": 200, "gold": (70, 140), "loot": ["batu gargoyle", "armor baja"]},
    "Naga Langit":      {"hp": 400, "atk": 45, "def": 22, "exp": 320, "gold": (120, 250),"loot": ["sisik naga", "pedang naga"]},
    "Phoenix Bayangan": {"hp": 360, "atk": 48, "def": 18, "exp": 330, "gold": (130, 260),"loot": ["bulu phoenix", "tongkat phoenix"]},
    "Raksasa Awan":     {"hp": 450, "atk": 42, "def": 25, "exp": 350, "gold": (140, 280),"loot": ["awan padat", "armor langit"]},
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
}

SHOP_STOCK = [
    "pedang kayu", "tongkat kayu", "busur kayu", "belati kayu", "armor kulit",
    "potion kecil", "potion besar", "elixir",
    "roti", "daging panggang", "air minum", "jus buah",
    "benih gandum", "benih tomat", "benih labu",
    "kalung pet", "zirah pet",
]

BLACKMARKET_POOL = [
    "pedang hitam", "tongkat gelap", "belati bayangan", "armor baja",
    "jimat keberuntungan", "kristal void", "telur naga", "mahkota pet",
]

RECIPES = {
    "pedang besi":      {"needs": {"pedang kayu": 1, "bijih besi": 2}, "gold": 50},
    "pedang baja":      {"needs": {"pedang besi": 1, "bijih besi": 3}, "gold": 150},
    "armor kulit kuat": {"needs": {"armor kulit": 1, "kulit monster": 3}, "gold": 60},
    "tongkat api":      {"needs": {"tongkat kayu": 1, "kristal api": 1}, "gold": 100},
    "busur elang":      {"needs": {"busur kayu": 1, "bulu elang": 2}, "gold": 100},
    "potion besar":     {"needs": {"potion kecil": 2, "lendir slime": 2}, "gold": 20},
}

GACHA_POOL = {
    "common":    ["potion kecil", "roti", "air minum", "kayu", "daging"],
    "rare":      ["potion besar", "bijih besi", "armor kulit", "pedang kayu", "kalung pet"],
    "epic":      ["pedang besi", "tongkat api", "armor kulit kuat", "zirah pet", "kristal api"],
    "legendary": ["pedang naga", "tongkat phoenix", "armor langit", "telur naga", "jimat keberuntungan"],
}

# ---------------------------------------------------------------- quest
# counter: kills | wins | gold_earned | crafts | jobs_done | level
QUESTS = {
    # utama (berurutan, harus klaim satu-satu)
    "mq1": {"name": "Pertarungan Pertama", "kind": "main", "counter": "kills", "target": 3, "gold": 100, "exp": 50, "desc": "Kalahkan 3 monster."},
    "mq2": {"name": "Naik Level", "kind": "main", "counter": "level", "target": 5, "gold": 250, "exp": 150, "desc": "Capai level 5."},
    "mq3": {"name": "Pemburu Gua", "kind": "main", "counter": "kills", "target": 15, "gold": 500, "exp": 300, "desc": "Kalahkan total 15 monster."},
    "mq4": {"name": "Pahlawan Sejati", "kind": "main", "counter": "level", "target": 15, "gold": 1500, "exp": 800, "desc": "Capai level 15 dan berevolusi."},
    # sampingan
    "sq1": {"name": "Tukang Kumpul Gold", "kind": "side", "counter": "gold_earned", "target": 1000, "gold": 200, "exp": 100, "desc": "Kumpulkan total 1000 gold dari semua sumber."},
    "sq2": {"name": "Perajin Pemula", "kind": "side", "counter": "crafts", "target": 3, "gold": 300, "exp": 150, "desc": "Craft 3 item."},
    "sq3": {"name": "Pekerja Keras", "kind": "side", "counter": "jobs_done", "target": 5, "gold": 300, "exp": 150, "desc": "Selesaikan 5 pekerjaan."},
    # harian (reset tiap hari)
    "dq1": {"name": "Harian: Berburu", "kind": "daily", "counter": "kills", "target": 2, "gold": 80, "exp": 40, "desc": "Kalahkan 2 monster hari ini."},
    "dq2": {"name": "Harian: Kerja", "kind": "daily", "counter": "jobs_done", "target": 1, "gold": 60, "exp": 30, "desc": "Kerja 1 kali hari ini."},
}

# ---------------------------------------------------------------- pet
PETS = {
    "Serigala Api":    {"skill": "Gigitan Membara", "skill_mult": 1.5, "atk": 5,  "forms": ["Anak Serigala Api", "Serigala Api", "Serigala Inferno"]},
    "Kucing Bayangan": {"skill": "Cakaran Senyap",  "skill_mult": 1.4, "atk": 4,  "forms": ["Anak Kucing Bayangan", "Kucing Bayangan", "Macan Bayangan"]},
    "Naga Mini":       {"skill": "Napas Api Kecil", "skill_mult": 1.8, "atk": 7,  "forms": ["Bayi Naga", "Naga Mini", "Naga Muda"]},
    "Kelinci Bulan":   {"skill": "Tendangan Lunar", "skill_mult": 1.3, "atk": 3,  "forms": ["Kelinci Kecil", "Kelinci Bulan", "Kelinci Dewa Bulan"]},
}
PET_ADOPT_COST = 200

# ---------------------------------------------------------------- job
JOBS = {
    "tukang kayu": {"gold": (30, 60),  "items": ["kayu"],       "cooldown": 3600},
    "penambang":   {"gold": (40, 80),  "items": ["bijih besi"], "cooldown": 3600},
    "pemburu":     {"gold": (35, 70),  "items": ["daging", "kulit monster"], "cooldown": 3600},
}

# ---------------------------------------------------------------- event
EVENTS = {
    "Halloween":  {"months_days": [(10, 20), (10, 31)], "boss": "Labu Raksasa", "boss_hp": 3000,
                   "shop": ["topi labu", "tongkat permen"], "desc": "Labu-labu bangkit! Boss Labu Raksasa muncul di raid."},
    "Natal":      {"months_days": [(12, 20), (12, 26)], "boss": "Rusa Kutub Jahat", "boss_hp": 3500,
                   "shop": ["tongkat permen"], "desc": "Salju turun, Rusa Kutub Jahat mengamuk di raid."},
    "Tahun Baru": {"months_days": [(12, 30), (1, 2)], "boss": "Kembang Api Hidup", "boss_hp": 4000,
                   "shop": ["lonceng tahun baru"], "desc": "Langit berpesta! Boss Kembang Api Hidup muncul di raid."},
}
WEEKLY_BOSS = {"name": "Raja Iblis", "hp": 5000}

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
]

# ---------------------------------------------------------------- dungeon
DUNGEON_PUZZLES = [
    {"q": "Aku berjalan tanpa kaki, bersuara tanpa mulut. Siapakah aku? (jawab: angin)", "a": "angin"},
    {"q": "Berapa hasil 7 x 8 + 6? (jawab angka saja)", "a": "62"},
    {"q": "Benda apa yang makin diambil makin besar? (jawab: lubang)", "a": "lubang"},
    {"q": "Aku punya kota tapi tak ada rumah, hutan tapi tak ada pohon, sungai tapi tak ada air. Siapakah aku? (jawab: peta)", "a": "peta"},
    {"q": "Urutan berikutnya: 2, 6, 12, 20, 30, ...? (jawab angka saja)", "a": "42"},
]
DUNGEON_REWARD_GOLD = (150, 400)
