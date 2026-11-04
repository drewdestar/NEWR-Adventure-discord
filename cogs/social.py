# -*- coding: utf-8 -*-
"""Cog sosial: guild, guild quest, guild buff, party."""
import time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import logic
from .common import (COLOR_SOCIAL, add_guild_exp, bar_line, emb, err_embed,
                     get_conn, guild_buff_text, load_player, need_player)

GUILD_CREATE_COST = 500
GUILD_QUEST_TARGET = 5  # total klaim daily anggota guild dalam seminggu
GUILD_QUEST_REWARD = 200


def week_period():
    return datetime.now(logic.WIB).strftime("%Y-W%W")


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="guild", description="Create, join, leave, or view a guild")
    @app_commands.describe(aksi="create/join/leave/info", nama="Guild name")
    @app_commands.rename(aksi="action", nama="name")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="join", value="join"),
        app_commands.Choice(name="leave", value="leave"),
        app_commands.Choice(name="info", value="info"),
    ])
    async def guild(self, interaction: discord.Interaction, aksi: str, nama: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if aksi == "create":
            if p["guild_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You're already in a guild. Leave first if you want to create a new one."),
                    ephemeral=True)
                return
            if not nama or len(nama) > 24:
                await interaction.response.send_message(
                    embed=err_embed('Guild names must be 1-24 characters.'), ephemeral=True)
                return
            if db.get_guild_by_name(conn, nama):
                await interaction.response.send_message(
                    embed=err_embed('That guild name is already taken.'), ephemeral=True)
                return
            if p["gold"] < GUILD_CREATE_COST:
                await interaction.response.send_message(
                    embed=err_embed(f"Creating a guild needs {GUILD_CREATE_COST} gold."),
                    ephemeral=True)
                return
            p["gold"] -= GUILD_CREATE_COST
            cur = conn.execute(
                "INSERT INTO guilds (name, leader_id, created_at) VALUES (?, ?, ?)",
                (nama, p["user_id"], int(time.time())))
            gid = cur.lastrowid
            conn.execute(
                "INSERT INTO guild_members (guild_id, user_id) VALUES (?, ?)",
                (gid, p["user_id"]))
            p["guild_id"] = gid
            db.save_player(conn, p)
            conn.commit()
            await interaction.response.send_message(embed=emb('🏰 Guild Created!',
                f"**{nama}** resmi berdiri, dipimpin {p['name']}! "
                f"Invite friends to join with `/guild join {nama}`.",
                color=COLOR_SOCIAL))
            return
        if aksi == "join":
            if p["guild_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You're already in a guild."), ephemeral=True)
                return
            g = db.get_guild_by_name(conn, nama)
            if not g:
                await interaction.response.send_message(
                    embed=err_embed(f"Guild '{nama}' not found."), ephemeral=True)
                return
            conn.execute(
                "INSERT INTO guild_members (guild_id, user_id) VALUES (?, ?)",
                (g["id"], p["user_id"]))
            p["guild_id"] = g["id"]
            db.save_player(conn, p)
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🏰 Guild',
                          f"You joined guild **{g['name']}**! Active buff: {guild_buff_text(g['level'])}.",
                          color=COLOR_SOCIAL))
            return
        if aksi == "leave":
            if not p["guild_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You're not in any guild."), ephemeral=True)
                return
            gid = p["guild_id"]
            conn.execute(
                "DELETE FROM guild_members WHERE guild_id = ? AND user_id = ?",
                (gid, p["user_id"]))
            p["guild_id"] = None
            db.save_player(conn, p)
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🏰 Guild','You left the guild.', color=COLOR_SOCIAL))
            return
        # info
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild yet. Create one with `/guild create <name>`."),
                ephemeral=True)
            return
        g = db.get_guild(conn, p["guild_id"])
        members = db.guild_member_ids(conn, g["id"])
        names = []
        for mid in members:
            mp = db.get_player(conn, mid)
            names.append(f"{mp['name']} (Lv {mp['level']})" if mp else str(mid))
        leader = db.get_player(conn, g["leader_id"])
        await interaction.response.send_message(embed=emb(
            f"🏰 Guild {g['name']}",
            f"Leader: {leader['name'] if leader else g['leader_id']}\n"
            f"Guild level: {g['level']}\n"
            f"{bar_line('✨ Guild EXP', g['exp'], 200 * g['level'])}\n"
            f"Buff: {guild_buff_text(g['level'])}\n"
            f"Members ({len(members)}): {', '.join(names)}",
            color=COLOR_SOCIAL))

    @app_commands.command(name="guildquest", description="Special quest for guild members (shared progress)")
    @app_commands.describe(aksi="info/claim")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="claim", value="claim"),
    ])
    async def guildquest(self, interaction: discord.Interaction, aksi: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild."), ephemeral=True)
            return
        period = week_period()
        row = conn.execute(
            "SELECT * FROM guild_quest_progress WHERE guild_id = ? AND quest_id = 'gq_daily'",
            (p["guild_id"],)).fetchone()
        prog = 0
        if row and row["period"] == period:
            prog = row["progress"]
        elif row:
            conn.execute(
                "UPDATE guild_quest_progress SET progress = 0, period = ? "
                "WHERE guild_id = ? AND quest_id = 'gq_daily'",
                (period, p["guild_id"]))
            conn.commit()
        if aksi == "info":
            await interaction.response.send_message(embed=emb("🏰 This Week's Guild Quest",
                f"Quest: all members claim `/daily` {GUILD_QUEST_TARGET}x in total.\n"
                f"{bar_line('📋 Progress', prog, GUILD_QUEST_TARGET)}\n"
                f"Reward per member: {GUILD_QUEST_REWARD} gold (claim with `/guildquest claim`).",
                color=COLOR_SOCIAL))
            return
        if prog < GUILD_QUEST_TARGET:
            await interaction.response.send_message(
                embed=err_embed(f"Not finished yet! Progress {prog}/{GUILD_QUEST_TARGET}. "
                                "Ask members to claim `/daily`."),
                ephemeral=True)
            return
        claimed = conn.execute(
            "SELECT * FROM guild_quest_claims WHERE guild_id = ? AND user_id = ? AND period = ?",
            (p["guild_id"], p["user_id"], period)).fetchone()
        if claimed:
            await interaction.response.send_message(
                embed=emb('🏰 Guild Quest',"You've already claimed this week's guild quest reward.",
                          color=COLOR_SOCIAL),
                ephemeral=True)
            return
        p["gold"] += GUILD_QUEST_REWARD
        p["gold_earned"] += GUILD_QUEST_REWARD
        db.save_player(conn, p)
        conn.execute(
            "INSERT INTO guild_quest_claims (guild_id, user_id, period, claimed_at)"
            " VALUES (?, ?, ?, ?)",
            (p["guild_id"], p["user_id"], period, int(time.time())))
        conn.commit()
        await interaction.response.send_message(
            embed=emb('🏰 Guild Quest',
                      f"🎉 Guild quest reward: {GUILD_QUEST_REWARD} gold for you!",
                      color=COLOR_SOCIAL))

    @app_commands.command(name="guildbuff", description="View your guild's stat bonuses")
    async def guildbuff(self, interaction: discord.Interaction):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild."), ephemeral=True)
            return
        g = db.get_guild(conn, p["guild_id"])
        await interaction.response.send_message(embed=emb(
            f"✨ Guild Buff {g['name']}",
            f"Guild level {g['level']} gives: {guild_buff_text(g['level'])}\n"
            f"ATK/DEF bonus is active while fighting, EXP bonus is active when gaining EXP.\n"
            f"Raise the guild level with member daily claims & guild war wins.",
            color=COLOR_SOCIAL))

    @app_commands.command(name="party", description="Create/join a party to raid together")
    @app_commands.describe(aksi="create/join/leave/info", nama="Party name (for create/join)")
    @app_commands.rename(aksi="action", nama="name")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="create", value="create"),
        app_commands.Choice(name="join", value="join"),
        app_commands.Choice(name="leave", value="leave"),
        app_commands.Choice(name="info", value="info"),
    ])
    async def party(self, interaction: discord.Interaction, aksi: str, nama: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if aksi == "create":
            if p["party_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You're already in a party."), ephemeral=True)
                return
            if not nama:
                await interaction.response.send_message(
                    embed=err_embed('Give the party a name first.'), ephemeral=True)
                return
            cur = conn.execute(
                "INSERT INTO parties (name, leader_id, created_at) VALUES (?, ?, ?)",
                (nama, p["user_id"], int(time.time())))
            pid = cur.lastrowid
            conn.execute(
                "INSERT INTO party_members (party_id, user_id) VALUES (?, ?)",
                (pid, p["user_id"]))
            p["party_id"] = pid
            db.save_player(conn, p)
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🎉 Party',
                          f"Party **{nama}** created! A party with 2+ members gets +10% raid damage.",
                          color=COLOR_SOCIAL))
            return
        if aksi == "join":
            if p["party_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You're already in a party."), ephemeral=True)
                return
            row = conn.execute(
                "SELECT * FROM parties WHERE name = ? ORDER BY id DESC LIMIT 1",
                (nama,)).fetchone()
            if not row:
                await interaction.response.send_message(
                    embed=err_embed(f"Party '{nama}' not found."), ephemeral=True)
                return
            conn.execute(
                "INSERT INTO party_members (party_id, user_id) VALUES (?, ?)",
                (row["id"], p["user_id"]))
            p["party_id"] = row["id"]
            db.save_player(conn, p)
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🎉 Party', f"You joined party **{row['name']}**!",
                          color=COLOR_SOCIAL))
            return
        if aksi == "leave":
            if not p["party_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You're not in any party."), ephemeral=True)
                return
            pid = p["party_id"]
            conn.execute(
                "DELETE FROM party_members WHERE party_id = ? AND user_id = ?",
                (pid, p["user_id"]))
            p["party_id"] = None
            db.save_player(conn, p)
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🎉 Party','You left the party.', color=COLOR_SOCIAL))
            return
        if not p["party_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a party yet."), ephemeral=True)
            return
        row = conn.execute(
            "SELECT * FROM parties WHERE id = ?", (p["party_id"],)).fetchone()
        members = conn.execute(
            "SELECT user_id FROM party_members WHERE party_id = ?",
            (p["party_id"],)).fetchall()
        names = []
        for m in members:
            mp = db.get_player(conn, m["user_id"])
            names.append(mp["name"] if mp else str(m["user_id"]))
        await interaction.response.send_message(embed=emb(
            f"🎉 Party {row['name']}", "Members: " + ", ".join(names),
            color=COLOR_SOCIAL))


async def setup(bot):
    await bot.add_cog(Social(bot))
