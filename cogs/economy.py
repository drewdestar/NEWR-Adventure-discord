# -*- coding: utf-8 -*-
"""Cog ekonomi: shop, black market, crafting, gacha, trade, tradeboard."""
import random

import discord
from discord import app_commands
from discord.ext import commands

import database as db
import display as disp
import logic
from data import BLACKMARKET_POOL, GACHA_POOL, ITEMS, RECIPES, SHOP_STOCK
from .common import COLOR_ECONOMY, emb, err_embed, get_conn, need_player, sync_quests


def item_line(item_id):
    info = ITEMS[item_id]
    bonus = ""
    if "atk" in info:
        bonus = f" (+{info['atk']} ATK)"
    if "def" in info:
        bonus = f" (+{info['def']} DEF)"
    if "heal" in info:
        bonus = f" (heal {info['heal']})"
    return f"{disp.item(item_id)}{bonus} — {info['price']} gold"


def execute_trade_accept(conn, trade_id, acceptor_id):
    """Eksekusi terima trade. Kembalikan (ok, teks). Dipakai command & tombol."""
    row = conn.execute(
        "SELECT * FROM trades WHERE id = ? AND status = 'pending'", (trade_id,)).fetchone()
    if not row:
        return False, "That trade doesn't exist / is already done."
    row = dict(row)
    if row["to_id"] != acceptor_id:
        return False, "Only the trade recipient can accept."
    if db.item_qty(conn, acceptor_id, row["want_item"]) < row["want_qty"]:
        return False, "You don't have enough of the requested item."
    if db.item_qty(conn, row["from_id"], row["offer_item"]) < row["offer_qty"]:
        return False, "The offerer no longer has the item."
    db.remove_item(conn, row["from_id"], row["offer_item"], row["offer_qty"])
    db.remove_item(conn, acceptor_id, row["want_item"], row["want_qty"])
    db.add_item(conn, row["from_id"], row["want_item"], row["want_qty"])
    db.add_item(conn, acceptor_id, row["offer_item"], row["offer_qty"])
    conn.execute("UPDATE trades SET status = 'accepted' WHERE id = ?", (trade_id,))
    conn.commit()
    return True, '🔄 Trade successful! You got {item} x{qty}.'.format(item=disp.item(row['offer_item']), qty=row['offer_qty'])


def execute_trade_decline(conn, trade_id, acceptor_id):
    """Tolak trade. Kembalikan (ok, teks)."""
    row = conn.execute(
        "SELECT * FROM trades WHERE id = ? AND status = 'pending'", (trade_id,)).fetchone()
    if not row:
        return False, "That trade doesn't exist / is already done."
    if dict(row)["to_id"] != acceptor_id:
        return False, "Only the trade recipient can accept/decline."
    conn.execute("UPDATE trades SET status = 'declined' WHERE id = ?", (trade_id,))
    conn.commit()
    return True, "Trade declined."


class TradeView(discord.ui.View):
    """Tombol Terima / Tolak buat tawaran trade. Cuma penerima yang bisa klik."""

    def __init__(self, trade_id, to_id):
        super().__init__(timeout=3600)
        self.trade_id = trade_id
        self.to_id = to_id

    async def _check(self, interaction):
        if interaction.user.id != self.to_id:
            await interaction.response.send_message(
                embed=err_embed('Only the trade recipient can accept/decline.'),
                ephemeral=True)
            return False
        return True

    def _disable(self):
        for child in self.children:
            child.disabled = True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_btn(self, interaction, button):
        if not await self._check(interaction):
            return
        conn = get_conn()
        ok, text = execute_trade_accept(conn, self.trade_id, self.to_id)
        if not ok:
            await interaction.response.send_message(
                embed=err_embed(text), ephemeral=True)
            return
        self._disable()
        await interaction.response.edit_message(
            embed=emb('🔄 Trade', text, color=COLOR_ECONOMY), view=self)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
    async def decline_btn(self, interaction, button):
        if not await self._check(interaction):
            return
        conn = get_conn()
        ok, text = execute_trade_decline(conn, self.trade_id, self.to_id)
        if not ok:
            await interaction.response.send_message(
                embed=err_embed(text), ephemeral=True)
            return
        self._disable()
        await interaction.response.edit_message(
            embed=emb('🔄 Trade', text, color=COLOR_ECONOMY), view=self)


