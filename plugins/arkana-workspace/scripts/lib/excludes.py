#!/usr/bin/env python3
"""Exclusiones locales de git de las piezas del workspace: lo que Arkana y Claude Code crean en un repo de trabajo no debe versionarse ni aparecer en `.gitignore`.

  excludes.py status [--component A]... [--home DIR] [--json]
  excludes.py apply  [--component A]... [--home DIR] [--dry-run] [--json]

Se añade a `.git/info/exclude` de cada repo (fichero local, que no se versiona; vale también para worktrees y submódulos) lo que `git check-ignore` no
cubra ya por otra vía: `.claude/`, `.claude-session/` y `ARKANA.local.md`. Nunca toca el `.gitignore` del repo.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, manifest, output  # noqa: E402

ENTRIES = [(".claude/", ".claude/x"), (".claude-session/", ".claude-session/x"), ("ARKANA.local.md", "ARKANA.local.md")]


def git(path, *args):
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=15, env=dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def is_ignored(path, probe):
    return git(path, "check-ignore", "-q", probe)[0] == 0


def exclude_file(path):
    rc, out = git(path, "rev-parse", "--git-path", "info/exclude")
    if rc != 0 or not out:
        return None
    return out if os.path.isabs(out) else os.path.join(path, out)


def missing(path):
    return [(pat, probe) for pat, probe in ENTRIES if not is_ignored(path, probe)]


def apply_one(path, dry):
    """-> [(patrón, estado)]; estado: 'añadido' | 'se añadiría'."""
    faltan = missing(path)
    if not faltan:
        return []
    f = exclude_file(path)
    if not f:
        return []
    if not dry:
        cur = ""
        try:
            cur = open(f, encoding="utf-8").read()
        except OSError:
            pass
        add = "".join(f"{pat}\n" for pat, _ in faltan)
        datafiles.atomic_write(f, cur + ("" if not cur or cur.endswith("\n") else "\n") + add)
    return [(pat, "se añadiría" if dry else "añadido") for pat, _ in faltan]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="excludes.py")
    ap.add_argument("cmd", choices=("status", "apply"))
    ap.add_argument("--component", action="append")
    ap.add_argument("--home")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        al = [manifest.canon(c) for c in a.component] if a.component else ws.aliases()
        for c in al:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = output.Report("arkana-workspace", "excludes")
    for c in al:
        p = ws.path(c)
        if not os.path.isdir(p) or git(p, "rev-parse", "--git-dir")[0] != 0:
            rep.add("WARN", f"excludes-{c}", "no es un repositorio git", component=c)
            continue
        if a.cmd == "status":
            m = missing(p)
            rep.add("WARN" if m else "OK", f"excludes-{c}", ("sin ignorar: " + ", ".join(x for x, _ in m)) if m else "todo ignorado", component=c)
            continue
        done = apply_one(p, a.dry_run)
        if done:
            for pat, st in done:
                rep.add("DRY" if a.dry_run else "OK", f"excludes-{c}", f"{pat}: {st} en .git/info/exclude", component=c)
        else:
            rep.add("OK", f"excludes-{c}", "nada que añadir", component=c)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
