# 🐉 NEWR Adventure — Discord Bot RPG

**Credit by NEWR LABS.**

Bot RPG lengkap untuk Discord, semua perintah berupa **slash command**
(`app_commands`) — tanpa prefix command. Bot ini sepenuhnya terpisah dari
bot NEWR lainnya (Support, AI, Music, Reminder, Social, Stats, Guardian,
Clip): kode, database, dan tokennya sendiri. Jangan memakai atau mengubah
kode, token, atau database bot lain untuk bot ini.

## Fitur

### 1. Sistem Dasar
- `/register` — buat karakter (nama + kelas: Warrior, Mage, Archer, Assassin)
- `/profile` — Level, HP, MP, EXP, Gold, Attack, Defense, Speed
- `/evolve` — evolusi job (Warrior → Knight → Paladin, Mage → Wizard → Archmage,
  Archer → Ranger → Sharpshooter, Assassin → Shadow → Nightblade; gerbang level 15 & 35)
- `/daily` — hadiah login harian + bonus streak
- `/inventory` — lihat, pakai, pasang, lepas, buang item
- `/map` — jelajah area yang terbuka sesuai level (Hutan Pemula → Langit Terlarang)
- `/quest` — quest utama, sampingan, dan harian dengan progress tersimpan di database

### 2. Sistem Battle
- `/fight` — lawan monster sesuai level, pertarungan tombol (Serang / Skill / Potion / Kabur)
- `/raid` — boss mingguan/event ber-HP besar, damage party terkumpul di database
- `/pvp` — tantang pemain lain, terima/tolak lewat tombol, pemenang +25 poin ranking
- `/arena` — leaderboard PVP
- `/guildwar` — deklarasi perang antar guild, hasil dihitung 1 jam kemudian dari
  kekuatan total anggota + level guild (lazy resolve saat dicek)

### 3. Ekonomi & Item
- `/shop` — beli senjata, armor, potion, benih, gear pet
- `/blackmarket` — item langka, harga 1.5x, stok 3 item acak per hari (reset harian)
- `/craft` — resep gabung item jadi senjata/armor lebih kuat
- Loot acak tiap menang battle (VIP +peluang)
- `/gacha` — tarik 1x/10x, rarity common / rare / epic / legendary (VIP lebih bagus)
- `/trade` — tawar-terima item antar pemain; `/tradeboard` — papan jual-beli pakai gold

### 4. Pet & Partner
- `/pet` — adopsi pet (Serigala Api, Kucing Bayangan, Naga Mini, Kelinci Bulan),
  pet ikut battle nambah damage, naik level, berevolusi bentuk di Lv 10 & 25
- `/petgear` — senjata/armor khusus pet

### 5. Survival
- Lapar & haus berkurang tiap aksi dan tiap 2 jam waktu nyata; kalau 0, HP terkuras
  pelan tapi berhenti di 10 HP (tidak mati mendadak) + ada peringatan di `/profile`
- `/status` — cek lapar/haus/stamina/durability; `/eat` & `/drink` buat isi ulang
- Stamina: batas 100/hari, penuh lagi tiap pergantian hari WIB
- Durability: senjata/armor aus tiap battle; `/repair` perbaiki pakai gold

### 6. Sosial
- `/guild` — buat (500 gold) / gabung / keluar / info guild
- `/guildquest` — quest bersama: total klaim `/daily` anggota seminggu, hadiah per anggota
- `/guildbuff` — bonus stats semua anggota sesuai level guild (ATK/DEF + EXP%)
- `/party` — buat/gabung party; party 2+ orang dapat +10% damage raid

### 7. Premium & Event
- `/vip` — status VIP (EXP x1.5, gold x1.25, loot & gacha lebih bagus)
- `/vipgrant` — khusus admin server, memberi VIP 30 hari (TANPA pembayaran)
- Event musiman: Halloween (20–31 Okt), Natal (20–26 Des), Tahun Baru (30 Des–2 Jan) —
  mengubah stok toko & boss raid; `/event` buat cek
- `/ranking` — top player mingguan, top 3 bisa klaim hadiah

### 8. Fitur Unik
- `/casino` — tebak angka (bayar 5x) & tebak koin (bayar 2x); taruhan maks 500 gold,
  limit rugi harian 2000 gold
- `/job` — tukang kayu, penambang, pemburu (cooldown 1 jam, hasil gold + material)
- `/house` — bangun/tingkatkan rumah, tanam tanaman (tumbuh real-time), pelihara
  ayam/sapi dan kumpulkan hasilnya tiap 6 jam
