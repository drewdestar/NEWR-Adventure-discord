# -*- coding: utf-8 -*-
"""Cog hospital: check admission status and leave once healed enough.

Admission happens automatically: monster defeat and PvP when the winner
picks "Hospital". Healing is 10 HP per whole minute, computed lazily
from the admission row (see hospital_db) — no background loop needed.

- /hospital status: current (computed) HP, max HP, minutes until you
  may leave (25% of max), minutes until full HP, and the reminder that
  potions (or medicine sent by friends via /transfer) heal instantly.
- /hospital leave: allowed only at 25% of max HP or more. Staying
  longer keeps healing to full HP; reaching full HP discharges
  automatically on the next player load.
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import hospital_db as hb
from .common import COLOR_BATTLE, emb, err_embed, get_conn, need_player


def _conn():
    conn = get_conn()
    hb.ensure_tables(conn)
    return conn


class Hospital(commands.Cog):
    hospital = app_commands.Group(
        name="hospital",
        description="Hospital stay: heal over time after a defeat")

    def __init__(self, bot):
        self.bot = bot

    @hospital.command(name="status", description="Check your hospital stay and healing progress")
    async def hospital_status(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        adm = hb.get_admission(conn, p["user_id"])
        if adm is None:
            await interaction.response.send_message(embed=emb(
                "🏥 Hospital",
                "You are not in the hospital. You are free to fight, raid, and duel.",
                color=COLOR_BATTLE))
            return
        hp = hb.computed_hp(adm, p["max_hp"])
        to_leave = hb.minutes_to_discharge(adm, p["max_hp"])
        to_full = hb.minutes_to_full(adm, p["max_hp"])
        reason = "lost a duel (the winner chose hospital)" if adm["reason"] == "pvp" else "fell in battle"
        if to_leave == 0:
            leave_line = ("You may leave now — use `/hospital leave`. Staying "
                          "longer keeps healing you to full HP.")
        else:
            leave_line = (f"You may leave in about **{to_leave} minute(s)** "
                          f"(once HP reaches 25% of max).")
        await interaction.response.send_message(embed=emb(
            "🏥 Hospital Stay",
            f"You were admitted because you {reason}.\n"
            f"HP now: **{hp}/{p['max_hp']}** (healing 10 HP per minute)\n"
            f"{leave_line}\n"
            f"Full HP in about **{to_full} minute(s)** if you stay.\n"
            f"Shortcut: use a potion from `/inventory` — healing items restore "
            f"instantly, and reaching 25% HP discharges you at once. Friends "
            f"can send you medicine with `/transfer`.",
            color=COLOR_BATTLE))

    @hospital.command(name="leave", description="Leave the hospital (only at 25% of max HP or more)")
    async def hospital_leave(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        adm = hb.get_admission(conn, p["user_id"])
        if adm is None:
            await interaction.response.send_message(embed=emb(
                "🏥 Hospital", "You are not in the hospital.",
                color=COLOR_BATTLE))
            return
        hp = hb.computed_hp(adm, p["max_hp"])
        if not hb.can_leave(hp, p["max_hp"]):
            to_leave = hb.minutes_to_discharge(adm, p["max_hp"])
            await interaction.response.send_message(
                embed=err_embed(
                    f"Not healed enough yet! HP is {hp}/{p['max_hp']} — you may "
                    f"leave at 25% of max HP (about {to_leave} more minute(s)), "
                    f"or use a potion to heal instantly."),
                ephemeral=True)
            return
        p["hp"] = hp
        db.save_player(conn, p)
        hb.discharge(conn, p["user_id"])
        await interaction.response.send_message(embed=emb(
            "🏥 Discharged!",
            f"You left the hospital with **{hp}/{p['max_hp']} HP**. You can "
            f"fight, raid, and duel again.",
            color=COLOR_BATTLE))


async def setup(bot):
    await bot.add_cog(Hospital(bot))
