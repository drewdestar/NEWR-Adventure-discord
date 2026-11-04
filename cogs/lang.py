# -*- coding: utf-8 -*-
"""Cog /language: per-user language choice for NEWR Adventure.

One choice per user, stored in the shared rpg.db table user_prefs
(default English; existing players are untouched until they run this
command). The choice changes reply TEXTS only.

Discord limitation: slash command names, descriptions and option
names are registered per application and cannot switch per user —
only the reply texts switch language.

Why autocomplete instead of fixed choices: Discord allows at most 25
choices per option, but discord.Locale has 32 values. Autocomplete
shows up to 25 matches filtered by what the user types, so all 32
locales are reachable (Indonesian 'id' included natively).
"""
import discord
from discord import app_commands
from discord.ext import commands

import i18n
from .common import emb, err_embed, get_conn


async def _lang_autocomplete(interaction: discord.Interaction,
                             current: str):
    cur = current.lower()
    out = []
    for value, label in i18n.SUPPORTED:
        if cur in value.lower() or cur in label.lower():
            out.append(app_commands.Choice(
                name=f"{label} ({value})", value=value))
        if len(out) >= 25:
            break
    return out


class Language(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="language",
        description="Set the language of the bot's replies for you")
    @app_commands.describe(
        language="Language for your replies (type to search all languages)")
    @app_commands.autocomplete(language=_lang_autocomplete)
    async def language(self, interaction: discord.Interaction,
                       language: str):
        conn = get_conn()
        # Read the CURRENT stored language first, so even the error
        # below is shown in the user's current language.
        i18n.set_ctx(interaction, conn)
        if language not in i18n.SUPPORTED_VALUES:
            await interaction.response.send_message(
                embed=err_embed(
                    "Unknown language. Please pick one from the suggestions."),
                ephemeral=True)
            return
        i18n.set_lang(conn, interaction.user.id, language)
        i18n.set_ctx(interaction, conn)
        label = dict(i18n.SUPPORTED)[language]
        await interaction.response.send_message(
            embed=emb(i18n.t("🌐 Language set"),
                      i18n.t("Your replies will now use {label}.").format(label=label)),
            ephemeral=True)


async def setup(bot):
    await bot.add_cog(Language(bot))