- `/dungeon` — masuk dungeon (15 stamina), jawab teka-teki penjaga, rebut harta
- `/meteor` — hujan meteor tiap hari jam 21:00–21:59 WIB, klaim item langka sekali sehari
- `/story` — 5 chapter cerita panjang dengan syarat level & hadiah
- `/help` & `/about` — daftar perintah & info bot

## Desain UI/UX

Semua balasan bot memakai embed Discord lewat helper bersama `emb()` di
`cogs/common.py` (tidak ada lagi balasan teks polos), dengan pola yang sama:
judul jelas, info kunci, lalu aksi. Footer setiap embed: "NEWR Adventure by
NEWR LABS".

### Warna per sistem
- Dasar (register/profile/daily/inventory/map/quest): ungu `0x8B5CF6`
- Battle, raid, PVP, arena, guild war: merah `0xEF4444`
- Ekonomi (shop, black market, craft, gacha, trade): emas `0xF59E0B`
- Pet & pet gear: hijau `0x22C55E`
- Sosial (guild, guild quest, party): biru `0x3B82F6`
- Survival (status, makan/minum, repair): teal `0x14B8A6`
- Premium (VIP, ranking, event): magenta `0xD946EF`
- Seru-seruan (casino, job, house, dungeon, meteor, story): oranye `0xF97316`
- Error / aksi gagal: embed merah `⚠️ Ups!` (tetap ephemeral kalau memang privat)

### Bar visual
Stats tidak lagi tampil sebagai angka telanjang: HP, MP, EXP, lapar, haus,
stamina, durability gear, EXP pet, EXP guild, dan HP boss/raid memakai bar
`████░░` lewat helper `bar_line()` di `cogs/common.py`.

### Tombol & menu
- `/fight`: Serang / Skill / Potion / Kabur (sudah ada, dipertahankan)
- `/pvp`: Terima / Tolak duel (sudah ada, dipertahankan)
- `/inventory list`: menu pilih item, lalu tombol Pakai / Pasang / Lepas buat
  item terpilih (aksi yang sama dengan parameter `/inventory`, tanpa ubah logika)
- `/trade tawar`: tombol Terima / Tolak buat penerima tawaran (logika terima/tolak
  yang sama dengan `/trade terima/tolak`, dipakai bersama lewat helper)
- Party tidak punya alur invite (gabung langsung pakai nama), jadi tidak ada
  tombol invite di sana — sesuai spek, hanya alur yang sudah ada yang diubah
  tampilannya.

## Menjalankan

```bash
bash ~/workspace/bots/ops/run-rpg.sh
```

- Python 3.12, discord.py 2.7.1 di venv `~/workspace/bots/rpg/.venv`
- Database SQLite otomatis dibuat di `~/workspace/bots/rpg/rpg.db`
- Log di `~/workspace/bots/logs/rpg.log`
- Token HANYA dari `DISCORD_TOKEN` di `.env` (chmod 600). Kalau token tidak ada,
  bot berhenti dengan pesan error yang jelas. Lihat [SETUP.md](SETUP.md).

## Struktur kode

```
bot.py            # entry point: cek token, load cog, sync slash command, presence
database.py       # skema & helper SQLite (22 tabel)
data.py           # semua data statis game (kelas, monster, item, quest, event...)
logic.py          # rumus murni (level, damage, loot, gacha, decay, event)
cogs/             # core, battle, economy, pets, survival, social, premium, extra
test_logic.py     # test offline tanpa Discord (20 cek)
schema.sql        # ekspor skema (tanpa data pemain)
seed.py           # rebuild rpg.db kosong dari skema
scripts/export_db.sh  # ekspor skema + backup lokal database live
```

## Yang disederhanakan (jujur)

- Pertarungan `/fight` memakai state in-memory: kalau bot restart di tengah fight,
  fight itu hilang tanpa penalti (hadiah & HP hanya disimpan saat fight selesai).
- Jelajah `/map` menyelesaikan encounter monster otomatis (bukan tombol seperti `/fight`).
- Guild war dihitung 1 jam setelah deklarasi dan diselesaikan saat ada yang mengecek
  (`/guildwar info`), bukan lewat notifikasi real-time.
- VIP diberikan admin, bukan lewat pembayaran (sesuai spek build ini).

## Git — PENTING

- Database pemain live (`rpg.db`) **TIDAK di-commit** (lihat `.gitignore`).
  Yang masuk repo: kode + `schema.sql` + `seed.py` untuk rebuild struktur.
- Push ke GitHub dilakukan **NANTI**, setelah user memilih repo & visibilitasnya.
  Saat ini TIDAK ada remote git yang dibuat dan TIDAK ada yang di-push.

NEWR Adventure by NEWR LABS.
