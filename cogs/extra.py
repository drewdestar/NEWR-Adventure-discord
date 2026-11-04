# -*- coding: utf-8 -*-
"""Cog tambahan unik: casino, job, house, dungeon, meteor, story."""
import random
import time
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import logic
from data import (DUNGEON_PUZZLES, DUNGEON_REWARD_GOLD, GACHA_POOL, ITEMS,
                  JOBS, STORY)
from .common import (COLOR_EXTRA, bump_daily, emb, err_embed, get_conn,
                     need_player, reward, sync_quests)

DUNGEON_STATE = {}  # user_id -> {"q": ..., "a": ...}
CROP_YIELD = {
    "gandum": [("roti", 3)],
    "tomat": [("jus buah", 2)],
    "labu": [("daging panggang", 2)],
}
ANIMALS = {"ayam": {"price": 150, "yield": "telur ayam", "cooldown": 6 * 3600},
           "sapi": {"price": 400, "yield": "susu", "cooldown": 6 * 3600}}


class Extra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------------------- casino
    @app_commands.command(name="casino", description="Casual gambling: guess the number / guess the coin (daily limit!)")
    @app_commands.describe(game="Guess number 1-10 (pays 5x) or guess coin (pays 2x)",
                           taruhan="Gold amount (10-500)", tebakan="Number 1-10 or heads/tails")
    @app_commands.rename(taruhan="bet", tebakan="guess")
    @app_commands.choices(game=[
        app_commands.Choice(name="guess number", value="number"),
        app_commands.Choice(name="guess coin", value="coin"),
    ])
    async def casino(self, interaction: discord.Interaction, game: str,
                     taruhan: int, tebakan: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        ok, msg = logic.casino_limits_ok(p, taruhan)
        if not ok:
            await interaction.response.send_message(
                embed=err_embed(msg), ephemeral=True)
            return
        if p["gold"] < taruhan:
            await interaction.response.send_message(
                embed=err_embed("You don't have enough gold for that bet."), ephemeral=True)
            return
        if game == "number":
            try:
                guess = int(tebakan)
            except ValueError:
                await interaction.response.send_message(
                    embed=err_embed('Number guesses must be 1-10.'), ephemeral=True)
                return
            if not 1 <= guess <= 10:
                await interaction.response.send_message(
                    embed=err_embed('Number guesses must be 1-10.'), ephemeral=True)
                return
            result = random.randint(1, 10)
            win = guess == result
            payout = taruhan * 5
            detail = f"The casino die shows **{result}**, your guess was {guess}."
        else:
            # Coin guesses accept English heads/tails as well as the old
            # Indonesian kepala/ekor (input values are never stored).
            coin_alias = {"heads": "heads", "kepala": "heads",
                          "tails": "tails", "ekor": "tails"}
            guess = coin_alias.get(tebakan.lower())
            if guess is None:
                await interaction.response.send_message(
                    embed=err_embed("Coin guess: 'heads' or 'tails'."), ephemeral=True)
                return
            result = random.choice(["heads", "tails"])
            win = guess == result
            payout = taruhan * 2
            detail = f"The coin shows **{result}**, your guess was {guess}."
        if win:
            p["gold"] += payout - taruhan
            db.save_player(conn, p)
            await interaction.response.send_message(
                embed=emb('🎰 Casino',
                          f"YOU WIN! {detail} You got {payout} gold (profit {payout - taruhan}).",
                          color=COLOR_EXTRA))
        else:
            p["gold"] -= taruhan
            p["casino_lost"] += taruhan
            p["casino_date"] = logic.today_wib()
            db.save_player(conn, p)
            await interaction.response.send_message(
                embed=emb('🎰 Casino',
                          f"You lost... {detail} You lost {taruhan} gold. "
                          f"Total loss today: {p['casino_lost']}/2000 gold. Don't chase your losses!",
                          color=COLOR_EXTRA))

    # ------------------------------------------------------------------ job
    @app_commands.command(name="job", description="Realistic work: carpenter, miner, hunter")
    @app_commands.describe(pekerjaan="Pick a job")
    @app_commands.rename(pekerjaan="job")
    @app_commands.choices(pekerjaan=[
        app_commands.Choice(name="Carpenter", value="tukang kayu"),
        app_commands.Choice(name="Miner", value="penambang"),
        app_commands.Choice(name="Hunter", value="pemburu"),
    ])
    async def job(self, interaction: discord.Interaction, pekerjaan: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        job = JOBS[pekerjaan]
        row = conn.execute(
            "SELECT * FROM jobs_cd WHERE user_id = ? AND job = ?",
            (p["user_id"], pekerjaan)).fetchone()
        now = int(time.time())
        if row and now - row["last_work"] < job["cooldown"]:
            left = (job["cooldown"] - (now - row["last_work"])) // 60
            await interaction.response.send_message(
                embed=emb('🪓 Work',
                          f"Tired! Rest first, work again in {left} minutes.",
                          color=COLOR_EXTRA),
                ephemeral=True)
            return
        gold = random.randint(*job["gold"])
        item = random.choice(job["items"])
        qty = random.randint(1, 3)
        logic.add_gold(p, logic.gold_gain(p, gold))
        p["jobs_done"] += 1
        p["hunger"] = max(0, p["hunger"] - 3)
        p["thirst"] = max(0, p["thirst"] - 3)
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], item, qty)
        conn.execute(
            "INSERT INTO jobs_cd (user_id, job, last_work) VALUES (?, ?, ?)"
            " ON CONFLICT(user_id, job) DO UPDATE SET last_work = ?",
            (p["user_id"], pekerjaan, now, now))
        conn.commit()
        bump_daily(conn, p, "jobs_done")
        sync_quests(conn, p)
        await interaction.response.send_message(
            embed=emb('🪓 Work',
                      f"You worked as a {disp.job(pekerjaan)}: got {gold} gold + {disp.item(item)} x{qty}!",
                      color=COLOR_EXTRA))

    # ---------------------------------------------------------------- house
    @app_commands.command(name="house", description="House, garden & livestock")
    @app_commands.describe(aksi="build/upgrade/info/plant/harvest/animal/collect",
                           item="Seed (plant) / animal chicken/cow (animal)")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="build", value="build"),
        app_commands.Choice(name="upgrade", value="upgrade"),
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="plant", value="plant"),
        app_commands.Choice(name="harvest", value="harvest"),
        app_commands.Choice(name="animal", value="animal"),
        app_commands.Choice(name="collect", value="collect"),
    ])
    async def house(self, interaction: discord.Interaction, aksi: str, item: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        now = int(time.time())
        if aksi == "build":
            if p["house_level"] > 0:
                await interaction.response.send_message(
                    embed=emb('🏠 House','You already have a house. Upgrade with `/house upgrade`.',
                              color=COLOR_EXTRA),
                    ephemeral=True)
                return
            if p["gold"] < 300:
                await interaction.response.send_message(
                    embed=err_embed('Building a house needs 300 gold.'), ephemeral=True)
                return
            p["gold"] -= 300
            p["house_level"] = 1
            db.save_player(conn, p)
            await interaction.response.send_message(
                embed=emb('🏠 House','House Lv 1 built! Now you can plant with `/house plant <seed>` and raise animals with `/house animal <chicken/cow>`.',
                          color=COLOR_EXTRA))
            return
        if p["house_level"] == 0:
            await interaction.response.send_message(
                embed=err_embed("You don't have a house yet. Build one first with `/house build` (300 gold)."),
                ephemeral=True)
            return
        if aksi == "upgrade":
            cost = 500 * p["house_level"]
            if p["gold"] < cost:
                await interaction.response.send_message(
                    embed=err_embed(f"Upgrading the house needs {cost} gold."), ephemeral=True)
                return
            p["gold"] -= cost
            p["house_level"] += 1
            db.save_player(conn, p)
            await interaction.response.send_message(
                embed=emb('🏠 House',
                          f"House rose to Lv {p['house_level']}! Your garden gets bigger.",
                          color=COLOR_EXTRA))
            return
        if aksi == "info":
            crops = conn.execute(
                "SELECT * FROM crops WHERE user_id = ? AND harvested = 0",
                (p["user_id"],)).fetchall()
            animals = conn.execute(
                "SELECT * FROM animals WHERE user_id = ?", (p["user_id"],)).fetchall()
            crop_lines = []
            for c in crops:
                left = max(0, (c["ready_at"] - now) // 60)
                crop_lines.append(f"{disp.crop(c['crop'])} — {'ready to harvest!' if left == 0 else f'{left} minutes left'}")
            animal_lines = [disp.animal(a["animal"]) for a in animals] or ["No animals yet."]
            await interaction.response.send_message(embed=emb(
                f"🏠 House Lv {p['house_level']}",
                "Plants:\n" + ("\n".join(crop_lines) if crop_lines else "No plants yet.") +
                "\n\nAnimals:\n" + "\n".join(animal_lines),
                color=COLOR_EXTRA))
            return
        if aksi == "plant":
            item = disp.resolve_item(item)
            if item is None or ITEMS[item].get("type") != "seed":
                await interaction.response.send_message(
                    embed=err_embed('Available seeds: Wheat Seeds, Tomato Seeds, Pumpkin Seeds. Buy at `/shop`.'),
                    ephemeral=True)
                return
            if db.item_qty(conn, p["user_id"], item) < 1:
                await interaction.response.send_message(
                    embed=err_embed(f"You don't have {disp.item(item)}."), ephemeral=True)
                return
            slots = p["house_level"] + 1
            active = conn.execute(
                "SELECT COUNT(*) AS c FROM crops WHERE user_id = ? AND harvested = 0",
                (p["user_id"],)).fetchone()["c"]
            if active >= slots:
                await interaction.response.send_message(
                    embed=err_embed(f"Garden full! (capacity {slots}, upgrade the house for more slots.)"),
                    ephemeral=True)
                return
            db.remove_item(conn, p["user_id"], item, 1)
            grow = ITEMS[item]["grow_minutes"] * 60
            conn.execute(
                "INSERT INTO crops (user_id, crop, planted_at, ready_at) VALUES (?, ?, ?, ?)",
                (p["user_id"], ITEMS[item]["crop"], now, now + grow))
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🌱 Garden',
                          f"{disp.crop(ITEMS[item]['crop'])} planted! Ready to harvest in {ITEMS[item]['grow_minutes']} minutes.",
                          color=COLOR_EXTRA))
            return
        if aksi == "harvest":
            ready = conn.execute(
                "SELECT * FROM crops WHERE user_id = ? AND harvested = 0 AND ready_at <= ?",
                (p["user_id"], now)).fetchall()
            if not ready:
                await interaction.response.send_message(
                    embed=err_embed('No crops are ready to harvest yet.'), ephemeral=True)
                return
            got = []
            for c in ready:
                for it, qty in CROP_YIELD[c["crop"]]:
                    db.add_item(conn, p["user_id"], it, qty)
                    got.append(f"{disp.item(it)} x{qty}")
                conn.execute("UPDATE crops SET harvested = 1 WHERE id = ?", (c["id"],))
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🌾 Harvest', f"You got: {', '.join(got)}.",
                          color=COLOR_EXTRA))
            return
        if aksi == "animal":
            animal = disp.resolve_animal(item)
            if animal is None:
                await interaction.response.send_message(
                    embed=err_embed('Animals you can raise: chicken (150 gold), cow (400 gold).'),
                    ephemeral=True)
                return
            price = ANIMALS[animal]["price"]
            if p["gold"] < price:
                await interaction.response.send_message(
                    embed=err_embed(f"You need {price} gold to buy a {disp.animal(animal)}."), ephemeral=True)
                return
            p["gold"] -= price
            db.save_player(conn, p)
            conn.execute(
                "INSERT INTO animals (user_id, animal, last_collect) VALUES (?, ?, ?)",
                (p["user_id"], animal, now))
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🐔 Livestock',
                          f"You're raising a {disp.animal(animal)}! Collect the produce with `/house collect`.",
                          color=COLOR_EXTRA))
            return
        # collect
        animals = conn.execute(
            "SELECT * FROM animals WHERE user_id = ?", (p["user_id"],)).fetchall()
        if not animals:
            await interaction.response.send_message(
                embed=err_embed("You aren't raising any animals yet."), ephemeral=True)
            return
        got = []
        for a in animals:
            info = ANIMALS[a["animal"]]
            if now - a["last_collect"] >= info["cooldown"]:
                db.add_item(conn, p["user_id"], info["yield"], 1)
                conn.execute("UPDATE animals SET last_collect = ? WHERE id = ?",
                             (now, a["id"]))
                got.append(disp.item(info["yield"]))
        conn.commit()
        if got:
            await interaction.response.send_message(
                embed=emb('🥚 Livestock', f"Livestock produce collected: {', '.join(got)}.",
                          color=COLOR_EXTRA))
        else:
            await interaction.response.send_message(
                embed=emb('🥚 Livestock',"Your animals haven't produced again yet. Check again in 6 hours.",
                          color=COLOR_EXTRA))

    # --------------------------------------------------------------- dungeon
    @app_commands.command(name="dungeon", description="Dungeon with a treasure-guardian riddle")
    @app_commands.describe(aksi="enter/answer/info", jawaban="Riddle answer (for answer)")
    @app_commands.rename(aksi="action", jawaban="answer")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="enter", value="enter"),
        app_commands.Choice(name="answer", value="answer"),
        app_commands.Choice(name="info", value="info"),
    ])
    async def dungeon(self, interaction: discord.Interaction, aksi: str, jawaban: str = ""):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if aksi == "info":
            await interaction.response.send_message(
                embed=emb('🏰 Dungeon',"Enter (needs 15 stamina), answer the guardian's riddle, and grab treasure of 150-400 gold + a random item. Wrong answer? Try again, no penalty.",
                          color=COLOR_EXTRA))
            return
        if aksi == "enter":
            if not logic.spend_stamina(p, 15):
                await interaction.response.send_message(
                    embed=err_embed('Not enough stamina (need 15).'), ephemeral=True)
                return
            db.save_player(conn, p)
            puzzle = random.choice(DUNGEON_PUZZLES)
            DUNGEON_STATE[p["user_id"]] = puzzle
            await interaction.response.send_message(embed=emb('🏰 You enter the dungeon...',
                f"The treasure guardian asks:\n**{disp.riddle(puzzle['q'])}**\n\nAnswer with `/dungeon answer <answer>`.",
                color=COLOR_EXTRA))
            return
        state = DUNGEON_STATE.get(p["user_id"])
        if not state:
            await interaction.response.send_message(
                embed=err_embed("You haven't entered a dungeon yet. Use `/dungeon enter` first."),
                ephemeral=True)
            return
        _ans = jawaban.strip().lower()
        _en_ans = disp.riddle_answer_en(state["a"])
        if _ans == state["a"].lower() or (_en_ans and _ans == _en_ans.lower()):
            del DUNGEON_STATE[p["user_id"]]
            gold = random.randint(*DUNGEON_REWARD_GOLD)
            item = random.choice(GACHA_POOL["rare"] + GACHA_POOL["epic"])
            logic.add_gold(p, logic.gold_gain(p, gold))
            db.save_player(conn, p)
            db.add_item(conn, p["user_id"], item, 1)
            sync_quests(conn, p)
            await interaction.response.send_message(
                embed=emb('🎉 Dungeon Treasure!',
                          f"CORRECT! Treasure unlocked: {gold} gold + {disp.item(item)}!",
                          color=COLOR_EXTRA))
        else:
            await interaction.response.send_message(
                embed=err_embed('Wrong answer, try again! (No penalty.)'),
                ephemeral=True)

    # ---------------------------------------------------------------- meteor
    @app_commands.command(name="meteor", description="Catch the 21:00 WIB meteor shower for rare items")
    async def meteor(self, interaction: discord.Interaction):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if not logic.meteor_window_now():
            now_wib = datetime.now(logic.WIB).strftime("%H:%M")
            await interaction.response.send_message(
                embed=emb('☄️ Meteor',
                          f"The sky is still calm (now {now_wib} WIB). Meteor showers only happen 21:00-21:59 WIB!",
                          color=COLOR_EXTRA),
                ephemeral=True)
            return
        if p["meteor_date"] == logic.today_wib():
            await interaction.response.send_message(
                embed=emb('☄️ Meteor',"You've already caught a meteor today. Come back tomorrow at 21:00 WIB!",
                          color=COLOR_EXTRA),
                ephemeral=True)
            return
        item = random.choice(GACHA_POOL["epic"] + GACHA_POOL["legendary"])
        p["meteor_date"] = logic.today_wib()
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], item, 1)
        await interaction.response.send_message(
            embed=emb('☄️ METEOR SHOWER!',
                      f"A meteor fell near you and left **{disp.item(item)}**!",
                      color=COLOR_EXTRA))

    # ----------------------------------------------------------------- story
    @app_commands.command(name="story", description="Follow the long RPG story arc")
    @app_commands.describe(aksi="info/next")
    @app_commands.rename(aksi="action")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="info", value="info"),
        app_commands.Choice(name="next", value="next"),
    ])
    async def story(self, interaction: discord.Interaction, aksi: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        nxt = p["story_chapter"] + 1
        chapter = next((c for c in STORY if c["chapter"] == nxt), None)
        if chapter is None:
            await interaction.response.send_message(
                embed=emb('📖 Story',"🎬 You've finished all available chapters! Wait for the next story update.",
                          color=COLOR_EXTRA))
            return
        if aksi == "info":
            await interaction.response.send_message(embed=emb(
                f"📖 Story Chapter {chapter['chapter']}: {disp.story_title(chapter['chapter'])}",
                disp.story_text(chapter['chapter']) + f"\n\nRequirements: Lv {chapter['min_level']} • Rewards: {chapter['gold']} gold + {chapter['exp']} EXP",
                color=COLOR_EXTRA))
            return
        if p["level"] < chapter["min_level"]:
            await interaction.response.send_message(
                embed=err_embed(f"This chapter needs Lv {chapter['min_level']}, you're still Lv {p['level']}. Keep grinding!"),
                ephemeral=True)
            return
        p["story_chapter"] = nxt
        levels = reward(conn, p, chapter["gold"], chapter["exp"])
        await interaction.response.send_message(embed=emb(
            f"📖 Chapter {chapter['chapter']} complete: {disp.story_title(chapter['chapter'])}",
            disp.story_text(chapter['chapter']) + f"\n\nRewards: {chapter['gold']} gold + {chapter['exp']} EXP"
            + (f", leveled up {levels} levels!" if levels else "") +
            "\nContinue the next chapter with `/story next`.",
            color=COLOR_EXTRA))


async def setup(bot):
    await bot.add_cog(Extra(bot))
