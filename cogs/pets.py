# -*- coding: utf-8 -*-
"""Cog pet: adopsi, info, latih, pet gear."""
import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import logic
from data import ITEMS, PETS, PET_ADOPT_COST
from .common import COLOR_PET, bar_line, emb, err_embed, get_conn, need_player


class Pets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pet", description="Adopt & care for companion pets")
    @app_commands.describe(aksi="adopt/list/info/train", spesies="Pet species (for adopt)",
                           nama="Pet name (for adopt)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="adopt", value="adopt"),
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="train", value="train"),
    ])
    @app_commands.rename(aksi="action", spesies="species", nama="name")
    async def pet(self, interaction: discord.Interaction, aksi: str,
                  spesies: str = "", nama: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        pets = db.get_pets(conn, p["user_id"])
        if aksi == "adopt":
            spesies = disp.resolve_pet(spesies) or spesies
            if spesies not in PETS:
                await interaction.response.send_message(
                    embed=err_embed("Available species: " + ", ".join(disp.pet(s) for s in PETS) + "."),
                    ephemeral=True)
                return
            if p["gold"] < PET_ADOPT_COST:
                await interaction.response.send_message(
                    embed=err_embed(f"Adoption needs {PET_ADOPT_COST} gold."), ephemeral=True)
                return
            p["gold"] -= PET_ADOPT_COST
            db.save_player(conn, p)
            db.add_pet(conn, p["user_id"], spesies, nama.strip() or spesies)
            await interaction.response.send_message(embed=emb('🐾 New Pet!',
                f"You adopted **{nama.strip() or disp.pet(spesies)}** ({disp.pet(spesies)})!\n"
                f"Unique skill: **{disp.pet_skill(PETS[spesies]['skill'])}**.\n"
                f"Pets join fights and add damage. Train with `/pet train`.",
                color=COLOR_PET))
            return
        if aksi == "list" or aksi == "info":
            if not pets:
                await interaction.response.send_message(
                    embed=emb('🐾 Your Pets', "You don't have a pet yet. Adopt with `/pet adopt <species>`.",
                              color=COLOR_PET),
                    ephemeral=True)
                return
            lines = []
            for pet in pets:
                form = disp.pet_form(logic.pet_form(pet["species"], pet["level"]))
                spec = PETS[pet["species"]]
                gear = []
                if pet["gear_weapon"]:
                    gear.append(disp.item(pet["gear_weapon"]))
                if pet["gear_armor"]:
                    gear.append(disp.item(pet["gear_armor"]))
                lines.append(
                    f"ID {pet['id']} — **{pet['name']}** ({form}, Lv {pet['level']})\n"
                    f"{bar_line('✨ EXP', pet['exp'], logic.pet_exp_needed(pet['level']))}\n"
                    f"Skill: {disp.pet_skill(spec['skill'])} • ATK Bonus: {spec['atk'] + pet['level'] // 2}"
                    + (f" • Gear: {', '.join(gear)}" if gear else ""))
            await interaction.response.send_message(
                embed=emb('🐾 Your Pets', "\n\n".join(lines), color=COLOR_PET))
            return
        # train
        if not pets:
            await interaction.response.send_message(
                embed=err_embed("You don't have a pet yet."), ephemeral=True)
            return
        if p["gold"] < 50:
            await interaction.response.send_message(
                embed=err_embed('Training a pet needs 50 gold.'), ephemeral=True)
            return
        pet = pets[0]
        p["gold"] -= 50
        db.save_player(conn, p)
        before_form = logic.pet_form(pet["species"], pet["level"])
        gained = logic.pet_gain_exp(pet, 40)
        db.save_pet(conn, pet)
        after_form = logic.pet_form(pet["species"], pet["level"])
        evo_note = ""
        if after_form != before_form:
            evo_note = f"\n🌟 Pet evolved into **{disp.pet_form(after_form)}**!"
        await interaction.response.send_message(
            embed=emb('🐾 Pet Training',
                      f"{pet['name']} trained (+40 EXP)!"
                      + (f" Leveled up {gained} levels, now Lv {pet['level']}." if gained else
                         f" EXP {pet['exp']}/{logic.pet_exp_needed(pet['level'])}.") + evo_note,
                      color=COLOR_PET))

    @app_commands.command(name="petgear", description="Equip/unequip special pet gear")
    @app_commands.describe(aksi="equip/unequip", item="Gear name (for equip)",
                           pet_id="Pet ID (see /pet list)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="equip", value="equip"),
        app_commands.Choice(name="unequip", value="unequip"),
    ])
    @app_commands.rename(aksi="action")
    async def petgear(self, interaction: discord.Interaction, aksi: str,
                      item: str = "", pet_id: int = 0):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        pets = db.get_pets(conn, p["user_id"])
        pet = next((x for x in pets if x["id"] == pet_id), None)
        if not pet:
            await interaction.response.send_message(
                embed=err_embed('Pet ID not found. Check `/pet list`.'), ephemeral=True)
            return
        if aksi == "equip":
            item = disp.resolve_item(item) or item.lower()
            if item not in ITEMS or ITEMS[item].get("type") != "petgear":
                await interaction.response.send_message(
                    embed=err_embed("That's not pet gear. Pet gear: Pet Necklace, Pet Armor, Pet Crown."),
                    ephemeral=True)
                return
            if db.item_qty(conn, p["user_id"], item) < 1:
                await interaction.response.send_message(
                    embed=err_embed(f"You don't have {disp.item(item)}."), ephemeral=True)
                return
            slot = "gear_weapon" if "atk" in ITEMS[item] else "gear_armor"
            old = pet[slot]
            if old:
                db.add_item(conn, p["user_id"], old, 1)
            db.remove_item(conn, p["user_id"], item, 1)
            pet[slot] = item
            db.save_pet(conn, pet)
            await interaction.response.send_message(
                embed=emb('🐾 Pet Gear',
                          f"{disp.item(item)} equipped to {pet['name']}" + (f" (old gear {disp.item(old)} returned)." if old else "."),
                          color=COLOR_PET))
        else:
            returned = []
            for slot in ("gear_weapon", "gear_armor"):
                if pet[slot]:
                    db.add_item(conn, p["user_id"], pet[slot], 1)
                    returned.append(disp.item(pet[slot]))
                    pet[slot] = None
            db.save_pet(conn, pet)
            if returned:
                await interaction.response.send_message(
                    embed=emb('🐾 Pet Gear',
                              f"Gear removed from {pet['name']}: {', '.join(returned)}.",
                              color=COLOR_PET))
            else:
                await interaction.response.send_message(
                    embed=emb('🐾 Pet Gear', f"{pet['name']} isn't wearing any gear right now.",
                              color=COLOR_PET),
                    ephemeral=True)


async def setup(bot):
    await bot.add_cog(Pets(bot))
