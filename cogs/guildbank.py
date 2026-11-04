# -*- coding: utf-8 -*-
"""Cog guild economy (phase 2): guild bank, guild loans, personal bank,
guild marketplace, and tax leaderboards.

- /guildbank deposit/info/withdraw: guild-owned stock. Anyone in the
  guild may deposit gold, items, or pets; withdrawals are leader-only
  so a random member cannot drain guild stock. Every deposit is
  recorded per player (donor leaderboards).
- /guildloan request/approve/decline/repay/list: borrow gold and/or
  items from the guild bank. The leader approves (DM buttons, or the
  approve command if the buttons expired). Cap = what the bank holds.
  Gold loans carry 10% interest; item loans return as-is. Full
  repayment only; unpaid guild debt follows the bot-debt rule (balance
  may go negative, jobs stay open, no new guild/bot loan until clear).
- /bank deposit/withdraw/balance: personal bank. Banked gold is
  separate from carried gold — shop, defeat loss, and PvP steals only
  ever touch carried gold. Interest is 1% per whole day, accrued
  lazily on every read/move (restart-safe). Withdraw before spending.
- /guildmarket list/listings/buy/cancel: the leader lists guild-bank
  items at a set price; ANY registered player may buy (member or
  outsider). 10% of the price goes to the central bot tax pool, 90%
  to the selling guild's bank. Every sale is tax-ledgered.
- /taxboard: top taxpayers and top gold depositors, per player and
  per guild.
"""
import discord
from discord import app_commands
from discord.ext import commands

import botloan_db
import database as db
import display as disp
import guildbank_db as gb
from data import ITEMS
from .common import COLOR_ECONOMY, COLOR_SOCIAL, emb, err_embed, get_conn, need_player


def _conn():
    conn = get_conn()
    gb.ensure_tables(conn)
    botloan_db.ensure_tables(conn)
    return conn


def _name(conn, user_id):
    p = db.get_player(conn, user_id)
    return p["name"] if p else f"User {user_id}"


def _guild_name(conn, guild_id):
    g = db.get_guild(conn, guild_id)
    return g["name"] if g else f"Guild {guild_id}"


def _is_leader(guild, user_id):
    return guild is not None and guild["leader_id"] == user_id


def _approve_loan(conn, loan):
    """Shared approve path (DM button + command). Returns (ok, text).
    Re-checks everything at approve time: loan still pending, caller is
    still the guild leader, borrower still in the guild, bank still
    holds the funds. Nothing moves until all checks pass."""
    guild = db.get_guild(conn, loan["guild_id"])
    if guild is None:
        return False, "That guild no longer exists."
    borrower = db.get_player(conn, loan["borrower_id"])
    if borrower is None or borrower["guild_id"] != loan["guild_id"]:
        return False, "The borrower is no longer in this guild."
    if loan["gold_principal"] > 0 and gb.bank_gold(conn, loan["guild_id"]) < loan["gold_principal"]:
        return False, "The guild bank no longer holds enough gold for this loan."
    if loan["item_id"] and gb.bank_item_qty(conn, loan["guild_id"], loan["item_id"]) < loan["item_qty"]:
        return False, "The guild bank no longer holds enough of that item."
    if loan["gold_principal"] > 0:
        gb.add_bank_gold(conn, loan["guild_id"], -loan["gold_principal"])
        borrower["gold"] += loan["gold_principal"]
    if loan["item_id"]:
        gb.take_bank_item(conn, loan["guild_id"], loan["item_id"], loan["item_qty"])
        db.add_item(conn, loan["borrower_id"], loan["item_id"], loan["item_qty"])
    db.save_player(conn, borrower)
    gb.approve_guild_loan(conn, loan["id"])
    parts = []
    if loan["gold_principal"] > 0:
        parts.append(f"**{loan['gold_principal']} gold** (repay **{loan['gold_total_due']} gold** with 10% interest)")
    if loan["item_id"]:
        parts.append(f"**{disp.item(loan['item_id'])} x{loan['item_qty']}** (return as-is)")
    return True, "Guild loan approved: " + " + ".join(parts) + "."


