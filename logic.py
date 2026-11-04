# -*- coding: utf-8 -*-
"""Rumus game murni (tanpa Discord, tanpa database).

Fungsi-fungsi di sini dipakai bot DAN test offline, jadi ekonominya
konsisten di kedua tempat.
"""
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from data import CLASSES, EVOLUTIONS, ITEMS, MONSTERS, PETS, STARTER_TIERS

WIB = ZoneInfo("Asia/Jakarta")
MAX_STAMINA = 100
MAX_HUNGER = 100
MAX_THIRST = 100


def now_ts():
    import time
    return int(time.time())


def today_wib():
    return datetime.now(WIB).strftime("%Y-%m-%d")


def exp_needed(level):
    """EXP untuk naik dari `level` ke `level + 1`."""
    return 100 * level


def roll_starter_tier(rng=None):
    """Roll one starter tier for a NEW player.

    Returns (tier name, bonus percent, bonus items dict). The bonus
    percent is rolled per player inside the tier range. Deterministic
    when an rng with randint() is passed (useful for tests).
    """
    rng = rng or random
    roll = rng.randint(1, 100)
    acc = 0
    for name, weight, lo, hi, bonus in STARTER_TIERS:
        acc += weight
        if roll <= acc:
            return name, rng.randint(lo, hi), dict(bonus)
    name, _w, lo, hi, bonus = STARTER_TIERS[-1]
    return name, rng.randint(lo, hi), dict(bonus)


def apply_starter_bonus(base_stats, bonus_pct):
    """Apply a rolled bonus percent to hp/mp/atk/def/spd on top of the
    class base. Skill and skill_mult are copied unchanged, so the
    class identity never changes — only power is randomised. Every
    stat stays >= 1. Level-up and evolution add on top of the
    resulting player stats, so the tier bonus is never recomputed
    or lost."""
    out = dict(base_stats)
    for key in ("hp", "mp", "atk", "def", "spd"):
        out[key] = max(1, round(base_stats[key] * (1 + bonus_pct / 100)))
    return out


def apply_exp(player, amount):
    """Tambah EXP (sudah dikali bonus VIP di luar bila perlu).

    Mengembalikan jumlah level yang naik. Mengubah dict player in-place:
    level, exp, max_hp, max_mp, atk, def, spd, hp, mp (full heal tiap naik).
    """
    player["exp"] += amount
    gained = 0
    while player["exp"] >= exp_needed(player["level"]):
        player["exp"] -= exp_needed(player["level"])
        player["level"] += 1
        gained += 1
        player["max_hp"] += 10
        player["max_mp"] += 5
        player["atk"] += 2
        player["def"] += 1
        player["spd"] += 1
        player["hp"] = player["max_hp"]
        player["mp"] = player["max_mp"]
    return gained


def add_gold(player, amount):
    player["gold"] += amount
    player["gold_earned"] += amount
    return amount


