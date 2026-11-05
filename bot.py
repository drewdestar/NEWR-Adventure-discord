# -*- coding: utf-8 -*-
# NEWR Adventure by NEWR LABS — credit marker, do not remove.
"""NEWR Adventure — Discord bot RPG (slash commands only).

Credit by NEWR LABS. Bot ini sepenuhnya terpisah dari bot NEWR lainnya:
kode, database, dan tokennya sendiri, tidak memakai / mengubah bot lain.

Token dibaca dari environment DISCORD_TOKEN (dimuat dari .env oleh
run-rpg.sh atau dari environment). Kalau token tidak ada, bot berhenti
dengan pesan error yang jelas (bukan crash misterius).
Jangan pernah menulis nilai token ke kode, log, atau README.
"""
import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

BOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BOT_DIR))

import credit_guard  # noqa: E402 — marker-only check, no other code hash

# Muat .env lokal (kalau ada) tanpa mencetak nilainya.
try:
    from dotenv import load_dotenv
    load_dotenv(BOT_DIR / ".env")
except ImportError:
    pass

# Path database bisa di-override lewat env (dipakai test offline).
os.environ.setdefault(
    "RPG_DB_PATH", str(BOT_DIR / "rpg.db"))

from cogs import common  # noqa: E402  (set env dulu sebelum cog memakai DB_PATH)
common.DB_PATH = os.environ["RPG_DB_PATH"]

COGS = [
    "cogs.core",
    "cogs.battle",
    "cogs.economy",
    "cogs.pets",
    "cogs.survival",
    "cogs.social",
    "cogs.premium",
    "cogs.extra",
    "cogs.lang",
    "cogs.friends",
    "cogs.guildpower",
    "cogs.leaderboard",
    "cogs.info",
    "cogs.announce",
    "cogs.botloan",
    "cogs.guildbank",
    "cogs.hospital",
]


def _proxy_kwargs() -> dict:
    """VM egress goes through an HTTP proxy; direct TLS to Discord fails
    here (SSL WRONG_VERSION_NUMBER), while aiohttp with trust_env works.
    discord.py does not read proxy env vars itself, so pass them explicitly.
    Credentials stay in the environment, never in code or logs."""
    from urllib.parse import unquote, urlparse

    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    if not raw:
        return {}
    parsed = urlparse(raw)
    proxy = f"{parsed.scheme}://{parsed.hostname}:{parsed.port or 3128}"
    kwargs: dict = {"proxy": proxy}
    if parsed.username:
        import aiohttp

        kwargs["proxy_auth"] = aiohttp.BasicAuth(
            unquote(parsed.username),
            unquote(parsed.password or ""))
    return kwargs


def main():
    # Credit guard runs FIRST, before any token/network use. It checks
    # credit markers only — any other code change passes it.
    credit_guard.enforce_credit_markers(BOT_DIR)
    token = os.environ.get("DISCORD_TOKEN", "").strip().strip("\"'")
    if not token or token.startswith("<") or "YOUR_" in token or "EXAMPLE" in token:
        print(
            "ERROR: DISCORD_TOKEN tidak ditemukan atau masih placeholder.\n"
            "Salin .env.example menjadi .env, isi DISCORD_TOKEN dengan token bot "
            "Discord yang asli, lalu jalankan lagi via ~/workspace/bots/ops/run-rpg.sh.\n"
            "Token TIDAK BOLEH ditulis di chat, kode, atau file lain selain .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    intents = discord.Intents.default()
    intents.guilds = True
    bot = commands.Bot(command_prefix="!", intents=intents, **_proxy_kwargs())

    @bot.event
    async def on_ready():
        guild_id = os.environ.get("GUILD_ID", "").strip()
        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                print(f"Slash commands disinkron ke guild {guild_id}: {len(synced)} perintah.")
            else:
                synced = await bot.tree.sync()
                print(f"Slash commands disinkron global: {len(synced)} perintah.")
        except Exception as exc:  # sinkron gagal: bot tetap jalan, log saja
            print(f"WARNING: gagal sinkron slash commands: {exc}")
        activity = discord.Game("NEWR Adventure by NEWR LABS | /help")
        await bot.change_presence(activity=activity)
        print(f"Bot login sebagai {bot.user} — NEWR Adventure by NEWR LABS siap!")

    async def load_cogs():
        for name in COGS:
            await bot.load_extension(name)

    @bot.event
    async def setup_hook():
        await load_cogs()

    # NOTE: tidak ada prefix command yang didaftarkan. Semua perintah
    # adalah slash command (app_commands) sesuai permintaan user.
    bot.run(token)


if __name__ == "__main__":
    main()
