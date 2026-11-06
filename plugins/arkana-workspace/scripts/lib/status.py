#!/usr/bin/env python3
"""Estado de ARKANA y de cada componente (todo con git local, sin red): rama, ◌ ✚ ● ⇡ y ⇣ (⇣? si no se sabe).

  status.py [--component A]... [--home DIR] [--json]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, HERE)
from arkana_core import manifest, output  # noqa: E402
import gitstate  # noqa: E402


def build(ws, components=None):
    rep = output.Report("arkana-workspace", "status")
    for a in (components or ws.aliases()):
        p = ws.path(a)
        if not os.path.isdir(p):
            rep.add("WARN", a, "la carpeta no existe", component=a)
            continue
        s = gitstate.state(p)
        if s is None:
            rep.add("WARN", a, "no es un repositorio git", component=a)
            continue
        rep.add("OK" if s["clean"] else "INFO", a, f"{manifest.display(a)}{gitstate.badge(s)}".rstrip(), component=a)
        rep.items[-1]["git"] = {k: s[k] for k in ("branch", "untracked", "staged", "modified", "ahead", "behind", "has_remote")}
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="status.py")
    ap.add_argument("--component", action="append")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        comps = [manifest.canon(c) for c in a.component] if a.component else None
        for c in comps or []:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    sys.stdout.write(build(ws, comps).render(a.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
