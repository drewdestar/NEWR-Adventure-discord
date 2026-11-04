# -*- coding: utf-8 -*-
"""Helper bersama untuk semua cog: embed, database, quest, reward."""
import os
from pathlib import Path

import discord

import database as db
import i18n
import logic
from data import CREDIT, QUESTS

DEFAULT_DB = Path.home() / "workspace" / "bots" / "rpg" / "rpg.db"
DB_PATH = os.environ.get("RPG_DB_PATH", str(DEFAULT_DB))

TITLE = "NEWR Adventure"

# --- Sistem warna embed (satu warna per sistem, konsisten di semua cog) ---
COLOR_CORE = 0x8B5CF6      # ungu — dasar (register/profile/daily/inventory/map/quest)
COLOR_BATTLE = 0xEF4444    # merah — battle, raid, pvp, arena, guild war
COLOR_ECONOMY = 0xF59E0B   # emas — shop, black market, craft, gacha, trade
COLOR_PET = 0x22C55E       # hijau — pet & pet gear
COLOR_SOCIAL = 0x3B82F6    # biru — guild, guild quest, party
COLOR_SURVIVAL = 0x14B8A6  # teal — status, makan/minum, repair
COLOR_PREMIUM = 0xD946EF   # magenta — VIP, ranking, event
COLOR_EXTRA = 0xF97316     # oranye — casino, job, house, dungeon, meteor, story
COLOR_ERROR = 0xEF4444     # merah — semua pesan error/notifikasi gagal


def emb(title, desc="", color=COLOR_CORE):
    """Central embed builder. Title/description pass through the i18n
    layer: central-path strings translate to the caller's language,
    everything else keeps the English base. Footer credit stays
    'NEWR Adventure by NEWR LABS' (footer only, no author link)."""
    e = discord.Embed(title=i18n.t(title), description=i18n.t(desc),
                      color=color)
    e.set_footer(text=f"{TITLE} {CREDIT}")
    return e


def err_embed(msg):
    """Embed error standar (ephemeral): merah, judul jelas, footer tetap ada."""
    return emb("⚠️ Oops!", msg, color=COLOR_ERROR)


def get_conn():
    return db.connect(DB_PATH)


def load_player(conn, user_id):
    """Ambil player + terapkan refill stamina & decay lapar/haus."""
    p = db.get_player(conn, user_id)
    if p is None:
        return None
    changed = False
    if logic.refill_stamina(p):
        changed = True
    h, t, hp = logic.apply_passive_decay(p)
    if h or t or hp:
        changed = True
    if changed:
        db.save_player(conn, p)
    return p


async def need_player(interaction, conn):
    """Kembalikan player, atau kirim pesan 'belum daftar' dan None.
    Also sets the i18n context (language + connection) for this
    interaction, so emb() replies use the user's language."""
    i18n.set_ctx(interaction, conn)
    p = load_player(conn, interaction.user.id)
    if p is None:
        await interaction.response.send_message(
            embed=err_embed("You don't have a character yet! Register first with `/register`."),
            ephemeral=True,
        )
        return None
    return p


def warnings_for(player):
    out = []
    if player["hunger"] < 20:
        out.append(i18n.t("⚠️ Hungry! Eat with `/eat` so your HP doesn't drain."))
    if player["thirst"] < 20:
        out.append(i18n.t("⚠️ Thirsty! Drink with `/drink` so your HP doesn't drain."))
    if player["hp"] <= 0:
        out.append(i18n.t('💀 Your HP is 0! Use a potion from `/inventory` so you can fight again.'))
    return out


def set_quest_progress(conn, user_id, quest_id, value):
    row = db.quest_row(conn, user_id, quest_id)
    if row is None:
        conn.execute(
            "INSERT INTO quests_progress (user_id, quest_id, progress) VALUES (?, ?, ?)",
            (user_id, quest_id, value),
        )
    elif not row["claimed"]:
        conn.execute(
            "UPDATE quests_progress SET progress = ? WHERE user_id = ? AND quest_id = ?",
            (value, user_id, quest_id),
        )
    conn.commit()


def sync_quests(conn, player):
    """Sinkronkan progress quest utama/sampingan dari counter pemain."""
    counters = {
        "kills": player["kills"],
        "wins": player["wins"],
        "gold_earned": player["gold_earned"],
        "crafts": player["crafts"],
        "jobs_done": player["jobs_done"],
        "level": player["level"],
    }
    for qid, q in QUESTS.items():
        if q["kind"] == "daily":
            continue
        set_quest_progress(conn, player["user_id"], qid, counters[q["counter"]])


def bump_daily(conn, player, counter, amount=1):
    """Tambah progress quest harian yang counter-nya cocok."""
    today = logic.today_wib()
    for qid, q in QUESTS.items():
        if q["kind"] == "daily" and q["counter"] == counter:
            db.bump_quest(conn, player["user_id"], qid, amount, today)


def reward(conn, player, gold=0, exp=0):
    """Beri gold + exp (sudah termasuk bonus VIP), simpan, sinkron quest."""
    if gold:
        logic.add_gold(player, logic.gold_gain(player, gold))
    levels = 0
    if exp:
        levels = logic.apply_exp(
            player, logic.exp_gain(player, exp, guild_level_of(conn, player)))
    db.save_player(conn, player)
    sync_quests(conn, player)
    return levels


def hp_bar(cur, maximum, length=10):
    if maximum <= 0:
        return "░" * length
    filled = max(0, min(length, int(cur / maximum * length)))
    return "█" * filled + "░" * (length - filled)


# Alias generik: bar yang sama dipakai buat MP/EXP/stamina/durability/dll.
def bar(cur, maximum, length=10):
    return hp_bar(cur, maximum, length)


def bar_line(label, cur, maximum, length=10):
    """Satu baris bar standar: '❤️ HP ██████░░░░ 80/120'."""
    return f"{label} {bar(cur, maximum, length)} {cur}/{maximum}"


def guild_level_of(conn, player):
    if not player.get("guild_id"):
        return 0
    g = db.get_guild(conn, player["guild_id"])
    return g["level"] if g else 0


def guild_buff_text(guild_level):
    b = logic.guild_buff(guild_level)
    return f"+{b['atk']} ATK, +{b['def']} DEF, +{b['exp_pct']}% EXP"


def add_guild_exp(conn, guild_id, amount):
    g = db.get_guild(conn, guild_id)
    if not g:
        return
    g["exp"] += amount
    while g["exp"] >= 200 * g["level"]:
        g["exp"] -= 200 * g["level"]
        g["level"] += 1
    conn.execute(
        "UPDATE guilds SET exp = ?, level = ? WHERE id = ?",
        (g["exp"], g["level"], guild_id),
    )
    conn.commit()
