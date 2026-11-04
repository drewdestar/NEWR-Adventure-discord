# -*- coding: utf-8 -*-
"""Guild economy + personal bank + tax pool (phase 2).

Own tables only — never modifies database.py tables, only reads/writes
player rows through database helpers. All timestamps are Unix seconds.
Call ensure_tables(conn) once per handler before using any table here.

Rules (user-confirmed, see the cog docstrings for the user-facing text):
- Guild bank: guild-owned stock. Deposits by any member; withdrawals and
  marketplace listings are leader-only. Every deposit is recorded per
  player (feeds the donor leaderboards).
- Guild loans: a member borrows gold and/or items from their guild's
  bank. The guild leader approves (button DM, or /guildloan approve).
  Cap = whatever the bank currently holds. Gold loans carry flat 10%
  interest; item loans are returned as-is (no interest on items).
  Full repayment only. Unpaid guild debt follows the bot-debt rule:
  the balance may go negative, jobs stay open, and no new guild or bot
  loan is possible until the debt is cleared (active loan gone AND
  balance back to 0 or more).
- Personal bank (/bank): banked gold is separate from carried gold.
  Only carried gold is ever touched by shop/craft/gacha, monster-defeat
  loss, or PvP steals — banked gold is safe from all of them. Interest
  is 1% per whole day on the banked balance, accrued lazily whenever
  the balance is read or moved (restart-safe: last_accrual is stored).
  Withdraw anytime; players must withdraw before spending.
- Marketplace: the leader lists guild-bank items at a set price. ANY
  registered player may buy (guild member or outsider). On each sale
  10% of the price goes to the central bot tax pool and 90% to the
  selling guild's bank. Every sale is recorded in the tax ledger with
  buyer, buyer guild, and seller guild.
- Tax giveaways: paid from the tax pool, run by admins. Prize total
  must fit the pool; winners are drawn from registered players.
"""
import time

GUILD_LOAN_INTEREST_PCT = 10
MARKET_TAX_PCT = 10
BANK_INTEREST_PCT = 1  # percent per whole day on banked gold
WAR_BANK_PRIZE = 1000  # gold to the winning guild's bank per war win

SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_bank (
    guild_id INTEGER PRIMARY KEY,
    gold INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_bank_items (
    guild_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, item_id)
);
CREATE TABLE IF NOT EXISTS guild_bank_pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    species TEXT NOT NULL,
    name TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    exp INTEGER NOT NULL DEFAULT 0,
    gear_weapon TEXT,
    gear_armor TEXT,
    depositor_id INTEGER NOT NULL,
    deposited_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_bank_deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    item_id TEXT,
    qty INTEGER NOT NULL DEFAULT 0,
    gold INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    borrower_id INTEGER NOT NULL,
    gold_principal INTEGER NOT NULL DEFAULT 0,
    gold_interest INTEGER NOT NULL DEFAULT 0,
    gold_total_due INTEGER NOT NULL DEFAULT 0,
    item_id TEXT,
    item_qty INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL DEFAULT 0,
    approved_at INTEGER,
    repaid_at INTEGER
);
CREATE TABLE IF NOT EXISTS personal_bank (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0,
    last_accrual INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tax_pool (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tax_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_id INTEGER NOT NULL,
    buyer_guild_id INTEGER,
    seller_guild_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    sale_price INTEGER NOT NULL DEFAULT 0,
    tax INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tax_giveaways (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_gold INTEGER NOT NULL DEFAULT 0,
    per_winner INTEGER NOT NULL DEFAULT 0,
    winners_count INTEGER NOT NULL DEFAULT 0,
    winners TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS guild_market_listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    price INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    created_at INTEGER NOT NULL DEFAULT 0
);
"""


def ensure_tables(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def now():
    return int(time.time())


def _row(row):
    return dict(row) if row is not None else None


# ------------------------------------------------------------ pure rules
def guild_loan_terms(principal):
    """(interest, total_due) for a gold principal at flat 10% (floor)."""
    principal = int(principal)
    interest = principal * GUILD_LOAN_INTEREST_PCT // 100
    return interest, principal + interest


def market_split(price):
    """(tax, guild_gets) for a sale price at 10% tax (floor)."""
    price = int(price)
    tax = price * MARKET_TAX_PCT // 100
    return tax, price - tax


def bank_interest(balance, whole_days):
    """Interest on a banked balance: 1% per whole day (floor)."""
    return int(balance) * BANK_INTEREST_PCT * int(whole_days) // 100


def split_prize(total, winners_count):
    """(per_winner, remainder): equal split, remainder stays in the pool."""
    winners_count = max(1, int(winners_count))
    per_winner = int(total) // winners_count
    return per_winner, int(total) - per_winner * winners_count


# ------------------------------------------------------------ guild bank
def bank_gold(conn, guild_id):
    row = conn.execute(
        "SELECT gold FROM guild_bank WHERE guild_id = ?",
        (guild_id,)).fetchone()
    return row["gold"] if row else 0


def add_bank_gold(conn, guild_id, delta):
    """Adjust a guild's bank gold (creates the row if missing). Never
    clamps: the war prize and marketplace income only ever add."""
    conn.execute(
        "INSERT INTO guild_bank (guild_id, gold) VALUES (?, ?) "
        "ON CONFLICT(guild_id) DO UPDATE SET gold = gold + excluded.gold",
        (guild_id, int(delta)))
    conn.commit()
    return bank_gold(conn, guild_id)


def bank_items(conn, guild_id):
    rows = conn.execute(
        "SELECT * FROM guild_bank_items WHERE guild_id = ? AND qty > 0 "
        "ORDER BY item_id", (guild_id,)).fetchall()
    return [_row(r) for r in rows]


def bank_item_qty(conn, guild_id, item_id):
    row = conn.execute(
        "SELECT qty FROM guild_bank_items WHERE guild_id = ? AND item_id = ?",
        (guild_id, item_id)).fetchone()
    return row["qty"] if row else 0


def add_bank_item(conn, guild_id, item_id, qty):
    conn.execute(
        "INSERT INTO guild_bank_items (guild_id, item_id, qty) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id, item_id) DO UPDATE SET qty = qty + excluded.qty",
        (guild_id, item_id, int(qty)))
    conn.commit()


def take_bank_item(conn, guild_id, item_id, qty):
    """Remove qty from bank stock. Returns False if stock is short."""
    if bank_item_qty(conn, guild_id, item_id) < qty:
        return False
    conn.execute(
        "UPDATE guild_bank_items SET qty = qty - ? "
        "WHERE guild_id = ? AND item_id = ?",
        (qty, guild_id, item_id))
    conn.commit()
    return True


def bank_pets(conn, guild_id):
    rows = conn.execute(
        "SELECT * FROM guild_bank_pets WHERE guild_id = ? ORDER BY id",
        (guild_id,)).fetchall()
    return [_row(r) for r in rows]


def record_deposit(conn, guild_id, user_id, kind, item_id=None, qty=0,
                   gold=0):
    conn.execute(
        "INSERT INTO guild_bank_deposits (guild_id, user_id, kind, item_id, "
        "qty, gold, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (guild_id, user_id, kind, item_id, int(qty), int(gold), now()))
    conn.commit()


# ------------------------------------------------------------ guild loans
def get_guild_loan(conn, loan_id):
    return _row(conn.execute(
        "SELECT * FROM guild_loans WHERE id = ?", (loan_id,)).fetchone())


def get_active_guild_loan(conn, user_id):
    return _row(conn.execute(
        "SELECT * FROM guild_loans WHERE borrower_id = ? AND status IN "
        "('pending', 'active') ORDER BY id LIMIT 1", (user_id,)).fetchone())


def get_active_guild_loans_for_guild(conn, guild_id):
    rows = conn.execute(
        "SELECT * FROM guild_loans WHERE guild_id = ? AND status IN "
        "('pending', 'active') ORDER BY id", (guild_id,)).fetchall()
    return [_row(r) for r in rows]


def create_guild_loan(conn, guild_id, borrower_id, gold_principal, item_id,
                      item_qty):
    interest, total = guild_loan_terms(gold_principal)
    cur = conn.execute(
        "INSERT INTO guild_loans (guild_id, borrower_id, gold_principal, "
        "gold_interest, gold_total_due, item_id, item_qty, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (guild_id, borrower_id, int(gold_principal), interest, total,
         item_id or None, int(item_qty), now()))
    conn.commit()
    return cur.lastrowid


def approve_guild_loan(conn, loan_id):
    conn.execute(
        "UPDATE guild_loans SET status = 'active', approved_at = ? "
        "WHERE id = ?", (now(), loan_id))
    conn.commit()


def decline_guild_loan(conn, loan_id):
    conn.execute(
        "UPDATE guild_loans SET status = 'declined' WHERE id = ?",
        (loan_id,))
    conn.commit()


def repay_guild_loan(conn, loan_id):
    conn.execute(
        "UPDATE guild_loans SET status = 'repaid', repaid_at = ? "
        "WHERE id = ?", (now(), loan_id))
    conn.commit()


def has_guild_debt(conn, user_id):
    """True if the player owes anything on a guild loan (pending/active
    rows are open debt, same as an active bot loan)."""
    return get_active_guild_loan(conn, user_id) is not None


# ------------------------------------------------------------ personal bank
def _bank_row(conn, user_id, ts):
    row = conn.execute(
        "SELECT * FROM personal_bank WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO personal_bank (user_id, balance, last_accrual) "
            "VALUES (?, 0, ?)", (user_id, ts))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM personal_bank WHERE user_id = ?",
            (user_id,)).fetchone()
    return dict(row)


def accrue_bank(conn, user_id, ts=None):
    """Apply 1%/day interest for whole days elapsed since last accrual.

    Returns (balance, interest_just_added). Restart-safe: last_accrual
    advances by whole days only, so partial days are never lost and
    interest is never double-counted. A zero balance still advances
    the clock so a later deposit does not earn backdated interest.
    """
    ts = int(ts if ts is not None else now())
    row = _bank_row(conn, user_id, ts)
    days = (ts - row["last_accrual"]) // 86400
    interest = 0
    if days > 0:
        if row["balance"] > 0:
            interest = bank_interest(row["balance"], days)
            row["balance"] += interest
        row["last_accrual"] += days * 86400
        conn.execute(
            "UPDATE personal_bank SET balance = ?, last_accrual = ? "
            "WHERE user_id = ?",
            (row["balance"], row["last_accrual"], user_id))
        conn.commit()
    return row["balance"], interest


def bank_balance(conn, user_id, ts=None):
    """Current banked balance after accruing interest to now."""
    balance, _ = accrue_bank(conn, user_id, ts)
    return balance


# ------------------------------------------------------------ tax pool
def tax_pool_balance(conn):
    row = conn.execute(
        "SELECT balance FROM tax_pool WHERE id = 1").fetchone()
    return row["balance"] if row else 0


def add_tax(conn, amount):
    conn.execute(
        "INSERT INTO tax_pool (id, balance) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET balance = balance + excluded.balance",
        (int(amount),))
    conn.commit()
    return tax_pool_balance(conn)


def take_tax_pool(conn, amount):
    """Remove amount from the pool. Returns False if funds are short."""
    if tax_pool_balance(conn) < amount:
        return False
    conn.execute(
        "UPDATE tax_pool SET balance = balance - ? WHERE id = 1",
        (int(amount),))
    conn.commit()
    return True


def record_tax(conn, buyer_id, buyer_guild_id, seller_guild_id, item_id,
               qty, sale_price, tax):
    conn.execute(
        "INSERT INTO tax_ledger (buyer_id, buyer_guild_id, seller_guild_id, "
        "item_id, qty, sale_price, tax, created_at) VALUES (?, ?, ?, ?, ?, "
        "?, ?, ?)",
        (buyer_id, buyer_guild_id, seller_guild_id, item_id, int(qty),
         int(sale_price), int(tax), now()))
    conn.commit()


def record_tax_giveaway(conn, total_gold, per_winner, winners_count,
                        winners, created_by):
    cur = conn.execute(
        "INSERT INTO tax_giveaways (total_gold, per_winner, winners_count, "
        "winners, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (int(total_gold), int(per_winner), int(winners_count),
         ",".join(str(w) for w in winners), created_by, now()))
    conn.commit()
    return cur.lastrowid


def list_tax_giveaways(conn, limit=5):
    rows = conn.execute(
        "SELECT * FROM tax_giveaways ORDER BY id DESC LIMIT ?",
        (limit,)).fetchall()
    return [_row(r) for r in rows]


# ------------------------------------------------------------ marketplace
def create_listing(conn, guild_id, item_id, qty, price):
    cur = conn.execute(
        "INSERT INTO guild_market_listings (guild_id, item_id, qty, price, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (guild_id, item_id, int(qty), int(price), now()))
    conn.commit()
    return cur.lastrowid


def get_listing(conn, listing_id):
    return _row(conn.execute(
        "SELECT * FROM guild_market_listings WHERE id = ?",
        (listing_id,)).fetchone())


def open_listings(conn):
    rows = conn.execute(
        "SELECT * FROM guild_market_listings WHERE status = 'open' "
        "ORDER BY id").fetchall()
    return [_row(r) for r in rows]


def set_listing_status(conn, listing_id, status):
    conn.execute(
        "UPDATE guild_market_listings SET status = ? WHERE id = ?",
        (status, listing_id))
    conn.commit()


# ------------------------------------------------------------ leaderboards
def top_tax_players(conn, limit=5):
    rows = conn.execute(
        "SELECT buyer_id, SUM(tax) AS total FROM tax_ledger "
        "GROUP BY buyer_id ORDER BY total DESC LIMIT ?",
        (limit,)).fetchall()
    return [(r["buyer_id"], r["total"]) for r in rows]


def top_tax_guilds(conn, limit=5):
    rows = conn.execute(
        "SELECT buyer_guild_id, SUM(tax) AS total FROM tax_ledger "
        "WHERE buyer_guild_id IS NOT NULL GROUP BY buyer_guild_id "
        "ORDER BY total DESC LIMIT ?",
        (limit,)).fetchall()
    return [(r["buyer_guild_id"], r["total"]) for r in rows]


def top_depositors(conn, limit=5):
    """Ranked by total GOLD deposited (items/pets are tracked in bank
    info, but only gold has a single comparable value)."""
    rows = conn.execute(
        "SELECT user_id, SUM(gold) AS total FROM guild_bank_deposits "
        "WHERE kind = 'gold' GROUP BY user_id ORDER BY total DESC LIMIT ?",
        (limit,)).fetchall()
    return [(r["user_id"], r["total"]) for r in rows]


def top_depositor_guilds(conn, limit=5):
    rows = conn.execute(
        "SELECT guild_id, SUM(gold) AS total FROM guild_bank_deposits "
        "WHERE kind = 'gold' GROUP BY guild_id ORDER BY total DESC LIMIT ?",
        (limit,)).fetchall()
    return [(r["guild_id"], r["total"]) for r in rows]
