# NEWR Adventure

Bot RPG buat server Discord NEWR LABS. Semua perintah slash command,
tanpa prefix.

Buat karakter dulu pakai `/register` (Warrior, Mage, Archer, Assassin),
terus main: `/fight` lawan monster, `/raid` lawan boss, `/pvp` duel
pemain lain, `/guild` buat gabung guild, `/shop`, `/craft`, `/gacha`,
`/pet`, `/job`, `/house`, `/dungeon`, `/meteor`, `/story`, `/casino`,
plus fitur sosial (`/friend`, `/transfer`, `/borrow`, `/botloan`) dan
`/language` buat ganti bahasa balasan. Ada sistem lapar / haus /
stamina / durability, event musiman, dan VIP (dikasih admin, bukan
dibeli).

Jalanin:

```bash
bash ~/workspace/bots/ops/run-rpg.sh
```

Token cuma dibaca dari `DISCORD_TOKEN` di `.env` (chmod 600). Database
pemain (`rpg.db`) nggak masuk repo, yang di-commit cuma kode,
`schema.sql`, dan `seed.py`.

Dua hal yang perlu diketahui: state `/fight` disimpan di memori, jadi
kalau bot restart di tengah fight, fight-nya hilang tanpa penalti.
Guild war dihitung 1 jam setelah deklarasi, pas ada yang ngecek
(`/guildwar info`).

NEWR Adventure by NEWR LABS.
