# -*- coding: utf-8 -*-
"""Hospital system (phase 2 refinement).

Replaces instant healing after a loss: a defeated player is ADMITTED
to the hospital instead of getting HP back on the spot. Healing is
over time at a fixed rate, computed LAZILY from the admission row —
no background loop, restart-safe (admitted_at is stored).

Rules:
- Admission: monster defeat (FightView) and PvP when the winner picks
  "Rumah Sakit". The old instant 20% HP restore on monster defeat is
  GONE: defeat now admits with HP 0 and healing starts from there.
- Rate: 10 HP per whole minute since admission, capped at max HP.
- Discharge: the patient may leave once HP is at least 25% of max HP
  (manual /hospital leave). Staying longer keeps healing up to full
  HP; reaching full HP auto-discharges on the next player load.
- While admitted, the player cannot start fights, raids, or PvP duels
  (enforced in battle.py gates). Jobs, shop, transfers, and item use
  stay open — that is how friends help: /transfer sends medicine and
  the patient uses it from inventory.
- Healing items bypass the wait: apply_use_item (core.py) discharges
  the patient immediately once a potion pushes HP to 25% or more.
- HP governance while admitted: common.load_player syncs stored HP to
  the lazily computed value AFTER stamina/decay, so hunger/thirst
  still decay but HP drain from starvation does not fight hospital
  healing — hospital healing alone governs HP until discharge.
"""
import time

HEAL_PER_MIN = 10
DISCHARGE_NUM = 1  # 25% = 1/4 of max HP (integer-safe: hp*4 >= max_hp)
DISCHARGE_DEN = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS hospital_admissions (
    user_id INTEGER PRIMARY KEY,
    admitted_at INTEGER NOT NULL,
    hp_at_admission INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT 'defeat',
    admitted_by INTEGER
);
"""


def ensure_tables(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def now():
    return int(time.time())


def _row(row):
    return dict(row) if row is not None else None


def admit(conn, user_id, hp, reason="defeat", admitted_by=None, ts=None):
    """Admit a player. If already admitted, the original admission is
    kept (no timer reset) and the existing row is returned."""
    existing = get_admission(conn, user_id)
    if existing is not None:
        return existing
    ts = int(ts if ts is not None else now())
    conn.execute(
        "INSERT INTO hospital_admissions (user_id, admitted_at, "
        "hp_at_admission, reason, admitted_by) VALUES (?, ?, ?, ?, ?)",
        (user_id, ts, int(hp), reason, admitted_by))
    conn.commit()
    return get_admission(conn, user_id)


def get_admission(conn, user_id):
    return _row(conn.execute(
        "SELECT * FROM hospital_admissions WHERE user_id = ?",
        (user_id,)).fetchone())


def computed_hp(admission, max_hp, ts=None):
    """HP right now: admission HP + 10 per whole minute elapsed,
    capped at max HP. Pure function of the stored row — no side effects."""
    ts = int(ts if ts is not None else now())
    minutes = max(0, (ts - admission["admitted_at"]) // 60)
    return min(int(max_hp), int(admission["hp_at_admission"])
               + HEAL_PER_MIN * minutes)


def can_leave(hp, max_hp):
    """Discharge threshold: HP at least 25% of max HP (integer-safe)."""
    return int(hp) * DISCHARGE_DEN >= int(max_hp) * DISCHARGE_NUM


def minutes_to_discharge(admission, max_hp, ts=None):
    """Whole minutes until the patient may leave (0 if already able).
    Ceiling division: even 1 HP short of the threshold needs a minute."""
    ts = int(ts if ts is not None else now())
    hp = computed_hp(admission, max_hp, ts)
    threshold = (int(max_hp) * DISCHARGE_NUM + DISCHARGE_DEN - 1) // DISCHARGE_DEN
    if hp >= threshold:
        return 0
    return (threshold - hp + HEAL_PER_MIN - 1) // HEAL_PER_MIN


def minutes_to_full(admission, max_hp, ts=None):
    """Whole minutes until full HP (0 if already full)."""
    ts = int(ts if ts is not None else now())
    hp = computed_hp(admission, max_hp, ts)
    if hp >= max_hp:
        return 0
    return (int(max_hp) - hp + HEAL_PER_MIN - 1) // HEAL_PER_MIN


def discharge(conn, user_id):
    conn.execute(
        "DELETE FROM hospital_admissions WHERE user_id = ?", (user_id,))
    conn.commit()


def sync_patient(conn, player, ts=None):
    """Sync a loaded player's stored HP to the lazily computed hospital
    value. Returns (status, hp): status is 'admitted', 'discharged'
    (reached full HP, row removed), or None (not admitted).

    Callers must save the player row afterwards when status is not
    None and hp changed. The discharge DELETE is committed here.
    """
    adm = get_admission(conn, player["user_id"])
    if adm is None:
        return None, player["hp"]
    ts = int(ts if ts is not None else now())
    hp = computed_hp(adm, player["max_hp"], ts)
    if hp >= player["max_hp"]:
        discharge(conn, player["user_id"])
        player["hp"] = player["max_hp"]
        return "discharged", player["hp"]
    player["hp"] = hp
    return "admitted", hp
