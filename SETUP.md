# SETUP — NEWR Adventure by NEWR LABS

Target server bot ini: **NEWR LABS** (guild ID `1465422166790242377`).

Bot ini berjalan **berdampingan** dengan bot NEWR yang sudah ada, tapi tetap
**bot yang sepenuhnya terpisah**: kode sendiri (`~/workspace/bots/rpg/`),
database sendiri (`~/workspace/bots/rpg/rpg.db`), dan token sendiri.
JANGAN memakai ulang atau mengubah kode, token, atau database bot NEWR
Support / AI / Music / Reminder / Social / Stats / Guardian / Clip.

## Langkah user (belum dilakukan — butuh klik user sendiri)

### 1. Buat Discord Application
1. Buka https://discord.com/developers/applications
2. **New Application** → beri nama, misal `NEWR Adventure`
3. Catat **Application ID** (ini = CLIENT_ID di bawah)

### 2. Buat Bot User & salin token
1. Di aplikasi tadi → menu **Bot** → **Add Bot** (atau Reset Token kalau sudah ada)
2. Salin tokennya. **Token ini rahasia** — jangan ditempel di chat, kode, atau
   file lain selain `.env` di bawah.

### 3. Isi `.env` (di VM)
```bash
cp ~/workspace/bots/rpg/.env.example ~/workspace/bots/rpg/.env
chmod 600 ~/workspace/bots/rpg/.env
# lalu isi di dalam .env:
#   DISCORD_TOKEN=<token dari langkah 2>
#   GUILD_ID=1465422166790242377   (opsional, lihat catatan di bawah)
```

Catatan `GUILD_ID`:
- Diisi = slash command disinkron **instan** ke server NEWR LABS saja.
- Dikosongkan = sinkron global (bisa butuh waktu sampai ~1 jam sampai perintah
  muncul di semua server).
- Untuk pemakaian pertama di NEWR LABS, disarankan isi `GUILD_ID=1465422166790242377`.

### 4. Invite bot ke NEWR LABS
Buka link ini di browser (ganti `CLIENT_ID` dengan Application ID dari langkah 1):

```
https://discord.com/oauth2/authorize?client_id=CLIENT_ID&permissions=84032&scope=bot%20applications.commands&guild_id=1465422166790242377
```

- `permissions=84032` = kirim pesan, embed link, baca riwayat pesan, tambah reaksi
  (izin minimal yang dibutuhkan bot ini).
- `scope=bot applications.commands` = bot + slash command.
- `guild_id=...` = langsung memilih server NEWR LABS di halaman invite.
- Di halaman invite, pilih server **NEWR LABS**, centang izin, lalu **Authorize**.
- Bot TIDAK butuh role khusus di server untuk jalan; cukup ada di server.
  (Perintah `/vipgrant` hanya bisa dipakai anggota dengan izin Administrator.)

### 5. Jalankan bot
```bash
bash ~/workspace/bots/ops/run-rpg.sh
```

- Kalau `.env` / token belum diisi, bot berhenti dengan pesan error yang jelas
  (`DISCORD_TOKEN tidak ditemukan...`) — itu normal, bukan crash.
- Kalau berhasil, log di `~/workspace/bots/logs/rpg.log` menampilkan
  `Bot login sebagai ... — NEWR Adventure by NEWR LABS siap!`
- Cek di server NEWR LABS: ketik `/help` — harus muncul daftar perintah.
  Kalau `/help` belum muncul, tunggu sebentar (sinkron global) atau pastikan
  `GUILD_ID` terisi lalu restart bot.

### 6. Tes cepat di NEWR LABS
1. `/register` → isi nama & kelas
2. `/profile` → cek stats
3. `/daily` → klaim hadiah
4. `/fight` → lawan monster pertama
5. `/help` → pastikan semua perintah muncul

## GitHub (nanti, belum dilakukan)

- **JANGAN push sekarang.** Push menunggu user memilih repo & visibilitasnya.
- Proyek ini sudah git-ready:
  - `.gitignore` mengecualikan `.env`, `rpg.db`, log, dan `backups/`
  - `schema.sql` = struktur database (tanpa data pemain)
  - `seed.py` = rebuild `rpg.db` kosong dari skema
  - `scripts/export_db.sh` = ekspor ulang skema + backup lokal database live
- Database pemain live **TIDAK PERNAH** di-commit, supaya data pemain tidak
  tersebar di repo publik.

## Troubleshooting singkat

| Gejala | Penyebab umum |
|---|---|
| Bot berhenti: `DISCORD_TOKEN tidak ditemukan` | `.env` belum dibuat / token kosong / masih placeholder |
| Slash command tidak muncul | Sinkron global butuh waktu; isi `GUILD_ID` lalu restart, atau invite ulang dengan scope `applications.commands` |
| Bot tidak bisa kirim pesan | Cek izin bot di channel (Send Messages + Embed Links) |
| `/vipgrant` ditolak | Hanya Administrator server yang bisa memakai perintah itu |

NEWR Adventure by NEWR LABS.
