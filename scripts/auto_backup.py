#!/usr/bin/env python3
"""Auto-backup database NEWR Adventure (bot RPG + bot admin, satu file rpg.db).

Dipakai oleh cron tiap jam. Aman dijalankan saat bot sedang jalan karena
memakai SQLite online backup API (bukan sekadar cp file yang bisa korup
kalau bot sedang menulis).

- Lokasi backup: ~/workspace/bots/rpg/backups/rpg-YYYYMMDD-HHMMSS.db
- Retensi: backup yang umurnya lebih dari 7 hari otomatis dihapus.
- Kalau rpg.db belum ada (bot belum pernah jalan), keluar normal tanpa error.
- Setiap backup dicek integrity_check; kalau tidak 'ok', file dibuang.

Env override (buat testing): RPG_DB_PATH, RPG_BACKUP_DIR, RPG_BACKUP_RETENTION_DAYS.
"""
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
DB_PATH = Path(os.environ.get("RPG_DB_PATH", HOME / "workspace/bots/rpg/rpg.db"))
BACKUP_DIR = Path(os.environ.get("RPG_BACKUP_DIR", HOME / "workspace/bots/rpg/backups"))
RETENTION_DAYS = int(os.environ.get("RPG_BACKUP_RETENTION_DAYS", "7"))


def main() -> int:
    if not DB_PATH.exists():
        print(f"rpg.db belum ada di {DB_PATH} (bot belum pernah jalan). Backup dilewati.")
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tmp_path = BACKUP_DIR / f".rpg-{stamp}.db.tmp"
    final_path = BACKUP_DIR / f"rpg-{stamp}.db"

    src = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(tmp_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # Verifikasi hasil backup sebelum dipakai.
    check = sqlite3.connect(tmp_path)
    try:
        row = check.execute("PRAGMA integrity_check").fetchone()
    finally:
        check.close()
    if not row or row[0] != "ok":
        tmp_path.unlink(missing_ok=True)
        print(f"Backup GAGAL integrity_check ({row}), file dibuang.", file=sys.stderr)
        return 1

    tmp_path.replace(final_path)
    print(f"Backup OK: {final_path} ({final_path.stat().st_size} bytes)")

    # Rotasi: hapus backup lebih tua dari retensi.
    cutoff = time.time() - RETENTION_DAYS * 86400
    removed = 0
    for old in BACKUP_DIR.glob("rpg-*.db"):
        if old.stat().st_mtime < cutoff:
            old.unlink()
            removed += 1
    if removed:
        print(f"Rotasi: {removed} backup lama (> {RETENTION_DAYS} hari) dihapus.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
