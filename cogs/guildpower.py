# -*- coding: utf-8 -*-
"""Cog guild power: tiers from member strength + war trophies.

Guild power = sum over members of (level*10 + ATK + DEF + wins*5)
              + guild level * 50.
Tiers by total power:
    Bronze   < 500
    Silver   500 - 1,499
    Gold     1,500 - 3,499
    Platinum 3,500 - 7,499
    Diamond  7,500+

War trophies are NOT awarded by editing the existing war flow. Instead,
this cog scans finished wars (state='done' with a winner) and records
one trophy per war id the first time it is seen. Callers run the sync at
the start of every handler, so a trophy shows up shortly after a war
resolves (the war-result message itself is still produced by battle.py
and does not mention trophies).
"""
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import friends_db
from .common import (COLOR_SOCIAL, bar_line, emb, err_embed, get_conn,
                     guild_buff_text, need_player)

TIERS = [
    (7500, "💎 Diamond"),
    (3500, "🔮 Platinum"),
    (1500, "🥇 Gold"),
    (500, "🥈 Silver"),
    (0, "🥉 Bronze"),
]


def tier_for(power):
    for threshold, name in TIERS:
        if power >= threshold:
            return name
    return TIERS[-1][1]


def _conn():
    conn = get_conn()
    friends_db.ensure_tables(conn)
    return conn


class GuildPower(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="guildpower", description="Show a guild's tier, power, and war trophies")
    @app_commands.describe(guild="Guild name (empty = your own guild)")
    async def guildpower(self, interaction: discord.Interaction, guild: str = ""):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        friends_db.sync_war_trophies(conn)

        if guild.strip():
            g = db.get_guild_by_name(conn, guild.strip())
            if not g:
                await interaction.response.send_message(
                    embed=err_embed(f"Guild '{guild}' not found."),
                    ephemeral=True)
                return
        else:
            if not p["guild_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You are not in a guild. Create one with `/guild create`."),
                    ephemeral=True)
                return
            g = db.get_guild(conn, p["guild_id"])
            if not g:
                await interaction.response.send_message(
                    embed=err_embed("Your guild no longer exists."),
                    ephemeral=True)
                return

        power, member_count = friends_db.guild_power(conn, g["id"])
        tier = tier_for(power)
        trophies = friends_db.guild_trophy_count(conn, g["id"])
        trophy_note = ""
        trophy_row, war = friends_db.latest_trophy(conn, g["id"])
        if trophy_row and war:
            loser_id = war["guild_b"] if war["winner_id"] == war["guild_a"] else war["guild_a"]
            loser = db.get_guild(conn, loser_id)
            date = datetime.fromtimestamp(
                trophy_row["awarded_at"], tz=timezone.utc).strftime("%Y-%m-%d")
            trophy_note = (f"\nLatest trophy: war vs "
                           f"**{loser['name'] if loser else 'a rival guild'}** "
                           f"({war['score_a']} vs {war['score_b']}) on {date}.")
        leader = db.get_player(conn, g["leader_id"])
        desc = (
            f"Leader: {leader['name'] if leader else g['leader_id']}\n"
            f"Tier: **{tier}**\n"
            f"Power: **{power}** (members: {member_count}, guild level: {g['level']})\n"
            f"{bar_line('✨ Guild EXP', g['exp'], 200 * g['level'])}\n"
            f"Buff: {guild_buff_text(g['level'])}\n"
            f"🏆 War trophies: **{trophies}**{trophy_note}"
        )
        # Top guilds by power, for context.
        all_guilds = conn.execute("SELECT id FROM guilds").fetchall()
        ranked = []
        for row in all_guilds:
            pw, _n = friends_db.guild_power(conn, row["id"])
            ranked.append((pw, row["id"]))
        ranked.sort(reverse=True)
        top_lines = []
        for i, (pw, gid) in enumerate(ranked[:5], 1):
            gg = db.get_guild(conn, gid)
            top_lines.append(f"{i}. **{gg['name']}** — {tier_for(pw)} ({pw} power)")
        if top_lines:
            desc += "\n\n**Top guilds by power:**\n" + "\n".join(top_lines)
        await interaction.response.send_message(embed=emb(
            f"🏰 {g['name']}", desc, color=COLOR_SOCIAL))


async def setup(bot):
    await bot.add_cog(GuildPower(bot))
