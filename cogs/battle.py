# -*- coding: utf-8 -*-
"""Cog battle: fight (tombol), raid party, pvp duel, arena, guild war."""
import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import friends_db
import info_db
import logic
import rolesync
from data import AREAS, ITEMS, WEEKLY_BOSS
from .common import (COLOR_BATTLE, add_guild_exp, bar_line, bump_daily, emb,
                     err_embed, get_conn, guild_level_of, load_player,
                     need_player, reward, sync_quests)

FIGHTS = {}  # user_id -> state (in-memory; kalah/menang disimpan ke DB)


def resolve_war(conn, war):
    """Resolve a due guild war. Returns the winning guild id or None.

    Moved verbatim out of the /guildwar handler so the announcement
    loop can resolve overdue wars too. Formula and rewards are
    unchanged: total member power (level*10 + atk) + guild level*50,
    random 1.0-1.25 factor; winner +150 guild EXP, loser +30, every
    winning member +100 gold.
    """
    if war["state"] != "pending" or int(time.time()) < war["resolves_at"]:
        return None

    def power(gid):
        members = db.guild_member_ids(conn, gid)
        total = 0
        for mid in members:
            mp = db.get_player(conn, mid)
            if mp:
                total += mp["level"] * 10 + mp["atk"]
        g = db.get_guild(conn, gid)
        return total + (g["level"] * 50 if g else 0)

    pa = power(war["guild_a"]) * random.uniform(1.0, 1.25)
    pb = power(war["guild_b"]) * random.uniform(1.0, 1.25)
    winner = war["guild_a"] if pa >= pb else war["guild_b"]
    loser = war["guild_b"] if winner == war["guild_a"] else war["guild_a"]
    conn.execute(
        "UPDATE wars SET state = 'done', score_a = ?, score_b = ?, winner_id = ? WHERE id = ?",
        (int(pa), int(pb), winner, war["id"]))
    conn.commit()
    add_guild_exp(conn, winner, 150)
    add_guild_exp(conn, loser, 30)
    for mid in db.guild_member_ids(conn, winner):
        mp = db.get_player(conn, mid)
        if mp:
            mp["gold"] += 100
            mp["gold_earned"] += 100
            db.save_player(conn, mp)
    return winner


