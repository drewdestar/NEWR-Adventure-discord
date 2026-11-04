# -*- coding: utf-8 -*-
"""Rebuild database bot RPG dari skema (tanpa data pemain).

Pakai ini setelah clone repo, sebelum pertama kali menjalankan bot:
    python3 seed.py [path-ke-db]
Default: rpg.db di folder yang sama dengan file ini.

Script ini HANYA membuat struktur tabel kosong. Data pemain TIDAK PERNAH
ikut di-commit ke repo (lihat .gitignore: rpg.db dikecualikan), jadi
database hasil clone selalu kosong dan aman.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import database as db


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "rpg.db"
    if target.exists():
        print(f"Database sudah ada di {target}, tidak di-overwrite.")
        print("Hapus dulu file itu kalau memang mau rebuild dari nol.")
        return 0
    conn = db.connect(str(target))
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
    conn.close()
    print(f"Database baru dibuat di {target}")
    print(f"Tabel ({len(tables)}): {', '.join(tables)}")
    print("Siap dipakai bot. Data pemain akan terisi saat pemain /register.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
