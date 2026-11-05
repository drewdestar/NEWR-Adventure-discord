# -*- coding: utf-8 -*-
"""Startup credit guard (phase 3) — NEWR Adventure by NEWR LABS.

This guard checks CREDIT MARKERS ONLY. It verifies that a short credit
marker line is still present, verbatim, in the bot's entry point and
main shared modules, and that the LICENSE file still carries the
NEWR LABS proprietary notice. It does NOT hash or compare any other
code, so ordinary edits, new features, and the user's own updates
never trip it. It deters casual copying; it cannot stop a determined
person who already has the source (they could also delete this file
and its call site — that is a known, accepted limit, not a bug).

Marker line (must appear verbatim in every REQUIRED_FILES entry):
    # NEWR Adventure by NEWR LABS — credit marker, do not remove.
"""
import sys
from pathlib import Path

# NEWR Adventure by NEWR LABS — credit marker, do not remove.
CREDIT_MARKER = "# NEWR Adventure by NEWR LABS \u2014 credit marker, do not remove."
REQUIRED_FILES = ("bot.py", "data.py", "database.py", "cogs/common.py")
LICENSE_MARKERS = ("NEWR LABS", "written permission")


def verify_credit_markers(bot_dir=None):
    """Return a list of problems (empty = all markers present).

    Pure function, no Discord, no token, no database — safe to unit-test
    against a temporary directory.
    """
    base = Path(bot_dir) if bot_dir else Path(__file__).resolve().parent
    problems = []
    for rel in REQUIRED_FILES:
        path = base / rel
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            problems.append(f"missing file: {rel}")
            continue
        if CREDIT_MARKER not in text:
            problems.append(f"credit marker missing or altered in: {rel}")
    lic = base / "LICENSE"
    try:
        lic_text = lic.read_text(encoding="utf-8")
    except OSError:
        problems.append("missing file: LICENSE")
        return problems
    for marker in LICENSE_MARKERS:
        if marker not in lic_text:
            problems.append(f"LICENSE notice missing or altered: {marker!r}")
    return problems


def enforce_credit_markers(bot_dir=None):
    """Exit with a clear error if any credit marker is gone.

    Called once from bot.py main(), before any token or network use.
    """
    problems = verify_credit_markers(bot_dir)
    if problems:
        print("ERROR: NEWR Adventure credit check failed — the bot "
              "refuses to run.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Restore the 'NEWR Adventure by NEWR LABS' credit markers "
              "and the LICENSE file, then start the bot again.",
              file=sys.stderr)
        sys.exit(1)
    return True
