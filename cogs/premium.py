# -*- coding: utf-8 -*-
"""Cog premium & event: VIP, VIP grant (admin), ranking, event."""
import time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import logic
import i18n
from data import ITEMS
from .common import COLOR_PREMIUM, emb, err_embed, get_conn, need_player

VIP_DAYS = 30


class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vip", description="View your VIP status & benefits")
    async def vip(self, interaction: discord.Interaction):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if logic.vip_active(p):
            until = datetime.fromtimestamp(p["vip_until"]).strftime("%d %b %Y %H:%M")
            txt = (f"👑 Your VIP is ACTIVE until {until}.\n"
                   f"Benefits: EXP x1.5, gold x1.25, better loot & gacha odds.")
        else:
            txt = ("Your VIP is not active yet.\n"
                   "VIP benefits: EXP x1.5, gold x1.25, better loot & gacha odds.\n"
                   "VIP on this server is granted by an admin with `/vipgrant` (no payment).")
        await interaction.response.send_message(
            embed=emb("👑 VIP Membership", txt, color=COLOR_PREMIUM))

    @app_commands.command(name="vipgrant", description="Give 30 days of VIP to a player (server admins only)")
    @app_commands.describe(target="Player receiving VIP: mention or user ID")
    async def vipgrant(self, interaction: discord.Interaction, target: discord.User):
        i18n.set_ctx(interaction, get_conn())
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=err_embed('Only server admins can grant VIP.'),
                ephemeral=True)
            return
        conn = get_conn()
        t = db.get_player(conn, target.id)
        if not t:
            await interaction.response.send_message(
                embed=err_embed("That player hasn't registered a character."), ephemeral=True)
            return
        t["vip"] = 1
        t["vip_until"] = int(time.time()) + VIP_DAYS * 86400
        db.save_player(conn, t)
        until = datetime.fromtimestamp(t["vip_until"]).strftime("%d %b %Y")
        await interaction.response.send_message(
            embed=emb("👑 VIP Membership",
                      f"VIP granted to **{t['name']}** until {until} (30 days).",
                      color=COLOR_PREMIUM))

    @app_commands.command(name="ranking", description="Weekly ranking & top player reward claims")
    @app_commands.describe(aksi="list/claim")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="claim", value="claim"),
    ])
    async def ranking(self, interaction: discord.Interaction, aksi: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        rows = conn.execute(
            "SELECT * FROM players ORDER BY level DESC, exp DESC LIMIT 10").fetchall()
        names = []
        for i, r in enumerate(rows, 1):
            names.append(f"{i}. **{r['name']}** — Lv {r['level']} ({r['exp']} EXP)")
        if aksi == "list":
            await interaction.response.send_message(embed=emb('🏆 Top Player Ranking',
                "\n".join(names) +
                "\n\nThis week's top 3 can claim rewards with `/ranking claim`.",
                color=COLOR_PREMIUM))
            return
        period = datetime.now(logic.WIB).strftime("%Y-W%W")
        claimed = conn.execute(
            "SELECT * FROM ranking_claims WHERE user_id = ? AND period = ?",
            (p["user_id"], period)).fetchone()
        if claimed:
            await interaction.response.send_message(
                embed=emb('🏆 Ranking',"You've already claimed this week's ranking reward.",
                          color=COLOR_PREMIUM),
                ephemeral=True)
            return
        rank = next((i for i, r in enumerate(rows, 1) if r["user_id"] == p["user_id"]), None)
        if rank is None or rank > 3:
            await interaction.response.send_message(
                embed=err_embed("You haven't made this week's top 3 yet. Keep grinding!"),
                ephemeral=True)
            return
        rewards = {1: (1000, "jimat keberuntungan"), 2: (500, "potion besar"), 3: (250, "potion kecil")}
        gold, item = rewards[rank]
        p["gold"] += gold
        p["gold_earned"] += gold
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], item, 1)
        conn.execute(
            "INSERT INTO ranking_claims (user_id, period, claimed_at) VALUES (?, ?, ?)",
            (p["user_id"], period, int(time.time())))
        conn.commit()
        await interaction.response.send_message(
            embed=emb('🏆 Ranking',
                      f"You're ranked #{rank} this week! Reward: {gold} gold + {disp.item(item)}.",
                      color=COLOR_PREMIUM))

    @app_commands.command(name="event", description="View currently active seasonal events")
    async def event(self, interaction: discord.Interaction):
        i18n.set_ctx(interaction, get_conn())
        events = logic.active_events()
        if not events:
            await interaction.response.send_message(embed=emb('🎉 Seasonal Event','No seasonal event is active right now.\nEvents: **Halloween** (20-31 Oct), **Christmas** (20-26 Dec), **New Year** (30 Dec-2 Jan), **Summer Festival** (1-31 Jul), **Harvest Festival** (1-30 Sep). Weekly raid bosses rotate: Demon King, Void King, Snow Queen.\nDuring an active event, the shop gets special stock and event bosses appear in `/raid`.',
                color=COLOR_PREMIUM))
            return
        lines = []
        for name, ev in events:
            shop_txt = ", ".join(disp.item(it) for it in ev['shop'])
            lines.append(f"**{disp.event_name(name)}**: {disp.event_desc(name)}\nEvent boss: {disp.event_boss(name)} • Event stock: {shop_txt}")
        await interaction.response.send_message(
            embed=emb('🎉 Active Event!', "\n\n".join(lines), color=COLOR_PREMIUM))


async def setup(bot):
    await bot.add_cog(Premium(bot))