class _GuildLoanApproveView(discord.ui.View):
    """Leader approval buttons sent by DM. The command path
    (/guildloan approve) always works even after these buttons expire
    or the bot restarts."""

    def __init__(self, loan_id, leader_id):
        super().__init__(timeout=None)
        self.loan_id = loan_id
        self.leader_id = leader_id

    async def _check(self, interaction):
        if interaction.user.id != self.leader_id:
            await interaction.response.send_message(
                embed=err_embed("Only the guild leader can approve this loan."),
                ephemeral=True)
            return False
        return True

    async def _finish(self, interaction, approve):
        if not await self._check(interaction):
            return
        for child in self.children:
            child.disabled = True
        conn = _conn()
        loan = gb.get_guild_loan(conn, self.loan_id)
        if loan is None or loan["status"] != "pending":
            await interaction.response.edit_message(
                embed=err_embed("That loan request is no longer pending."),
                view=self)
            return
        guild = db.get_guild(conn, loan["guild_id"])
        if not _is_leader(guild, interaction.user.id):
            await interaction.response.edit_message(
                embed=err_embed("You are no longer this guild's leader."),
                view=self)
            return
        if not approve:
            gb.decline_guild_loan(conn, self.loan_id)
            await interaction.response.edit_message(
                embed=emb("🏰 Guild Loan Declined",
                          f"Loan request #{self.loan_id} was declined.",
                          color=COLOR_SOCIAL),
                view=self)
            return
        ok, text = _approve_loan(conn, loan)
        await interaction.response.edit_message(
            embed=(emb("🏰 Guild Loan Approved!", text, color=COLOR_SOCIAL)
                   if ok else err_embed(text)),
            view=self)

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction, button):
        await self._finish(interaction, True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction, button):
        await self._finish(interaction, False)


