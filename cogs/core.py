# -*- coding: utf-8 -*-
"""Cog inti: register, profile, evolve, daily, inventory, map, quest, help."""
import random
import time
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import i18n
import logic
import rolesync
from data import AREAS, CLASSES, EVOLUTIONS, ITEMS, MONSTERS, QUESTS
from .common import (COLOR_CORE, bar_line, bump_daily, emb, err_embed,
                     get_conn, guild_buff_text, guild_level_of,
                     load_player, need_player, reward, sync_quests, warnings_for)

STARTER_WEAPON = {
    "Warrior": "pedang kayu",
    "Mage": "tongkat kayu",
    "Archer": "busur kayu",
    "Assassin": "belati kayu",
}


def apply_use_item(conn, p, item):
    """Pakai satu item. Kembalikan (ok, teks). Dipakai command & tombol inventory."""
    info = ITEMS[item]
    name = disp.item(item)
    if info["type"] == "potion":
        if p["hp"] >= p["max_hp"] and p["mp"] >= p["max_mp"]:
            return False, "Your HP and MP are already full, don't waste the potion!"
        heal = info.get("heal", 0)
        p["hp"] = min(p["max_hp"], p["hp"] + heal)
        if info.get("mp"):
            p["mp"] = min(p["max_mp"], p["mp"] + info["mp"])
        db.remove_item(conn, p["user_id"], item, 1)
        db.save_player(conn, p)
        return True, '🧪 You used {item}! HP now {hp}/{maxhp}, MP {mp}/{maxmp}.'.format(item=name, hp=p['hp'], maxhp=p['max_hp'], mp=p['mp'], maxmp=p['max_mp'])
    if info["type"] == "food":
        p["hunger"] = min(100, p["hunger"] + info.get("hunger", 0))
        p["thirst"] = min(100, p["thirst"] + info.get("thirst", 0))
        db.remove_item(conn, p["user_id"], item, 1)
        db.save_player(conn, p)
        return True, '🍽️ You ate/drank {item}! Hunger {hunger}/100, Thirst {thirst}/100.'.format(item=name, hunger=p['hunger'], thirst=p['thirst'])
    return False, "{item} can't be used directly. Weapons/armor are equipped, seeds are planted at `/house`.".format(item=name)


def apply_equip_item(conn, p, item):
    """Pasang senjata/armor. Kembalikan (ok, teks)."""
    info = ITEMS[item]
    name = disp.item(item)
    if info["type"] not in ("weapon", "armor"):
        return False, 'Only weapons and armor can be equipped.'
    inv = db.get_inventory(conn, p["user_id"])
    for row in inv:
        if row["equipped"] and ITEMS.get(row["item_id"], {}).get("type") == info["type"]:
            db.set_equipped(conn, row["id"], 0)
    target = next((r for r in inv if r["item_id"] == item and not r["equipped"]), None)
    if target is None:
        return False, 'No {item} available to equip right now.'.format(item=name)
    db.set_equipped(conn, target["id"], 1)
    return True, '⚔️ {item} equipped!'.format(item=name)


def apply_unequip_item(conn, p, item):
    """Lepas gear. Kembalikan (ok, teks)."""
    inv = db.get_inventory(conn, p["user_id"])
    name = disp.item(item)
    rows = [r for r in inv if r["item_id"] == item and r["equipped"]]
    if not rows:
        return False, "{item} isn't equipped right now.".format(item=name)
    db.set_equipped(conn, rows[0]["id"], 0)
    return True, '{item} unequipped.'.format(item=name)


