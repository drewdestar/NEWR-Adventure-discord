# -*- coding: utf-8 -*-
"""Cog /info: discovery encyclopedia + world history for NEWR Adventure.

Read-only, except for the info_db tables (boss_kills) and the trophy
sync that friends_db already performs. Never touches battle.py, social.py,
or any other cog's tables. All user-facing strings are English; entity
names go through display.py, so internal keys never change.

Boss kills are NOT recorded by the current raid flow (battle.py only
marks the raid 'done' and rewards participants). Until the parent adds
the hook lines from the /info report to battle.py, /info boss honestly
reports an empty history instead of inventing one.

/info needs no registration, except the power topic, which looks up the
target player's row (read-only). Rankings live in /leaderboard and
server stats in the separate Stats bot; this cog only mentions them.
"""
from datetime import date, datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import friends_db
import info_db
import logic
from data import (AREAS, BLACKMARKET_POOL, CLASSES, EVENTS, EVOLUTIONS,
                  GACHA_POOL, ITEMS, MONSTERS, PETS, PET_ADOPT_COST,
                  RECIPES, SHOP_STOCK, WEEKLY_BOSS)
from .common import (COLOR_BATTLE, COLOR_CORE, COLOR_ECONOMY, COLOR_EXTRA,
                     COLOR_PET, COLOR_PREMIUM, COLOR_SOCIAL, bar_line,
                     emb, err_embed, get_conn)

TOPIC_CHOICES = [
    app_commands.Choice(name="📅 Events", value="events"),
    app_commands.Choice(name="👹 Monsters", value="monsters"),
    app_commands.Choice(name="🗺️ Areas", value="areas"),
    app_commands.Choice(name="🐉 Boss", value="boss"),
    app_commands.Choice(name="⚔️ Guild Wars", value="guildwars"),
    app_commands.Choice(name="💪 Power", value="power"),
    app_commands.Choice(name="🎒 Items", value="items"),
    app_commands.Choice(name="🛡️ Classes", value="classes"),
    app_commands.Choice(name="🐾 Pets", value="pets"),
    app_commands.Choice(name="🌍 World", value="world"),
]

TYPE_ORDER = ["weapon", "armor", "potion", "food", "material", "seed",
              "petgear", "rare", "misc"]
TYPE_LABEL = {
    "weapon": "⚔️ Weapons", "armor": "🛡️ Armor", "potion": "🧪 Potions",
    "food": "🍽️ Food & Drink", "material": "🔩 Materials",
    "seed": "🌱 Seeds", "petgear": "🐾 Pet Gear", "rare": "✨ Rare",
    "misc": "📦 Other",
}


# ------------------------------------------------------------------ helpers
def fmt_power(n):
    """Power display: 1,234 -> '1.23k (1,234)'; 1,234,567 -> '1.23M
    (1,234,567)'; >=1e9 -> '1.23B (1,234,567,890)'. Exact value always
    shown alongside the short form."""
    n = int(n)
    if n >= 1_000_000_000:
        short = f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        short = f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        short = f"{n / 1_000:.2f}k"
    else:
        return f"{n:,}"
    return f"{short} ({n:,})"


def fmt_date(ts):
    """Unix timestamp -> '05 Nov 2026 14:32 WIB'."""
    return datetime.fromtimestamp(ts, tz=logic.WIB).strftime("%d %b %Y %H:%M WIB")


def fmt_day(d):
    return d.strftime("%d %b %Y")


def trim(text, limit=4000):
    if len(text) > limit:
        return text[:limit - 1] + "…"
    return text


def all_bosses():
    """Internal boss keys: seasonal event bosses + the weekly boss."""
    bosses = [ev["boss"] for ev in EVENTS.values()]
    if WEEKLY_BOSS["name"] not in bosses:
        bosses.append(WEEKLY_BOSS["name"])
    return bosses