class GuildBank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _dm_leader(self, leader_id, embed, view):
        try:
            user = self.bot.get_user(leader_id)
            if user is None:
                user = await self.bot.fetch_user(leader_id)
            await user.send(embed=embed, view=view)
            return True
        except Exception:
            return False

    # ---------------------------------------------------------- guildbank
    guildbank = app_commands.Group(
        name="guildbank",
        description="Your guild's shared bank: deposit, view, withdraw (leader-only)")

    @guildbank.command(name="deposit", description="Deposit gold, an item, or a pet into your guild's bank")
    @app_commands.describe(kind="What to deposit", amount="Gold amount (for gold)",
                           item="Item name (for item)", qty="Item amount (for item)",
                           pet_id="Pet ID from /pet list (for pet)")
    @app_commands.choices(kind=[
        app_commands.Choice(name="gold", value="gold"),
        app_commands.Choice(name="item", value="item"),
        app_commands.Choice(name="pet", value="pet"),
    ])
    async def guildbank_deposit(self, interaction: discord.Interaction, kind: str,
                                amount: int = 0, item: str = "", qty: int = 0,
                                pet_id: int = 0):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild. Join one first."),
                ephemeral=True)
            return
        gid = p["guild_id"]
        if kind == "gold":
            if amount <= 0 or p["gold"] < amount:
                await interaction.response.send_message(
                    embed=err_embed(f"Deposit an amount between 1 and your carried gold ({p['gold']})."),
                    ephemeral=True)
                return
            p["gold"] -= amount
            db.save_player(conn, p)
            gb.add_bank_gold(conn, gid, amount)
            gb.record_deposit(conn, gid, p["user_id"], "gold", gold=amount)
            await interaction.response.send_message(embed=emb(
                "🏰 Guild Bank Deposit",
                f"Deposited **{amount} gold** into **{_guild_name(conn, gid)}**'s bank. "
                f"Bank gold is now **{gb.bank_gold(conn, gid)}**.",
                color=COLOR_SOCIAL))
            return
        if kind == "item":
            item_id = disp.resolve_item(item) or item.lower()
            if item_id not in ITEMS:
                await interaction.response.send_message(
                    embed=err_embed("That item is unknown. Check `/inventory list` first."),
                    ephemeral=True)
                return
            if qty <= 0 or not db.remove_item(conn, p["user_id"], item_id, qty):
                await interaction.response.send_message(
                    embed=err_embed(f"You don't have {qty}x {disp.item(item_id)}."),
                    ephemeral=True)
                return
            gb.add_bank_item(conn, gid, item_id, qty)
            gb.record_deposit(conn, gid, p["user_id"], "item", item_id=item_id, qty=qty)
            await interaction.response.send_message(embed=emb(
                "🏰 Guild Bank Deposit",
                f"Deposited **{disp.item(item_id)} x{qty}** into **{_guild_name(conn, gid)}**'s bank.",
                color=COLOR_SOCIAL))
            return
        # pet
        pets = db.get_pets(conn, p["user_id"])
        pet = next((x for x in pets if x["id"] == pet_id), None)
        if pet is None:
            await interaction.response.send_message(
                embed=err_embed("No pet with that ID. Check `/pet list` first."),
                ephemeral=True)
            return
        conn.execute("DELETE FROM pets WHERE id = ?", (pet["id"],))
        conn.execute(
            "INSERT INTO guild_bank_pets (guild_id, species, name, level, exp, "
            "gear_weapon, gear_armor, depositor_id, deposited_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (gid, pet["species"], pet["name"], pet["level"], pet["exp"],
             pet["gear_weapon"], pet["gear_armor"], p["user_id"], gb.now()))
        conn.commit()
        gb.record_deposit(conn, gid, p["user_id"], "pet", qty=1)
        await interaction.response.send_message(embed=emb(
            "🏰 Guild Bank Deposit",
            f"Deposited pet **{pet['name']}** ({disp.pet(pet['species'])}, Lv {pet['level']}) "
            f"into **{_guild_name(conn, gid)}**'s bank. Withdraw it later with "
            f"`/guildbank withdraw` (leader-only).",
            color=COLOR_SOCIAL))

    @guildbank.command(name="info", description="View your guild bank's gold, items, and pets")
    async def guildbank_info(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild."), ephemeral=True)
            return
        gid = p["guild_id"]
        items = gb.bank_items(conn, gid)
        pets = gb.bank_pets(conn, gid)
        item_lines = [f"{disp.item(i['item_id'])} x{i['qty']}" for i in items] or ["(empty)"]
        pet_lines = [f"ID {x['id']} — **{x['name']}** ({disp.pet(x['species'])}, Lv {x['level']}, from {_name(conn, x['depositor_id'])})" for x in pets] or ["(none)"]
        dep = conn.execute(
            "SELECT user_id, SUM(gold) AS total FROM guild_bank_deposits "
            "WHERE guild_id = ? AND kind = 'gold' GROUP BY user_id "
            "ORDER BY total DESC LIMIT 5", (gid,)).fetchall()
        dep_lines = [f"{_name(conn, r['user_id'])} — {r['total']} gold" for r in dep] or ["(no gold deposits yet)"]
        await interaction.response.send_message(embed=emb(
            f"🏰 Guild Bank — {_guild_name(conn, gid)}",
            f"💰 Gold: **{gb.bank_gold(conn, gid)}**\n\n"
            f"📦 Items:\n" + "\n".join(item_lines) + "\n\n"
            f"🐾 Pets:\n" + "\n".join(pet_lines) + "\n\n"
            f"🤝 Top gold depositors:\n" + "\n".join(dep_lines),
            color=COLOR_SOCIAL))

    @guildbank.command(name="withdraw", description="Withdraw from the guild bank (leader-only)")
    @app_commands.describe(kind="What to withdraw", amount="Gold amount (for gold)",
                           item="Item name (for item)", qty="Item amount (for item)",
                           pet_id="Bank pet ID (for pet)",
                           target="Guild member receiving it (default: you)")
    @app_commands.choices(kind=[
        app_commands.Choice(name="gold", value="gold"),
        app_commands.Choice(name="item", value="item"),
        app_commands.Choice(name="pet", value="pet"),
    ])
    async def guildbank_withdraw(self, interaction: discord.Interaction, kind: str,
                                 amount: int = 0, item: str = "", qty: int = 0,
                                 pet_id: int = 0, target: discord.User = None):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild."), ephemeral=True)
            return
        guild = db.get_guild(conn, p["guild_id"])
        if not _is_leader(guild, p["user_id"]):
            await interaction.response.send_message(
                embed=err_embed("Only the guild leader can withdraw from the guild bank."),
                ephemeral=True)
            return
        gid = p["guild_id"]
        tid = target.id if target is not None else p["user_id"]
        t = db.get_player(conn, tid)
        if t is None or t["guild_id"] != gid:
            await interaction.response.send_message(
                embed=err_embed("The recipient must be a member of this guild."),
                ephemeral=True)
            return
        if kind == "gold":
            if amount <= 0 or gb.bank_gold(conn, gid) < amount:
                await interaction.response.send_message(
                    embed=err_embed(f"Bank gold is {gb.bank_gold(conn, gid)} — withdraw at most that."),
                    ephemeral=True)
                return
            gb.add_bank_gold(conn, gid, -amount)
            t["gold"] += amount
            db.save_player(conn, t)
            await interaction.response.send_message(embed=emb(
                "🏰 Guild Bank Withdrawal",
                f"**{amount} gold** from the bank went to **{t['name']}**.",
                color=COLOR_SOCIAL))
            return
        if kind == "item":
            item_id = disp.resolve_item(item) or item.lower()
            if qty <= 0 or not gb.take_bank_item(conn, gid, item_id, qty):
                await interaction.response.send_message(
                    embed=err_embed(f"The bank doesn't hold {qty}x {disp.item(item_id)}."),
                    ephemeral=True)
                return
            db.add_item(conn, tid, item_id, qty)
            await interaction.response.send_message(embed=emb(
                "🏰 Guild Bank Withdrawal",
                f"**{disp.item(item_id)} x{qty}** from the bank went to **{t['name']}**.",
                color=COLOR_SOCIAL))
            return
        row = conn.execute(
            "SELECT * FROM guild_bank_pets WHERE id = ? AND guild_id = ?",
            (pet_id, gid)).fetchone()
        if row is None:
            await interaction.response.send_message(
                embed=err_embed("No bank pet with that ID in this guild."),
                ephemeral=True)
            return
        conn.execute("DELETE FROM guild_bank_pets WHERE id = ?", (pet_id,))
        conn.execute(
            "INSERT INTO pets (user_id, species, name, level, exp, gear_weapon, gear_armor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tid, row["species"], row["name"], row["level"], row["exp"],
             row["gear_weapon"], row["gear_armor"]))
        conn.commit()
        await interaction.response.send_message(embed=emb(
            "🏰 Guild Bank Withdrawal",
            f"Pet **{row['name']}** ({disp.pet(row['species'])}, Lv {row['level']}) "
            f"from the bank went to **{t['name']}**.",
            color=COLOR_SOCIAL))

    # ---------------------------------------------------------- guildloan
    guildloan = app_commands.Group(
        name="guildloan",
        description="Borrow gold/items from your guild's bank (leader approves)")

    @guildloan.command(name="request", description="Request a loan from your guild's bank")
    @app_commands.describe(gold="Gold to borrow (0 = none)", item="Item to borrow (empty = none)",
                           qty="Item amount (for item)")
    async def guildloan_request(self, interaction: discord.Interaction,
                                gold: int = 0, item: str = "", qty: int = 0):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild."), ephemeral=True)
            return
        gid = p["guild_id"]
        if gb.get_active_guild_loan(conn, p["user_id"]) is not None:
            await interaction.response.send_message(
                embed=err_embed("You already have an open guild loan. Repay it first."),
                ephemeral=True)
            return
        if botloan_db.get_active_loan(conn, p["user_id"]) is not None:
            await interaction.response.send_message(
                embed=err_embed("You have an outstanding bot loan. Clear it before a guild loan."),
                ephemeral=True)
            return
        if p["gold"] < 0:
            await interaction.response.send_message(
                embed=err_embed(f"Your gold balance is negative ({p['gold']} gold) — that is outstanding debt. "
                                f"Earn gold until your balance is 0 or more before borrowing again."),
                ephemeral=True)
            return
        item_id = None
        if item:
            item_id = disp.resolve_item(item) or item.lower()
            if qty <= 0 or gb.bank_item_qty(conn, gid, item_id) < qty:
                await interaction.response.send_message(
                    embed=err_embed(f"The guild bank doesn't hold {qty}x {disp.item(item_id)}."),
                    ephemeral=True)
                return
        if gold < 0 or (gold == 0 and item_id is None):
            await interaction.response.send_message(
                embed=err_embed("Request gold, an item, or both."),
                ephemeral=True)
            return
        if gold > gb.bank_gold(conn, gid):
            await interaction.response.send_message(
                embed=err_embed(f"The guild bank only holds {gb.bank_gold(conn, gid)} gold — "
                                f"a loan cannot exceed the bank balance."),
                ephemeral=True)
            return
        lid = gb.create_guild_loan(conn, gid, p["user_id"], gold, item_id, qty)
        interest, total = gb.guild_loan_terms(gold)
        guild = db.get_guild(conn, gid)
        desc = f"**{p['name']}** requests a guild loan (ID {lid}):\n"
        if gold > 0:
            desc += f"• **{gold} gold** (repay **{total} gold**, 10% interest = {interest})\n"
        if item_id:
            desc += f"• **{disp.item(item_id)} x{qty}** (return as-is)\n"
        desc += "Nothing moves until the guild leader approves."
        view = _GuildLoanApproveView(lid, guild["leader_id"])
        sent = await self._dm_leader(guild["leader_id"], emb(
            "🏰 Guild Loan Request", desc, color=COLOR_SOCIAL), view)
        note = ("The leader was notified by DM — approve with the buttons there."
                if sent else
                "The leader could not be reached by DM — they can approve with "
                f"`/guildloan approve {lid}`.")
        await interaction.response.send_message(embed=emb(
            "🏰 Guild Loan Requested",
            desc + f"\n{note}\nFull repayment only; unpaid guild debt may push "
            "your balance negative and blocks new guild/bot loans until clear.",
            color=COLOR_SOCIAL))

    @guildloan.command(name="approve", description="Approve a pending guild loan (leader-only)")
    @app_commands.describe(loan_id="Loan ID from /guildloan list")
    async def guildloan_approve(self, interaction: discord.Interaction, loan_id: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        loan = gb.get_guild_loan(conn, loan_id)
        if loan is None or loan["status"] != "pending" or loan["guild_id"] != p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("No pending loan request with that ID in your guild."),
                ephemeral=True)
            return
        guild = db.get_guild(conn, p["guild_id"])
        if not _is_leader(guild, p["user_id"]):
            await interaction.response.send_message(
                embed=err_embed("Only the guild leader can approve loans."),
                ephemeral=True)
            return
        ok, text = _approve_loan(conn, loan)
        await interaction.response.send_message(
            embed=(emb("🏰 Guild Loan Approved!", text, color=COLOR_SOCIAL)
                   if ok else err_embed(text)))

    @guildloan.command(name="decline", description="Decline a pending guild loan (leader-only)")
    @app_commands.describe(loan_id="Loan ID from /guildloan list")
    async def guildloan_decline(self, interaction: discord.Interaction, loan_id: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        loan = gb.get_guild_loan(conn, loan_id)
        if loan is None or loan["status"] != "pending" or loan["guild_id"] != p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("No pending loan request with that ID in your guild."),
                ephemeral=True)
            return
        guild = db.get_guild(conn, p["guild_id"])
        if not _is_leader(guild, p["user_id"]):
            await interaction.response.send_message(
                embed=err_embed("Only the guild leader can decline loans."),
                ephemeral=True)
            return
        gb.decline_guild_loan(conn, loan_id)
        await interaction.response.send_message(embed=emb(
            "🏰 Guild Loan Declined", f"Loan request #{loan_id} was declined.",
            color=COLOR_SOCIAL))

    @guildloan.command(name="repay", description="Repay your active guild loan in full")
    @app_commands.describe(loan_id="Loan ID from /guildloan list")
    async def guildloan_repay(self, interaction: discord.Interaction, loan_id: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        loan = gb.get_guild_loan(conn, loan_id)
        if loan is None or loan["status"] != "active" or loan["borrower_id"] != p["user_id"]:
            await interaction.response.send_message(
                embed=err_embed("No active guild loan with that ID for you."),
                ephemeral=True)
            return
        if loan["item_id"] and db.item_qty(conn, p["user_id"], loan["item_id"]) < loan["item_qty"]:
            await interaction.response.send_message(
                embed=err_embed(f"You no longer hold {disp.item(loan['item_id'])} x{loan['item_qty']} to return."),
                ephemeral=True)
            return
        # Gold repayment is always taken in full, even if the balance
        # goes negative — same rule as bot debt. Item return must be
        # physically possible (checked above).
        if loan["gold_total_due"] > 0:
            p["gold"] -= loan["gold_total_due"]
            gb.add_bank_gold(conn, loan["guild_id"], loan["gold_total_due"])
        if loan["item_id"]:
            db.remove_item(conn, p["user_id"], loan["item_id"], loan["item_qty"])
            gb.add_bank_item(conn, loan["guild_id"], loan["item_id"], loan["item_qty"])
        db.save_player(conn, p)
        gb.repay_guild_loan(conn, loan_id)
        note = ""
        if p["gold"] < 0:
            note = (f"\nYour balance is now **{p['gold']} gold** (negative) — "
                    f"that is remaining debt. Earn gold (jobs stay open) until "
                    f"your balance is 0 or more before borrowing again.")
        await interaction.response.send_message(embed=emb(
            "🏰 Guild Loan Repaid!",
            f"Loan #{loan_id} is closed." + note,
            color=COLOR_SOCIAL))

    @guildloan.command(name="list", description="List your guild loans (leaders also see pending requests)")
    async def guildloan_list(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        lines = []
        rows = conn.execute(
            "SELECT * FROM guild_loans WHERE borrower_id = ? AND status IN "
            "('pending', 'active') ORDER BY id", (p["user_id"],)).fetchall()
        for r in rows:
            parts = []
            if r["gold_principal"] > 0:
                parts.append(f"{r['gold_principal']} gold (repay {r['gold_total_due']})")
            if r["item_id"]:
                parts.append(f"{disp.item(r['item_id'])} x{r['item_qty']}")
            lines.append(f"ID {r['id']}: {' + '.join(parts)} — {r['status']} (guild {_guild_name(conn, r['guild_id'])})")
        if p["guild_id"]:
            guild = db.get_guild(conn, p["guild_id"])
            if _is_leader(guild, p["user_id"]):
                for r in gb.get_active_guild_loans_for_guild(conn, p["guild_id"]):
                    if r["borrower_id"] == p["user_id"]:
                        continue
                    parts = []
                    if r["gold_principal"] > 0:
                        parts.append(f"{r['gold_principal']} gold (repay {r['gold_total_due']})")
                    if r["item_id"]:
                        parts.append(f"{disp.item(r['item_id'])} x{r['item_qty']}")
                    lines.append(f"ID {r['id']}: {_name(conn, r['borrower_id'])} requests {' + '.join(parts)} — {r['status']} (approve with `/guildloan approve {r['id']}`)")
        if not lines:
            lines = ["No open guild loans. Request one with `/guildloan request`."]
        await interaction.response.send_message(embed=emb(
            "🏰 Guild Loans", "\n".join(lines), color=COLOR_SOCIAL))

    # ---------------------------------------------------------- personal bank
    bank = app_commands.Group(
        name="bank",
        description="Your personal bank: safe gold with 1% daily interest")

    @bank.command(name="deposit", description="Move carried gold into your personal bank (safe from loss)")
    @app_commands.describe(amount="Gold to deposit")
    async def bank_deposit(self, interaction: discord.Interaction, amount: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if amount <= 0 or p["gold"] < amount:
            await interaction.response.send_message(
                embed=err_embed(f"Deposit between 1 and your carried gold ({p['gold']})."),
                ephemeral=True)
            return
        balance, interest = gb.accrue_bank(conn, p["user_id"])
        balance += amount
        conn.execute("UPDATE personal_bank SET balance = ? WHERE user_id = ?",
                     (balance, p["user_id"]))
        conn.commit()
        p["gold"] -= amount
        db.save_player(conn, p)
        note = f" (+{interest} gold interest accrued)" if interest else ""
        await interaction.response.send_message(embed=emb(
            "🏦 Personal Bank",
            f"Deposited **{amount} gold**{note}. Bank balance: **{balance} gold**. "
            f"Banked gold is safe from defeat loss and PvP steals — withdraw "
            f"with `/bank withdraw` before spending.",
            color=COLOR_ECONOMY))

    @bank.command(name="withdraw", description="Move gold from your personal bank back to carried gold")
    @app_commands.describe(amount="Gold to withdraw")
    async def bank_withdraw(self, interaction: discord.Interaction, amount: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        balance, interest = gb.accrue_bank(conn, p["user_id"])
        if amount <= 0 or balance < amount:
            await interaction.response.send_message(
                embed=err_embed(f"Withdraw between 1 and your bank balance ({balance})."),
                ephemeral=True)
            return
        balance -= amount
        conn.execute("UPDATE personal_bank SET balance = ? WHERE user_id = ?",
                     (balance, p["user_id"]))
        conn.commit()
        p["gold"] += amount
        db.save_player(conn, p)
        note = f" (+{interest} gold interest accrued)" if interest else ""
        await interaction.response.send_message(embed=emb(
            "🏦 Personal Bank",
            f"Withdrew **{amount} gold**{note}. Bank balance: **{balance} gold**. "
            f"Carried gold: **{p['gold']}**.",
            color=COLOR_ECONOMY))

    @bank.command(name="balance", description="Show your personal bank balance and accrued interest")
    async def bank_balance(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        balance, interest = gb.accrue_bank(conn, p["user_id"])
        note = f"\nInterest just accrued: **+{interest} gold** (1% per whole day)." if interest else ""
        await interaction.response.send_message(embed=emb(
            "🏦 Personal Bank",
            f"Bank balance: **{balance} gold**\nCarried gold: **{p['gold']}**\n"
            f"Interest: 1% per whole day on banked gold, added automatically."
            f"{note}\nBanked gold is safe from defeat loss and PvP steals.",
            color=COLOR_ECONOMY))

    # ---------------------------------------------------------- marketplace
    guildmarket = app_commands.Group(
        name="guildmarket",
        description="Buy and sell guild-bank items (10% tax funds bot giveaways)")

    @guildmarket.command(name="list", description="List a guild-bank item for sale (leader-only)")
    @app_commands.describe(item="Item name", qty="Amount to list", price="Total sale price in gold")
    async def guildmarket_list(self, interaction: discord.Interaction,
                               item: str, qty: int, price: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You're not in a guild."), ephemeral=True)
            return
        guild = db.get_guild(conn, p["guild_id"])
        if not _is_leader(guild, p["user_id"]):
            await interaction.response.send_message(
                embed=err_embed("Only the guild leader can list guild-bank items."),
                ephemeral=True)
            return
        item_id = disp.resolve_item(item) or item.lower()
        if qty <= 0 or price <= 0 or not gb.take_bank_item(conn, p["guild_id"], item_id, qty):
            await interaction.response.send_message(
                embed=err_embed(f"The guild bank doesn't hold {qty}x {disp.item(item_id)} (or price must be > 0)."),
                ephemeral=True)
            return
        lid = gb.create_listing(conn, p["guild_id"], item_id, qty, price)
        tax, gets = gb.market_split(price)
        await interaction.response.send_message(embed=emb(
            "🛒 Guild Market Listing",
            f"Listed **{disp.item(item_id)} x{qty}** for **{price} gold** (ID {lid}). "
            f"On sale: the guild bank gets **{gets} gold**, the bot tax pool "
            f"gets **{tax} gold** (10%). Anyone — member or outsider — may buy "
            f"with `/guildmarket buy {lid}`.",
            color=COLOR_ECONOMY))

    @guildmarket.command(name="listings", description="Browse open guild market listings")
    async def guildmarket_listings(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        rows = gb.open_listings(conn)
        if not rows:
            await interaction.response.send_message(embed=emb(
                "🛒 Guild Market", "No open listings right now.",
                color=COLOR_ECONOMY))
            return
        lines = [f"ID {r['id']}: **{disp.item(r['item_id'])} x{r['qty']}** — {r['price']} gold (guild {_guild_name(conn, r['guild_id'])})"
                 for r in rows]
        await interaction.response.send_message(embed=emb(
            "🛒 Guild Market Listings", "\n".join(lines), color=COLOR_ECONOMY))

    @guildmarket.command(name="buy", description="Buy an open guild market listing (any registered player)")
    @app_commands.describe(listing_id="Listing ID from /guildmarket listings")
    async def guildmarket_buy(self, interaction: discord.Interaction, listing_id: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        listing = gb.get_listing(conn, listing_id)
        if listing is None or listing["status"] != "open":
            await interaction.response.send_message(
                embed=err_embed("That listing is not open anymore."),
                ephemeral=True)
            return
        if p["gold"] < listing["price"]:
            await interaction.response.send_message(
                embed=err_embed(f"You need {listing['price']} gold, you carry {p['gold']}."),
                ephemeral=True)
            return
        tax, gets = gb.market_split(listing["price"])
        p["gold"] -= listing["price"]
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], listing["item_id"], listing["qty"])
        gb.add_bank_gold(conn, listing["guild_id"], gets)
        gb.add_tax(conn, tax)
        gb.record_tax(conn, p["user_id"], p["guild_id"], listing["guild_id"],
                      listing["item_id"], listing["qty"], listing["price"], tax)
        gb.set_listing_status(conn, listing_id, "sold")
        await interaction.response.send_message(embed=emb(
            "🛒 Guild Market Purchase",
            f"You bought **{disp.item(listing['item_id'])} x{listing['qty']}** for "
            f"**{listing['price']} gold** from guild **{_guild_name(conn, listing['guild_id'])}**. "
            f"Tax **{tax} gold** (10%) went to the bot tax pool; the guild bank "
            f"received **{gets} gold**.",
            color=COLOR_ECONOMY))

    @guildmarket.command(name="cancel", description="Cancel your guild's listing and return stock to the bank (leader-only)")
    @app_commands.describe(listing_id="Listing ID from /guildmarket listings")
    async def guildmarket_cancel(self, interaction: discord.Interaction, listing_id: int):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        listing = gb.get_listing(conn, listing_id)
        if listing is None or listing["status"] != "open" or listing["guild_id"] != p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("No open listing with that ID in your guild."),
                ephemeral=True)
            return
        guild = db.get_guild(conn, p["guild_id"])
        if not _is_leader(guild, p["user_id"]):
            await interaction.response.send_message(
                embed=err_embed("Only the guild leader can cancel listings."),
                ephemeral=True)
            return
        gb.add_bank_item(conn, listing["guild_id"], listing["item_id"], listing["qty"])
        gb.set_listing_status(conn, listing_id, "cancelled")
        await interaction.response.send_message(embed=emb(
            "🛒 Guild Market Listing Cancelled",
            f"**{disp.item(listing['item_id'])} x{listing['qty']}** returned to the guild bank.",
            color=COLOR_ECONOMY))

    # ---------------------------------------------------------- taxboard
    @app_commands.command(name="taxboard", description="Top taxpayers and donors, per player and per guild")
    async def taxboard(self, interaction: discord.Interaction):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        tp = gb.top_tax_players(conn)
        tg = gb.top_tax_guilds(conn)
        dp = gb.top_depositors(conn)
        dg = gb.top_depositor_guilds(conn)
        def fmt(rows, namer):
            return "\n".join(f"{i}. **{namer(uid)}** — {total} gold"
                             for i, (uid, total) in enumerate(rows, 1)) or "(none yet)"
        await interaction.response.send_message(embed=emb(
            "📊 Tax & Donation Leaderboards",
            "💸 Top taxpayers (players):\n" + fmt(tp, lambda u: _name(conn, u)) + "\n\n"
            "🏰 Top taxpayer guilds:\n" + fmt(tg, lambda g: _guild_name(conn, g)) + "\n\n"
            "🤝 Top gold depositors (players):\n" + fmt(dp, lambda u: _name(conn, u)) + "\n\n"
            "🏰 Top gold depositor guilds:\n" + fmt(dg, lambda g: _guild_name(conn, g)) + "\n\n"
            "Tax = 10% of every guild market sale, paid into the bot tax pool. "
            "Depositor ranks count gold deposits only (items/pets are tracked in /guildbank info).",
            color=COLOR_ECONOMY))


async def setup(bot):
    await bot.add_cog(GuildBank(bot))
