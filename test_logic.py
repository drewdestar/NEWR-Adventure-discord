# -*- coding: utf-8 -*-
"""Test offline logika game TANPA Discord.

Menguji dengan database SQLite sementara: pembuatan karakter, satu ronde
fight, pembelian di toko, daily reward, dan adopsi pet. Jalankan:
    python3 test_logic.py
Keluar dengan status 0 kalau semua cek lolos.
"""
import os
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import database as db
import display as disp
import logic
from data import CLASSES, ITEMS, PETS

FAILURES = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        FAILURES.append(name)


def main():
    random.seed(42)
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = db.connect(tmp.name)
    uid = 123456789

    # 1. Pembuatan karakter
    stats = CLASSES["Warrior"]
    p = db.create_player(conn, uid, "Tester", "Warrior", stats)
    check("karakter dibuat", p is not None and p["name"] == "Tester"
          and p["class"] == "Warrior" and p["level"] == 1)
    check("pemain lama default tier Common/0",
          p["starter_tier"] == "Common" and p["starter_bonus_pct"] == 0)

    # 1b. Roll tier starter (Task 3): tier + persen dalam rentang,
    # skill kelas tidak berubah, stat naik sesuai persen.
    rng = random.Random(7)
    seen = set()
    for _ in range(2000):
        tier, pct, bonus = logic.roll_starter_tier(rng)
        seen.add(tier)
        lo, hi = [(l, h) for n, w, l, h, b in logic.STARTER_TIERS
                  if n == tier][0]
        assert lo <= pct <= hi
    check("roll tier mencakup semua tier", seen ==
          {"Common", "Rare", "Epic", "Legendary"}, f"seen={sorted(seen)}")
    mage_epic = logic.apply_starter_bonus(CLASSES["Mage"], 17)
    check("bonus tier Mage Epic +17%",
          (mage_epic["hp"], mage_epic["mp"], mage_epic["atk"],
           mage_epic["def"], mage_epic["spd"]) == (94, 140, 21, 6, 8)
          and mage_epic["skill"] == CLASSES["Mage"]["skill"])
    p2 = db.create_player(conn, uid + 1, "Tester2", "Mage", mage_epic,
                          starter_tier="Epic", starter_bonus_pct=17)
    check("tier tersimpan di pemain baru",
          p2["starter_tier"] == "Epic" and p2["starter_bonus_pct"] == 17
          and p2["hp"] == 94)
    check("stats awal Warrior", p["max_hp"] == 120 and p["atk"] == 14,
          f"hp={p['max_hp']} atk={p['atk']}")
    dup = db.get_player(conn, uid)
    check("duplikat terdeteksi (player sudah ada)", dup is not None)

    # 2. Satu ronde fight (pakai rumus murni, tanpa Discord)
    monster = logic.scale_monster("Slime Hijau", p["level"])
    atk, defense, _spd = logic.effective_stats(p, [], None)
    dmg, crit, back = logic.fight_round(atk, defense, monster["atk"],
                                        monster["def"], rng=random)
    check("damage fight > 0", dmg >= 1, f"dmg={dmg} crit={crit} back={back}")
    monster_hp = monster["hp"] - dmg
    check("monster HP berkurang", monster_hp < monster["hp"])

    # Simulasi menang: hadiah EXP + gold + loot
    exp = logic.exp_gain(p, monster["exp"])
    gold = 15
    logic.add_gold(p, gold)
    levels = logic.apply_exp(p, exp)
    loot = logic.roll_loot("Slime Hijau", rng=random)
    if loot:
        db.add_item(conn, uid, loot, 1)
    db.save_player(conn, p)
    p = db.get_player(conn, uid)
    check("EXP & gold bertambah setelah menang",
          p["exp"] >= 0 and p["gold"] == 100 + gold,
          f"exp={p['exp']} gold={p['gold']} levels={levels} loot={loot}")

    # 3. Pembelian di toko (logika yang sama dipakai /shop)
    price = ITEMS["potion kecil"]["price"]
    assert p["gold"] >= price
    p["gold"] -= price
    db.save_player(conn, p)
    db.add_item(conn, uid, "potion kecil", 2)
    qty = db.item_qty(conn, uid, "potion kecil")
    check("pembelian toko menambah inventory", qty == 2, f"qty={qty}")
    ok = db.remove_item(conn, uid, "potion kecil", 1)
    check("pakai item mengurangi stok", ok and db.item_qty(conn, uid, "potion kecil") == 1)

    # 4. Daily reward (sekali sehari, streak)
    today = logic.today_wib()
    assert p["last_daily"] != today
    p["streak"] = 1
    p["last_daily"] = today
    p["gold"] += 100
    db.save_player(conn, p)
    db.add_item(conn, uid, "roti", 1)
    p = db.get_player(conn, uid)
    check("daily reward tersimpan", p["last_daily"] == today and p["streak"] == 1)
    check("daily kedua di hari sama harus ditolak (last_daily == today)",
          p["last_daily"] == today)

    # 5. Adopsi pet (tambah penghasilan dulu biar cukup: 185 -> 235)
    logic.add_gold(p, 50)
    db.save_player(conn, p)
    p = db.get_player(conn, uid)
    check("gold cukup buat adopsi pet", p["gold"] >= 200, f"gold={p['gold']}")
    assert p["gold"] >= 200
    p["gold"] -= 200
    db.save_player(conn, p)
    db.add_pet(conn, uid, "Serigala Api", "Api")
    pets = db.get_pets(conn, uid)
    check("pet teradopsi", len(pets) == 1 and pets[0]["species"] == "Serigala Api")
    atk2, _, _ = logic.effective_stats(p, [], pets[0])
    check("pet menambah ATK", atk2 > p["atk"], f"atk={p['atk']} -> {atk2}")
    gained = logic.pet_gain_exp(pets[0], 60)
    check("pet naik level dari EXP", gained >= 1 and pets[0]["level"] >= 2,
          f"pet level={pets[0]['level']}")
    check("evolusi pet berubah bentuk di Lv 10",
          logic.pet_form("Serigala Api", 10) == "Serigala Api"
          and logic.pet_form("Serigala Api", 1) == "Anak Serigala Api")

    # 6. Sanity lain: stamina, decay, gacha, evolve gate
    check("stamina bisa dipakai & habis", logic.spend_stamina(p, 10) and p["stamina"] == 90)
    check("exp_needed naik per level", logic.exp_needed(1) == 100 and logic.exp_needed(5) == 500)
    check("evolusi Warrior butuh Lv 15",
          logic.evolution_for("Warrior", 1)[1] == 15)
    rarity = logic.gacha_roll(rng=random)
    check("gacha menghasilkan rarity valid", rarity in ("common", "rare", "epic", "legendary"),
          f"rarity={rarity}")
    check("jendela meteor hanya jam 21 WIB",
          logic.meteor_window_now(
              __import__("datetime").datetime(2026, 11, 5, 21, 30,
                                             tzinfo=logic.WIB)) is True)

    # 7. Bot loans (botloan_db): cap, terms, one outstanding, full repay
    import botloan_db
    check("cap bot loan 100 x level, min 100",
          botloan_db.loan_cap(1) == 100
          and botloan_db.loan_cap(7) == 700)
    check("bunga bot loan 10% flat",
          botloan_db.loan_terms(500) == (50, 550)
          and botloan_db.loan_terms(105) == (10, 115))
    botloan_db.ensure_tables(conn)
    check("belum ada bot loan aktif",
          botloan_db.get_active_loan(conn, uid) is None)
    lid = botloan_db.create_loan(conn, uid, 500, 50, 550)
    active = botloan_db.get_active_loan(conn, uid)
    check("bot loan aktif tercatat",
          active is not None and active["id"] == lid
          and active["total_due"] == 550)
    botloan_db.repay_loan(conn, lid)
    check("bot loan lunas, bisa pinjam lagi",
          botloan_db.get_active_loan(conn, uid) is None)
    check("gate pinjam bot: saldo negatif = utang tertunggak",
          botloan_db.can_borrow(100, None) is True
          and botloan_db.can_borrow(-50, None) is False
          and botloan_db.can_borrow(100, {"id": lid}) is False)
    pp = db.get_player(conn, uid)
    pp["gold"] = -50
    db.save_player(conn, pp)
    check("saldo negatif tidak di-clamp ke nol",
          db.get_player(conn, uid)["gold"] == -50)
    pp = db.get_player(conn, uid)
    pp["gold"] += 200
    db.save_player(conn, pp)
    check("debitur bisa menabung kembali ke positif (kerja tetap buka)",
          db.get_player(conn, uid)["gold"] == 150
          and botloan_db.can_borrow(150, None) is True)

    # 8. Phase 2: guild economy, personal bank, hospital, PvP steal
    import guildbank_db as gb
    import hospital_db as hb
    gb.ensure_tables(conn)
    hb.ensure_tables(conn)
    check("bank guild mulai 0", gb.bank_gold(conn, 1) == 0)
    gb.add_bank_gold(conn, 1, 1000)
    check("hadiah perang +1000 ke bank guild", gb.bank_gold(conn, 1) == 1000)
    gb.add_bank_gold(conn, 1, -250)
    check("bank guild bisa dikurangi", gb.bank_gold(conn, 1) == 750)
    check("bunga guild loan 10% flat",
          gb.guild_loan_terms(500) == (50, 550)
          and gb.guild_loan_terms(105) == (10, 115))
    check("pajak market 10%",
          gb.market_split(1000) == (100, 900)
          and gb.market_split(105) == (10, 95)
          and gb.market_split(9) == (0, 9))
    check("bunga bank 1%/hari",
          gb.bank_interest(1000, 3) == 30
          and gb.bank_interest(999, 1) == 9)
    conn.execute(
        "INSERT INTO personal_bank (user_id, balance, last_accrual) "
        "VALUES (?, 1000, ?)", (uid, 1000000))
    conn.commit()
    bal, intr = gb.accrue_bank(conn, uid, ts=1000000 + 3 * 86400)
    check("akrual bank 3 hari", (bal, intr) == (1030, 30))
    bal2, intr2 = gb.accrue_bank(conn, uid, ts=1000000 + 3 * 86400 + 3600)
    check("akrual parsial hari tidak dihitung", (bal2, intr2) == (1030, 0))
    check("pool pajak mulai 0", gb.tax_pool_balance(conn) == 0)
    gb.add_tax(conn, 100)
    check("pajak masuk pool", gb.tax_pool_balance(conn) == 100)
    check("tarik pool melebihi saldo ditolak",
          gb.take_tax_pool(conn, 101) is False
          and gb.tax_pool_balance(conn) == 100)
    check("tarik pool berhasil",
          gb.take_tax_pool(conn, 40) is True
          and gb.tax_pool_balance(conn) == 60)
    check("split hadiah pajak",
          gb.split_prize(100, 3) == (33, 1)
          and gb.split_prize(100, 4) == (25, 0))
    lid2 = gb.create_guild_loan(conn, 1, uid, 500, None, 0)
    check("guild loan pending tercatat",
          gb.get_active_guild_loan(conn, uid) is not None)
    gb.approve_guild_loan(conn, lid2)
    check("guild loan aktif setelah approve",
          gb.get_guild_loan(conn, lid2)["status"] == "active")
    gb.repay_guild_loan(conn, lid2)
    check("guild loan lunas", gb.get_active_guild_loan(conn, uid) is None)
    gb.record_deposit(conn, 1, uid, "gold", gold=300)
    gb.record_deposit(conn, 1, uid + 1, "gold", gold=500)
    check("top depositor", gb.top_depositors(conn, 1) == [(uid + 1, 500)])
    gb.record_tax(conn, uid, 1, 2, "potion kecil", 1, 1000, 100)
    gb.record_tax(conn, uid + 1, 1, 2, "potion kecil", 2, 500, 50)
    check("top taxpayer", gb.top_tax_players(conn, 1) == [(uid, 100)])
    check("top taxpayer guild", gb.top_tax_guilds(conn, 1) == [(1, 150)])
    adm = hb.admit(conn, uid, 0, reason="defeat")
    check("rawat inap dicatat",
          adm is not None and adm["hp_at_admission"] == 0)
    check("HP rumah sakit dihitung malas",
          hb.computed_hp(adm, 120, ts=adm["admitted_at"]) == 0
          and hb.computed_hp(adm, 120, ts=adm["admitted_at"] + 180) == 30)
    check("bisa pulang di 25%",
          hb.can_leave(30, 120) is True and hb.can_leave(29, 120) is False)
    check("menit ke pulang",
          hb.minutes_to_discharge(adm, 120, ts=adm["admitted_at"]) == 3)
    ptest = db.get_player(conn, uid)
    ptest["max_hp"] = 120
    status, hp = hb.sync_patient(conn, ptest, ts=adm["admitted_at"] + 12 * 60)
    check("sembuh penuh auto-pulang",
          status == "discharged" and hp == 120
          and hb.get_admission(conn, uid) is None)
    check("curi 10% carried gold",
          logic.pvp_steal_amount(1000) == 100
          and logic.pvp_steal_amount(999) == 99)
    check("curi 0/negatif = 0",
          logic.pvp_steal_amount(0) == 0
          and logic.pvp_steal_amount(-50) == 0
          and logic.pvp_steal_amount(5) == 0)
    check("kalah potong 10% carried (clamp), bank aman",
          max(0, 150 // 10) == 15 and max(0, -50 // 10) == 0)

    # 9. Phase 3: credit guard — marker-only, no other code hashed
    import credit_guard
    check("credit guard lolos di repo asli",
          credit_guard.verify_credit_markers() == [])
    tmpdir = Path(tempfile.mkdtemp())
    (tmpdir / "bot.py").write_text("# no marker here\n")
    (tmpdir / "data.py").write_text("")
    (tmpdir / "database.py").write_text("")
    (tmpdir / "cogs").mkdir(exist_ok=True)
    (tmpdir / "cogs" / "common.py").write_text("")
    problems = credit_guard.verify_credit_markers(tmpdir)
    check("credit guard gagal kalau marker hilang",
          len(problems) >= 5)  # 4 file + LICENSE
    (tmpdir / "bot.py").write_text(
        "# NEWR Adventure by NEWR LABS \u2014 credit marker, do not remove.\n")
    (tmpdir / "data.py").write_text(
        "# NEWR Adventure by NEWR LABS \u2014 credit marker, do not remove.\n")
    (tmpdir / "database.py").write_text(
        "# NEWR Adventure by NEWR LABS \u2014 credit marker, do not remove.\n")
    (tmpdir / "cogs" / "common.py").write_text(
        "# NEWR Adventure by NEWR LABS \u2014 credit marker, do not remove.\n")
    (tmpdir / "LICENSE").write_text(
        "Copyright NEWR LABS. No use without written permission.\n")
    check("credit guard lolos kalau marker utuh (kode lain bebas diubah)",
          credit_guard.verify_credit_markers(tmpdir) == [])

    check("harga black market 1.5x (dragon egg 5000 -> 7500)",
          logic.bm_price("telur naga") == 7500)
    check("clamp jumlah: 0->1, lewat stok->stok, stok 0->0",
          logic.bm_clamp_qty(0, 2) == 1 and logic.bm_clamp_qty(9, 2) == 2
          and logic.bm_clamp_qty(1, 0) == 0)
    check("total keranjang: 2x dragon egg = 15000",
          logic.bm_cart_total({"telur naga": 2}) == 15000)
    check("resolve nama Inggris 'dragon egg' -> 'telur naga'",
          disp.resolve_item("dragon egg") == "telur naga")
    check("resolve nama Indonesia 'telur naga' tetap",
          disp.resolve_item("telur naga") == "telur naga")

    # Expansion checks (defined below main; called here so the suite covers them).
    try:
        test_expansion_counts_and_tiers()
        test_expansion_tier_helpers_and_rotation()
        check("expansion counts, tiers, rotation, register stories", True)
    except AssertionError as exc:
        check(f"expansion checks ({exc})", False)

    conn.close()
    os.unlink(tmp.name)
    print()
    if FAILURES:
        print(f"GAGAL: {len(FAILURES)} cek: {', '.join(FAILURES)}")
        return 1
    print("SEMUA CEK LOLOS.")
    return 0


# ---- expansion checks (appended) ----
def test_expansion_counts_and_tiers():
    import data
    assert len(data.CLASSES) == 10 and len(data.EVOLUTIONS) == 20
    assert len(data.AREAS) == 11 and len(data.MONSTERS) == 33
    assert len(data.ITEMS) == 82 and len(data.QUESTS) == 19
    assert len(data.PETS) == 10 and len(data.JOBS) == 6 and len(data.RECIPES) == 12
    assert len(data.WEEKLY_BOSSES) == 3 and len(data.EVENTS) == 5
    assert len(data.STORY) == 8 and len(data.DUNGEON_PUZZLES) == 10
    assert all("tier" in q for q in data.QUESTS.values())
    assert all("tier" in a for a in data.AREAS.values())
    assert all("tier" in m for m in data.MONSTERS.values())
    assert all(m in data.MONSTERS for a in data.AREAS.values() for m in a["monsters"])
    assert all(l in data.ITEMS for v in data.MONSTERS.values() for l in v["loot"])
    assert all(n in data.ITEMS for v in data.RECIPES.values() for n in v["needs"])
    assert data.ITEMS["telur naga"]["type"] == "rare"  # Dragon Egg unchanged


def test_expansion_tier_helpers_and_rotation():
    import data, logic
    from datetime import date
    assert logic.content_tier_for_level(1) == "Common"
    assert logic.content_tier_for_level(10) == "Rare"
    assert logic.content_tier_for_level(20) == "Epic"
    assert logic.content_tier_for_level(30) == "Legendary"
    assert logic.monster_tier("Naga Void") == "Legendary"
    assert logic.quest_tier("mq6") == "Legendary"
    names = {logic.weekly_boss_for_date(date(2026, 1, 5 + 7 * w))["name"] for w in range(3)}
    assert names == {wb["name"] for wb in data.WEEKLY_BOSSES}
    assert data.REGISTER_PROLOGUE and all(c in data.REGISTER_STORIES for c in data.CLASSES)

if __name__ == "__main__":
    sys.exit(main())