class InventorySelect(discord.ui.Select):
    """Pilih item dari tas, lalu muncul tombol aksi buat item itu."""

    def __init__(self, owner_id, inv):
        self.owner_id = owner_id
        options = []
        for row in inv[:25]:
            desc = f"x{row['qty']}"
            if row["equipped"]:
                desc += ' • equipped'
            if ITEMS.get(row["item_id"], {}).get("type") in ("weapon", "armor"):
                desc += ' • durability {d}'.format(d=row['durability'])
            options.append(discord.SelectOption(
                label=disp.item(row["item_id"])[:100], description=desc[:100],
                value=row["item_id"]))
        super().__init__(placeholder='Choose an item...', options=options)

    async def callback(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("That's someone else's bag!"), ephemeral=True)
            return
        item = self.values[0]
        info = ITEMS[item]
        bonus = ""
        if "atk" in info:
            bonus = f" (+{info['atk']} ATK)"
        elif "def" in info:
            bonus = f" (+{info['def']} DEF)"
        elif "heal" in info:
            bonus = f" (heal {info['heal']})"
        e = emb(f"🎒 {disp.item(item)}",
                'Type: {tipe}{bonus} • Shop price: {harga} gold. Choose an action below.'.format(tipe=info['type'], bonus=bonus, harga=info['price']),
                color=COLOR_CORE)
        await interaction.response.edit_message(
            embed=e, view=ItemActionView(self.owner_id, item))


class InventoryView(discord.ui.View):
    def __init__(self, owner_id, inv):
        super().__init__(timeout=300)
        self.add_item(InventorySelect(owner_id, inv))


class ItemActionView(discord.ui.View):
    """Tombol Pakai / Pasang / Lepas buat satu item terpilih."""

    def __init__(self, owner_id, item):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.item = item

    async def _act(self, interaction, fn, title):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("That's someone else's bag!"), ephemeral=True)
            return
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if db.item_qty(conn, p["user_id"], self.item) < 1:
            await interaction.response.send_message(
                embed=err_embed("You don't have {item}.".format(item=disp.item(self.item))),
                ephemeral=True)
            return
        ok, text = fn(conn, p)
        if ok:
            await interaction.response.send_message(
                embed=emb(title, text, color=COLOR_CORE), ephemeral=True)
        else:
            await interaction.response.send_message(
                embed=err_embed(text), ephemeral=True)

    @discord.ui.button(label="Use", style=discord.ButtonStyle.primary, emoji="🧪")
    async def use_btn(self, interaction, button):
        await self._act(interaction, apply_use_item, "🎒 Inventory")

    @discord.ui.button(label="Equip", style=discord.ButtonStyle.success, emoji="⚔️")
    async def equip_btn(self, interaction, button):
        await self._act(interaction, apply_equip_item, "🎒 Inventory")

    @discord.ui.button(label="Unequip", style=discord.ButtonStyle.secondary, emoji="📦")
    async def unequip_btn(self, interaction, button):
        await self._act(interaction, apply_unequip_item, "🎒 Inventory")


