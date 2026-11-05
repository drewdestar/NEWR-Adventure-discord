# -*- coding: utf-8 -*-
"""AST scan for i18n leaks in NEWR Adventure (main + admin bots).

Checks user-visible call sites only:
  * emb()/err_embed()/err() arguments -- translated by the builder itself.
  * Button labels -- translated iff the view inherits TranslatedView
    (main bot) or the label is wrapped in i18n.t().
  * Select placeholders / option descriptions -- translated iff wrapped
    in i18n.t()/t_fmt().
  * Plain content= arguments to send_message -- must be empty except
    the '@everyone' mention (announcements) or authored raw content.

A literal is an ID-LEAK when it contains a strong Indonesian marker word
at a user-visible site. Internal game keys shown as *input-format
examples* (e.g. 'pedang besi' inside an admin error that tells the
admin which key to type) are reported separately as EXCEPTIONS, not
leaks: like /command names, keys are never translated, only explained.

Excludes: docstrings, i18n.py tables, data.py/display.py name tables,
tests, .venv, SQL, URLs, paths. Exit code 0 only when leaks == 0 and
untranslated buttons == 0 (exceptions and '@everyone' do not fail).
"""
import ast
import re
import sys
from pathlib import Path

ID_WORDS = ["kamu", "nggak", "tidak", "sudah", "belum", "buat", "pakai",
            "dengan", "untuk", "dari", "adalah", "juga", "kalau", "saat",
            "ketika", "dapat", "harus", "akan", "jika", "atau", "sangat",
            "semua", "setiap", "antara", "oleh", "pada", "dalam", "jangan",
            "silakan", "tolong", "terima", "tolak", "menang", "kalah",
            "banget", "lagi", "masih", "cuma", "bisa", "boleh", "mau",
            "ingin", "coba", "lihat", "cek", "beli", "jual", "bayar",
            "kerja", "latih", "pelihara", "tanam", "panen", "bangun",
            "naik", "habis", "penuh", "kosong", "baru", "besar", "kecil",
            "cepat", "kuat", "lemah"]
PAT = re.compile(r"\b(" + "|".join(ID_WORDS) + r")\b", re.I)
KEY_EXAMPLE = re.compile(r"'(pedang [a-z]+|potion [a-z]+|armor [a-z]+)'")


def _is_docstring(node, parent):
    p = parent.get(id(node))
    return (isinstance(p, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef))
            and p.body and p.body[0] is node)


def scan(root):
    leaks, exceptions, bad_buttons, plain_content = [], [], [], []
    for path in sorted(Path(root).rglob("*.py")):
        text_path = str(path)
        if ("__pycache__" in text_path or ".venv" in text_path
                or path.name in ("i18n.py", "data.py", "display.py")
                or path.name.startswith("test_")):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"),
                         filename=text_path)
        parent = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parent[id(child)] = node
        # class -> base names, for TranslatedView detection
        bases = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases[node.name] = [ast.unparse(b) for b in node.bases]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fname = (node.func.id if isinstance(node.func, ast.Name)
                     else node.func.attr if isinstance(node.func, ast.Attribute)
                     else "")
            # plain content= on a send call (not via emb)
            if fname in ("send_message", "edit_message", "send", "followup"):
                for kw in node.keywords:
                    if kw.arg == "content" and isinstance(kw.value, ast.Constant) \
                            and isinstance(kw.value.value, str):
                        if kw.value.value.strip() not in ("", "@everyone"):
                            plain_content.append((text_path, kw.value.lineno,
                                                  kw.value.value[:100]))
            # Button labels: find enclosing class
            if fname == "Button":
                label = None
                for kw in node.keywords:
                    if kw.arg == "label" and isinstance(kw.value, ast.Constant):
                        label = kw.value.value
                if label and re.search(r"[A-Za-z]{3,}", label):
                    # translated if inside a TranslatedView subclass or wrapped
                    enclosing = None
                    cur = parent.get(id(node))
                    while cur is not None:
                        if isinstance(cur, ast.ClassDef):
                            enclosing = cur.name
                            break
                        cur = parent.get(id(cur))
                    ok = enclosing and any("TranslatedView" in b
                                           for b in bases.get(enclosing, []))
                    if not ok:
                        bad_buttons.append((text_path, node.lineno, label))
            # every string literal at a user-visible site
            if fname in ("emb", "err_embed", "err", "send_message",
                         "edit_message", "send", "Button", "SelectOption",
                         "Select", "Embed"):
                def _pruned(n):
                    if isinstance(n, ast.Call):
                        fn = (n.func.id if isinstance(n.func, ast.Name)
                              else n.func.attr if isinstance(n.func, ast.Attribute)
                              else "")
                        if fn in ("emb", "err_embed", "err", "t", "t_fmt"):
                            return
                    yield n
                    for ch in ast.iter_child_nodes(n):
                        yield from _pruned(ch)
                for arg in list(node.args) + [kw.value for kw in node.keywords]:
                    for sub in _pruned(arg):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            txt = sub.value
                            if len(txt.strip()) < 3 or _is_docstring(sub, parent):
                                continue
                            if txt.startswith(("http", "/", "SELECT")):
                                continue
                            if PAT.search(txt):
                                if KEY_EXAMPLE.search(txt):
                                    exceptions.append((text_path, sub.lineno, txt[:130]))
                                else:
                                    leaks.append((text_path, sub.lineno, txt[:130]))
    return leaks, exceptions, bad_buttons, plain_content


def main():
    roots = sys.argv[1:] or ["."]
    total_leaks = total_bad = 0
    for root in roots:
        leaks, exc, bad, plain = scan(root)
        total_leaks += len(leaks)
        total_bad += len(bad)
        print(f"== {root}: ID-leaks={len(leaks)} "
              f"untranslated-buttons={len(bad)} "
              f"key-example-exceptions={len(exc)} "
              f"plain-content={len(plain)}")
        for f, ln, s in leaks:
            print(f"  LEAK {f}:{ln}: {s!r}")
        for f, ln, s in bad:
            print(f"  BUTTON {f}:{ln}: {s!r}")
        for f, ln, s in exc:
            print(f"  EXCEPTION {f}:{ln}: {s!r}")
        for f, ln, s in plain:
            print(f"  CONTENT {f}:{ln}: {s!r}")
    print(f"TOTAL leaks={total_leaks} untranslated-buttons={total_bad}")
    return 0 if (total_leaks == 0 and total_bad == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
