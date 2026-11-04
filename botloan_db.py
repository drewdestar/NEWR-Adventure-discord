# -*- coding: utf-8 -*-
"""Bot loans: gold borrowed directly from the bot.

Deliberately separate from friend-to-friend loans (friends_db.loans):
its own bot_loans table, its own /botloan command group. Rules:
one outstanding bot loan per player, cap 100 gold x level (minimum
100), flat 10% interest shown upfront, the borrower confirms the
exact terms before any gold moves, full repayment only. Bot debt
MUST be repaid: repaying deducts the full amount even if the balance
goes negative — negative gold balances are allowed for debtors and
are never clamped back to zero. A negative balance counts as
outstanding debt and blocks any new bot loan until it is earned back
to 0 or more (jobs stay open for debtors, so they can earn their way
out). Nothing else is seized: no items or pets are ever taken.
"""
import time


def ensure_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            principal INTEGER NOT NULL,
            interest INTEGER NOT NULL,
            total_due INTEGER NOT NULL,
            borrowed_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            repaid_at INTEGER
        )
    """)
    conn.commit()


def now():
    return int(time.time())


def loan_cap(level):
    """Max borrowable gold: 100 x level, at least 100."""
    return max(100, 100 * int(level))


def loan_terms(principal):
    """(interest, total_due) for a principal at flat 10% (rounded down)."""
    principal = int(principal)
    interest = principal * 10 // 100
    return interest, principal + interest


def get_active_loan(conn, user_id):
    return conn.execute(
        "SELECT * FROM bot_loans WHERE user_id = ? AND status = 'active' "
        "ORDER BY id LIMIT 1", (user_id,)).fetchone()


def can_borrow(gold, active_loan):
    """Borrowing is blocked by an active loan OR a negative balance.

    A negative balance is outstanding bot debt: it must be earned back
    to 0 or more before the player can borrow again.
    """
    return active_loan is None and int(gold) >= 0


def create_loan(conn, user_id, principal, interest, total_due):
    cur = conn.execute(
        "INSERT INTO bot_loans (user_id, principal, interest, total_due, "
        "borrowed_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, principal, interest, total_due, now()))
    conn.commit()
    return cur.lastrowid


def repay_loan(conn, loan_id):
    conn.execute(
        "UPDATE bot_loans SET status = 'repaid', repaid_at = ? WHERE id = ?",
        (now(), loan_id))
    conn.commit()