class Core(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------ register
    @app_commands.command(name="register", description="Create your RPG character")
    @app_commands.describe(name="Your character name", cls="Starting class")
    @app_commands.rename(cls="class")
    @app_commands.choices(cls=[
        app_commands.Choice(name="Warrior", value="Warrior"),
        app_commands.Choice(name="Mage", value="Mage"),
        app_commands.Choice(name="Archer", value="Archer"),
        app_commands.Choice(name="Assassin", value="Assassin"),
    ])
    async def register(self, interaction: discord.Interaction, name: str, cls: str):
        conn = get_conn()
        i18n.set_ctx(interaction, conn)
        if db.get_player(conn, interaction.user.id):
            await interaction.response.send_message(
                embed=err_embed('You already have a character! Check with `/profile`.'),
                ephemeral=True)
            return
        if len(name) > 24 or not name.strip():
            await interaction.response.send_message(
                embed=err_embed('Character names must be 1-24 characters.'), ephemeral=True)
            return
        # Tier + luck roll: every new registration differs in power.
        # The class skill never changes; only the stats are randomised.
        # Existing players are never re-rolled (early return above).
        tier, pct, bonus_items = logic.roll_starter_tier()
        stats = logic.apply_starter_bonus(CLASSES[cls], pct)
        p = db.create_player(conn, interaction.user.id, name.strip(), cls, stats,
                             starter_tier=tier, starter_bonus_pct=pct)
        pack = [(STARTER_WEAPON[cls], 1), ("armor kulit", 1), ("potion kecil", 3),
                ("roti", 2), ("air minum", 2)]
        for item, qty in bonus_items.items():
            pack.append((item, qty))
        for item, qty in pack:
            db.add_item(conn, interaction.user.id, item, qty)
        merged = {}
        for item, qty in pack:
            merged[item] = merged.get(item, 0) + qty
        pack_txt = ", ".join(
            f"{qty} {disp.item(item)}" if qty > 1 else disp.item(item)
            for item, qty in merged.items())
        e = emb("🎮 Character Created!",
                "\n".join([
                    i18n.t("Welcome, **{name}** the {cls}!").format(name=p["name"], cls=cls),
                    i18n.t("Starter tier: **{tier}** (+{pct}% stats)").format(tier=tier, pct=pct),
                    i18n.t("Starting skill: **{skill}**").format(skill=disp.skill(stats["skill"])),
                    i18n.t("Stats: HP {hp} • MP {mp} • ATK {atk} • DEF {df} • SPD {spd}").format(
                        hp=p["hp"], mp=p["mp"], atk=p["atk"], df=p["def"], spd=p["spd"]),
                    i18n.t("Starter pack: {pack}").format(pack=pack_txt),
                    i18n.t("Your Discord ID (copy it for ID commands like /profile):\n```{id}```").format(id=interaction.user.id),
                    i18n.t("First steps: `/daily` for daily rewards, then `/fight` to hunt!"),
                ]))
        await interaction.response.send_message(embed=e)
        if interaction.guild is not None:
            try:
                member = interaction.guild.get_member(interaction.user.id)
                if member is None:
                    member = await interaction.guild.fetch_member(
                        interaction.user.id)
                if member is not None:
                    await rolesync.sync_member_roles(
                        interaction.guild, member, p, conn)
            except Exception as exc:
                print(f"WARNING: role sync after register failed: {exc}")

    # ------------------------------------------------------------- profile
    @app_commands.command(name="profile", description="View a character profile")
    @app_commands.describe(user="Player to look up: mention, user ID, or leave empty for your own profile")
    async def profile(self, interaction: discord.Interaction,
                      user: Optional[discord.User] = None):
        conn = get_conn()
        if user is None:
            p = await need_player(interaction, conn)
            if not p:
                return
        else:
            i18n.set_ctx(interaction, conn)
            p = load_player(conn, user.id)
            if p is None:
                await interaction.response.send_message(
                    embed=err_embed("That user doesn't have a character yet."),
                    ephemeral=True)
                return
        await interaction.response.send_message(
            embed=self._profile_embed(conn, p))
    def _profile_embed(self, conn, p):
        eq = db.equipped_items(conn, p["user_id"])
        pets = db.get_pets(conn, p["user_id"])
        atk, defense, spd = logic.effective_stats(p, eq, pets[0] if pets else None)
        evo_name = p["class"]
        for (base, stage), (name, _lvl, _b) in EVOLUTIONS.items():
            if base == p["class"] and stage == p["evo_stage"]:
                evo_name = name
        guild_txt = "-"
        if p["guild_id"]:
            g = db.get_guild(conn, p["guild_id"])
            if g:
                guild_txt = f"{g['name']} (Lv {g['level']}, buff {guild_buff_text(g['level'])})"
        pet_txt = "-"
        if pets:
            pet = pets[0]
            pet_txt = f"{disp.pet_form(logic.pet_form(pet['species'], pet['level']))} Lv {pet['level']}"
        vip_txt = i18n.t('Not active')
        if logic.vip_active(p):
            until = datetime.fromtimestamp(p["vip_until"]).strftime("%d %b %Y")
            vip_txt = i18n.t('✅ Active until {until}').format(until=until)
        e = emb(f"🧙 {p['name']} — {evo_name} Lv {p['level']}",
                "\n".join([
                    bar_line('❤️ HP', p['hp'], p['max_hp']),
                    bar_line('💙 MP', p['mp'], p['max_mp']),
                    f"{bar_line('✨ EXP', p['exp'], logic.exp_needed(p['level']))} • Gold 💰 {p['gold']}",
                    f"ATK {atk} • DEF {defense} • SPD {spd}",
                    bar_line(i18n.t('🍗 Hunger'), p['hunger'], 100),
                    bar_line(i18n.t('💧 Thirst'), p['thirst'], 100),
                    bar_line('⚡ Stamina', p['stamina'], 100),
                    i18n.t('🐾 Pet: {pet}').format(pet=pet_txt),
                    i18n.t('🏰 Guild: {guild}').format(guild=guild_txt),
                    i18n.t('👑 VIP: {vip}').format(vip=vip_txt),
                    i18n.t('📖 Story chapter: {ch} • 🏠 House Lv {lv}').format(ch=p['story_chapter'],lv=p['house_level']),
                    i18n.t('🔥 Daily streak: {n} days').format(n=p['streak']),
                ]),
                color=COLOR_CORE)
        for w in warnings_for(p):
            e.add_field(name=i18n.t('Warning'), value=w, inline=False)
        return e

    # -------------------------------------------------------------- evolve
    @app_commands.command(name="evolve", description="Evolve your class to the next job")
    async def evolve(self, interaction: discord.Interaction):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        nxt = logic.evolution_for(p["class"], p["evo_stage"] + 1)
        if nxt is None:
            await interaction.response.send_message(
                embed=emb('✨ Evolution',"You're already at the highest evolution, awesome!",
                          color=COLOR_CORE),
                ephemeral=True)
            return
        name, min_level, bonus = nxt
        if p["level"] < min_level:
            await interaction.response.send_message(
                embed=err_embed("Can't evolve yet! {name} needs level {lvl}, you're still Lv {clvl}.".format(name=name,lvl=min_level,clvl=p['level'])),
                ephemeral=True)
            return
        p["evo_stage"] += 1
        p["max_hp"] += bonus["hp"]
        p["max_mp"] += bonus["mp"]
        p["atk"] += bonus["atk"]
        p["def"] += bonus["def"]
        p["spd"] += bonus["spd"]
        p["hp"] = p["max_hp"]
        p["mp"] = p["max_mp"]
        db.save_player(conn, p)
        await interaction.response.send_message(embed=emb('✨ EVOLUTION!',
            '**{name}** evolved into **{evo}**!\nBonus: +{hp} HP, +{mp} MP, +{atk} ATK, +{dfn} DEF, +{spd} SPD. HP/MP fully restored!'.format(name=p['name'],evo=name,hp=bonus['hp'],mp=bonus['mp'],atk=bonus['atk'],dfn=bonus['def'],spd=bonus['spd']),
            color=COLOR_CORE))

    # --------------------------------------------------------------- daily
    @app_commands.command(name="daily", description="Claim your daily login reward")
    async def daily(self, interaction: discord.Interaction):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        today = logic.today_wib()
        if p["last_daily"] == today:
            await interaction.response.send_message(
                embed=emb("🎁 Daily Reward","Today's daily is already claimed, come back tomorrow!",
                          color=COLOR_CORE),
                ephemeral=True)
            return
        yesterday = (datetime.now(logic.WIB) - timedelta(days=1)).strftime("%Y-%m-%d")
        p["streak"] = p["streak"] + 1 if p["last_daily"] == yesterday else 1
        bonus = min(200, (p["streak"] - 1) * 25)
        gold = 100 + bonus
        item = random.choice(["potion kecil", "roti", "air minum"])
        p["last_daily"] = today
        p["gold"] += gold
        p["gold_earned"] += gold
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], item)
        if p["guild_id"]:
            period = datetime.now(logic.WIB).strftime("%Y-W%W")
            grow = conn.execute(
                "SELECT * FROM guild_quest_progress WHERE guild_id = ? AND quest_id = 'gq_daily'",
                (p["guild_id"],)).fetchone()
            if grow is None:
                conn.execute(
                    "INSERT INTO guild_quest_progress (guild_id, quest_id, progress, period)"
                    " VALUES (?, 'gq_daily', 1, ?)", (p["guild_id"], period))
            elif grow["period"] != period:
                conn.execute(
                    "UPDATE guild_quest_progress SET progress = 1, period = ? "
                    "WHERE guild_id = ? AND quest_id = 'gq_daily'",
                    (period, p["guild_id"]))
            else:
                conn.execute(
                    "UPDATE guild_quest_progress SET progress = progress + 1 "
                    "WHERE guild_id = ? AND quest_id = 'gq_daily'", (p["guild_id"],))
            conn.commit()
            from .common import add_guild_exp
            add_guild_exp(conn, p["guild_id"], 10)
        sync_quests(conn, p)
        await interaction.response.send_message(embed=emb(
            "🎁 Daily Reward!",
            'Streak: **{n} days**\nYou got **{gold} gold** + 1x {item}.\nLonger streaks give bigger gold bonuses (max +200)!'.format(n=p['streak'], gold=gold, item=disp.item(item)),
            color=COLOR_CORE))

    # ------------------------------------------------------------ inventory
    @app_commands.command(name="inventory", description="View & manage your items")
    @app_commands.describe(aksi="What to do", item="Item name (for use/equip/unequip/discard)", jumlah="Amount (for discard)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="use", value="use"),
        app_commands.Choice(name="equip", value="equip"),
        app_commands.Choice(name="unequip", value="unequip"),
        app_commands.Choice(name="discard", value="discard"),
    ])
    @app_commands.rename(aksi="action", jumlah="amount")
    async def inventory(self, interaction: discord.Interaction, aksi: str,
                        item: str = "", jumlah: int = 1):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        inv = db.get_inventory(conn, p["user_id"])
        if aksi == "list":
            if not inv:
                await interaction.response.send_message(
                    embed=emb('🎒 Empty Bag','Your bag is empty. Buy something at `/shop` first!',
                              color=COLOR_CORE),
                    ephemeral=True)
                return
            lines = []
            for row in inv:
                mark = ' • equipped' if row["equipped"] else ""
                dura = ""
                if ITEMS.get(row["item_id"], {}).get("type") in ("weapon", "armor"):
                    dura = ' • durability {d}'.format(d=row['durability'])
                lines.append(f"{disp.item(row['item_id'])} x{row['qty']}{mark}{dura}")
            await interaction.response.send_message(
                embed=emb(f"🎒 {p['name']}'s Bag",
                          "\n".join(lines) + "\n\n" + 'Choose an item below to use/equip.',
                          color=COLOR_CORE),
                view=InventoryView(p["user_id"], inv))
            return
        if not item:
            await interaction.response.send_message(
                embed=err_embed('Tell me the item name first.'), ephemeral=True)
            return
        item = item.lower()
        if item not in ITEMS:
            await interaction.response.send_message(
                embed=err_embed("Item '{item}' is unknown. Check `/inventory list` first.".format(item=disp.item(item))),
                ephemeral=True)
            return
        if db.item_qty(conn, p["user_id"], item) < 1:
            await interaction.response.send_message(
                embed=err_embed("You don't have {item}.".format(item=disp.item(item))), ephemeral=True)
            return
        info = ITEMS[item]
        if aksi == "use":
            ok, text = apply_use_item(conn, p, item)
            if ok:
                await interaction.response.send_message(
                    embed=emb('🎒 Inventory', text, color=COLOR_CORE))
            else:
                await interaction.response.send_message(
                    embed=err_embed(text), ephemeral=True)
        elif aksi == "equip":
            ok, text = apply_equip_item(conn, p, item)
            if ok:
                await interaction.response.send_message(
                    embed=emb('🎒 Inventory', text, color=COLOR_CORE))
            else:
                await interaction.response.send_message(
                    embed=err_embed(text), ephemeral=True)
        elif aksi == "unequip":
            ok, text = apply_unequip_item(conn, p, item)
            if ok:
                await interaction.response.send_message(
                    embed=emb('🎒 Inventory', text, color=COLOR_CORE))
            else:
                await interaction.response.send_message(
                    embed=err_embed(text), ephemeral=True)
        elif aksi == "discard":
            if db.remove_item(conn, p["user_id"], item, max(1, jumlah)):
                await interaction.response.send_message(
                    embed=emb('🎒 Inventory', '🗑️ {item} x{n} discarded.'.format(item=disp.item(item), n=jumlah),
                              color=COLOR_CORE))
            else:
                await interaction.response.send_message(
                    embed=err_embed("You don't have that much in stock."), ephemeral=True)

    # ------------------------------------------------------------------ map
    @app_commands.command(name="map", description="View areas & explore the world")
    @app_commands.describe(aksi="list areas or explore", area="Area name (for explore)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="explore", value="explore"),
    ])
    @app_commands.rename(aksi="action")
    async def map_cmd(self, interaction: discord.Interaction, aksi: str, area: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if aksi == "list":
            lines = []
            for name, info in AREAS.items():
                lock = "🔓" if p["level"] >= info["min_level"] else '🔒 (requires Lv {n})'.format(n=info['min_level'])
                mons = ', '.join(disp.monster(m) for m in info['monsters'])
                lines.append(f"{lock} **{disp.area(name)}** — monsters: {mons}")
            await interaction.response.send_message(
                embed=emb('🗺️ World Map', "\n".join(lines), color=COLOR_CORE))
            return
        if not area:
            await interaction.response.send_message(
                embed=err_embed('Choose an area first, e.g. `/map explore Beginner Forest`.'),
                ephemeral=True)
            return
        match = disp.resolve_area(area)
        if not match:
            await interaction.response.send_message(
                embed=err_embed("Area '{area}' doesn't exist. Check `/map list`.".format(area=area)),
                ephemeral=True)
            return
        if p["level"] < AREAS[match]["min_level"]:
            await interaction.response.send_message(
                embed=err_embed('{match} is still locked! Requires Lv {n}.'.format(match=disp.area(match), n=AREAS[match]['min_level'])),
                ephemeral=True)
            return
        if not logic.spend_stamina(p, 5):
            await interaction.response.send_message(
                embed=err_embed("You're out of stamina! Stamina refills tomorrow."),
                ephemeral=True)
            return
        p["hunger"] = max(0, p["hunger"] - 2)
        p["thirst"] = max(0, p["thirst"] - 2)
        roll = random.random()
        if roll < 0.4:
            gold = random.randint(10, 60)
            logic.add_gold(p, logic.gold_gain(p, gold))
            db.save_player(conn, p)
            sync_quests(conn, p)
            msg = 'You found an old chest in {area}: **{gold} gold**!'.format(area=disp.area(match), gold=gold)
        elif roll < 0.7:
            item = random.choice(["potion kecil", "kayu", "daging", "roti"])
            db.add_item(conn, p["user_id"], item)
            db.save_player(conn, p)
            msg = 'You found **{item}** lying around in {area}!'.format(item=disp.item(item), area=disp.area(match))
        else:
            monster_name = random.choice(AREAS[match]["monsters"])
            m = logic.scale_monster(monster_name, p["level"])
            # Pertarungan jelajah diselesaikan otomatis (lihat README: simplified).
            player_power = p["atk"] + p["spd"] + p["level"] * 2
            monster_power = m["atk"] + m["def"]
            if random.random() < player_power / (player_power + monster_power + 5):
                exp = logic.exp_gain(p, m["exp"], guild_level_of(conn, p))
                gold = random.randint(*m["gold"])
                logic.add_gold(p, logic.gold_gain(p, gold))
                p["kills"] += 1
                bump_daily(conn, p, "kills")
                loot = logic.roll_loot(monster_name, logic.vip_active(p))
                if loot:
                    db.add_item(conn, p["user_id"], loot)
                levels = logic.apply_exp(p, exp)
                db.save_player(conn, p)
                sync_quests(conn, p)
                msg = ('You met **{m}** and won! +{e} EXP, +{g} gold'.format(m=disp.monster(monster_name), e=exp, g=gold)
                       + (f", loot {disp.item(loot)}" if loot else "")
                       + (', leveled up {n} levels!'.format(n=levels) if levels else ""))
            else:
                lost = max(1, p["max_hp"] // 4)
                p["hp"] = max(10, p["hp"] - lost)
                db.save_player(conn, p)
                msg = 'You met **{m}** and fled wounded... -{lost} HP.'.format(m=disp.monster(monster_name), lost=lost)
        await interaction.response.send_message(
            embed=emb(f"🗺️ Explore {disp.area(match)}", msg, color=COLOR_CORE))

    # ---------------------------------------------------------------- quest
    @app_commands.command(name="quest", description="View & claim your quests")
    @app_commands.describe(aksi="list quests or claim", quest="Quest ID (for claim, e.g. mq1)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="claim", value="claim"),
    ])
    @app_commands.rename(aksi="action")
    async def quest(self, interaction: discord.Interaction, aksi: str, quest: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        sync_quests(conn, p)
        if aksi == "list":
            lines = []
            for qid, q in QUESTS.items():
                row = db.quest_row(conn, p["user_id"], qid)
                prog = row["progress"] if row else 0
                claimed = row["claimed"] if row else 0
                status = '✅ claimed' if claimed else ('🎁 ready to claim!' if prog >= q["target"] else f"{prog}/{q['target']}")
                lines.append('**[{qid}] {name}** ({kind}) — {desc} — {status} — reward {gold} gold + {exp} EXP'.format(qid=qid, name=disp.quest_name(qid), kind=q['kind'], desc=disp.quest_desc(qid), status=status, gold=q['gold'], exp=q['exp']))
            await interaction.response.send_message(
                embed=emb('📜 Quests', "\n".join(lines), color=COLOR_CORE))
            return
        qid = quest.lower()
        if qid not in QUESTS:
            await interaction.response.send_message(
                embed=err_embed('Unknown quest ID. Check `/quest list`.'),
                ephemeral=True)
            return
        q = QUESTS[qid]
        row = db.quest_row(conn, p["user_id"], qid)
        if row and row["claimed"]:
            await interaction.response.send_message(
                embed=emb('📜 Quests','This quest is already claimed.', color=COLOR_CORE),
                ephemeral=True)
            return
        prog = row["progress"] if row else 0
        if prog < q["target"]:
            await interaction.response.send_message(
                embed=err_embed('Not finished yet! Progress {prog}/{target}.'.format(prog=prog,target=q['target'])),
                ephemeral=True)
            return
        db.claim_quest(conn, p["user_id"], qid)
        levels = reward(conn, p, q["gold"], q["exp"])
        await interaction.response.send_message(embed=emb('🎉 Quest Complete!',
            '**{name}** — you got {gold} gold + {exp} EXP'.format(name=disp.quest_name(qid), gold=q['gold'], exp=q['exp'])
            + (', leveled up {n} levels!'.format(n=levels) if levels else ""),
            color=COLOR_CORE))

    # ---------------------------------------------------------------- help
    @app_commands.command(name="help", description="List all RPG bot commands")
    async def help_cmd(self, interaction: discord.Interaction):
        i18n.set_ctx(interaction, get_conn())
        e = emb('📖 NEWR Adventure Help','All commands here are slash commands.\n\n**Basics:** `/register` `/profile` `/evolve` `/daily` `/inventory` `/map` `/quest`\n**Battle:** `/fight` `/raid` `/pvp` `/arena` `/guildwar`\n**Economy:** `/shop` `/blackmarket` `/craft` `/gacha` `/trade` `/tradeboard`\n**Pet:** `/pet` `/petgear`\n**Survival:** `/status` `/eat` `/drink` `/repair`\n**Social:** `/guild` `/guildquest` `/guildbuff` `/party`\n**Premium & Event:** `/vip` `/vipgrant` `/ranking` `/event`\n**Fun & Games:** `/casino` `/job` `/house` `/dungeon` `/meteor` `/story`\n\nStart with `/register`, claim `/daily`, then `/fight` to level up!\nNEWR Adventure by NEWR LABS',
                color=COLOR_CORE)
        await interaction.response.send_message(embed=e)

    @app_commands.command(name="about", description="About this RPG bot")
    async def about(self, interaction: discord.Interaction):
        i18n.set_ctx(interaction, get_conn())
        await interaction.response.send_message(embed=emb(
            "🐉 NEWR Adventure",'A complete RPG bot: create characters, pick classes, evolve jobs, fight monsters, raid bosses with your party, PVP, guild wars, crafting, gacha, pets, house & farm, dungeon puzzles, and story mode.\n\nCredit by NEWR LABS'))


async def setup(bot):
    await bot.add_cog(Core(bot))