class FightView(discord.ui.View):
    def __init__(self, cog, interaction, player, monster):
        super().__init__(timeout=180)
        self.cog = cog
        self.owner_id = interaction.user.id
        self.player = player
        self.monster = monster
        self.monster_hp = monster["hp"]
        self.player_hp = player["hp"]
        self.player_mp = player["mp"]
        self.msg = None

    def _embed(self, note=""):
        m = self.monster
        mname = disp.monster(m['name'])
        return emb(f"⚔️ {self.player['name']} vs {mname}",
                   f"{self.player['name']} {bar_line('❤️ HP', self.player_hp, self.player['max_hp'])} • {bar_line('💙 MP', self.player_mp, self.player['max_mp'])}\n"
                   f"{mname} {bar_line('❤️ HP', self.monster_hp, m['hp'])}\n\n{note}",
                   color=COLOR_BATTLE)

    async def _monster_turn(self, interaction, note):
        if self.monster_hp <= 0:
            return await self._win(interaction)
        dmg, _ = logic.damage(self.monster["atk"], self.player["def"])
        self.player_hp = max(0, self.player_hp - dmg)
        note += "\n" + '{m} strikes back: -{dmg} HP!'.format(m=disp.monster(self.monster['name']), dmg=dmg)
        if self.player_hp <= 0:
            return await self._lose(interaction)
        await interaction.response.edit_message(embed=self._embed(note), view=self)

    async def _finish(self, interaction, won):
        conn = get_conn()
        p = load_player(conn, self.owner_id)
        # Pakai state terakhir dari view (HP sudah berubah selama fight).
        if won:
            exp = logic.exp_gain(p, self.monster["exp"], guild_level_of(conn, p))
            gold = random.randint(*self.monster["gold"])
            logic.add_gold(p, logic.gold_gain(p, gold))
            p["kills"] += 1
            p["hp"] = max(1, self.player_hp)
            p["mp"] = max(0, self.player_mp)
            p["stamina"] = max(0, p["stamina"] - 10)
            p["hunger"] = max(0, p["hunger"] - 3)
            p["thirst"] = max(0, p["thirst"] - 3)
            bump_daily(conn, p, "kills")
            loot = logic.roll_loot(self.monster["name"], logic.vip_active(p))
            if loot:
                db.add_item(conn, p["user_id"], loot)
            pets = db.get_pets(conn, p["user_id"])
            pet_note = ""
            if pets:
                gained = logic.pet_gain_exp(pets[0], 10)
                db.save_pet(conn, pets[0])
                if gained:
                    pet_note = ' Pet {name} leveled up {n} levels!'.format(name=pets[0]['name'],n=gained)
            # Durability senjata/armor berkurang.
            for row in db.equipped_items(conn, p["user_id"]):
                if row["durability"] > 0:
                    conn.execute(
                        "UPDATE inventory SET durability = MAX(0, durability - 2) WHERE id = ?",
                        (row["id"],))
            conn.commit()
            levels = logic.apply_exp(p, exp)
            db.save_player(conn, p)
            sync_quests(conn, p)
            text = ('🎉 VICTORY! +{e} EXP, +{g} gold'.format(e=exp, g=gold)
                    + (f", loot {disp.item(loot)}" if loot else "")
                    + (', leveled up {n} levels!'.format(n=levels) if levels else "") + pet_note)
        else:
            lost_gold = max(0, p["gold"] // 10)
            p["gold"] -= lost_gold
            p["hp"] = max(1, p["max_hp"] // 5)
            p["mp"] = max(0, self.player_mp)
            p["stamina"] = max(0, p["stamina"] - 5)
            db.save_player(conn, p)
            text = '💀 DEFEAT... {m} is too strong. You lost {lost} gold, HP restored to {hp}.'.format(m=disp.monster(self.monster['name']), lost=lost_gold, hp=p['hp'])
        FIGHTS.pop(self.owner_id, None)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=emb('⚔️ Fight Over', text, color=COLOR_BATTLE), view=self)

    async def _win(self, interaction):
        await self._finish(interaction, True)

    async def _lose(self, interaction):
        await self._finish(interaction, False)

    async def on_timeout(self):
        FIGHTS.pop(self.owner_id, None)

    async def _check_owner(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("This is someone else's fight!"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="⚔️ Attack", style=discord.ButtonStyle.primary)
    async def attack(self, interaction, button):
        if not await self._check_owner(interaction):
            return
        conn = get_conn()
        p = load_player(conn, self.owner_id)
        pets = db.get_pets(conn, self.owner_id)
        atk, defense, _ = logic.effective_stats(p, db.equipped_items(conn, self.owner_id),
                                                pets[0] if pets else None)
        atk += guild_level_of(conn, p)
        dmg, crit, _back = logic.fight_round(atk, defense, self.monster["atk"],
                                             self.monster["def"], rng=random)
        self.monster_hp = max(0, self.monster_hp - dmg)
        note = 'You attack: -{dmg} HP!'.format(dmg=dmg) + (" CRITICAL!" if crit else "")
        await self._monster_turn(interaction, note)

    @discord.ui.button(label="✨ Skill", style=discord.ButtonStyle.danger)
    async def skill(self, interaction, button):
        if not await self._check_owner(interaction):
            return
        if self.player_mp < 20:
            await interaction.response.send_message(
                embed=err_embed('Not enough MP! Skills need 20 MP.'), ephemeral=True)
            return
        conn = get_conn()
        p = load_player(conn, self.owner_id)
        pets = db.get_pets(conn, self.owner_id)
        atk, defense, _ = logic.effective_stats(p, db.equipped_items(conn, self.owner_id),
                                                pets[0] if pets else None)
        atk += guild_level_of(conn, p)
        name, mult = logic.class_skill(p)
        self.player_mp -= 20
        dmg, crit, _ = logic.fight_round(atk, defense, self.monster["atk"],
                                         self.monster["def"], use_skill=True,
                                         skill_mult=mult, rng=random)
        self.monster_hp = max(0, self.monster_hp - dmg)
        note = f"{disp.skill(name)}! -{dmg} HP!" + (" CRITICAL!" if crit else "")
        await self._monster_turn(interaction, note)

    @discord.ui.button(label="🧪 Potion", style=discord.ButtonStyle.success)
    async def potion(self, interaction, button):
        if not await self._check_owner(interaction):
            return
        conn = get_conn()
        if db.item_qty(conn, self.owner_id, "potion kecil") < 1 and \
                db.item_qty(conn, self.owner_id, "potion besar") < 1:
            await interaction.response.send_message(
                embed=err_embed("You don't have any potions! Buy at `/shop`."), ephemeral=True)
            return
        if db.item_qty(conn, self.owner_id, "potion kecil") >= 1:
            db.remove_item(conn, self.owner_id, "potion kecil", 1)
            heal = 50
        else:
            db.remove_item(conn, self.owner_id, "potion besar", 1)
            heal = 150
        self.player_hp = min(self.player["max_hp"], self.player_hp + heal)
        await self._monster_turn(interaction, 'You drank a potion: +{heal} HP!'.format(heal=heal))

    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.secondary)
    async def flee(self, interaction, button):
        if not await self._check_owner(interaction):
            return
        FIGHTS.pop(self.owner_id, None)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=emb('🏃 Flee','You fled the fight. No rewards, no wounds.',
                      color=COLOR_BATTLE),
            view=self)