def boss_source(name):
    """(hp, note) for a raid boss, or None when it is not a boss."""
    for ev_name, ev in EVENTS.items():
        if ev["boss"] == name:
            return ev["boss_hp"], (
                f"Event boss — appears in /raid during "
                f"{disp.event_name(ev_name)}.")
    if name == WEEKLY_BOSS["name"]:
        return WEEKLY_BOSS["hp"], (
            "Weekly raid boss — appears in /raid when no seasonal "
            "event is active.")
    return None


def monster_areas(name):
    return [a for a, info in AREAS.items() if name in info["monsters"]]


def event_window(name, year):
    """(start, end) dates of an event's window for a given start year."""
    (m1, d1), (m2, d2) = EVENTS[name]["months_days"]
    start = date(year, m1, d1)
    if (m1, d1) <= (m2, d2):
        end = date(year, m2, d2)
    else:
        end = date(year + 1, m2, d2)
    return start, end


def next_event_occurrences(today, count=3):
    """Next `count` event windows starting on/after `today`, sorted."""
    out = []
    for name in EVENTS:
        for year in (today.year, today.year + 1):
            start, end = event_window(name, year)
            if start >= today:
                out.append((start, end, name))
                break
    out.sort()
    return out[:count]


def item_stat_bits(info):
    bits = []
    if info.get("atk"):
        bits.append(f"ATK +{info['atk']}")
    if info.get("def"):
        bits.append(f"DEF +{info['def']}")
    if info.get("heal"):
        bits.append(f"Heals {info['heal']} HP")
    if info.get("mp"):
        bits.append(f"+{info['mp']} MP")
    if info.get("hunger"):
        bits.append(f"Hunger +{info['hunger']}")
    if info.get("thirst"):
        bits.append(f"Thirst +{info['thirst']}")
    if info.get("crop"):
        bits.append(f"Grows {disp.crop(info['crop'])} "
                    f"in {info['grow_minutes']} min")
    return " • ".join(bits)


def item_sources(key):
    sources = []
    if key in SHOP_STOCK:
        sources.append("Shop (/shop)")
    if key in BLACKMARKET_POOL:
        sources.append("Black Market (/blackmarket, daily stock)")
    if key in RECIPES:
        needs = ", ".join(
            f"{disp.item(k)} x{v}"
            for k, v in RECIPES[key]["needs"].items())
        sources.append(
            f"Craftable: {needs} + {RECIPES[key]['gold']} gold")
    droppers = [m for m, info in MONSTERS.items() if key in info["loot"]]
    if droppers:
        sources.append("Dropped by: " + ", ".join(
            disp.monster(m) for m in droppers))
    tiers = [t for t, pool in GACHA_POOL.items() if key in pool]
    if tiers:
        sources.append("Gacha: " + ", ".join(tiers))
    return sources


def player_name(conn, user_id):
    p = db.get_player(conn, user_id)
    return p["name"] if p else f"User {user_id}"


def guild_name(conn, guild_id):
    g = db.get_guild(conn, guild_id)
    return g["name"] if g else "a rival guild"


def active_raid_line(conn):
    """One-line summary of the active raid, or None."""
    raid = db.active_raid(conn)
    if not raid:
        return None
    members = db.raid_members(conn, raid["id"])
    return (f"🐉 Active raid: **{disp.monster(raid['boss'])}** — "
            f"{raid['hp']}/{raid['max_hp']} HP "
            f"({len(members)} joined). Attack with /raid!")