def pvp_steal_amount(carried_gold):
    """Gold a PvP winner steals with 'Curi': 10% of the loser's CARRIED
    gold only (floor). Banked gold is never stealable — it lives in a
    separate balance this function never sees. Zero or negative carried
    gold yields 0 (and a tiny positive balance below 10 also yields 0).
    """
    return max(0, int(carried_gold) // 10)


def vip_active(player, now=None):
    return bool(player.get("vip")) and (player.get("vip_until") or 0) > (now or now_ts())


def exp_gain(player, base, guild_level=0):
    """EXP yang diterima pemain (VIP x1.5, buff guild +2% per level guild)."""
    mult = 1.0
    if vip_active(player):
        mult *= 1.5
    if guild_level:
        mult *= (1 + guild_level * 0.02)
    return int(base * mult)


def gold_gain(player, base):
    """Gold yang diterima pemain (VIP x1.25)."""
    return int(base * 1.25) if vip_active(player) else base


def refill_stamina(player):
    """Stamina penuh tiap pergantian hari WIB."""
    today = today_wib()
    if player.get("stamina_date") != today:
        player["stamina"] = MAX_STAMINA
        player["stamina_date"] = today
        return True
    return False


def apply_passive_decay(player, now=None):
    """Lapar/haus berkurang 1 poin tiap 2 jam sejak last_seen.

    Kalau lapar atau haus 0, HP terkuras 5 poin per 2 jam tapi berhenti di
    10 HP (tidak mati mendadak, sesuai spek: peringatan dulu, drain pelan).
    Mengembalikan (hunger_lost, thirst_lost, hp_lost).
    """
    now = now or now_ts()
    last = player.get("last_seen") or now
    hours = (now - last) // 7200
    if hours <= 0:
        player["last_seen"] = now
        return (0, 0, 0)
    h_lost = min(player["hunger"], hours)
    t_lost = min(player["thirst"], hours)
    player["hunger"] -= h_lost
    player["thirst"] -= t_lost
    hp_lost = 0
    if player["hunger"] == 0 or player["thirst"] == 0:
        drain = 5 * hours
        hp_lost = min(drain, max(0, player["hp"] - 10))
        player["hp"] -= hp_lost
    player["last_seen"] = now
    return (h_lost, t_lost, hp_lost)


def spend_stamina(player, amount):
    if player["stamina"] < amount:
        return False
    player["stamina"] -= amount
    return True


def effective_stats(player, equipped, pet=None):
    """ATK/DEF/SPD final = base + equipment + pet."""
    atk, defense, spd = player["atk"], player["def"], player["spd"]
    for row in equipped:
        item = ITEMS.get(row["item_id"], {})
        if row.get("durability", 100) > 0:
            atk += item.get("atk", 0)
            defense += item.get("def", 0)
    if pet is not None:
        spec = PETS[pet["species"]]
        atk += spec["atk"] + pet["level"] // 2
        if pet.get("gear_weapon"):
            atk += ITEMS.get(pet["gear_weapon"], {}).get("atk", 0)
        if pet.get("gear_armor"):
            defense += ITEMS.get(pet["gear_armor"], {}).get("def", 0)
    return atk, defense, spd


def class_skill(player):
    """Nama skill kelas pemain (termasuk evolusi — skill tetap sama)."""
    base = CLASSES[player["class"]]
    return base["skill"], base["skill_mult"]


def damage(atk, defense, mult=1.0, rng=None):
    """Damage = (ATK - DEF*0.5) * mult, minimal 1, crit 10% = x2."""
    rng = rng or random
    raw = max(1, int((atk - defense * 0.5) * mult))
    crit = rng.random() < 0.10
    if crit:
        raw *= 2
    return raw, crit


def scale_monster(name, player_level):
    """Monster ikut naik seiring level pemain (biar tetap menantang)."""
    base = MONSTERS[name]
    bonus = max(0, player_level - 1)
    return {
        "name": name,
        "hp": base["hp"] + bonus * 8,
        "atk": base["atk"] + bonus,
        "def": base["def"] + bonus // 2,
        "exp": base["exp"] + bonus * 3,
        "gold": base["gold"],
        "loot": base["loot"],
    }


def fight_round(attacker_atk, attacker_def, defender_atk, defender_def,
                use_skill=False, skill_mult=1.0, rng=None):
    """Satu ronde serang-balasan. Kembalikan (dmg_ke_musuh, crit, dmg_ke_pemain)."""
    rng = rng or random
    mult = skill_mult if use_skill else 1.0
    dmg, crit = damage(attacker_atk, defender_def, mult, rng)
    back, _ = damage(defender_atk, attacker_def, 1.0, rng)
    return dmg, crit, back


def roll_loot(monster_name, vip=False, rng=None):
    """Loot acak dari monster. VIP +10% peluang dapat loot."""
    rng = rng or random
    loot = MONSTERS[monster_name]["loot"]
    chance = 0.70 if vip else 0.60
    if rng.random() < chance:
        return rng.choice(loot)
    return None


def gacha_roll(vip=False, rng=None):
    """Rarity gacha: common 60 / rare 28 / epic 10 / legendary 2.
    VIP menggeser 5% dari common ke epic+legendary."""
    rng = rng or random
    roll = rng.random()
    if vip:
        if roll < 0.55:
            return "common"
        if roll < 0.83:
            return "rare"
        if roll < 0.97:
            return "epic"
        return "legendary"
    if roll < 0.60:
        return "common"
    if roll < 0.88:
        return "rare"
    if roll < 0.98:
        return "epic"
    return "legendary"


def pet_form(species, level):
    forms = PETS[species]["forms"]
    if level >= 25:
        return forms[2]
    if level >= 10:
        return forms[1]
    return forms[0]


def pet_exp_needed(level):
    return 50 * level


def pet_gain_exp(pet, amount):
    pet["exp"] += amount
    gained = 0
    while pet["exp"] >= pet_exp_needed(pet["level"]):
        pet["exp"] -= pet_exp_needed(pet["level"])
        pet["level"] += 1
        gained += 1
    return gained


def guild_buff(guild_level):
    """Bonus stats untuk semua anggota guild (aktif dihitung saat bertarung)."""
    return {"atk": guild_level, "def": guild_level, "exp_pct": guild_level * 2}


def evolution_for(base_class, stage):
    """Kembalikan (nama_baru, level_min, bonus) atau None."""
    return EVOLUTIONS.get((base_class, stage))


def active_events(on_date=None):
    """Event musiman yang aktif pada tanggal tertentu (default: hari ini WIB)."""
    from data import EVENTS
    d = on_date or datetime.now(WIB).date()
    active = []
    for name, ev in EVENTS.items():
        (m1, d1), (m2, d2) = ev["months_days"]
        start = (m1, d1)
        end = (m2, d2)
        cur = (d.month, d.day)
        if start <= end:
            in_window = start <= cur <= end
        else:  # melewati pergantian tahun (mis. 30 Des - 2 Jan)
            in_window = cur >= start or cur <= end
        if in_window:
            active.append((name, ev))
    return active


def meteor_window_now(now=None):
    """Meteor shower: tiap hari 21:00-21:59 WIB."""
    dt = now or datetime.now(WIB)
    return dt.hour == 21


def casino_limits_ok(player, bet):
    """Batas judi: taruhan maks 500 gold, rugi harian maks 2000 gold."""
    if bet < 10 or bet > 500:
        return False, "Bets must be 10-500 gold."
    if player.get("casino_date") != today_wib():
        player["casino_lost"] = 0
        player["casino_date"] = today_wib()
    if player["casino_lost"] + bet > 2000:
        return False, "Your daily loss limit (2000 gold) is almost reached, take a break."
    return True, ""
