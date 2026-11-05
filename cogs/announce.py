# -*- coding: utf-8 -*-
"""Automatic announcements + role reconciler (no command needed).

The announcement loop runs every 2 minutes and posts ONLY on state
changes, deduped across restarts in the announce_state DB table:
- a seasonal event becomes active,
- the meteor shower goes live (21:00 WIB window),
- a raid boss spawns,
- a raid boss is defeated (killing-blow player named),
- a guild war resolves (winner + score, War Champion granted).

The reconcile loop runs every 10 minutes and re-syncs every player's
Discord roles from the database (drift repair + top-10 roles).

Destination is one dedicated channel: ANNOUNCE_CHANNEL_ID wins when set
and reachable, otherwise an existing #adventure-info channel is reused,
otherwise one is created when the bot may manage channels. If none of
that works, announcements stay disabled and a warning is logged (the
bot never posts into a random channel). Announcements ping @everyone:
the channel is dedicated, so members can mute it to opt out.
"""
import json
import logging
import os
import time

import discord
from discord.ext import commands, tasks

import database as db
import display as disp
import logic
import rolesync
from .battle import resolve_war
from .common import COLOR_BATTLE, COLOR_CORE, COLOR_EXTRA, emb, get_conn

log = logging.getLogger("rpg.announce")

CHANNEL_NAME = "adventure-info"


