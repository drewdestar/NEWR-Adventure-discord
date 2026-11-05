# -*- coding: utf-8 -*-
"""Display names (English) for game content.

CRITICAL RULE: internal keys/IDs stored in the database or used by code for
lookups NEVER change (e.g. item key "potion kecil", area key "Hutan Pemula",
monster key "Slime Hijau", quest id "mq1"). Only what the user SEES is
translated, through these maps. Unknown keys fall back to the key itself,
so nothing breaks if new content is added later.

User-chosen names (player names, guild names, pet names) are NOT mapped:
they are shown exactly as the user typed them.
"""

ITEM_EN = {
    "pedang kayu": "Wooden Sword",
    "pedang besi": "Iron Sword",
    "pedang baja": "Steel Sword",
    "pedang hitam": "Black Sword",
    "pedang naga": "Dragon Sword",
    "tongkat kayu": "Wooden Staff",
    "tongkat api": "Fire Staff",
    "tongkat gelap": "Dark Staff",
    "tongkat phoenix": "Phoenix Staff",
    "busur kayu": "Wooden Bow",
    "busur elang": "Eagle Bow",
    "belati kayu": "Wooden Dagger",
    "belati bayangan": "Shadow Dagger",
    "armor kulit": "Leather Armor",
    "armor kulit kuat": "Strong Leather Armor",
    "armor baja": "Steel Armor",
    "armor langit": "Sky Armor",
    "potion kecil": "Small Potion",
    "potion besar": "Large Potion",
    "elixir": "Elixir",
    "roti": "Bread",
    "daging panggang": "Grilled Meat",
    "air minum": "Drinking Water",
    "jus buah": "Fruit Juice",
    "telur ayam": "Chicken Egg",
    "susu": "Milk",
    "kayu": "Wood",
    "bijih besi": "Iron Ore",
    "kulit monster": "Monster Hide",
    "daging": "Meat",
    "lendir slime": "Slime Goo",
    "tulang": "Bone",
    "batu lava": "Lava Stone",
    "kristal api": "Fire Crystal",
    "sisik api": "Flame Scale",
    "bulu elang": "Eagle Feather",
    "bulu kelinci": "Rabbit Fur",
    "koin goblin": "Goblin Coin",
    "sayap kelelawar": "Bat Wing",
    "jaring laba-laba": "Spider Web",
    "bisa laba-laba": "Spider Venom",
    "kulit magma": "Magma Hide",
    "batu gargoyle": "Gargoyle Stone",
    "sisik naga": "Dragon Scale",
    "bulu phoenix": "Phoenix Feather",
    "awan padat": "Solid Cloud",
    "benih gandum": "Wheat Seeds",
    "benih tomat": "Tomato Seeds",
    "benih labu": "Pumpkin Seeds",
    "kalung pet": "Pet Necklace",
    "zirah pet": "Pet Armor",
    "mahkota pet": "Pet Crown",
    "jimat keberuntungan": "Lucky Charm",
    "kristal void": "Void Crystal",
    "telur naga": "Dragon Egg",
    "topi labu": "Pumpkin Hat",
    "tongkat permen": "Candy Staff",
    "lonceng tahun baru": "New Year Bell",
    "tongkat suci": "Holy Staff",
    "kapak kayu": "Wooden Axe",
    "kitab roh": "Spirit Tome",
    "seruling kayu": "Wooden Flute",
    "katana kayu": "Wooden Katana",
    "tongkat alam": "Nature Staff",
    "pedang es": "Ice Sword",
    "tombak petir": "Lightning Spear",
    "pedang void": "Void Sword",
    "busur bulan": "Moon Bow",
    "armor salju": "Snow Armor",
    "armor void": "Void Armor",
    "jubah penyihir": "Wizard Robe",
    "zirah druid": "Druid Armor",
    "potion sedang": "Medium Potion",
    "sup jamur": "Mushroom Soup",
    "sup hangat": "Warm Soup",
    "roti gandum": "Wheat Bread",
    "sisik es": "Ice Scale",
    "bulu salju": "Snow Feather",
    "pasir void": "Void Sand",
    "racun ular": "Snake Venom",
    "cangkang karang": "Coral Shell",
    "bulu kupu": "Butterfly Wing",
}

