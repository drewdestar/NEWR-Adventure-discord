# -*- coding: utf-8 -*-
"""Cog /linkcode: issue a Telegram link code from Discord.

Players used to have no way to get a link code from Discord itself:
codes were issued out-of-band by the assistant, and the Telegram
bot's /start text misleadingly said the code was "shown in Discord".
This command closes that gap: a registered player runs /linkcode here
and gets a single-use code (DM-only, so only they see it) to redeem
with /link <code> at @NEWRAdventureBot on Telegram.

DM-ONLY by design (user decision 2026-11-05): the code is sensitive,
so /linkcode refuses in any server channel and only works in a DM
with the bot. Inside a DM there is no ephemeral flag at all: a DM is
already private to the player, so no extra hiding is needed.

Rules, mirroring the Telegram bot's redeem checks (tgdb.py):
- Used outside a DM -> refuse, tell the player to DM the bot.
- No character yet -> refuse, tell the player to /register first.
- Discord account already linked to a Telegram account -> refuse and
  tell them to /unlink on Telegram first if they want to move.
- An existing unused code younger than 24h is re-shown instead of
  minting a duplicate.
- Otherwise mint NEWR-XXXXXXXX (secrets, 8 uppercase alphanumerics),
  single-use, 24h expiry, stored in the shared link_codes table.
  The link itself is created by the Telegram bot on redeem; this
  command never writes telegram_links.
"""

import secrets
import string
import time

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import i18n
from .common import emb, err_embed, get_conn

_ALPHABET = string.ascii_uppercase + string.digits
_CODE_TTL = 24 * 60 * 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_links (
    telegram_id INTEGER PRIMARY KEY,
    discord_id INTEGER NOT NULL UNIQUE,
    linked_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS link_codes (
    code TEXT PRIMARY KEY,
    discord_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);
"""


def issue_link_code(conn, discord_id):
    """Return (code, reused_bool) for a Discord user, or None if linked."""
    conn.executescript(_SCHEMA)
    row = conn.execute(
        "SELECT telegram_id FROM telegram_links WHERE discord_id = ?",
        (int(discord_id),)).fetchone()
    if row is not None:
        return None
    now = int(time.time())
    row = conn.execute(
        "SELECT code FROM link_codes WHERE discord_id = ? AND used = 0"
        " AND created_at > ? ORDER BY created_at DESC LIMIT 1",
        (int(discord_id), now - _CODE_TTL)).fetchone()
    if row is not None:
        return row[0], True
    for _ in range(10):
        code = "NEWR-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        try:
            conn.execute(
                "INSERT INTO link_codes (code, discord_id, created_at, used)"
                " VALUES (?, ?, ?, 0)",
                (code, int(discord_id), now))
            conn.commit()
            return code, False
        except Exception:
            continue
    raise RuntimeError("could not generate a unique link code")


class LinkCode(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Instant code delivery (2026-11-05, user: "satset, kirim langsung"):
    # global slash commands can take up to ~1 hour to appear in DMs, and
    # that wait is unacceptable for something that works like an auth
    # code. So a DM text trigger bypasses sync entirely: DM content is
    # a Discord exception and reaches the bot even without the
    # privileged message-content intent (dm_messages is on by default).
    # DM the bot "link" (or "code"/"linkcode") and it replies instantly
    # with the same code + deep link as /linkcode. Server messages are
    # still ignored: the bot stays slash-only in servers, and the code
    # itself is only ever sent in a private DM.
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is not None:
            return
        if message.content.strip().lower() not in (
                "link", "code", "linkcode", "/linkcode", "kode"):
            return
        conn = get_conn()
        i18n.set_ctx_for_user(message.author.id, conn)
        player = db.get_player(conn, message.author.id)
        if player is None:
            await message.channel.send(
                "You don't have a character yet! "
                "Register first with `/register` in NEWR LABS.")
            return
        result = issue_link_code(conn, message.author.id)
        if result is None:
            await message.channel.send(
                "Your Discord character is already linked to Telegram. "
                "If you want to link a different Telegram account, "
                "send /unlink to @NEWRAdventureBot first, then DM me "
                "\"link\" again.")
            return
        code, reused = result
        head = ("You already have a link code that is still valid."
                if reused else "Your Telegram link code is:")
        await message.channel.send(
            f"{head}\n"
            f"Tap this link to link automatically:\n"
            f"https://t.me/NEWRAdventureBot?start={code}\n"
            f"Or copy the code below (tap the copy icon on the code "
            f"block) and send it to @NEWRAdventureBot on Telegram:\n"
            f"```\n{code}\n```\n"
            f"Or send `/link {code}` in Telegram.\n"
            f"It is single-use and expires in 24 hours. "
            f"Do not share it with anyone else.")

    @app_commands.command(
        name="linkcode",
        description="Get a code to link your Discord character to Telegram")
    async def linkcode(self, interaction: discord.Interaction):
        conn = get_conn()
        i18n.set_ctx(interaction, conn)
        if interaction.guild is not None:
            await interaction.response.send_message(
                embed=err_embed(
                    "This command only works in a DM with me, because the "
                    "code is sensitive. DM me and run /linkcode there."),
                ephemeral=True)
            return
        player = db.get_player(conn, interaction.user.id)
        if player is None:
            await interaction.response.send_message(
                embed=err_embed(
                    "You don't have a character yet! "
                    "Register first with `/register`."))
            return
        result = issue_link_code(conn, interaction.user.id)
        if result is None:
            await interaction.response.send_message(
                embed=err_embed(
                    "Your Discord character is already linked to Telegram. "
                    "If you want to link a different Telegram account, "
                    "send /unlink to @NEWRAdventureBot first, then run "
                    "/linkcode again."))
            return
        code, reused = result
        # Tap-to-copy + tap-to-link (2026-11-05): the code sits in its
        # own code block, which Discord renders with a copy icon, so
        # tapping it copies just the code. Discord has no clipboard
        # button component, so the deep link below is the real
        # one-tap path: tapping it opens Telegram and /start redeems
        # the code automatically (see the Telegram bot's cmd_start).
        if reused:
            desc = i18n.t_fmt(
                "You already have a link code that is still valid.\n"
                "Tap this link to link automatically:\n"
                "https://t.me/NEWRAdventureBot?start={code}\n"
                "Or copy the code below (tap the copy icon on the code "
                "block) and send it to @NEWRAdventureBot on Telegram:\n"
                "```\n{code}\n```\n"
                "Or send `/link {code}` in Telegram.\n"
                "It is single-use and expires 24 hours after it was issued.",
                code=code)
        else:
            desc = i18n.t_fmt(
                "Your Telegram link code is:\n"
                "Tap this link to link automatically:\n"
                "https://t.me/NEWRAdventureBot?start={code}\n"
                "Or copy the code below (tap the copy icon on the code "
                "block) and send it to @NEWRAdventureBot on Telegram:\n"
                "```\n{code}\n```\n"
                "Or send `/link {code}` in Telegram.\n"
                "It is single-use and expires in 24 hours. "
                "Do not share it with anyone else.",
                code=code)
        await interaction.response.send_message(
            embed=emb(i18n.t("🔗 Telegram link code"), desc))


async def setup(bot):
    await bot.add_cog(LinkCode(bot))