class DuelView(discord.ui.View):
    def __init__(self, challenger_id, target_id, challenger_name, target_name):
        super().__init__(timeout=120)
        self.challenger_id = challenger_id
        self.target_id = target_id
        self.challenger_name = challenger_name
        self.target_name = target_name

    @discord.ui.button(label="✅ Accept Duel", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message(
                embed=err_embed('Only the challenged player can accept.'), ephemeral=True)
            return
        conn = get_conn()
        a = load_player(conn, self.challenger_id)
        b = load_player(conn, self.target_id)
        pa = a["level"] * 10 + a["atk"] + a["spd"] + random.randint(0, 50)
        pb = b["level"] * 10 + b["atk"] + b["spd"] + random.randint(0, 50)
        if pa >= pb:
            winner, loser = a, b
        else:
            winner, loser = b, a
        ra = db.pvp_row(conn, winner["user_id"])
        rb = db.pvp_row(conn, loser["user_id"])
        ra["points"] += 25
        ra["wins"] += 1
        rb["points"] = max(0, rb["points"] - 10)
        rb["losses"] += 1
        db.save_pvp(conn, ra)
        db.save_pvp(conn, rb)
        winner["wins"] += 1
        db.save_player(conn, winner)
        sync_quests(conn, winner)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=emb('⚔️ Duel Result',
                      '**{w}** beat **{l}**!\n+25 ranking points for the winner, -10 for the loser.'.format(w=winner['name'],l=loser['name']),
                      color=COLOR_BATTLE),
            view=self)

    @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction, button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message(
                embed=err_embed('Only the challenged player can decline.'), ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            embed=emb('Duel declined', '{name} declined the duel.'.format(name=self.target_name),
                      color=COLOR_BATTLE),
            view=self)