PET_EN = {
    "Serigala Api": "Fire Wolf",
    "Kucing Bayangan": "Shadow Cat",
    "Naga Mini": "Mini Dragon",
    "Kelinci Bulan": "Moon Rabbit",
    "Rubah Es": "Ice Fox",
    "Burung Guntur": "Thunder Bird",
    "Kura-kura Karang": "Coral Turtle",
    "Lebah Madu": "Honey Bee",
    "Harimau Gurun": "Desert Tiger",
    "Roh Void": "Void Spirit",
}

PET_SKILL_EN = {
    "Gigitan Membara": "Burning Bite",
    "Cakaran Senyap": "Silent Claw",
    "Napas Api Kecil": "Small Fire Breath",
    "Tendangan Lunar": "Lunar Kick",
    "Gigitan Beku": "Freezing Bite",
    "Sambar Petir": "Lightning Strike",
    "Hantaman Karang": "Coral Slam",
    "Sengatan Manis": "Sweet Sting",
    "Cakaran Pasir": "Sand Claw",
    "Sentuhan Void": "Void Touch",
}

PET_FORM_EN = {
    "Anak Serigala Api": "Fire Wolf Pup",
    "Serigala Api": "Fire Wolf",
    "Serigala Inferno": "Inferno Wolf",
    "Anak Kucing Bayangan": "Shadow Kitten",
    "Kucing Bayangan": "Shadow Cat",
    "Macan Bayangan": "Shadow Tiger",
    "Bayi Naga": "Baby Dragon",
    "Naga Mini": "Mini Dragon",
    "Naga Muda": "Young Dragon",
    "Kelinci Kecil": "Little Rabbit",
    "Kelinci Bulan": "Moon Rabbit",
    "Kelinci Dewa Bulan": "Moon God Rabbit",
    "Anak Rubah Es": "Ice Fox Pup",
    "Rubah Es": "Ice Fox",
    "Rubah Badai Es": "Ice Storm Fox",
    "Anak Burung Guntur": "Thunder Chick",
    "Burung Guntur": "Thunder Bird",
    "Burung Badai": "Storm Bird",
    "Tukik Karang": "Coral Hatchling",
    "Kura-kura Karang": "Coral Turtle",
    "Kura-kura Purba": "Ancient Turtle",
    "Lebah Kecil": "Little Bee",
    "Lebah Madu": "Honey Bee",
    "Ratu Lebah": "Bee Queen",
    "Anak Harimau Gurun": "Desert Tiger Cub",
    "Harimau Gurun": "Desert Tiger",
    "Harimau Badai Pasir": "Sandstorm Tiger",
    "Wisp Void": "Void Wisp",
    "Roh Void": "Void Spirit",
    "Roh Void Agung": "Grand Void Spirit",
}

AREA_EN = {
    "Hutan Pemula": "Beginner Forest",
    "Gua Gelap": "Dark Cave",
    "Gunung Berapi": "Volcano Mountain",
    "Kastil Kegelapan": "Dark Castle",
    "Langit Terlarang": "Forbidden Sky",
    "Desa Tenang": "Quiet Village",
    "Pantai Karang": "Coral Beach",
    "Hutan Beracun": "Poison Forest",
    "Gurun Pasir": "Sand Desert",
    "Pegunungan Salju": "Snow Mountains",
    "Menara Void": "Void Tower",
}

