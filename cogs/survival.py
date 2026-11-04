# -*- coding: utf-8 -*-
"""Cog survival: status lapar/haus/stamina/durability, makan, minum, repair."""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
from data import ITEMS
from .common import (COLOR_SURVIVAL, bar_line, emb, err_embed, get_conn,
                     need_player, warnings_for)


class Survival(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="status", description="Check hunger, thirst, stamina & gear durability")
    async def status(self, interaction: discord.Interaction):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        eq = db.equipped_items(conn, p["user_id"])
        gear_lines = []
        for row in eq:
            gear_lines.append(bar_line(f"🔧 {disp.item(row['item_id'])}", row['durability'], 100))
        e = emb(f"💚 Status of {p['name']}",
                f"{bar_line('🍗 Hunger', p['hunger'], 100)}\n"
                f"{bar_line('💧 Thirst', p['thirst'], 100)}\n"
                f"{bar_line('⚡ Stamina', p['stamina'], 100)} (refills tomorrow)\n"
                f"{bar_line('❤️ HP', p['hp'], p['max_hp'])}\n"
                f"Equipped gear:\n" + ("\n".join(gear_lines) if gear_lines else "No gear equipped."),
                color=COLOR_SURVIVAL)
        for w in warnings_for(p):
            e.add_field(name="Warning", value=w, inline=False)
        await interaction.response.send_message(embed=e)

    async def _consume(self, interaction, item, want):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        item = disp.resolve_item(item) or item.lower()
        if item not in ITEMS or ITEMS[item].get("type") != "food":
            await interaction.response.send_message(
                embed=err_embed("That's not food/drink."), ephemeral=True)
            return
        info = ITEMS[item]
        if want == "hunger" and "hunger" not in info:
            await interaction.response.send_message(
                embed=err_embed(f"{disp.item(item)} isn't filling, that's a drink."),
                ephemeral=True)
            return
        if want == "thirst" and "thirst" not in info:
            await interaction.response.send_message(
                embed=err_embed(f"{disp.item(item)} doesn't quench thirst, that's food."),
                ephemeral=True)
            return
        if db.item_qty(conn, p["user_id"], item) < 1:
            await interaction.response.send_message(
                embed=err_embed(f"You don't have {disp.item(item)}."), ephemeral=True)
            return
        p["hunger"] = min(100, p["hunger"] + info.get("hunger", 0))
        p["thirst"] = min(100, p["thirst"] + info.get("thirst", 0))
        db.remove_item(conn, p["user_id"], item, 1)
        db.save_player(conn, p)
        await interaction.response.send_message(
            embed=emb('🍽️ Eat/Drink',
                      f"You consumed {disp.item(item)}!\n"
                      f"{bar_line('🍗 Hunger', p['hunger'], 100)}\n"
                      f"{bar_line('💧 Thirst', p['thirst'], 100)}",
                      color=COLOR_SURVIVAL))

    @app_commands.command(name="eat", description="Eat so you don't go hungry")
    @app_commands.describe(item="Food name, e.g. Bread")
    async def eat(self, interaction: discord.Interaction, item: str):
        await self._consume(interaction, item, "hunger")

    @app_commands.command(name="drink", description="Drink so you don't go thirsty")
    @app_commands.describe(item="Drink name, e.g. Drinking Water")
    async def drink(self, interaction: discord.Interaction, item: str):
        await self._consume(interaction, item, "thirst")

    @app_commands.command(name="repair", description="Repair damaged weapons & armor with gold")
    @app_commands.describe(item="Item name (empty = repair all equipped gear)")
    async def repair(self, interaction: discord.Interaction, item: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        eq = db.equipped_items(conn, p["user_id"])
        if item:
            item = disp.resolve_item(item) or item.lower()
            eq = [r for r in eq if r["item_id"] == item]
            if not eq:
                await interaction.response.send_message(
                    embed=err_embed("That item isn't equipped / doesn't exist."),
                    ephemeral=True)
                return
        damaged = [r for r in eq if r["durability"] < 100]
        if not damaged:
            await interaction.response.send_message(
                embed=emb('🔧 Repair','All your gear is still in perfect shape, no repair needed!',
                          color=COLOR_SURVIVAL))
            return
        total_cost = 0
        for r in damaged:
            missing = 100 - r["durability"]
            total_cost += ((missing + 9) // 10) * 10
        if p["gold"] < total_cost:
            await interaction.response.send_message(
                embed=err_embed(f"Not enough gold! Repair needs {total_cost} gold, you have {p['gold']}."),
                ephemeral=True)
            return
        p["gold"] -= total_cost
        db.save_player(conn, p)
        for r in damaged:
            conn.execute("UPDATE inventory SET durability = 100 WHERE id = ?", (r["id"],))
        conn.commit()
        names = ", ".join(disp.item(r["item_id"]) for r in damaged)
        await interaction.response.send_message(
            embed=emb('🔧 Repair',
                      f"{names} fully repaired! Cost {total_cost} gold. Gold left: {p['gold']}.",
                      color=COLOR_SURVIVAL))


async def setup(bot):
    await bot.add_cog(Survival(bot))