class Announce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self._warned_no_channel = False
        self._guild_id = 0
        try:
            self._guild_id = int(os.environ.get("GUILD_ID", "0") or 0)
        except ValueError:
            self._guild_id = 0

    async def cog_load(self):
        self.announce_loop.start()
        self.reconcile_loop.start()

    async def cog_unload(self):
        self.announce_loop.cancel()
        self.reconcile_loop.cancel()

    # ------------------------------------------------------------ channel
    async def _resolve_channel(self, guild):
        if self.channel is not None:
            if guild.get_channel(self.channel.id) is not None:
                return self.channel
            self.channel = None
        env_id = os.environ.get("ANNOUNCE_CHANNEL_ID", "").strip()
        if env_id:
            try:
                ch = guild.get_channel(int(env_id))
                if ch is None:
                    ch = await self.bot.fetch_channel(int(env_id))
                if isinstance(ch, discord.TextChannel):
                    self.channel = ch
                    return ch
            except (ValueError, discord.NotFound, discord.Forbidden,
                    discord.HTTPException) as exc:
                log.warning("ANNOUNCE_CHANNEL_ID unusable: %s", exc)
        for ch in guild.text_channels:
            if ch.name == CHANNEL_NAME:
                self.channel = ch
                return ch
        try:
            self.channel = await guild.create_text_channel(
                CHANNEL_NAME,
                topic="Automatic NEWR Adventure announcements: events, "
                      "meteor showers, raids, guild wars. "
                      "Mute this channel to opt out.",
                reason="NEWR Adventure announcements")
            return self.channel
        except discord.Forbidden:
            if not self._warned_no_channel:
                log.warning(
                    "Announcements disabled: no Manage Channels and no "
                    "ANNOUNCE_CHANNEL_ID set. Set ANNOUNCE_CHANNEL_ID to a "
                    "channel ID to enable them.")
                self._warned_no_channel = True
        except discord.HTTPException as exc:
            log.warning("Could not create announcement channel: %s", exc)
        return None

    async def _send(self, channel, title, desc, color):
        try:
            await channel.send(
                content="@everyone", embed=emb(title, desc, color=color),
                allowed_mentions=discord.AllowedMentions(everyone=True))
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Announcement send failed: %s", exc)

    def _guild(self):
        if not self._guild_id:
            return None
        return self.bot.get_guild(self._guild_id)

    # -------------------------------------------------------- announce loop
    @tasks.loop(minutes=2)
    async def announce_loop(self):
        guild = self._guild()
        if guild is None:
            return
        conn = get_conn()
        rolesync.ensure_tables(conn)
        channel = await self._resolve_channel(guild)
        if channel is None:
            return
        self._warned_no_channel = False
        now = int(time.time())
        try:
            await self._check_events(conn, channel)
            await self._check_meteor(conn, channel)
            await self._check_raid(conn, channel)
            await self._check_wars(conn, channel)
        except Exception as exc:
            log.warning("Announcement tick failed: %s", exc)

    async def _check_events(self, conn, channel):
        active = logic.active_events()
        names = [name for name, _ev in active]
        seen = rolesync.state_json_load(
            rolesync.get_state(conn, "events"), [])
        for name, ev in active:
            if name in seen:
                continue
            await self._send(
                channel, f"🎉 Event Started: {name}",
                f"The {name} event is live! Boss "
                f"{disp.monster(ev['boss'])} ({ev['boss_hp']} HP) awaits "
                f"in /raid. Join with /raid join, then attack with "
                f"/raid hit together!",
                COLOR_EXTRA)
        rolesync.set_state(conn, "events", json.dumps(names))

    async def _check_meteor(self, conn, channel):
        if not logic.meteor_window_now():
            return
        key = f"meteor:{logic.today_wib()}"
        if rolesync.get_state(conn, key) is not None:
            return
        await self._send(
            channel, "☄️ Meteor Shower Live!",
            "A meteor shower is falling until 22:00 WIB! Use /meteor to "
            "catch a meteor and earn rare items.",
            COLOR_EXTRA)
        rolesync.set_state(conn, key, "1")

    async def _check_raid(self, conn, channel):
        raid = db.active_raid(conn)
        if raid is not None:
            key = f"raid_spawn:{raid['id']}"
            if rolesync.get_state(conn, key) is None:
                await self._send(
                    channel, "🐉 Raid Boss Spawned!",
                    f"**{disp.monster(raid['boss'])}** appeared with "
                    f"{raid['hp']} HP! Join with /raid join, then attack "
                    f"with /raid hit together!",
                    COLOR_BATTLE)
                rolesync.set_state(conn, key, "1")
            return
        done = conn.execute(
            "SELECT * FROM raids WHERE state = 'done' "
            "ORDER BY id DESC LIMIT 1").fetchone()
        if done is None:
            return
        key = f"raid_defeat:{done['id']}"
        if rolesync.get_state(conn, key) is not None:
            return
        kill = conn.execute(
            "SELECT * FROM boss_kills WHERE raid_id = ? "
            "ORDER BY id DESC LIMIT 1", (done["id"],)).fetchone()
        killer = "Unknown"
        if kill is not None:
            kp = db.get_player(conn, kill["killer_id"])
            killer = kp["name"] if kp else str(kill["killer_id"])
        await self._send(
            channel, "🎉 Boss Defeated!",
            f"**{disp.monster(done['boss'])}** has fallen! Killing blow "
            f"by **{killer}**.",
            COLOR_BATTLE)
        rolesync.set_state(conn, key, "1")

    async def _check_wars(self, conn, channel):
        due = conn.execute(
            "SELECT * FROM wars WHERE state = 'pending' AND resolves_at <= ?",
            (int(time.time()),)).fetchall()
        for row in due:
            winner = resolve_war(conn, dict(row))
            if winner is not None:
                await self._announce_war(conn, channel, dict(row)["id"])
        done = conn.execute(
            "SELECT * FROM wars WHERE state = 'done' "
            "ORDER BY id DESC LIMIT 5").fetchall()
        for row in done:
            if rolesync.get_state(conn, f"war:{row['id']}") is None:
                await self._announce_war(conn, channel, row["id"])

    async def _announce_war(self, conn, channel, war_id):
        war = conn.execute(
            "SELECT * FROM wars WHERE id = ?", (war_id,)).fetchone()
        if war is None or war["state"] != "done":
            return
        winner = db.get_guild(conn, war["winner_id"])
        loser_id = (war["guild_b"] if war["winner_id"] == war["guild_a"]
                    else war["guild_a"])
        loser = db.get_guild(conn, loser_id)
        for mid in db.guild_member_ids(conn, war["winner_id"]):
            rolesync.grant_achievement(conn, mid, "War Champion")
        wname = winner["name"] if winner else str(war["winner_id"])
        lname = loser["name"] if loser else str(loser_id)
        await self._send(
            channel, "🏆 Guild War Over!",
            f"Winner: **{wname}**! **{wname}** beat **{lname}** "
            f"(score {war['score_a']} vs {war['score_b']}). All winning "
            f"members earned the War Champion achievement!",
            COLOR_BATTLE)
        rolesync.set_state(conn, f"war:{war_id}", "1")

    # ------------------------------------------------------- reconcile loop
    @tasks.loop(minutes=10)
    async def reconcile_loop(self):
        # Role sync runs for EVERY server the bot is in, not just the
        # primary guild: a player who joins the bot in another server
        # still gets their Season / Top / Guild Top roles there, from
        # the same central database. Announcements stay primary-only
        # (see announce_loop), only role sync is multi-guild.
        guilds = list(self.bot.guilds) or []
        if not guilds:
            guild = self._guild()
            guilds = [guild] if guild is not None else []
        conn = get_conn()
        for guild in guilds:
            try:
                await rolesync.reconcile_guild(guild, conn)
            except Exception as exc:
                log.warning("Role reconcile failed for guild %s: %s",
                            guild.id, exc)

    @announce_loop.before_loop
    @reconcile_loop.before_loop
    async def _before_loops(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Announce(bot))