MONSTER_EN = {
    "Slime Hijau": "Green Slime",
    "Kelinci Liar": "Wild Rabbit",
    "Goblin Kecil": "Little Goblin",
    "Kelelawar Gua": "Cave Bat",
    "Skeleton": "Skeleton",
    "Laba-laba Raksasa": "Giant Spider",
    "Golem Lava": "Lava Golem",
    "Salamander Api": "Fire Salamander",
    "Kadal Magma": "Magma Lizard",
    "Ksatria Hitam": "Black Knight",
    "Penyihir Gelap": "Dark Wizard",
    "Gargoyle": "Gargoyle",
    "Naga Langit": "Sky Dragon",
    "Phoenix Bayangan": "Shadow Phoenix",
    "Raksasa Awan": "Cloud Giant",
    # Boss event & boss mingguan.
    "Labu Raksasa": "Giant Pumpkin",
    "Rusa Kutub Jahat": "Evil Reindeer",
    "Kembang Api Hidup": "Living Firework",
    "Raja Iblis": "Demon King",
    "Raja Ombak": "Wave King",
    "Dewi Panen": "Harvest Goddess",
    "Raja Void": "Void King",
    "Ratu Salju": "Snow Queen",
    "Ayam Liar": "Wild Chicken",
    "Tikus Ladang": "Field Mouse",
    "Kupu-kupu Raksasa": "Giant Butterfly",
    "Kepiting Raksasa": "Giant Crab",
    "Ubur-ubur Listrik": "Electric Jellyfish",
    "Penyu Karang": "Coral Turtle",
    "Jamur Beracun": "Poison Mushroom",
    "Ular Berbisa": "Venomous Snake",
    "Katak Racun": "Poison Frog",
    "Kalajengking Pasir": "Sand Scorpion",
    "Mumi Kuno": "Ancient Mummy",
    "Cacing Gurun": "Desert Worm",
    "Serigala Salju": "Snow Wolf",
    "Yeti Muda": "Young Yeti",
    "Roh Es": "Ice Spirit",
    "Mata Void": "Void Eye",
    "Bayangan Void": "Void Shadow",
    "Naga Void": "Void Dragon",
}

QUEST_EN = {
    "mq1": ("First Battle", "Defeat 3 monsters."),
    "mq2": ("Level Up", "Reach level 5."),
    "mq3": ("Cave Hunter", "Defeat 15 monsters in total."),
    "mq4": ("True Hero", "Reach level 15 and evolve."),
    "sq1": ("Gold Collector", "Collect 1000 gold in total from all sources."),
    "sq2": ("Beginner Crafter", "Craft 3 items."),
    "sq3": ("Hard Worker", "Finish 5 jobs."),
    "dq1": ("Daily: Hunt", "Defeat 2 monsters today."),
    "dq2": ("Daily: Work", "Work 1 time today."),
    "mq5": ("New World Explorer", "Defeat 40 monsters in total."),
    "mq6": ("NEWR Legend", "Reach level 30."),
    "sq4": ("Duelist", "Win 10 PvP duels."),
    "sq5": ("Gold Tycoon", "Collect 10000 gold in total from all sources."),
    "sq6": ("Skilled Crafter", "Craft 10 items."),
    "sq7": ("Legendary Worker", "Finish 20 jobs."),
    "sq8": ("Monster Hunter", "Defeat 100 monsters in total."),
    "sq9": ("Master Adventurer", "Reach level 40."),
    "dq3": ("Daily: Heavy Hunt", "Defeat 5 monsters today."),
    "dq4": ("Daily: Hard Work", "Work 3 times today."),
}

SKILL_EN = {
    "Tebasan Baja": "Steel Slash",
    "Ledakan Api": "Fire Blast",
    "Panah Beruntun": "Arrow Barrage",
    "Tusukan Bayangan": "Shadow Stab",
    "Cahaya Suci": "Holy Light",
    "Amukan Liar": "Wild Rampage",
    "Panggil Roh": "Spirit Summon",
    "Lagu Perang": "War Song",
    "Tebasan Kilat": "Lightning Slash",
    "Akar Berduri": "Thorn Roots",
}