async def name_autocomplete(interaction: discord.Interaction, current: str):
    """Name suggestions depend on the chosen topic."""
    topic = ""
    for opt in interaction.data.get("options", []):
        if opt.get("name") == "topic":
            topic = opt.get("value", "") or ""
    cur = (current or "").lower()

    def _filter(pairs):
        out = []
        for label, value in pairs:
            if cur and cur not in label.lower() and cur not in value.lower():
                continue
            out.append(app_commands.Choice(name=label[:100], value=value))
            if len(out) >= 25:
                break
        return out

    if topic == "monsters":
        pairs = [(disp.monster(m), m) for m in MONSTERS]
        pairs += [(disp.monster(b), b) for b in all_bosses()
                  if b not in MONSTERS]
        return _filter(pairs)
    if topic == "areas":
        return _filter([(disp.area(a), a) for a in AREAS])
    if topic == "boss":
        return _filter([(disp.monster(b), b) for b in all_bosses()])
    if topic == "items":
        return _filter([(disp.item(k), k) for k in ITEMS])
    if topic == "classes":
        return _filter([(c, c) for c in CLASSES])
    if topic == "pets":
        return _filter([(disp.pet(s), s) for s in PETS])
    if topic == "guildwars":
        try:
            conn = get_conn()
            rows = conn.execute(
                "SELECT name FROM guilds WHERE name LIKE ? "
                "ORDER BY name LIMIT 25",
                (f"%{current}%",)).fetchall()
            conn.close()
            return [app_commands.Choice(name=r["name"][:100],
                                        value=r["name"]) for r in rows]
        except Exception:
            return []
    return []


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="info",
        description="Discover events, monsters, areas, bosses, guild wars, "
                    "items, classes, pets, and world status")
    @app_commands.describe(
        topic="What do you want to look up?",
        name="Name (monster, area, item, class, pet, boss, or guild)",
        user="Player: mention or user ID (only for the power topic)")
    @app_commands.choices(topic=TOPIC_CHOICES)
    @app_commands.autocomplete(name=name_autocomplete)
    async def info(self, interaction: discord.Interaction, topic: str,
                   name: str = "",
                   user: Optional[discord.User] = None):
        conn = get_conn()
        info_db.ensure_tables(conn)
        handler = {
            "events": self._events,
            "monsters": self._monsters,
            "areas": self._areas,
            "boss": self._boss,
            "guildwars": self._guildwars,
            "power": self._power,
            "items": self._items,
            "classes": self._classes,
            "pets": self._pets,
            "world": self._world,
        }.get(topic)
        if handler is None:
            await interaction.response.send_message(
                embed=err_embed("Unknown info topic."), ephemeral=True)
            return
        await handler(interaction, conn, name.strip(), user)

    # ---------------------------------------------------------------- events
    async def _events(self, interaction, conn, name, user):
        today = datetime.now(logic.WIB).date()
        active = logic.active_events()
        lines = []
        if active:
            for ev_name, ev in active:
                # Pick the window actually containing today (year-boundary
                # events active in January started last year).
                end = None
                for year in (today.year, today.year - 1):
                    _s, e = event_window(ev_name, year)
                    if _s <= today <= e:
                        end = e
                        break
                if end is None:
                    _s, end = event_window(ev_name, today.year)
                shop = ", ".join(disp.item(s) for s in ev["shop"])
                lines.append(
                    f"🎉 **{disp.event_name(ev_name)}** — ACTIVE NOW "
                    f"(ends {fmt_day(end)})\n"
                    f"{disp.event_desc(ev_name)}\n"
                    f"Boss: **{disp.event_boss(ev_name)}** • "
                    f"Event stock: {shop}")
        else:
            lines.append("No seasonal event is active right now.")
        upcoming = next_event_occurrences(today)
        up_lines = []
        for start, end, ev_name in upcoming:
            # Skip the window of an event that is already active.
            if any(ev_name == a[0] for a in active):
                continue
            up_lines.append(
                f"• **{disp.event_name(ev_name)}** — "
                f"{fmt_day(start)} to {fmt_day(end)} "
                f"(boss: {disp.event_boss(ev_name)})")
        desc = "\n\n".join(lines)
        if up_lines:
            desc += "\n\n**Upcoming:**\n" + "\n".join(up_lines)
        desc += (f"\n\nWhen no event is active, the weekly raid boss is "
                 f"**{disp.monster(WEEKLY_BOSS['name'])}** "
                 f"({WEEKLY_BOSS['hp']} HP).")
        await interaction.response.send_message(embed=emb(
            "📅 Seasonal Events", desc, color=COLOR_PREMIUM))

    # -------------------------------------------------------------- monsters
    async def _monsters(self, interaction, conn, name, user):
        if not name:
            sections = []
            for area, info in AREAS.items():
                lines = []
                for m in info["monsters"]:
                    mon = MONSTERS[m]
                    lines.append(
                        f"• **{disp.monster(m)}** — ❤️ {mon['hp']} "
                        f"⚔️ {mon['atk']} 🛡️ {mon['def']} • "
                        f"{mon['exp']} EXP")
                sections.append(
                    f"**{disp.area(area)}** (Lv {info['min_level']}+)\n"
                    + "\n".join(lines))
            desc = ("\n\n".join(sections)
                    + "\n\nSee details with /info topic:Monsters "
                      "name:<monster>. Monster stats scale with your "
                      "level in /fight.")
            await interaction.response.send_message(embed=emb(
                "👹 Monster Bestiary", trim(desc), color=COLOR_BATTLE))
            return
        key = disp.resolve_monster(name)
        if not key:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Monster '{name}' not found. Browse them all with "
                    f"/info topic:Monsters."),
                ephemeral=True)
            return
        if key in MONSTERS:
            mon = MONSTERS[key]
            areas = monster_areas(key)
            desc = (
                f"❤️ HP: **{mon['hp']}** • ⚔️ ATK: **{mon['atk']}** • "
                f"🛡️ DEF: **{mon['def']}**\n"
                f"⭐ EXP: **{mon['exp']}** • 💰 Gold: "
                f"**{mon['gold'][0]}–{mon['gold'][1]}**\n"
                f"🎁 Loot: {', '.join(disp.item(i) for i in mon['loot'])}\n"
                f"🗺️ Found in: {', '.join(disp.area(a) for a in areas)}\n\n"
                f"Stats scale with your level in /fight.")
            title = f"👹 {disp.monster(key)}"
        else:
            hp, note = boss_source(key)
            kills = info_db.boss_kill_count(conn, key)
            desc = (f"🐉 Raid boss — **{hp} HP**\n{note}\n"
                    f"Recorded kills: **{kills}** "
                    f"(see /info topic:Boss name:{disp.monster(key)}).")
            title = f"🐉 {disp.monster(key)}"
        await interaction.response.send_message(embed=emb(
            title, desc, color=COLOR_BATTLE))

    # ----------------------------------------------------------------- areas
    async def _areas(self, interaction, conn, name, user):
        if not name:
            sections = []
            for area, info in AREAS.items():
                mons = ", ".join(disp.monster(m)
                                 for m in info["monsters"])
                sections.append(
                    f"**{disp.area(area)}** (Lv {info['min_level']}+) — "
                    f"{len(info['monsters'])} monsters: {mons}")
            desc = ("\n\n".join(sections)
                    + "\n\nSee details with /info topic:Areas "
                      "name:<area>.")
            await interaction.response.send_message(embed=emb(
                "🗺️ Hunting Areas", trim(desc), color=COLOR_CORE))
            return
        key = disp.resolve_area(name)
        if not key:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Area '{name}' not found. Browse them all with "
                    f"/info topic:Areas."),
                ephemeral=True)
            return
        info = AREAS[key]
        lines = []
        for m in info["monsters"]:
            mon = MONSTERS[m]
            lines.append(
                f"• **{disp.monster(m)}** — ❤️ {mon['hp']} "
                f"⚔️ {mon['atk']} 🛡️ {mon['def']} • {mon['exp']} EXP • "
                f"💰 {mon['gold'][0]}–{mon['gold'][1]} gold")
        desc = (f"Minimum level: **{info['min_level']}**\n\n"
                + "\n".join(lines))
        await interaction.response.send_message(embed=emb(
            f"🗺️ {disp.area(key)}", desc, color=COLOR_CORE))

    # ------------------------------------------------------------------ boss
    async def _boss(self, interaction, conn, name, user):
        info_db.ensure_tables(conn)
        if name:
            key = disp.resolve_monster(name)
            if not key or (key not in MONSTERS and not boss_source(key)):
                # Fall back to an exact boss key seen in kill history.
                known = {r["boss"] for r in conn.execute(
                    "SELECT DISTINCT boss FROM boss_kills").fetchall()}
                key = name if name in known else None
            if not key:
                await interaction.response.send_message(
                    embed=err_embed(
                        f"Boss '{name}' not found. Bosses are the "
                        f"seasonal event bosses and the weekly boss — "
                        f"browse them with /info topic:Boss."),
                    ephemeral=True)
                return
            kills = info_db.recent_boss_kills(conn, key, limit=10)
            total = info_db.boss_kill_count(conn, key)
            title = f"🐉 {disp.monster(key)} — Kill History"
            if not kills:
                desc = (f"No recorded kills of **{disp.monster(key)}** "
                        f"yet. Be the first to land the killing blow "
                        f"in a /raid!")
            else:
                lines = []
                for k in kills:
                    lines.append(
                        f"• **{player_name(conn, k['killer_id'])}** — "
                        f"power {fmt_power(k['killer_power'])} "
                        f"(killing hit: {k['killer_damage']} damage) — "
                        f"{fmt_date(k['killed_at'])}")
                desc = (f"Total recorded kills: **{total}**\n\n"
                        + "\n".join(lines))
        else:
            kills = info_db.recent_boss_kills(conn, limit=10)
            total = info_db.boss_kill_count(conn)
            title = "🐉 Boss Kill History"
            if not kills:
                desc = ("No boss kills recorded yet. Be the first to "
                        "land the killing blow on a raid boss with "
                        "/raid — the killer's name and power will be "
                        "logged here.")
            else:
                lines = []
                for k in kills:
                    lines.append(
                        f"• **{disp.monster(k['boss'])}** — killed by "
                        f"**{player_name(conn, k['killer_id'])}** "
                        f"(power {fmt_power(k['killer_power'])}) — "
                        f"{fmt_date(k['killed_at'])}")
                desc = (f"Total recorded kills: **{total}**\n\n"
                        + "\n".join(lines))
        raid_line = active_raid_line(conn)
        if raid_line:
            desc += f"\n\n{raid_line}"
        await interaction.response.send_message(embed=emb(
            title, trim(desc), color=COLOR_BATTLE))

    # ------------------------------------------------------------- guildwars
    async def _guildwars(self, interaction, conn, name, user):
        friends_db.ensure_tables(conn)
        friends_db.sync_war_trophies(conn)
        if name:
            g = db.get_guild_by_name(conn, name)
            if not g:
                await interaction.response.send_message(
                    embed=err_embed(
                        f"Guild '{name}' not found."),
                    ephemeral=True)
                return
            done = conn.execute(
                "SELECT * FROM wars WHERE state = 'done' AND "
                "(guild_a = ? OR guild_b = ?) "
                "ORDER BY id DESC LIMIT 10",
                (g["id"], g["id"])).fetchall()
            wins = conn.execute(
                "SELECT COUNT(*) AS c FROM wars WHERE state = 'done' "
                "AND winner_id = ?", (g["id"],)).fetchone()["c"]
            losses = conn.execute(
                "SELECT COUNT(*) AS c FROM wars WHERE state = 'done' "
                "AND (guild_a = ? OR guild_b = ?) AND winner_id != ?",
                (g["id"], g["id"], g["id"])).fetchone()["c"]
            trophies = friends_db.guild_trophy_count(conn, g["id"])
            title = f"⚔️ {g['name']} — War History"
            desc = (f"Record: **{wins} wins / {losses} losses** • "
                    f"🏆 War trophies: **{trophies}**\n\n")
            if not done:
                desc += "This guild has never finished a war."
            else:
                lines = []
                for w in done:
                    w = dict(w)
                    won = w["winner_id"] == g["id"]
                    foe_id = (w["guild_b"] if w["guild_a"] == g["id"]
                              else w["guild_a"])
                    lines.append(
                        f"• {'🏆 WON' if won else '💔 Lost'} vs "
                        f"**{guild_name(conn, foe_id)}** "
                        f"({w['score_a']} vs {w['score_b']}) — "
                        f"{fmt_date(w['resolves_at'])}")
                desc += "\n".join(lines)
        else:
            done = conn.execute(
                "SELECT * FROM wars WHERE state = 'done' "
                "ORDER BY id DESC LIMIT 10").fetchall()
            title = "⚔️ Guild War History"
            if not done:
                desc = "No guild war has finished yet."
            else:
                lines = []
                for w in done:
                    w = dict(w)
                    winner = guild_name(conn, w["winner_id"])
                    loser_id = (w["guild_b"] if w["winner_id"] == w["guild_a"]
                                else w["guild_a"])
                    loser = guild_name(conn, loser_id)
                    trophies = friends_db.guild_trophy_count(
                        conn, w["winner_id"])
                    lines.append(
                        f"• **{winner}** beat **{loser}** "
                        f"({w['score_a']} vs {w['score_b']}) — "
                        f"{fmt_date(w['resolves_at'])} • "
                        f"🏆 {winner} now has {trophies} trophies")
                desc = "\n".join(lines)
        pending = conn.execute(
            "SELECT * FROM wars WHERE state = 'pending' "
            "ORDER BY resolves_at LIMIT 5").fetchall()
        if pending:
            now = int(datetime.now().timestamp())
            p_lines = []
            for w in pending:
                w = dict(w)
                left = max(0, w["resolves_at"] - now)
                when = (f"resolves in ~{left // 60} min" if left > 0
                        else "resolving — check /guildwar info")
                p_lines.append(
                    f"• **{guild_name(conn, w['guild_a'])}** vs "
                    f"**{guild_name(conn, w['guild_b'])}** — {when}")
            desc += "\n\n**Pending wars:**\n" + "\n".join(p_lines)
        await interaction.response.send_message(embed=emb(
            title, trim(desc), color=COLOR_SOCIAL))

    # ----------------------------------------------------------------- power
    async def _power(self, interaction, conn, name, user):
        target = user or interaction.user
        p = db.get_player(conn, target.id)
        if not p:
            await interaction.response.send_message(
                embed=err_embed(
                    "That player hasn't registered a character yet."),
                ephemeral=True)
            return
        power = friends_db.member_power(p)
        evo = EVOLUTIONS.get((p["class"], p["evo_stage"]))
        class_display = evo[0] if evo else p["class"]
        guild_txt = ""
        if p.get("guild_id"):
            guild_txt = f"\n🏰 Guild: **{guild_name(conn, p['guild_id'])}**"
        desc = (
            f"**{p['name']}** — {class_display} • Lv **{p['level']}**"
            f"{guild_txt}\n"
            f"💪 Power: **{fmt_power(power)}**\n"
            f"❤️ HP {p['hp']}/{p['max_hp']} • 💙 MP {p['mp']}/{p['max_mp']}\n"
            f"⚔️ ATK {p['atk']} • 🛡️ DEF {p['def']} • 💨 SPD {p['spd']}\n"
            f"🏆 Wins {p['wins']} • 👹 Kills {p['kills']} • "
            f"💰 Gold {fmt_power(p['gold'])}\n\n"
            f"Power = Lv×10 + ATK + DEF + wins×5 "
            f"(same formula as /guildpower). "
            f"See /leaderboard for rankings.")
        await interaction.response.send_message(embed=emb(
            f"💪 Power of {p['name']}", desc, color=COLOR_CORE))

    # ----------------------------------------------------------------- items
    async def _items(self, interaction, conn, name, user):
        if not name:
            sections = []
            for t in TYPE_ORDER:
                keys = [k for k, v in ITEMS.items() if v["type"] == t]
                if not keys:
                    continue
                lines = []
                for k in keys:
                    info = ITEMS[k]
                    bits = item_stat_bits(info)
                    lines.append(
                        f"• **{disp.item(k)}** — {info['price']}g"
                        + (f" ({bits})" if bits else ""))
                sections.append(f"**{TYPE_LABEL[t]}**\n" + "\n".join(lines))
            desc = ("\n\n".join(sections)
                    + "\n\nSee details with /info topic:Items "
                      "name:<item>.")
            await interaction.response.send_message(embed=emb(
                "🎒 Item Encyclopedia", trim(desc), color=COLOR_ECONOMY))
            return
        key = disp.resolve_item(name)
        if not key:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Item '{name}' not found. Browse them all with "
                    f"/info topic:Items."),
                ephemeral=True)
            return
        info = ITEMS[key]
        bits = item_stat_bits(info)
        desc = (f"Type: **{TYPE_LABEL.get(info['type'], info['type'])}**\n"
                f"Shop price: **{info['price']} gold**\n")
        if bits:
            desc += f"Effect: {bits}\n"
        sources = item_sources(key)
        desc += ("\n**Where to get it:**\n" + "\n".join(
            f"• {s}" for s in sources) if sources
            else "\nNo known source (event or special reward?).")
        await interaction.response.send_message(embed=emb(
            f"🎒 {disp.item(key)}", desc, color=COLOR_ECONOMY))

    # --------------------------------------------------------------- classes
    async def _classes(self, interaction, conn, name, user):
        if not name:
            lines = []
            for cls, base in CLASSES.items():
                lines.append(
                    f"**{cls}** — ❤️ {base['hp']} HP • 💙 {base['mp']} MP "
                    f"• ⚔️ {base['atk']} ATK • 🛡️ {base['def']} DEF • "
                    f"💨 {base['spd']} SPD\n"
                    f"Skill: **{disp.skill(base['skill'])}** "
                    f"(×{base['skill_mult']} damage)")
            desc = ("\n\n".join(lines)
                    + "\n\nSee evolutions with /info topic:Classes "
                      "name:<class>.")
            await interaction.response.send_message(embed=emb(
                "🛡️ Class Guide", desc, color=COLOR_CORE))
            return
        key = None
        for cls in CLASSES:
            if cls.lower() == name.lower():
                key = cls
                break
        if not key:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Class '{name}' not found. Classes: "
                    + ", ".join(CLASSES) + "."),
                ephemeral=True)
            return
        base = CLASSES[key]
        lines = [
            f"Base stats: ❤️ {base['hp']} HP • 💙 {base['mp']} MP • "
            f"⚔️ {base['atk']} ATK • 🛡️ {base['def']} DEF • "
            f"💨 {base['spd']} SPD",
            f"Skill: **{disp.skill(base['skill'])}** "
            f"(×{base['skill_mult']} damage)",
        ]
        for stage in (1, 2):
            evo = EVOLUTIONS.get((key, stage))
            if evo:
                ename, lvl, bonus = evo
                b = ", ".join(f"+{v} {k.upper()}"
                              for k, v in bonus.items())
                lines.append(
                    f"Evolution {stage}: **{ename}** (Lv {lvl}+) — {b}")
        desc = "\n".join(lines)
        await interaction.response.send_message(embed=emb(
            f"🛡️ Class: {key}", desc, color=COLOR_CORE))

    # ------------------------------------------------------------------ pets
    async def _pets(self, interaction, conn, name, user):
        if not name:
            lines = []
            for species, spec in PETS.items():
                forms = " → ".join(disp.pet_form(f)
                                   for f in spec["forms"])
                lines.append(
                    f"**{disp.pet(species)}** — "
                    f"Skill: **{disp.pet_skill(spec['skill'])}** "
                    f"(×{spec['skill_mult']}) • Base ATK +{spec['atk']}\n"
                    f"Forms: {forms}")
            desc = ("\n\n".join(lines)
                    + f"\n\nAdoption costs {PET_ADOPT_COST} gold. "
                      f"See details with /info topic:Pets name:<pet>, "
                      f"and adopt with /pet.")
            await interaction.response.send_message(embed=emb(
                "🐾 Pet Guide", desc, color=COLOR_PET))
            return
        key = disp.resolve_pet(name)
        if not key:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Pet '{name}' not found. Species: "
                    + ", ".join(disp.pet(s) for s in PETS) + "."),
                ephemeral=True)
            return
        spec = PETS[key]
        forms = [(1, spec["forms"][0]), (10, spec["forms"][1]),
                 (25, spec["forms"][2])]
        form_lines = "\n".join(
            f"• Lv {lv}+: **{disp.pet_form(f)}**" for lv, f in forms)
        desc = (
            f"Skill: **{disp.pet_skill(spec['skill'])}** "
            f"(×{spec['skill_mult']} damage)\n"
            f"Base ATK bonus: **+{spec['atk']}** "
            f"(+1 per 2 pet levels)\n"
            f"Adoption cost: **{PET_ADOPT_COST} gold**\n\n"
            f"**Evolutions:**\n{form_lines}\n\n"
            f"Pets fight alongside you and gain EXP from fight wins.")
        await interaction.response.send_message(embed=emb(
            f"🐾 {disp.pet(key)}", desc, color=COLOR_PET))

    # ----------------------------------------------------------------- world
    async def _world(self, interaction, conn, name, user):
        now_wib = datetime.now(logic.WIB)
        today = now_wib.date()
        active = logic.active_events()
        if active:
            event_txt = ", ".join(
                f"**{disp.event_name(n)}** (boss: "
                f"{disp.event_boss(n)})" for n, _e in active)
        else:
            event_txt = "No seasonal event active."
        upcoming = next_event_occurrences(today, count=1)
        next_txt = "No upcoming event scheduled."
        if upcoming:
            start, end, ev_name = upcoming[0]
            if not any(ev_name == a[0] for a in active):
                next_txt = (f"**{disp.event_name(ev_name)}** — "
                            f"{fmt_day(start)} to {fmt_day(end)}")
        if logic.meteor_window_now(now_wib):
            meteor_txt = ("☄️ Meteor shower is LIVE right now "
                          "(21:00–21:59 WIB)! Catch one with /meteor.")
        else:
            nxt = now_wib.replace(hour=21, minute=0, second=0,
                                  microsecond=0)
            if now_wib >= nxt:
                nxt += timedelta(days=1)
            meteor_txt = (f"Next meteor shower: "
                          f"{nxt.strftime('%d %b %Y 21:00 WIB')}.")
        raid_line = active_raid_line(conn)
        raid_txt = raid_line or "No active raid — start one with /raid."
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM wars WHERE state = 'pending'"
        ).fetchone()["c"]
        players = conn.execute(
            "SELECT COUNT(*) AS c FROM players").fetchone()["c"]
        guilds = conn.execute(
            "SELECT COUNT(*) AS c FROM guilds").fetchone()["c"]
        desc = (
            f"📅 Events: {event_txt}\n"
            f"🔜 Next event: {next_txt}\n"
            f"{meteor_txt}\n"
            f"{raid_txt}\n"
            f"⚔️ Pending guild wars: **{pending}**\n"
            f"👥 Players: **{players}** • 🏰 Guilds: **{guilds}**\n\n"
            f"Rankings live in /leaderboard.")
        await interaction.response.send_message(embed=emb(
            "🌍 World Status", desc, color=COLOR_EXTRA))


async def setup(bot):
    await bot.add_cog(Info(bot))
