# -*- coding: utf-8 -*-
"""Cog botloan: borrow gold directly from the bot.

Visually and mechanically separate from friend-to-friend /loan:
its own /botloan command group and its own bot_loans table. Rules:
one outstanding bot loan per player, cap 100 gold x level (minimum
100), flat 10% interest shown upfront, the borrower confirms the
exact terms before any gold moves, full repayment only. Bot debt
MUST be repaid: repaying deducts the full amount even if the balance
goes negative — negative gold balances are allowed for debtors and
never clamped to zero, and a negative balance blocks any new bot loan
until it is earned back to 0 or more. Jobs stay open for debtors, so
they can always earn gold to repay. Nothing else is seized.
"""
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

import botloan_db
import database as db
import guildbank_db
from .common import COLOR_ECONOMY, emb, err_embed, get_conn, need_player


def _conn():
    conn = get_conn()
    botloan_db.ensure_tables(conn)
    guildbank_db.ensure_tables(conn)
    return conn


def _wib(ts):
    return datetime.fromtimestamp(
        ts, tz=timezone(timedelta(hours=7))).strftime("%d %b %Y %H:%M WIB")


class _ConfirmView(discord.ui.View):
    """Confirm-before-move: gold moves only after the borrower clicks Confirm."""

    def __init__(self, user_id, amount, interest, total):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.amount = amount
        self.interest = interest
        self.total = total

    async def _finish(self, interaction, confirmed):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=err_embed("This confirmation is not for you."),
                ephemeral=True)
            return
        for child in self.children:
            child.disabled = True
        if not confirmed:
            await interaction.response.edit_message(
                embed=emb("🏦 Bot Loan Cancelled",
                          "No gold moved.", color=COLOR_ECONOMY),
                view=self)
            return
        conn = _conn()
        p = db.get_player(conn, self.user_id)
        if p is None:
            await interaction.response.edit_message(
                embed=err_embed("You don't have a character."),
                view=self)
            return
        active = botloan_db.get_active_loan(conn, self.user_id)
        if active is not None:
            await interaction.response.edit_message(
                embed=err_embed(
                    "You already have an outstanding bot loan. Repay it "
                    "first with `/botloan repay`."),
                view=self)
            return
        if guildbank_db.get_active_guild_loan(conn, self.user_id) is not None:
            await interaction.response.edit_message(
                embed=err_embed(
                    "You have an open guild loan. Repay it first with "
                    "`/guildloan repay` before borrowing from the bot."),
                view=self)
            return
        if p["gold"] < 0:
            await interaction.response.edit_message(
                embed=err_embed(
                    f"Your gold balance is negative ({p['gold']} gold) — "
                    f"that is outstanding bot debt. Earn gold (jobs stay "
                    f"open for debtors) until your balance is 0 or more, "
                    f"then you can borrow again."),
                view=self)
            return
        cap = botloan_db.loan_cap(p["level"])
        if self.amount > cap:
            await interaction.response.edit_message(
                embed=err_embed(
                    f"Your cap is now {cap} gold (100 x level {p['level']})."),
                view=self)
            return
        p["gold"] += self.amount
        db.save_player(conn, p)
        lid = botloan_db.create_loan(conn, self.user_id, self.amount,
                                     self.interest, self.total)
        await interaction.response.edit_message(
            embed=emb("🏦 Bot Loan Approved!",
                      f"You received **{self.amount} gold** from the bot "
                      f"(loan ID {lid}).\n"
                      f"Interest: **{self.interest} gold** (10% flat).\n"
                      f"Repay **{self.total} gold** in full with "
                      f"`/botloan repay`. Bot debt must be repaid: the "
                      f"full amount is taken even if your balance goes "
                      f"negative, and no new bot loan is possible while "
                      f"you owe anything.",
                      color=COLOR_ECONOMY),
            view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        await self._finish(interaction, True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await self._finish(interaction, False)


class BotLoan(commands.Cog):
    botloan = app_commands.Group(
        name="botloan",
        description="Borrow gold directly from the bot (separate from friend loans)")

    def __init__(self, bot):
        self.bot = bot

    @botloan.command(name="borrow",
                     description="Borrow gold from the bot (10% flat interest)")
    @app_commands.describe(amount="Gold to borrow (max 100 x your level, minimum cap 100)")
    async def botloan_borrow(self, interaction: discord.Interaction,
                             amount: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        me = p["user_id"]
        active = botloan_db.get_active_loan(conn, me)
        if active is not None:
            await interaction.response.send_message(
                embed=err_embed(
                    "You already have an outstanding bot loan. Repay it "
                    "first with `/botloan repay` before borrowing again."),
                ephemeral=True)
            return
        if guildbank_db.get_active_guild_loan(conn, me) is not None:
            await interaction.response.send_message(
                embed=err_embed(
                    "You have an open guild loan. Repay it first with "
                    "`/guildloan repay` before borrowing from the bot."),
                ephemeral=True)
            return
        if p["gold"] < 0:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Your gold balance is negative ({p['gold']} gold) — "
                    f"that is outstanding bot debt. Earn gold (jobs stay "
                    f"open for debtors) until your balance is 0 or more, "
                    f"then you can borrow again."),
                ephemeral=True)
            return
        cap = botloan_db.loan_cap(p["level"])
        if amount <= 0 or amount > cap:
            await interaction.response.send_message(
                embed=err_embed(
                    f"Amount must be between 1 and {cap} gold "
                    f"(your cap: 100 x level {p['level']})."),
                ephemeral=True)
            return
        interest, total = botloan_db.loan_terms(amount)
        view = _ConfirmView(me, amount, interest, total)
        await interaction.response.send_message(
            embed=emb("🏦 Bot Loan Terms",
                      f"Borrow: **{amount} gold**\n"
                      f"Interest: **{interest} gold** (10% flat)\n"
                      f"You repay: **{total} gold** in full\n"
                      f"Your cap: {cap} gold (100 x level {p['level']})\n\n"
                      f"Confirm the exact terms below — nothing moves "
                      f"until you confirm. Bot debt must be repaid: "
                      f"repaying takes the full amount even if your "
                      f"balance goes negative, and no new bot loan is "
                      f"possible while you owe anything.",
                      color=COLOR_ECONOMY),
            view=view,
            ephemeral=True)

    @botloan.command(name="repay",
                     description="Repay your outstanding bot loan in full")
    async def botloan_repay(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        loan = botloan_db.get_active_loan(conn, p["user_id"])
        if loan is None:
            await interaction.response.send_message(
                embed=emb("🏦 Bot Loan",
                          "You have no outstanding bot loan.",
                          color=COLOR_ECONOMY),
                ephemeral=True)
            return
        # Full repayment only, and it is always taken in full: if the
        # player is short, the balance goes negative instead of the
        # repayment being refused. Negative balances are never clamped
        # to zero, and they block new bot loans until earned back.
        p["gold"] -= loan["total_due"]
        db.save_player(conn, p)
        botloan_db.repay_loan(conn, loan["id"])
        if p["gold"] < 0:
            note = (f"\nYour balance is now **{p['gold']} gold** "
                    f"(negative) — that is remaining bot debt. Earn gold "
                    f"(jobs stay open for debtors) until your balance is "
                    f"0 or more before you can borrow again.")
        else:
            note = ("\nYour balance is clear — you can borrow again "
                    "any time.")
        await interaction.response.send_message(
            embed=emb("🏦 Bot Loan Repaid!",
                      f"You repaid **{loan['total_due']} gold** in full "
                      f"(principal {loan['principal']} + interest "
                      f"{loan['interest']}).{note}",
                      color=COLOR_ECONOMY))

    @botloan.command(name="status",
                     description="Show your outstanding bot loan and your cap")
    async def botloan_status(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        loan = botloan_db.get_active_loan(conn, p["user_id"])
        cap = botloan_db.loan_cap(p["level"])
        balance_line = f"Your gold balance: **{p['gold']} gold**."
        if loan is None:
            desc = (f"No outstanding bot loan.\n"
                    f"{balance_line}\n"
                    f"Your current cap: **{cap} gold** "
                    f"(100 x level {p['level']}).")
            if p["gold"] < 0:
                desc += ("\nYour balance is negative — that is "
                         "outstanding bot debt. Earn gold (jobs stay "
                         "open for debtors) until your balance is 0 or "
                         "more before you can borrow again.")
        else:
            desc = (f"Loan ID {loan['id']} — borrowed {_wib(loan['borrowed_at'])}\n"
                    f"Principal: **{loan['principal']} gold**\n"
                    f"Interest: **{loan['interest']} gold** (10% flat)\n"
                    f"Repay in full: **{loan['total_due']} gold** "
                    f"with `/botloan repay`\n"
                    f"{balance_line}\n"
                    f"Bot debt must be repaid: the full amount is taken "
                    f"even if your balance goes negative. No new bot "
                    f"loan until this one is repaid and your balance is "
                    f"0 or more.")
        await interaction.response.send_message(
            embed=emb("🏦 Bot Loan Status", desc, color=COLOR_ECONOMY),
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(BotLoan(bot))