JOB_EN = {
    "tukang kayu": "Carpenter",
    "penambang": "Miner",
    "pemburu": "Hunter",
    "nelayan": "Fisher",
    "petani": "Farmer",
    "penjaga salju": "Snow Guard",
}

CROP_EN = {
    "gandum": "wheat",
    "tomat": "tomato",
    "labu": "pumpkin",
}

ANIMAL_EN = {
    "ayam": "chicken",
    "sapi": "cow",
}

EVENT_EN = {
    "Halloween": ("Halloween",
                  "Pumpkins rise! The Giant Pumpkin boss appears in raids.",
                  "Giant Pumpkin"),
    "Natal": ("Christmas",
              "Snow falls, the Evil Reindeer rampages in raids.",
              "Evil Reindeer"),
    "Tahun Baru": ("New Year",
                   "The sky celebrates! The Living Firework boss appears in raids.",
                   "Living Firework"),
    "Festival Musim Panas": ("Summer Festival",
                   "Waves rage! The Wave King boss appears in raids.",
                   "Wave King"),
    "Festival Panen": ("Harvest Festival",
                   "Harvest time! The Harvest Goddess boss appears in raids.",
                   "Harvest Goddess"),
}

STORY_EN = {
    1: ("Wake Up in Beginner Forest",
        "You wake up in Beginner Forest with no memories. A mysterious old man "
        "hands you a wooden sword and says: 'Defeat 3 monsters, and your "
        "memories will slowly return.'"),
    2: ("Tracks in Dark Cave",
        "In Dark Cave you find an old map leading to Dark Castle. But the road "
        "is blocked by monsters. You need to get stronger first."),
    3: ("Volcano Mountain Fire",
        "Volcano Mountain hides the legendary fire crystal. A Lava Golem guards "
        "it. If you can get through, the elders will acknowledge your power."),
    4: ("Dark Castle Gate",
        "Dark Castle is finally open. Inside, the Demon King waits. But your "
        "memories are still incomplete..."),
    5: ("Forbidden Sky",
        "The Sky Dragon takes you to the Forbidden Sky, where the final truth "
        "is kept. Are you ready to face your destiny?"),
    6: ("Void Tower",
        "A black tower rises from the void. The Void King waits at its top — "
        "and your lost memories are kept there."),
    7: ("Snow Queen",
        "The Snow Mountains freeze colder than ever. The Snow Queen guards "
        "the final key to your destiny."),
    8: ("Final Destiny",
        "Every memory returns. You are not just an adventurer — you are the "
        "guardian of the NEWR world. This story is only the beginning."),
}

RIDDLE_EN = {
    "Aku berjalan tanpa kaki, bersuara tanpa mulut. Siapakah aku? (jawab: angin)":
        "I walk without feet, speak without a mouth. Who am I? (answer: wind)",
    "Berapa hasil 7 x 8 + 6? (jawab angka saja)":
        "What is 7 x 8 + 6? (answer with a number only)",
    "Benda apa yang makin diambil makin besar? (jawab: lubang)":
        "What gets bigger the more you take from it? (answer: hole)",
    "Aku punya kota tapi tak ada rumah, hutan tapi tak ada pohon, sungai tapi tak ada air. Siapakah aku? (jawab: peta)":
        "I have cities but no houses, forests but no trees, rivers but no water. "
        "Who am I? (answer: map)",
    "Urutan berikutnya: 2, 6, 12, 20, 30, ...? (jawab angka saja)":
        "What comes next: 2, 6, 12, 20, 30, ...? (answer with a number only)",
    "Aku selalu di depanmu tapi tak pernah bisa kau sentuh. Siapakah aku? (jawab: bayangan)":
        "I am always in front of you but you can never touch me. Who am I? (answer: shadow)",
    "Aku mengulang semua yang kau katakan, tapi aku bukan dirimu. Siapakah aku? (jawab: gema)":
        "I repeat everything you say, but I am not you. Who am I? (answer: echo)",
    "Berapa hasil 12 x 12 - 44? (jawab angka saja)":
        "What is 12 x 12 - 44? (answer with a number only)",
    "Apa yang naik tapi tidak pernah turun? (jawab: usia)":
        "What goes up but never comes down? (answer: age)",
    "Benda apa yang punya jarum tapi tidak bisa menjahit? (jawab: jam)":
        "What has hands but cannot sew? (answer: clock)",
}