def ensure_bm_stock(conn):
    """Stok Black Market hari ini, dibuat dulu kalau belum ada (3 item acak)."""
    today = logic.today_wib()
    rows = conn.execute(
        "SELECT * FROM bm_stock WHERE date = ?", (today,)).fetchall()
    if not rows:
        rng = random.Random(today)
        picks = rng.sample(BLACKMARKET_POOL, 3)
        for it in picks:
            conn.execute(
                "INSERT INTO bm_stock (date, item_id, qty_left) VALUES (?, ?, 2)",
                (today, it))
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM bm_stock WHERE date = ?", (today,)).fetchall()
    return [dict(r) for r in rows]


# Keranjang Black Market per pemain, di memori saja (seperti state fight:
# hilang kalau bot restart, stok baru dikurangi pas checkout, bukan pas
# masuk keranjang).
BM_CARTS = {}


def bm_cart_embed(owner_id):
    """Embed isi keranjang + total, dipakai ulang view keranjang."""
    cart = BM_CARTS.get(owner_id, {})
    if not cart:
        return emb('🛒 Your Cart',
                   'Your cart is empty. Tap Buy on the Black Market list to add items.',
                   color=COLOR_ECONOMY)
    lines = [f"{disp.item(it)} x{q} — {logic.bm_price(it) * q} gold"
             for it, q in cart.items()]
    lines.append(f"\nTotal: {logic.bm_cart_total(cart)} gold")
    return emb('🛒 Your Cart', "\n".join(lines), color=COLOR_ECONOMY)


class BMCartView(discord.ui.View):
    """Checkout / kosongkan keranjang Black Market."""

    def __init__(self, owner_id):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        checkout = discord.ui.Button(label="Checkout", style=discord.ButtonStyle.success, emoji="💰")
        checkout.callback = self._checkout
        clear = discord.ui.Button(label="Clear cart", style=discord.ButtonStyle.danger)
        clear.callback = self._clear
        self.add_item(checkout)
        self.add_item(clear)

    async def _owner_ok(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("That's someone else's cart! Run `/blackmarket list` for your own."),
                ephemeral=True)
            return False
        return True

    async def _checkout(self, interaction):
        if not await self._owner_ok(interaction):
            return
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        cart = BM_CARTS.get(self.owner_id, {})
        if not cart:
            await interaction.response.send_message(
                embed=err_embed('Your cart is empty.'), ephemeral=True)
            return
        stock = {r["item_id"]: r["qty_left"] for r in ensure_bm_stock(conn)}
        problems = []
        for it, q in cart.items():
            if stock.get(it, 0) < q:
                problems.append(f"{disp.item(it)}: only {stock.get(it, 0)} left in stock")
        total = logic.bm_cart_total(cart)
        if p["gold"] < total:
            problems.append(f"Not enough gold! Need {total}, you have {p['gold']}")
        if problems:
            await interaction.response.send_message(
                embed=err_embed("Checkout failed:\n" + "\n".join(problems) + "\nYour cart is kept."),
                ephemeral=True)
            return
        p["gold"] -= total
        db.save_player(conn, p)
        for it, q in cart.items():
            db.add_item(conn, p["user_id"], it, q)
            conn.execute(
                "UPDATE bm_stock SET qty_left = qty_left - ? WHERE date = ? AND item_id = ?",
                (q, logic.today_wib(), it))
        conn.commit()
        BM_CARTS[self.owner_id] = {}
        bought = ", ".join(f"{disp.item(it)} x{q}" for it, q in cart.items())
        await interaction.response.edit_message(
            embed=emb('🕶️ Black Market',
                      f"Shady deal done: {bought} for {total} gold. Gold left: {p['gold']}.",
                      color=COLOR_ECONOMY),
            view=None)

    async def _clear(self, interaction):
        if not await self._owner_ok(interaction):
            return
        BM_CARTS[self.owner_id] = {}
        await interaction.response.edit_message(embed=bm_cart_embed(self.owner_id), view=self)


