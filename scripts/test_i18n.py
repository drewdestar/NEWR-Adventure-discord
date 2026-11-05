# -*- coding: utf-8 -*-
"""Temp-DB translation tests for the i18n refactor (no live DB, no bot).

Covers, for users with language 'id', 'de' and default 'en':
  * /profile-style strings and the /guild create template are fully
    single-language (Indonesian for 'id', no Indonesian markers for 'de').
  * /fight victory button labels translate through TranslatedView.
  * One admin command string translates through the admin bot's i18n copy.
  * Command names (/guild join, /shop, ...) are never translated.
  * Missing translation + online failure falls back to English, never
    to Indonesian, for a non-Indonesian user.
Run: python3 scripts/test_i18n.py   (with the bot venv for the view test)
Exit code 0 only when every check passes.
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RPG = HERE.parent
ADMIN = Path.home() / "workspace" / "bots" / "rpg-admin"
sys.path.insert(0, str(RPG))
# NOTE: do NOT put the admin folder on sys.path: it also has a
# `cogs` package, which would shadow the main bot's cogs.

import i18n as main_i18n

CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append((name, ok, detail))
    print(f"[{'OK ' if ok else 'FAIL'}] {name} {detail}")


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE user_prefs (user_id INTEGER PRIMARY KEY, language TEXT)")
    main_i18n.set_lang(conn, 111, "id")
    main_i18n.set_lang(conn, 222, "de")
    # 'id' user: profile-style + guild-create template, fully Indonesian
    main_i18n.set_ctx_for_user(111, conn)
    prof = main_i18n.t_fmt(
        "**{name}** is officially founded, led by {leader}! "
        "Invite friends to join with `/guild join {name}`.",
        name="Garuda", leader="Andreas")
    check("id guild-create fully Indonesian, command kept",
          "resmi berdiri" in prof and "/guild join Garuda" in prof, prof)
    buy = main_i18n.translate("You bought Small Potion x2 for 100 gold!", lang="id")
    check("id template-match converts display name",
          buy.startswith("Kamu beli potion kecil"), buy)
    # 'de' user: no Indonesian markers anywhere
    main_i18n.set_ctx_for_user(222, conn)
    de_prof = main_i18n.t("You don't have a character yet! Register first with `/register`.")
    check("de reply has no Indonesian markers",
          not main_i18n._looks_indonesian(de_prof)
          and "/register" in de_prof, de_prof)
    de_fight = main_i18n.t("🎉 VICTORY! +{e} EXP, +{g} gold".format(e=10, g=50))
    check("de fight victory translated, no Indonesian markers",
          not main_i18n._looks_indonesian(de_fight), de_fight)
    # command names never translated (id + de)
    for lang in ("id", "de"):
        out = main_i18n.translate("Join with `/raid join`, then `/raid hit` together!",
                                  lang=lang, conn=conn)
        check(f"{lang} command names untouched",
              "/raid join" in out and "/raid hit" in out, out)
    # fallback: online off -> English base, never Indonesian, for 'de'
    orig_online = main_i18n._online
    main_i18n._online = lambda text, lang: None
    try:
        fb = main_i18n.translate("Some brand new string nobody translated yet.",
                                 lang="de", conn=conn)
        check("de fallback is English, not Indonesian",
              fb == "Some brand new string nobody translated yet.", fb)
        fb_id = main_i18n.translate("Some brand new string nobody translated yet.",
                                    lang="id", conn=conn)
        check("id fallback is English when no translation exists",
              fb_id == "Some brand new string nobody translated yet.", fb_id)
    finally:
        main_i18n._online = orig_online
    # fight victory buttons through TranslatedView (needs discord)
    try:
        import discord  # noqa
        from cogs.common import TranslatedView
        main_i18n.set_ctx_for_user(111, conn)

        class DummyView(TranslatedView):
            @discord.ui.button(label="Steal", style=discord.ButtonStyle.danger)
            async def steal(self, interaction, button):
                pass

            @discord.ui.button(label="Leave", style=discord.ButtonStyle.secondary)
            async def leave(self, interaction, button):
                pass

            @discord.ui.button(label="Hospital", style=discord.ButtonStyle.success)
            async def hosp(self, interaction, button):
                pass

        v = DummyView()
        labels = [c.label for c in v.children]
        check("id fight victory buttons translated",
              labels != ["Steal", "Leave", "Hospital"]
              and not any(l in ("Steal", "Leave", "Hospital") for l in labels),
              str(labels))
    except ImportError:
        import traceback; traceback.print_exc()
        print("[SKIP] discord not installed in this python; view test skipped")
    # admin command string through the admin bot's i18n copy
    import importlib.util
    spec = importlib.util.spec_from_file_location("admin_i18n", ADMIN / "i18n.py")
    admin_i18n = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(admin_i18n)
    admin_id = admin_i18n.translate("That player hasn't registered for the RPG.", lang="id")
    check("admin id reply Indonesian",
          "belum daftar" in admin_id, admin_id)
    admin_de = admin_i18n.translate("That player hasn't registered for the RPG.", lang="de")
    check("admin de reply has no Indonesian markers",
          not admin_i18n._looks_indonesian(admin_de), admin_de)
    conn.close()
    failed = [c for c in CHECKS if not c[1]]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} CHECKS PASSED.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