# Jawaban teka-teki tetap memakai key Indonesia di data; jawaban English ini
# diterima TAMBAHAN (bukan pengganti) supaya riddle English tetap bisa dijawab.
RIDDLE_ANSWER_EN = {
    "angin": "wind",
    "lubang": "hole",
    "peta": "map",
    "bayangan": "shadow",
    "gema": "echo",
    "usia": "age",
    "jam": "clock",
}


def _get(table, key):
    return table.get(key, key)


def _reverse(table):
    """English display name (lowercased) -> internal key. Keys win on clash."""
    rev = {}
    for key, val in table.items():
        rev.setdefault(val.lower(), key)
    return rev


_ITEM_REV = _reverse(ITEM_EN)
_AREA_REV = _reverse(AREA_EN)
_MONSTER_REV = _reverse(MONSTER_EN)
_PET_REV = _reverse(PET_EN)
_JOB_REV = _reverse(JOB_EN)
_CROP_REV = _reverse(CROP_EN)
_ANIMAL_REV = _reverse(ANIMAL_EN)


def _resolve(table, rev, text):
    """Resolve free-text input to an internal key.

    Accepts the internal key itself (any case) or its English display name
    (any case). Returns None when neither matches, so callers can still
    report "unknown" exactly as before.
    """
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    if t in table:
        return t
    low = t.lower()
    for key in table:
        if key.lower() == low:
            return key
    return rev.get(low)


def resolve_item(text):
    return _resolve(ITEM_EN, _ITEM_REV, text)


def resolve_area(text):
    return _resolve(AREA_EN, _AREA_REV, text)


def resolve_monster(text):
    return _resolve(MONSTER_EN, _MONSTER_REV, text)


def resolve_pet(text):
    return _resolve(PET_EN, _PET_REV, text)


def resolve_job(text):
    return _resolve(JOB_EN, _JOB_REV, text)


def resolve_crop(text):
    return _resolve(CROP_EN, _CROP_REV, text)


def resolve_animal(text):
    return _resolve(ANIMAL_EN, _ANIMAL_REV, text)


def item(key):
    return _get(ITEM_EN, key)


def pet(key):
    return _get(PET_EN, key)


def pet_skill(key):
    return _get(PET_SKILL_EN, key)


def pet_form(key):
    return _get(PET_FORM_EN, key)


def area(key):
    return _get(AREA_EN, key)


def monster(key):
    return _get(MONSTER_EN, key)


def quest_name(qid):
    return QUEST_EN.get(qid, (qid, ""))[0]


def quest_desc(qid):
    return QUEST_EN.get(qid, ("", ""))[1]


def skill(key):
    return _get(SKILL_EN, key)


def job(key):
    return _get(JOB_EN, key)


def crop(key):
    return _get(CROP_EN, key)


def animal(key):
    return _get(ANIMAL_EN, key)


def event_name(key):
    return EVENT_EN.get(key, (key, "", ""))[0]


def event_desc(key):
    return EVENT_EN.get(key, ("", key, ""))[1]


def event_boss(key):
    return EVENT_EN.get(key, ("", "", key))[2]


def story_title(chapter):
    return STORY_EN.get(chapter, ("", ""))[0]


def story_text(chapter):
    return STORY_EN.get(chapter, ("", ""))[1]


def riddle(question):
    return _get(RIDDLE_EN, question)


def riddle_answer_en(key):
    return RIDDLE_ANSWER_EN.get(key)