class BMQtyView(discord.ui.View):
    """Pilih jumlah buat satu item Black Market, lalu masuk keranjang."""

    def __init__(self, owner_id, item_id, stock):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self.item_id = item_id
        self.stock = stock
        self.qty = 1
        self.minus = discord.ui.Button(label="−", style=discord.ButtonStyle.secondary)
        self.minus.callback = self._minus
        self.qty_btn = discord.ui.Button(label="x1", style=discord.ButtonStyle.primary, disabled=True)
        self.plus = discord.ui.Button(label="+", style=discord.ButtonStyle.secondary)
        self.plus.callback = self._plus
        self.add_btn = discord.ui.Button(label="Add to cart", style=discord.ButtonStyle.success, emoji="🛒")
        self.add_btn.callback = self._add
        for b in (self.minus, self.qty_btn, self.plus, self.add_btn):
            self.add_item(b)
        self._sync()

    def _sync(self):
        self.qty_btn.label = f"x{self.qty}"
        self.minus.disabled = self.qty <= 1
        self.plus.disabled = self.qty >= self.stock

    def _embed(self):
        price = logic.bm_price(self.item_id)
        return emb('🕶️ Black Market',
                   f"{disp.item(self.item_id)} — {price} gold each (stock {self.stock}).\n"
                   f"Buying x{self.qty} = {price * self.qty} gold.",
                   color=COLOR_ECONOMY)

    async def _owner_ok(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("That's someone else's market! Run `/blackmarket list` for your own."),
                ephemeral=True)
            return False
        return True

    async def _minus(self, interaction):
        if not await self._owner_ok(interaction):
            return
        self.qty = logic.bm_clamp_qty(self.qty - 1, self.stock)
        self._sync()
        await interaction.response.edit_message(embed=self._embed(), view=self)

    async def _plus(self, interaction):
        if not await self._owner_ok(interaction):
            return
        self.qty = logic.bm_clamp_qty(self.qty + 1, self.stock)
        self._sync()
        await interaction.response.edit_message(embed=self._embed(), view=self)

    async def _add(self, interaction):
        if not await self._owner_ok(interaction):
            return
        cart = BM_CARTS.setdefault(self.owner_id, {})
        cart[self.item_id] = logic.bm_clamp_qty(
            cart.get(self.item_id, 0) + self.qty, self.stock)
        await interaction.response.edit_message(
            embed=bm_cart_embed(self.owner_id), view=BMCartView(self.owner_id))


