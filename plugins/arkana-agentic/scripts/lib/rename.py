#!/usr/bin/env python3
"""Cambia el alias de un componente en los datos locales de la orquestación (lo invoca `arkana-workspace:component edit --rename`).

  rename.py --from A --to B [--dry-run]

Reescribe `repo` en las tareas, las claves de `ramas` en los planes y `component(es)` en el libro, tanto de los planes en curso como de los archivados.
Se niega mientras haya un plan activo o un worker vivo (sus ramas y rutas se resuelven por alias). Salida `ESTADO|ID|detalle`.
"""
import argparse
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
import state  # noqa: E402
from arkana_core import datafiles, output  # noqa: E402


def targets():
    base = state.base_dir()
    g = lambda pat: sorted(glob.glob(os.path.join(base, pat)))
    return ([(f, "tarea") for f in g("state/planes/*/tareas/*.json") + g("data/archive/*/tareas/*.json")]
            + [(f, "plan") for f in g("state/planes/*/plan.json") + g("data/archive/*/plan.json")]
            + [(f, "libro") for f in g("data/ledger/*/*.json")])


def fix(kind, d, old, new):
    ch = False
    if kind == "tarea" and d.get("repo") == old:
        d["repo"], ch = new, True
    elif kind == "plan" and isinstance(d.get("ramas"), dict) and old in d["ramas"]:
        d["ramas"][new] = d["ramas"].pop(old)
        ch = True
    elif kind == "libro":
        if d.get("component") == old:
            d["component"], ch = new, True
        if isinstance(d.get("componentes"), list) and old in d["componentes"]:
            d["componentes"] = [new if x == old else x for x in d["componentes"]]
            ch = True
    return d, ch


def active():
    res = []
    for f in glob.glob(os.path.join(state.base_dir(), "state", "planes", "*", "plan.json")):
        d = datafiles.read_json(f, {}) or {}
        if d.get("estado") in state.ACTIVE_PLAN_STATES:
            res.append(f"el plan {d.get('id', os.path.basename(os.path.dirname(f)))} está {d.get('estado')}")
    w = datafiles.read_json(os.path.join(state.base_dir(), "state", "run", "worker.json"), {}) or {}
    try:
        pid = int(w.get("pid", 0))
        if pid > 0:
            os.kill(pid, 0)
            res.append(f"hay un worker vivo (pid {pid})")
    except (OSError, ValueError, TypeError):
        pass
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rename.py")
    ap.add_argument("--from", dest="frm", required=True)
    ap.add_argument("--to", required=True)
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-agentic", "rename")
    old, new = a.frm.strip().lower(), a.to.strip().lower()
    bl = active()
    if bl:
        rep.add("FAIL", "rename", "no se renombra ahora: " + "; ".join(bl) + " (termínalo o deténlo y repite)")
        sys.stdout.write(rep.render())
        return rep.exit_code()
    n = 0
    for f, kind in targets():
        d = datafiles.read_json(f)
        if isinstance(d, dict):
            d, ch = fix(kind, d, old, new)
            if ch:
                n += 1
                if not a.dry_run:
                    datafiles.atomic_write_json(f, d)
    rep.add("DRY" if a.dry_run else "OK", "rename", f"{n} ficheros de la orquestación pasan de {old} a {new}")
    sys.stdout.write(rep.render())
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
