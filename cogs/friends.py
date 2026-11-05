# -*- coding: utf-8 -*-
"""Cog friends: friend list, transfers, borrows, boss & guild invites.

All friendships and agreements are two-party: nothing moves until the
other side explicitly accepts. Notifications go to the other user via DM
(best-effort: if DMs are closed, the requester gets an ephemeral warning).

No interest is ever charged automatically and nothing is ever seized:
borrowed items are returned with /borrow return. Friend-to-friend gold
loans (/loan) were removed in phase 2 — loans now come from the guild
bank (/guildloan) or the bot (/botloan); historical /loan rows stay in
the database untouched.
"""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import friends_db
from .common import (COLOR_BATTLE, COLOR_ECONOMY, COLOR_SOCIAL, emb,
                     err_embed, get_conn, need_player)


def _conn():
    conn = get_conn()
    friends_db.ensure_tables(conn)
    return conn


def _name(conn, user_id):
    p = db.get_player(conn, user_id)
    return p["name"] if p else f"User {user_id}"


class Friends(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------------------------------------------------ DM
    async def _dm(self, user_id, embed):
        """Send a DM embed. Returns True on success, False if undeliverable."""
        try:
            user = await self.bot.fetch_user(user_id)
            await user.send(embed=embed)
            return True
        except Exception:
            return False

    async def _warn_dm_failed(self, interaction):
        try:
            await interaction.followup.send(
                embed=err_embed(
                    "Note: I could not DM them (their DMs may be closed). "
                    "Ask them to check the command directly."),
                ephemeral=True)
        except Exception:
            pass

    async def _target_player(self, interaction, target):
        """Validate a player target: not self, not a bot, registered."""
        if target.id == interaction.user.id:
            await interaction.response.send_message(
                embed=err_embed("You cannot pick yourself."), ephemeral=True)
            return None
        if target.bot:
            await interaction.response.send_message(
                embed=err_embed("Bots cannot be friends or trade partners."),
                ephemeral=True)
            return None
        conn = _conn()
        t = db.get_player(conn, target.id)
        if not t:
            await interaction.response.send_message(
                embed=err_embed("That player hasn't registered a character yet."),
                ephemeral=True)
            return None
        return t

    # -------------------------------------------------------------- /friend
    @app_commands.command(name="friend", description="Add, accept, decline, remove, or list friends")
    @app_commands.describe(aksi="add/accept/decline/remove/list",
                           target="Player: mention or user ID (not needed for list)")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="add", value="add"),
        app_commands.Choice(name="accept", value="accept"),
        app_commands.Choice(name="decline", value="decline"),
        app_commands.Choice(name="remove", value="remove"),
        app_commands.Choice(name="list", value="list"),
    ])
    async def friend(self, interaction: discord.Interaction, aksi: str,
                     target: discord.User = None):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        me = interaction.user.id

        if aksi == "list":
            ids = friends_db.friend_ids(conn, me)
            if not ids:
                await interaction.response.send_message(embed=emb(
                    "👥 Friends",
                    "You have no friends yet. Add one with `/friend add @player`.",
                    color=COLOR_SOCIAL))
                return
            lines = []
            for fid in ids:
                fp = db.get_player(conn, fid)
                lines.append(f"• **{fp['name']}** (Lv {fp['level']})" if fp
                             else f"• User {fid}")
            await interaction.response.send_message(embed=emb(
                "👥 Friends", "\n".join(lines), color=COLOR_SOCIAL))
            return

        if target is None:
            await interaction.response.send_message(
                embed=err_embed("Pick a player for this action."), ephemeral=True)
            return
        t = await self._target_player(interaction, target)
        if not t:
            return

        if aksi == "add":
            if friends_db.is_friend(conn, me, target.id):
                await interaction.response.send_message(
                    embed=err_embed("You are already friends."), ephemeral=True)
                return
            if friends_db.pending_friend_request(conn, me, target.id):
                await interaction.response.send_message(
                    embed=err_embed("There is already a pending friend request between you two."),
                    ephemeral=True)
                return
            conn.execute(
                "INSERT INTO friend_requests (from_id, to_id, created_at) "
                "VALUES (?, ?, ?)", (me, target.id, friends_db.now()))
            conn.commit()
            sent = await self._dm(target.id, emb(
                "👥 Friend Request!",
                f"**{p['name']}** wants to be your friend!\n"
                f"Accept with `/friend accept @{interaction.user.name}` "
                f"or decline with `/friend decline @{interaction.user.name}`.",
                color=COLOR_SOCIAL))
            await interaction.response.send_message(embed=emb(
                "👥 Friend Request Sent",
                f"Request sent to **{t['name']}**. They need to accept before "
                f"you become friends.", color=COLOR_SOCIAL))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if aksi == "accept":
            req = conn.execute(
                "SELECT * FROM friend_requests WHERE status = 'pending' AND "
                "from_id = ? AND to_id = ? ORDER BY id DESC LIMIT 1",
                (target.id, me)).fetchone()
            if not req:
                await interaction.response.send_message(
                    embed=err_embed("No pending friend request from that player."),
                    ephemeral=True)
                return
            conn.execute(
                "UPDATE friend_requests SET status = 'accepted' WHERE id = ?",
                (req["id"],))
            conn.commit()
            friends_db.add_friendship(conn, me, target.id)
            sent = await self._dm(target.id, emb(
                "👥 Friend Request Accepted!",
                f"**{p['name']}** accepted your friend request. You are now friends!",
                color=COLOR_SOCIAL))
            await interaction.response.send_message(embed=emb(
                "👥 Friends!",
                f"You and **{t['name']}** are now friends. You can invite each "
                f"other to bosses, transfer gold/items, lend, and borrow.",
                color=COLOR_SOCIAL))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if aksi == "decline":
            req = conn.execute(
                "SELECT * FROM friend_requests WHERE status = 'pending' AND "
                "from_id = ? AND to_id = ? ORDER BY id DESC LIMIT 1",
                (target.id, me)).fetchone()
            if not req:
                await interaction.response.send_message(
                    embed=err_embed("No pending friend request from that player."),
                    ephemeral=True)
                return
            conn.execute(
                "UPDATE friend_requests SET status = 'declined' WHERE id = ?",
                (req["id"],))
            conn.commit()
            sent = await self._dm(target.id, emb(
                "👥 Friend Request Declined",
                f"**{p['name']}** declined your friend request.",
                color=COLOR_SOCIAL))
            await interaction.response.send_message(embed=emb(
                "👥 Friend Request Declined",
                f"You declined **{t['name']}**'s friend request.",
                color=COLOR_SOCIAL))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if aksi == "remove":
            if not friends_db.is_friend(conn, me, target.id):
                await interaction.response.send_message(
                    embed=err_embed("You are not friends with that player."),
                    ephemeral=True)
                return
            friends_db.remove_friendship(conn, me, target.id)
            sent = await self._dm(target.id, emb(
                "👥 Friend Removed",
                f"**{p['name']}** removed you from their friend list.",
                color=COLOR_SOCIAL))
            await interaction.response.send_message(embed=emb(
                "👥 Friend Removed",
                f"**{t['name']}** is no longer on your friend list.",
                color=COLOR_SOCIAL))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

    # ------------------------------------------------------------ /transfer
    @app_commands.command(name="transfer", description="Send gold and/or items to a friend (instant gift)")
    @app_commands.describe(target="Friend to send to: mention or user ID", gold="Gold to send (0 = none)",
                           item="Item name to send (empty = none)", qty="Item quantity")
    async def transfer(self, interaction: discord.Interaction,
                       target: discord.User, gold: int = 0,
                       item: str = "", qty: int = 0):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        t = await self._target_player(interaction, target)
        if not t:
            return
        if not friends_db.is_friend(conn, p["user_id"], target.id):
            await interaction.response.send_message(
                embed=err_embed("You can only transfer to a friend. Add them with `/friend add` first."),
                ephemeral=True)
            return
        gold = max(0, gold)
        qty = max(0, qty)
        item = item.strip()
        if gold <= 0 and (not item or qty <= 0):
            await interaction.response.send_message(
                embed=err_embed("Send some gold, an item, or both."),
                ephemeral=True)
            return
        if gold > 0 and p["gold"] < gold:
            await interaction.response.send_message(
                embed=err_embed(f"Not enough gold! You have {p['gold']} gold."),
                ephemeral=True)
            return
        if item and db.item_qty(conn, p["user_id"], item) < qty:
            await interaction.response.send_message(
                embed=err_embed(f"You don't have {qty}x {item}."), ephemeral=True)
            return
        if gold > 0:
            p["gold"] -= gold
            db.save_player(conn, p)
            t = db.get_player(conn, target.id)
            t["gold"] += gold
            db.save_player(conn, t)
        if item:
            if not db.remove_item(conn, p["user_id"], item, qty):
                await interaction.response.send_message(
                    embed=err_embed(f"Could not move {qty}x {item}."), ephemeral=True)
                return
            db.add_item(conn, target.id, item, qty)
        conn.execute(
            "INSERT INTO transfers_log (from_id, to_id, gold, item_id, qty, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (p["user_id"], target.id, gold, item or None, qty, friends_db.now()))
        conn.commit()
        parts = []
        if gold > 0:
            parts.append(f"**{gold} gold**")
        if item:
            parts.append(f"**{item} x{qty}**")
        sent = await self._dm(target.id, emb(
            "🎁 You Received a Transfer!",
            f"**{p['name']}** sent you {' + '.join(parts)}!",
            color=COLOR_ECONOMY))
        await interaction.response.send_message(embed=emb(
            "🎁 Transfer Sent",
            f"You sent {' + '.join(parts)} to **{t['name']}**.",
            color=COLOR_ECONOMY))
        if not sent:
            await self._warn_dm_failed(interaction)

    # --------------------------------------------------------------- /borrow
    @app_commands.command(name="borrow", description="Borrow an item from a friend (owner sets an optional fee)")
    @app_commands.describe(aksi="request/approve/return/list",
                           target="Friend who owns the item: mention or user ID (for request)",
                           item="Item name (for request)",
                           qty="Quantity (for request)",
                           borrow_id="Borrow ID from /borrow list (for approve/return)",
                           fee="Gold fee set by the owner, 0 = free (for approve)")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="request", value="request"),
        app_commands.Choice(name="approve", value="approve"),
        app_commands.Choice(name="return", value="return"),
        app_commands.Choice(name="list", value="list"),
    ])
    async def borrow(self, interaction: discord.Interaction, aksi: str,
                     target: discord.User = None, item: str = "",
                     qty: int = 1, borrow_id: int = 0, fee: int = 0):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        me = p["user_id"]

        if aksi == "list":
            rows = conn.execute(
                "SELECT * FROM borrows WHERE (owner_id = ? OR borrower_id = ?) "
                "AND status IN ('requested', 'approved') ORDER BY id",
                (me, me)).fetchall()
            if not rows:
                await interaction.response.send_message(embed=emb(
                    "📦 Borrowed Items",
                    "No open borrows. Request one with `/borrow request @friend <item> <qty>`.",
                    color=COLOR_ECONOMY))
                return
            lines = []
            for r in rows:
                if r["owner_id"] == me:
                    lines.append(f"ID {r['id']}: **{_name(conn, r['borrower_id'])}** "
                                 f"borrows **{r['item_id']} x{r['qty']}** from you "
                                 f"(fee {r['fee']} gold) — {r['status']}")
                else:
                    lines.append(f"ID {r['id']}: you borrow **{r['item_id']} x{r['qty']}** "
                                 f"from **{_name(conn, r['owner_id'])}** "
                                 f"(fee {r['fee']} gold) — {r['status']}")
            await interaction.response.send_message(embed=emb(
                "📦 Borrowed Items", "\n".join(lines), color=COLOR_ECONOMY))
            return

        if aksi == "request":
            if target is None or not item.strip():
                await interaction.response.send_message(
                    embed=err_embed("Pick the friend and the item you want to borrow."),
                    ephemeral=True)
                return
            t = await self._target_player(interaction, target)
            if not t:
                return
            if not friends_db.is_friend(conn, me, target.id):
                await interaction.response.send_message(
                    embed=err_embed("You can only borrow from a friend."),
                    ephemeral=True)
                return
            item = item.strip()
            qty = max(1, qty)
            if db.item_qty(conn, target.id, item) < qty:
                await interaction.response.send_message(
                    embed=err_embed(f"**{t['name']}** doesn't have {qty}x {item}."),
                    ephemeral=True)
                return
            cur = conn.execute(
                "INSERT INTO borrows (owner_id, borrower_id, item_id, qty, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (target.id, me, item, qty, friends_db.now()))
            bid = cur.lastrowid
            conn.commit()
            sent = await self._dm(target.id, emb(
                "📦 Borrow Request!",
                f"**{p['name']}** wants to borrow **{item} x{qty}** from you.\n"
                f"Approve with `/borrow approve {bid} [fee]` (fee 0 = free) — "
                f"nothing moves until you approve.",
                color=COLOR_ECONOMY))
            await interaction.response.send_message(embed=emb(
                "📦 Borrow Request Sent",
                f"Asked **{t['name']}** for **{item} x{qty}** (ID {bid}). "
                f"Nothing moves until they approve.",
                color=COLOR_ECONOMY))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if aksi == "approve":
            row = conn.execute(
                "SELECT * FROM borrows WHERE id = ?", (borrow_id,)).fetchone()
            if not row or row["status"] != "requested" or row["owner_id"] != me:
                await interaction.response.send_message(
                    embed=err_embed("No open borrow request with that ID for you."),
                    ephemeral=True)
                return
            fee = max(0, fee)
            borrower = db.get_player(conn, row["borrower_id"])
            if not borrower:
                await interaction.response.send_message(
                    embed=err_embed("The borrower no longer exists."),
                    ephemeral=True)
                return
            if borrower["gold"] < fee:
                await interaction.response.send_message(
                    embed=err_embed(f"The borrower needs {fee} gold for the fee."),
                    ephemeral=True)
                return
            if db.item_qty(conn, me, row["item_id"]) < row["qty"]:
                await interaction.response.send_message(
                    embed=err_embed(f"You no longer have {row['qty']}x {row['item_id']}."),
                    ephemeral=True)
                return
            if fee > 0:
                borrower["gold"] -= fee
                db.save_player(conn, borrower)
                p = db.get_player(conn, me)
                p["gold"] += fee
                db.save_player(conn, p)
            if not db.remove_item(conn, me, row["item_id"], row["qty"]):
                await interaction.response.send_message(
                    embed=err_embed("Could not move the item."), ephemeral=True)
                return
            db.add_item(conn, row["borrower_id"], row["item_id"], row["qty"])
            conn.execute(
                "UPDATE borrows SET status = 'approved', fee = ? WHERE id = ?",
                (fee, borrow_id))
            conn.commit()
            sent = await self._dm(row["borrower_id"], emb(
                "📦 Borrow Approved!",
                f"**{p['name']}** lent you **{row['item_id']} x{row['qty']}**"
                + (f" for a fee of **{fee} gold**." if fee else " for free.")
                + f"\nReturn it with `/borrow return {borrow_id}`.",
                color=COLOR_ECONOMY))
            await interaction.response.send_message(embed=emb(
                "📦 Borrow Approved!",
                f"You lent **{row['item_id']} x{row['qty']}** to "
                f"**{_name(conn, row['borrower_id'])}**"
                + (f" for **{fee} gold**." if fee else " for free."),
                color=COLOR_ECONOMY))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if aksi == "return":
            row = conn.execute(
                "SELECT * FROM borrows WHERE id = ?", (borrow_id,)).fetchone()
            if not row or row["status"] != "approved" or row["borrower_id"] != me:
                await interaction.response.send_message(
                    embed=err_embed("No borrowed item with that ID for you."),
                    ephemeral=True)
                return
            if db.item_qty(conn, me, row["item_id"]) < row["qty"]:
                await interaction.response.send_message(
                    embed=err_embed(
                        f"You no longer have {row['qty']}x {row['item_id']} to return. "
                        f"Get it back first — the record stays open."),
                    ephemeral=True)
                return
            if not db.remove_item(conn, me, row["item_id"], row["qty"]):
                await interaction.response.send_message(
                    embed=err_embed("Could not move the item."), ephemeral=True)
                return
            db.add_item(conn, row["owner_id"], row["item_id"], row["qty"])
            conn.execute("UPDATE borrows SET status = 'returned' WHERE id = ?",
                         (borrow_id,))
            conn.commit()
            sent = await self._dm(row["owner_id"], emb(
                "📦 Item Returned!",
                f"**{p['name']}** returned your **{row['item_id']} x{row['qty']}**.",
                color=COLOR_ECONOMY))
            await interaction.response.send_message(embed=emb(
                "📦 Item Returned!",
                f"You returned **{row['item_id']} x{row['qty']}** to "
                f"**{_name(conn, row['owner_id'])}**.",
                color=COLOR_ECONOMY))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

    # ------------------------------------------------------------ /bossinvite
    @app_commands.command(name="bossinvite", description="Invite a friend to join an active boss raid")
    @app_commands.describe(aksi="invite/accept/decline",
                           target="Friend: mention or user ID (for invite) or who invited you (for accept/decline)")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="invite", value="invite"),
        app_commands.Choice(name="accept", value="accept"),
        app_commands.Choice(name="decline", value="decline"),
    ])
    async def bossinvite(self, interaction: discord.Interaction, aksi: str,
                         target: discord.User = None):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        me = p["user_id"]

        if aksi == "invite":
            if target is None:
                await interaction.response.send_message(
                    embed=err_embed("Pick the friend to invite."), ephemeral=True)
                return
            t = await self._target_player(interaction, target)
            if not t:
                return
            if not friends_db.is_friend(conn, me, target.id):
                await interaction.response.send_message(
                    embed=err_embed("You can only invite a friend to a boss fight."),
                    ephemeral=True)
                return
            raid = db.active_raid(conn)
            if not raid:
                await interaction.response.send_message(
                    embed=err_embed("No active boss raid right now. Start one with `/raid start`."),
                    ephemeral=True)
                return
            cur = conn.execute(
                "INSERT INTO boss_invites (inviter_id, invitee_id, raid_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (me, target.id, raid["id"], friends_db.now()))
            conn.commit()
            sent = await self._dm(target.id, emb(
                "🐉 Boss Raid Invite!",
                f"**{p['name']}** invites you to fight **{raid['boss']}**!\n"
                f"Accept with `/bossinvite accept @{interaction.user.name}` "
                f"to join the raid.",
                color=COLOR_BATTLE))
            await interaction.response.send_message(embed=emb(
                "🐉 Boss Invite Sent",
                f"Invited **{t['name']}** to the **{raid['boss']}** raid.",
                color=COLOR_BATTLE))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if target is None:
            await interaction.response.send_message(
                embed=err_embed("Pick the player who invited you."), ephemeral=True)
            return
        inv = conn.execute(
            "SELECT * FROM boss_invites WHERE status = 'pending' AND "
            "inviter_id = ? AND invitee_id = ? ORDER BY id DESC LIMIT 1",
            (target.id, me)).fetchone()
        if not inv:
            await interaction.response.send_message(
                embed=err_embed("No pending boss invite from that player."),
                ephemeral=True)
            return
        if aksi == "decline":
            conn.execute("UPDATE boss_invites SET status = 'declined' WHERE id = ?",
                         (inv["id"],))
            conn.commit()
            sent = await self._dm(target.id, emb(
                "🐉 Boss Invite Declined",
                f"**{p['name']}** declined your boss raid invite.",
                color=COLOR_BATTLE))
            await interaction.response.send_message(embed=emb(
                "🐉 Boss Invite Declined",
                "You declined the boss raid invite.", color=COLOR_BATTLE))
            if not sent:
                await self._warn_dm_failed(interaction)
            return
        # accept
        raid = conn.execute(
            "SELECT * FROM raids WHERE id = ?", (inv["raid_id"],)).fetchone()
        if not raid or raid["state"] != "active":
            conn.execute("UPDATE boss_invites SET status = 'declined' WHERE id = ?",
                         (inv["id"],))
            conn.commit()
            await interaction.response.send_message(
                embed=err_embed("That raid is no longer active."),
                ephemeral=True)
            return
        conn.execute(
            "INSERT OR IGNORE INTO raid_members (raid_id, user_id, damage) "
            "VALUES (?, ?, 0)", (raid["id"], me))
        conn.execute("UPDATE boss_invites SET status = 'accepted' WHERE id = ?",
                     (inv["id"],))
        conn.commit()
        sent = await self._dm(target.id, emb(
            "🐉 Boss Invite Accepted!",
            f"**{p['name']}** joined your **{raid['boss']}** raid! "
            f"Attack with `/raid hit`.",
            color=COLOR_BATTLE))
        await interaction.response.send_message(embed=emb(
            "🐉 Boss Raid Joined!",
            f"You joined the **{raid['boss']}** raid! Attack with `/raid hit`.",
            color=COLOR_BATTLE))
        if not sent:
            await self._warn_dm_failed(interaction)

    # ----------------------------------------------------------- /guildinvite
    @app_commands.command(name="guildinvite", description="Invite a friend into your guild (leader only)")
    @app_commands.describe(aksi="invite/accept/decline",
                           target="Friend: mention or user ID (for invite) or who invited you (for accept/decline)")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="invite", value="invite"),
        app_commands.Choice(name="accept", value="accept"),
        app_commands.Choice(name="decline", value="decline"),
    ])
    async def guildinvite(self, interaction: discord.Interaction, aksi: str,
                          target: discord.User = None):
        conn = _conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        me = p["user_id"]

        if aksi == "invite":
            if target is None:
                await interaction.response.send_message(
                    embed=err_embed("Pick the friend to invite."), ephemeral=True)
                return
            t = await self._target_player(interaction, target)
            if not t:
                return
            if not p["guild_id"]:
                await interaction.response.send_message(
                    embed=err_embed("You are not in a guild. Create one with `/guild create`."),
                    ephemeral=True)
                return
            guild = db.get_guild(conn, p["guild_id"])
            if not guild or guild["leader_id"] != me:
                await interaction.response.send_message(
                    embed=err_embed("Only the guild leader can invite members."),
                    ephemeral=True)
                return
            if not friends_db.is_friend(conn, me, target.id):
                await interaction.response.send_message(
                    embed=err_embed("You can only invite a friend into your guild."),
                    ephemeral=True)
                return
            conn.execute(
                "INSERT INTO guild_invites (guild_id, inviter_id, invitee_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (guild["id"], me, target.id, friends_db.now()))
            conn.commit()
            sent = await self._dm(target.id, emb(
                "🏰 Guild Invite!",
                f"**{p['name']}** invites you to join the guild **{guild['name']}**!\n"
                f"Accept with `/guildinvite accept @{interaction.user.name}` "
                f"or decline with `/guildinvite decline @{interaction.user.name}`.",
                color=COLOR_SOCIAL))
            await interaction.response.send_message(embed=emb(
                "🏰 Guild Invite Sent",
                f"Invited **{t['name']}** to join **{guild['name']}**.",
                color=COLOR_SOCIAL))
            if not sent:
                await self._warn_dm_failed(interaction)
            return

        if target is None:
            await interaction.response.send_message(
                embed=err_embed("Pick the player who invited you."), ephemeral=True)
            return
        inv = conn.execute(
            "SELECT * FROM guild_invites WHERE status = 'pending' AND "
            "inviter_id = ? AND invitee_id = ? ORDER BY id DESC LIMIT 1",
            (target.id, me)).fetchone()
        if not inv:
            await interaction.response.send_message(
                embed=err_embed("No pending guild invite from that player."),
                ephemeral=True)
            return
        if aksi == "decline":
            conn.execute("UPDATE guild_invites SET status = 'declined' WHERE id = ?",
                         (inv["id"],))
            conn.commit()
            guild = db.get_guild(conn, inv["guild_id"])
            sent = await self._dm(target.id, emb(
                "🏰 Guild Invite Declined",
                f"**{p['name']}** declined the invite to "
                f"**{guild['name'] if guild else 'your guild'}**.",
                color=COLOR_SOCIAL))
            await interaction.response.send_message(embed=emb(
                "🏰 Guild Invite Declined",
                "You declined the guild invite.", color=COLOR_SOCIAL))
            if not sent:
                await self._warn_dm_failed(interaction)
            return
        # accept
        if p["guild_id"]:
            await interaction.response.send_message(
                embed=err_embed("You are already in a guild. Leave it first, then accept."),
                ephemeral=True)
            return
        guild = db.get_guild(conn, inv["guild_id"])
        if not guild:
            await interaction.response.send_message(
                embed=err_embed("That guild no longer exists."), ephemeral=True)
            return
        conn.execute(
            "INSERT OR IGNORE INTO guild_members (guild_id, user_id) VALUES (?, ?)",
            (guild["id"], me))
        p["guild_id"] = guild["id"]
        db.save_player(conn, p)
        conn.execute("UPDATE guild_invites SET status = 'accepted' WHERE id = ?",
                     (inv["id"],))
        conn.commit()
        sent = await self._dm(target.id, emb(
            "🏰 Guild Invite Accepted!",
            f"**{p['name']}** joined your guild **{guild['name']}**!",
            color=COLOR_SOCIAL))
        await interaction.response.send_message(embed=emb(
            "🏰 Welcome to the Guild!",
            f"You joined **{guild['name']}**!",
            color=COLOR_SOCIAL))
        if not sent:
            await self._warn_dm_failed(interaction)


async def setup(bot):
    await bot.add_cog(Friends(bot))