class Battle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="fight", description="Fight a monster matching your level")
    @app_commands.describe(area="Hunting area (empty = highest unlocked area)")
    async def fight(self, interaction: discord.Interaction, area: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if p["user_id"] in FIGHTS:
            await interaction.response.send_message(
                embed=err_embed("You're already fighting! Finish it first."), ephemeral=True)
            return
        if p["hp"] <= 0:
            await interaction.response.send_message(
                embed=err_embed('Your HP is 0! Use a potion from `/inventory` first.'),
                ephemeral=True)
            return
        if p["stamina"] < 10:
            await interaction.response.send_message(
                embed=err_embed('Not enough stamina (need 10). Stamina refills tomorrow.'),
                ephemeral=True)
            return
        unlocked = [a for a, info in AREAS.items() if p["level"] >= info["min_level"]]
        if area:
            match = disp.resolve_area(area)
            if not match or match not in unlocked:
                await interaction.response.send_message(
                    embed=err_embed("Area '{area}' isn't unlocked / doesn't exist. Your areas: {areas}.".format(area=area, areas=', '.join(disp.area(a) for a in unlocked))),
                    ephemeral=True)
                return
        else:
            match = unlocked[-1]
        monster_name = random.choice(AREAS[match]["monsters"])
        monster = logic.scale_monster(monster_name, p["level"])
        view = FightView(self, interaction, p, monster)
        FIGHTS[p["user_id"]] = view
        await interaction.response.send_message(
            embed=view._embed('Monster **{m}** appeared in {area}! Choose your action:'.format(m=disp.monster(monster_name), area=disp.area(match))),
            view=view)

    @app_commands.command(name="raid", description="Raid a boss together (damage is pooled in the database)")
    @app_commands.describe(aksi="start/info/join/hit")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="start", value="start"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="join", value="join"),
        app_commands.Choice(name="hit", value="hit"),
    ])
    @app_commands.rename(aksi="action")
    async def raid(self, interaction: discord.Interaction, aksi: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        raid = db.active_raid(conn)
        if aksi == "start":
            if raid:
                await interaction.response.send_message(
                    embed=err_embed("There's already an active raid: **{boss}** ({hp}/{maxhp} HP). Just join!".format(boss=disp.monster(raid['boss']), hp=raid['hp'], maxhp=raid['max_hp'])),
                    ephemeral=True)
                return
            from logic import active_events
            events = active_events()
            if events:
                name, ev = events[0]
                boss, hp = ev["boss"], ev["boss_hp"]
            else:
                boss, hp = WEEKLY_BOSS["name"], WEEKLY_BOSS["hp"]
            conn.execute(
                "INSERT INTO raids (boss, hp, max_hp, created_at) VALUES (?, ?, ?, ?)",
                (boss, hp, hp, int(time.time())))
            conn.commit()
            await interaction.response.send_message(embed=emb('🐉 RAID STARTED!',
                'Boss **{boss}** appeared with {hp} HP! Join with `/raid join`, then `/raid hit` together!'.format(boss=disp.monster(boss), hp=hp),
                color=COLOR_BATTLE))
            return
        if not raid:
            await interaction.response.send_message(
                embed=err_embed('No active raid yet. Start one with `/raid start`.'),
                ephemeral=True)
            return
        if aksi == "info":
            members = db.raid_members(conn, raid["id"])
            lines = [f"{m['user_id']}: {m['damage']} damage" for m in members] or ['Nobody has joined yet.']
            await interaction.response.send_message(embed=emb(
                f"🐉 Raid: {disp.monster(raid['boss'])}",
                f"{bar_line('🐉 HP', raid['hp'], raid['max_hp'])}\n\n"
                "Damage:\n" + "\n".join(lines), color=COLOR_BATTLE))
            return
        if aksi == "join":
            conn.execute(
                "INSERT OR IGNORE INTO raid_members (raid_id, user_id) VALUES (?, ?)",
                (raid["id"], p["user_id"]))
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🐉 Raid',
                          'You joined the **{boss}** raid! Attack with `/raid hit`.'.format(boss=disp.monster(raid['boss'])),
                          color=COLOR_BATTLE))
            return
        # hit
        member = conn.execute(
            "SELECT * FROM raid_members WHERE raid_id = ? AND user_id = ?",
            (raid["id"], p["user_id"])).fetchone()
        if not member:
            await interaction.response.send_message(
                embed=err_embed('Join first with `/raid join`.'), ephemeral=True)
            return
        if not logic.spend_stamina(p, 5):
            await interaction.response.send_message(
                embed=err_embed('Not enough stamina (need 5).'), ephemeral=True)
            return
        pets = db.get_pets(conn, p["user_id"])
        atk, _d, _s = logic.effective_stats(p, db.equipped_items(conn, p["user_id"]),
                                            pets[0] if pets else None)
        atk += guild_level_of(conn, p)
        party_bonus = 1.0
        if p["party_id"]:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM party_members WHERE party_id = ?",
                (p["party_id"],)).fetchone()["c"]
            if count >= 2:
                party_bonus = 1.10
        dmg = max(1, int((atk + random.randint(0, 20)) * party_bonus))
        new_hp = max(0, raid["hp"] - dmg)
        conn.execute("UPDATE raids SET hp = ? WHERE id = ?", (new_hp, raid["id"]))
        conn.execute(
            "UPDATE raid_members SET damage = damage + ? WHERE raid_id = ? AND user_id = ?",
            (dmg, raid["id"], p["user_id"]))
        p["hunger"] = max(0, p["hunger"] - 1)
        p["thirst"] = max(0, p["thirst"] - 1)
        db.save_player(conn, p)
        msg = 'You smashed **{boss}** for {dmg} damage! Boss HP left: {newhp}.'.format(boss=disp.monster(raid['boss']), dmg=dmg, newhp=new_hp)
        if new_hp <= 0:
            conn.execute("UPDATE raids SET state = 'done' WHERE id = ?", (raid["id"],))
            members = db.raid_members(conn, raid["id"])
            total = sum(m["damage"] for m in members) or 1
            top = members[0] if members else None
            for m in members:
                share = max(50, int(2000 * m["damage"] / total))
                mp = db.get_player(conn, m["user_id"])
                if mp:
                    logic.add_gold(mp, share)
                    logic.apply_exp(mp, logic.exp_gain(mp, 300, guild_level_of(conn, mp)))
                    db.save_player(conn, mp)
            if top:
                db.add_item(conn, top["user_id"], random.choice(["jimat keberuntungan", "kristal void", "pedang baja"]))
            info_db.record_boss_kill(conn, boss=raid["boss"], raid_id=raid["id"], killer_id=p["user_id"], killer_power=friends_db.member_power(p), killer_damage=dmg)
            rolesync.grant_achievement(conn, p["user_id"], "Boss Slayer")
            conn.commit()
            msg += '\n\n🎉 BOSS DEFEATED! All participants get gold based on contribution + 300 EXP. Top damage gets a rare item!'
        else:
            conn.commit()
        await interaction.response.send_message(
            embed=emb('🐉 Raid', msg, color=COLOR_BATTLE))
        if new_hp <= 0 and interaction.guild is not None:
            try:
                member = interaction.guild.get_member(p["user_id"])
                if member is None:
                    member = await interaction.guild.fetch_member(p["user_id"])
                if member is not None:
                    await rolesync.sync_member_roles(
                        interaction.guild, member, p, conn)
            except Exception as exc:
                print(f"WARNING: role sync after raid kill failed: {exc}")

    @app_commands.command(name="pvp", description="Challenge another player to a duel")
    @app_commands.describe(target="Player to challenge: mention or user ID")
    async def pvp(self, interaction: discord.Interaction, target: discord.User):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if target.id == interaction.user.id:
            await interaction.response.send_message(
                embed=err_embed("You can't duel yourself, bro."), ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message(
                embed=err_embed("Bots can't duel."), ephemeral=True)
            return
        t = db.get_player(conn, target.id)
        if not t:
            await interaction.response.send_message(
                embed=err_embed("That player hasn't registered a character."), ephemeral=True)
            return
        if not logic.spend_stamina(p, 5):
            await interaction.response.send_message(
                embed=err_embed('Not enough stamina (need 5).'), ephemeral=True)
            return
        db.save_player(conn, p)
        view = DuelView(p["user_id"], target.id, p["name"], t["name"])
        await interaction.response.send_message(
            embed=emb('⚔️ Duel Challenge!',
                      '**{a}** challenges **{b}** to a duel!\n{mention}, accept or decline within 2 minutes.'.format(a=p['name'],b=t['name'],mention=target.mention),
                      color=COLOR_BATTLE),
            view=view)

    @app_commands.command(name="arena", description="Server PVP ranking")
    async def arena(self, interaction: discord.Interaction):
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM pvp_rank ORDER BY points DESC LIMIT 10").fetchall()
        if not rows:
            await interaction.response.send_message(
                embed=emb('🏆 Arena Ranking','Nobody has dueled yet. Be the first with `/pvp`!',
                          color=COLOR_BATTLE),
                ephemeral=True)
            return
        lines = []
        for i, r in enumerate(rows, 1):
            p = db.get_player(conn, r["user_id"])
            name = p["name"] if p else f"User {r['user_id']}"
            lines.append('{i}. **{name}** — {points} points (W {w} / L {l})'.format(i=i,name=name,points=r['points'],w=r['wins'],l=r['losses']))
        await interaction.response.send_message(
            embed=emb('🏆 Arena Ranking', "\n".join(lines), color=COLOR_BATTLE))

    @app_commands.command(name="guildwar", description="War between guilds")
    @app_commands.describe(aksi="challenge/info/fight", guild="Enemy guild name (for challenge)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="challenge", value="declare"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="fight", value="fight"),
    ])
    @app_commands.rename(aksi="action")
    async def guildwar(self, interaction: discord.Interaction, aksi: str, guild: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild yet. Create/join one with `/guild`."),
                ephemeral=True)
            return
        my_guild = db.get_guild(conn, p["guild_id"])


        if aksi == "declare":
            if not guild:
                await interaction.response.send_message(
                    embed=err_embed('Name the opposing guild.'), ephemeral=True)
                return
            target = db.get_guild_by_name(conn, guild)
            if not target:
                await interaction.response.send_message(
                    embed=err_embed("Guild '{guild}' not found.".format(guild=guild)), ephemeral=True)
                return
            if target["id"] == my_guild["id"]:
                await interaction.response.send_message(
                    embed=err_embed("You can't war against your own guild."), ephemeral=True)
                return
            existing = conn.execute(
                "SELECT * FROM wars WHERE state = 'pending' AND "
                "((guild_a = ? AND guild_b = ?) OR (guild_a = ? AND guild_b = ?))",
                (my_guild["id"], target["id"], target["id"], my_guild["id"])).fetchone()
            if existing:
                await interaction.response.send_message(
                    embed=err_embed('War against that guild is already declared, wait for the result.'),
                    ephemeral=True)
                return
            conn.execute(
                "INSERT INTO wars (guild_a, guild_b, declarer_id, resolves_at, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (my_guild["id"], target["id"], p["user_id"],
                 int(time.time()) + 3600, int(time.time())))
            conn.commit()
            await interaction.response.send_message(embed=emb('⚔️ Guild War Declared!',
                '**{a}** vs **{b}**!\nThe fight is tallied 1 hour from now based on total member power + guild level. Check the result with `/guildwar info`.'.format(a=my_guild['name'],b=target['name']),
                color=COLOR_BATTLE))
            return
        war = conn.execute(
            "SELECT * FROM wars WHERE state = 'pending' AND (guild_a = ? OR guild_b = ?) "
            "ORDER BY id DESC LIMIT 1", (my_guild["id"], my_guild["id"])).fetchone()
        if not war:
            done = conn.execute(
                "SELECT * FROM wars WHERE state = 'done' AND (guild_a = ? OR guild_b = ?) "
                "ORDER BY id DESC LIMIT 1", (my_guild["id"], my_guild["id"])).fetchone()
            if done:
                wname = db.get_guild(conn, done["winner_id"])["name"]
                await interaction.response.send_message(
                    embed=emb('⚔️ Guild War',
                              'The last war was won by **{w}** (score {a} vs {b}).'.format(w=wname,a=done['score_a'],b=done['score_b']),
                              color=COLOR_BATTLE))
            else:
                await interaction.response.send_message(
                    embed=emb('⚔️ Guild War','Your guild has never warred. Declare with `/guildwar challenge <guild name>`.',
                              color=COLOR_BATTLE))
            return
        war = dict(war)
        winner = resolve_war(conn, war)
        if winner:
            wname = db.get_guild(conn, winner)["name"]
            await interaction.response.send_message(embed=emb('🏆 Guild War Over!',
                'Winner: **{w}**! The winning guild gets +150 guild EXP, all its members +100 gold.'.format(w=wname),
                color=COLOR_BATTLE))
            if interaction.guild is not None:
                for mid in db.guild_member_ids(conn, winner):
                    try:
                        rolesync.grant_achievement(conn, mid, "War Champion")
                        member = interaction.guild.get_member(mid)
                        if member is None:
                            member = await interaction.guild.fetch_member(mid)
                        mp = db.get_player(conn, mid)
                        if member is not None and mp is not None:
                            await rolesync.sync_member_roles(
                                interaction.guild, member, mp, conn)
                    except Exception as exc:
                        print(f"WARNING: role sync after war win failed: {exc}")
        else:
            a = db.get_guild(conn, war["guild_a"])["name"]
            b = db.get_guild(conn, war["guild_b"])["name"]
            left = max(0, war["resolves_at"] - int(time.time()))
            await interaction.response.send_message(
                embed=emb('⚔️ Guild War',
                          'War **{a}** vs **{b}** is still running, results come out in {n} more minutes.'.format(a=a,b=b,n=left // 60),
                          color=COLOR_BATTLE))


async def setup(bot):
    await bot.add_cog(Battle(bot))
