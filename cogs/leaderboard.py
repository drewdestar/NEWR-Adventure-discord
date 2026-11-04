# -*- coding: utf-8 -*-
"""Cog leaderboard: server and global player rankings.

Server scope ranks players who are members of the Discord server where
the command was used (resolved via the guild member list; if that list
cannot be fetched, it falls back to all registered players and says so).
Global scope ranks every registered player across all servers the bot
is in. The bot currently serves only NEWR LABS, so the two lists are
identical until it joins more servers — the embed footer says so.
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import friends_db
from .common import (COLOR_PREMIUM, emb, err_embed, get_conn, need_player)

CATEGORIES = {
    "level": ("level DESC, exp DESC", "Level"),
    "gold": ("gold DESC", "Gold"),
    "kills": ("kills DESC", "Kills"),
}


def _conn():
    conn = get_conn()
    friends_db.ensure_tables(conn)
    return conn


class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Top players, server-wide or global")
    @app_commands.describe(scope="server = this Discord server, global = all servers",
                           category="What to rank by")
    @app_commands.choices(scope=[
        app_commands.Choice(name="server", value="server"),
        app_commands.Choice(name="global", value="global"),
    ])
    @app_commands.choices(category=[
        app_commands.Choice(name="level", value="level"),
        app_commands.Choice(name="gold", value="gold"),
        app_commands.Choice(name="kills", value="kills"),
    ])
    async def leaderboard(self, interaction: discord.Interaction,
                          scope: str, category: str):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        order, label = CATEGORIES[category]
        rows = conn.execute(
            f"SELECT * FROM players ORDER BY {order} LIMIT 10").fetchall()
        note = ""
        if scope == "server":
            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message(
                    embed=err_embed("Server leaderboards only work inside a server. "
                                    "Use scope global here."),
                    ephemeral=True)
                return
            try:
                member_ids = {m.id async for m in guild.fetch_members(limit=None)}
            except Exception:
                member_ids = set()
            if member_ids:
                rows = [r for r in rows if r["user_id"] in member_ids]
            else:
                note = ("\n\nNote: the server member list was unavailable, "
                        "so this shows all registered players.")
        if not rows:
            await interaction.response.send_message(embed=emb(
                "🏆 Leaderboard",
                "No players on this leaderboard yet.",
                color=COLOR_PREMIUM))
            return
        lines = []
        for i, r in enumerate(rows, 1):
            lines.append(
                f"{i}. **{r['name']}** — Lv {r['level']} • "
                f"{r['gold']} gold • {r['kills']} kills")
        if scope == "global":
            note += ("\n\nNote: global covers all servers this bot is in. "
                     "It currently serves only NEWR LABS, so the global list "
                     "matches the server list for now.")
        title = ("🏆 Server Leaderboard" if scope == "server"
                 else "🌍 Global Leaderboard") + f" — {label}"
        await interaction.response.send_message(embed=emb(
            title, "\n".join(lines) + note, color=COLOR_PREMIUM))


async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