class BlackMarketView(discord.ui.View):
    """Daftar Black Market gaya kolom inventory: satu tombol Buy per item
    + tombol keranjang. Hanya pemilik daftar yang bisa klik tombolnya."""

    def __init__(self, owner_id, stock_rows):
        super().__init__(timeout=300)
        self.owner_id = owner_id
        for row in stock_rows:
            btn = discord.ui.Button(
                label=f"Buy {disp.item(row['item_id'])}"[:80],
                style=discord.ButtonStyle.primary, emoji="🕶️")

            async def _buy(interaction, item_id=row["item_id"]):
                if interaction.user.id != self.owner_id:
                    await interaction.response.send_message(
                        embed=err_embed("That's someone else's market! Run `/blackmarket list` for your own."),
                        ephemeral=True)
                    return
                conn = get_conn()
                stock = {r["item_id"]: r["qty_left"] for r in ensure_bm_stock(conn)}
                left = stock.get(item_id, 0)
                if left <= 0:
                    await interaction.response.send_message(
                        embed=err_embed(f"{disp.item(item_id)} is out of stock today."),
                        ephemeral=True)
                    return
                view = BMQtyView(self.owner_id, item_id, left)
                await interaction.response.send_message(
                    embed=view._embed(), view=view, ephemeral=True)

            btn.callback = _buy
            self.add_item(btn)
        cart_btn = discord.ui.Button(label="Cart", style=discord.ButtonStyle.secondary, emoji="🛒")
        cart_btn.callback = self._cart
        self.add_item(cart_btn)

    async def _cart(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=err_embed("That's someone else's cart! Run `/blackmarket list` for your own."),
                ephemeral=True)
            return
        await interaction.response.send_message(
            embed=bm_cart_embed(self.owner_id), view=BMCartView(self.owner_id), ephemeral=True)


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Buy weapons, armor, potions at the shop")
    @app_commands.describe(aksi="list/buy", item="Item name", jumlah="Amount")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="buy", value="buy"),
    ])
    @app_commands.rename(aksi="action", jumlah="amount")
    async def shop(self, interaction: discord.Interaction, aksi: str, item: str = "", jumlah: int = 1):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        stock = list(SHOP_STOCK)
        for _name, ev in logic.active_events():
            for it in ev["shop"]:
                if it not in stock:
                    stock.append(it)
        if aksi == "list":
            await interaction.response.send_message(embed=emb('🛒 Shop',
                "\n".join(item_line(i) for i in stock) +
                "\n\n" + 'Buy with `/shop buy <item name> <amount>`.',
                color=COLOR_ECONOMY))
            return
        item = disp.resolve_item(item) or item.lower()
        if item not in stock:
            await interaction.response.send_message(
                embed=err_embed("That item isn't sold in the shop."), ephemeral=True)
            return
        total = ITEMS[item]["price"] * max(1, jumlah)
        if p["gold"] < total:
            await interaction.response.send_message(
                embed=err_embed('Not enough gold! Need {total}, you have {gold}.'.format(total=total,gold=p['gold'])),
                ephemeral=True)
            return
        p["gold"] -= total
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], item, max(1, jumlah))
        await interaction.response.send_message(
            embed=emb('🛒 Purchase Successful',
                      'You bought {item} x{qty} for {total} gold. Gold left: {gold}.'.format(item=disp.item(item), qty=jumlah, total=total, gold=p['gold']),
                      color=COLOR_ECONOMY))

    def _bm_today(self, conn):
        return ensure_bm_stock(conn)

    @app_commands.command(name="blackmarket", description="Rare & forbidden items, limited daily stock")
    @app_commands.describe(aksi="list/buy", item="Item name", jumlah="Amount (for buy)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="buy", value="buy"),
    ])
    @app_commands.rename(aksi="action", jumlah="amount")
    async def blackmarket(self, interaction: discord.Interaction, aksi: str, item: str = "", jumlah: int = 1):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        stock = self._bm_today(conn)
        if aksi == "list":
            lines = []
            for s in stock:
                price = logic.bm_price(s["item_id"])
                lines.append(f"{disp.item(s['item_id'])} — {price} gold (stock {s['qty_left']})")
            await interaction.response.send_message(embed=emb('🕶️ Black Market (resets daily)',
                "\n".join(lines) + "\n\n" + "Tap Buy under an item to pick a quantity and add it to your cart, then check out from 🛒 Cart.\nPsst... don't tell anyone, ok.",
                color=COLOR_ECONOMY),
                view=BlackMarketView(interaction.user.id, stock))
            return
        item = disp.resolve_item(item) or item.lower()
        jumlah = max(1, jumlah)
        row = next((s for s in stock if s["item_id"] == item), None)
        if not row or row["qty_left"] < jumlah:
            await interaction.response.send_message(
                embed=err_embed("That item doesn't exist / not enough stock today (left: {left}).".format(left=row["qty_left"] if row else 0)),
                ephemeral=True)
            return
        price = logic.bm_price(item)
        total = price * jumlah
        if p["gold"] < total:
            await interaction.response.send_message(
                embed=err_embed('Not enough gold! Need {total}, you have {gold}.'.format(total=total, gold=p['gold'])), ephemeral=True)
            return
        p["gold"] -= total
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], item, jumlah)
        conn.execute(
            "UPDATE bm_stock SET qty_left = qty_left - ? WHERE date = ? AND item_id = ?",
            (jumlah, logic.today_wib(), item))
        conn.commit()
        await interaction.response.send_message(
            embed=emb("🕶️ Black Market",
                      'Shady deal done: {item} x{qty} for {total} gold. Gold left: {gold}.'.format(item=disp.item(item), qty=jumlah, total=total, gold=p['gold']),
                      color=COLOR_ECONOMY))

    @app_commands.command(name="craft", description="Combine items into stronger weapons/armor")
    @app_commands.describe(hasil="Item to craft")
    @app_commands.rename(hasil="result")
    async def craft(self, interaction: discord.Interaction, hasil: str):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        hasil = disp.resolve_item(hasil) or hasil.lower()
        if hasil not in RECIPES:
            await interaction.response.send_message(
                embed=err_embed('Unknown recipe. Available recipes: {recipes}.'.format(recipes=", ".join(disp.item(r) for r in RECIPES))),
                ephemeral=True)
            return
        recipe = RECIPES[hasil]
        missing = []
        for need_item, need_qty in recipe["needs"].items():
            if db.item_qty(conn, p["user_id"], need_item) < need_qty:
                missing.append(f"{disp.item(need_item)} x{need_qty}")
        if missing:
            await interaction.response.send_message(
                embed=err_embed('Missing materials: {missing}.'.format(missing=", ".join(missing))),
                ephemeral=True)
            return
        if p["gold"] < recipe["gold"]:
            await interaction.response.send_message(
                embed=err_embed('Not enough gold! Need {gold} for the crafting fee.'.format(gold=recipe['gold'])),
                ephemeral=True)
            return
        for need_item, need_qty in recipe["needs"].items():
            db.remove_item(conn, p["user_id"], need_item, need_qty)
        p["gold"] -= recipe["gold"]
        p["crafts"] += 1
        db.save_player(conn, p)
        db.add_item(conn, p["user_id"], hasil, 1)
        sync_quests(conn, p)
        await interaction.response.send_message(
            embed=emb('🔨 Craft Successful!', 'You got **{item}**.'.format(item=disp.item(hasil)),
                      color=COLOR_ECONOMY))

    @app_commands.command(name="gacha", description="Pull rare items/pets with gold")
    @app_commands.describe(jumlah="1x (200 gold) or 10x (1800 gold)")
    @app_commands.choices(jumlah=[
        app_commands.Choice(name="1x", value=1),
        app_commands.Choice(name="10x", value=10),
    ])
    @app_commands.rename(jumlah="amount")
    async def gacha(self, interaction: discord.Interaction, jumlah: int):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        cost = 200 if jumlah == 1 else 1800
        if p["gold"] < cost:
            await interaction.response.send_message(
                embed=err_embed('Not enough gold! Need {price}.'.format(price=cost)), ephemeral=True)
            return
        p["gold"] -= cost
        db.save_player(conn, p)
        results = []
        for _ in range(jumlah):
            rarity = logic.gacha_roll(logic.vip_active(p))
            item = random.choice(GACHA_POOL[rarity])
            db.add_item(conn, p["user_id"], item, 1)
            results.append(f"{rarity} — {disp.item(item)}")
        await interaction.response.send_message(embed=emb('🎰 Gacha!',
            'You pulled {n}x (paid {cost} gold):'.format(n=jumlah,cost=cost) + "\n" + "\n".join(results),
            color=COLOR_ECONOMY))

    @app_commands.command(name="trade", description="Trade items with other players")
    @app_commands.describe(aksi="offer/accept/decline/list", target="Opponent player: mention or user ID (for offer)",
                           tawar_item="Item you offer", tawar_jumlah="Offered item amount",
                           minta_item="Item you request", minta_jumlah="Requested item amount",
                           trade_id="Trade ID (for accept/decline)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="offer", value="offer"),
        app_commands.Choice(name="accept", value="accept"),
        app_commands.Choice(name="decline", value="decline"),
        app_commands.Choice(name="list", value="list"),
    ])
    @app_commands.rename(aksi="action", tawar_item="offer_item", tawar_jumlah="offer_amount", minta_item="request_item", minta_jumlah="request_amount")
    async def trade(self, interaction: discord.Interaction, aksi: str,
                    target: discord.User = None, tawar_item: str = "",
                    tawar_jumlah: int = 1, minta_item: str = "",
                    minta_jumlah: int = 1, trade_id: int = 0):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if aksi == "list":
            rows = conn.execute(
                "SELECT * FROM trades WHERE (from_id = ? OR to_id = ?) AND status = 'pending'",
                (p["user_id"], p["user_id"])).fetchall()
            if not rows:
                await interaction.response.send_message(
                    embed=err_embed('No pending trades.'), ephemeral=True)
                return
            lines = ['ID {id}: {frm} offers {oi} x{oq}, asks {wi} x{wq} from {to}'.format(id=r['id'], frm=r['from_id'], oi=disp.item(r['offer_item']), oq=r['offer_qty'], wi=disp.item(r['want_item']), wq=r['want_qty'], to=r['to_id']) for r in rows]
            await interaction.response.send_message(
                embed=emb('🔄 Pending Trades', "\n".join(lines), color=COLOR_ECONOMY))
            return
        if aksi == "offer":
            if not target or target.bot or target.id == p["user_id"]:
                await interaction.response.send_message(
                    embed=err_embed('Pick another valid player.'), ephemeral=True)
                return
            if not db.get_player(conn, target.id):
                await interaction.response.send_message(
                    embed=err_embed("That player hasn't registered a character."), ephemeral=True)
                return
            tawar_item = disp.resolve_item(tawar_item) or tawar_item.lower()
            minta_item = disp.resolve_item(minta_item) or minta_item.lower()
            if tawar_item not in ITEMS or minta_item not in ITEMS:
                await interaction.response.send_message(
                    embed=err_embed('Unknown item name.'), ephemeral=True)
                return
            if db.item_qty(conn, p["user_id"], tawar_item) < max(1, tawar_jumlah):
                await interaction.response.send_message(
                    embed=err_embed("You don't have enough of the offered item."), ephemeral=True)
                return
            cur = conn.execute(
                "INSERT INTO trades (from_id, to_id, offer_item, offer_qty, want_item, want_qty, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, strftime('%s','now'))",
                (p["user_id"], target.id, tawar_item, max(1, tawar_jumlah),
                 minta_item, max(1, minta_jumlah)))
            conn.commit()
            await interaction.response.send_message(
                embed=emb('🔄 Trade Offer',
                          "{mention}, you've been offered a trade!\n**{name}** offers {oi} x{oq} and asks for {wi} x{wq}.\nAccept/decline with the buttons below, or use `/trade accept {tid}`.".format(mention=target.mention, name=p['name'], oi=disp.item(tawar_item), oq=max(1, tawar_jumlah), wi=disp.item(minta_item), wq=max(1, minta_jumlah), tid=cur.lastrowid),
                          color=COLOR_ECONOMY),
                view=TradeView(cur.lastrowid, target.id))
            return
        # accept / decline (logika sama dipakai tombol TradeView)
        if aksi == "decline":
            ok, text = execute_trade_decline(conn, trade_id, p["user_id"])
            if ok:
                await interaction.response.send_message(
                    embed=emb('🔄 Trade', text, color=COLOR_ECONOMY))
            else:
                await interaction.response.send_message(
                    embed=err_embed(text), ephemeral=True)
            return
        ok, text = execute_trade_accept(conn, trade_id, p["user_id"])
        if ok:
            await interaction.response.send_message(
                embed=emb('🔄 Trade', text, color=COLOR_ECONOMY))
        else:
            await interaction.response.send_message(
                embed=err_embed(text), ephemeral=True)

    @app_commands.command(name="tradeboard", description="Player-to-player buy/sell board")
    @app_commands.describe(aksi="sell/list/buy", item="Item name (for sell)",
                           jumlah="Amount", harga="Total gold price (for sell)",
                           listing_id="Listing ID (for buy)")
    @app_commands.choices(aksi=[
        app_commands.Choice(name="sell", value="sell"),
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="buy", value="buy"),
    ])
    @app_commands.rename(aksi="action", jumlah="amount", harga="price")
    async def tradeboard(self, interaction: discord.Interaction, aksi: str,
                         item: str = "", jumlah: int = 1, harga: int = 0,
                         listing_id: int = 0):
        conn = get_conn()
        p = await need_player(interaction, conn)
        if not p:
            return
        if aksi == "list":
            rows = conn.execute("SELECT * FROM listings ORDER BY id DESC LIMIT 20").fetchall()
            if not rows:
                await interaction.response.send_message(
                    embed=emb('📋 Tradeboard','The board is still empty. Sell an item with `/tradeboard sell`.',
                              color=COLOR_ECONOMY),
                    ephemeral=True)
                return
            lines = []
            for r in rows:
                seller = db.get_player(conn, r["seller_id"])
                sname = seller["name"] if seller else str(r["seller_id"])
                lines.append('ID {id}: {item} x{qty} — {price} gold (by {seller})'.format(id=r['id'], item=disp.item(r['item_id']), qty=r['qty'], price=r['price'], seller=sname))
            await interaction.response.send_message(
                embed=emb('📋 Tradeboard', "\n".join(lines), color=COLOR_ECONOMY))
            return
        if aksi == "sell":
            item = disp.resolve_item(item) or item.lower()
            if item not in ITEMS:
                await interaction.response.send_message(
                    embed=err_embed('Unknown item.'), ephemeral=True)
                return
            if harga <= 0:
                await interaction.response.send_message(
                    embed=err_embed('Price must be > 0 gold.'), ephemeral=True)
                return
            if not db.remove_item(conn, p["user_id"], item, max(1, jumlah)):
                await interaction.response.send_message(
                    embed=err_embed("You don't have enough stock."), ephemeral=True)
                return
            cur = conn.execute(
                "INSERT INTO listings (seller_id, item_id, qty, price, created_at)"
                " VALUES (?, ?, ?, ?, strftime('%s','now'))",
                (p["user_id"], item, max(1, jumlah), harga))
            conn.commit()
            await interaction.response.send_message(
                embed=emb('📋 Tradeboard',
                          '{item} x{qty} listed on the tradeboard for {price} gold (ID {id}).'.format(item=disp.item(item), qty=jumlah, price=harga, id=cur.lastrowid),
                          color=COLOR_ECONOMY))
            return
        row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
        if not row:
            await interaction.response.send_message(
            embed=err_embed('Listing not found.'), ephemeral=True)
            return
        row = dict(row)
        if row["seller_id"] == p["user_id"]:
            await interaction.response.send_message(
                embed=err_embed("That's your own listing."), ephemeral=True)
            return
        if p["gold"] < row["price"]:
            await interaction.response.send_message(
                embed=err_embed('Not enough gold! Need {price}.'.format(price=row['price'])), ephemeral=True)
            return
        p["gold"] -= row["price"]
        db.save_player(conn, p)
        seller = db.get_player(conn, row["seller_id"])
        if seller:
            seller["gold"] += row["price"]
            seller["gold_earned"] += row["price"]
            db.save_player(conn, seller)
        db.add_item(conn, p["user_id"], row["item_id"], row["qty"])
        conn.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
        conn.commit()
        await interaction.response.send_message(
            embed=emb('🛒 Purchase Successful',
                      'You bought {item} x{qty} for {price} gold!'.format(item=disp.item(row['item_id']), qty=row['qty'], price=row['price']),
                      color=COLOR_ECONOMY))


async def setup(bot):
    await bot.add_cog(Economy(bot))
