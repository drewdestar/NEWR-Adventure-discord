#!/bin/bash
# Export skema database RPG ke schema.sql + backup lokal database live.
#
# YANG DIEKSPOR KE REPO: skema saja (CREATE TABLE), TANPA data pemain.
# Database pemain live (rpg.db) TIDAK PERNAH di-commit — lihat .gitignore.
# Backup lokal (.db lengkap) hanya disimpan di backups/ (juga di-ignore git)
# sebagai jaga-jaga kalau server pindah / database rusak.
#
# Pakai: bash scripts/export_db.sh
set -euo pipefail

BOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_FILE="$BOT_DIR/rpg.db"
SCHEMA_FILE="$BOT_DIR/schema.sql"
BACKUP_DIR="$BOT_DIR/backups"

if [ ! -f "$DB_FILE" ]; then
  echo "rpg.db belum ada (bot belum pernah jalan). Membuat schema.sql dari database.py..."
  "$BOT_DIR/.venv/bin/python" - "$BOT_DIR" <<'PYEOF'
import sys, tempfile, os
sys.path.insert(0, sys.argv[1])
import database as db
tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False); tmp.close()
conn = db.connect(tmp.name)
stmts = [r[0] for r in conn.execute(
    "SELECT sql FROM sqlite_master WHERE sql NOT NULL ORDER BY name")]
header = ("-- schema.sql — struktur database bot NEWR Adventure (by NEWR LABS).\n"
          "-- Dibuat dari database.py. Berisi skema SAJA, tanpa data pemain.\n"
          "-- Dibuat ulang dengan: bash scripts/export_db.sh\n")
with open(os.path.join(sys.argv[1], 'schema.sql'), 'w') as f:
    f.write(header)
    for s in stmts:
        f.write(s.rstrip(';') + ';\n')
conn.close(); os.unlink(tmp.name)
print("schema.sql ditulis dari database.py (database live belum ada).")
PYEOF
  exit 0
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
cp "$DB_FILE" "$BACKUP_DIR/rpg-$STAMP.db"
echo "Backup lokal: backups/rpg-$STAMP.db (tidak di-commit)"

"$BOT_DIR/.venv/bin/python" - "$DB_FILE" "$SCHEMA_FILE" <<'PYEOF'
import sqlite3, sys
db_path, schema_path = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db_path)
stmts = [r[0] for r in conn.execute(
    "SELECT sql FROM sqlite_master WHERE sql NOT NULL ORDER BY name")]
header = ("-- schema.sql — struktur database bot NEWR Adventure (by NEWR LABS).\n"
          "-- Dibuat dari database live. Berisi skema SAJA, tanpa data pemain.\n"
          "-- Dibuat ulang dengan: bash scripts/export_db.sh\n")
with open(schema_path, 'w') as f:
    f.write(header)
    for s in stmts:
        f.write(s.rstrip(';') + ';\n')
print(f"schema.sql ditulis ({len(stmts)} tabel, tanpa data pemain).")
PYEOF
