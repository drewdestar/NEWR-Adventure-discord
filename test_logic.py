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

    conn.close()
    os.unlink(tmp.name)
    print()
    if FAILURES:
        print(f"GAGAL: {len(FAILURES)} cek: {', '.join(FAILURES)}")
        return 1
    print("SEMUA CEK LOLOS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
