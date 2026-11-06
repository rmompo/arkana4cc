#!/usr/bin/env python3
"""Informe de traspaso del workspace: qué hay, en qué estado está y qué requiere atención. Solo lectura, sin red.

  handover.py [--out FICHERO] [--format md|json] [--home DIR]

Sin secretos (ni valores, ni longitudes) y sin rutas absolutas: las rutas van relativas a la raíz del workspace, los remotos
se reducen al host (una URL puede llevar usuario) y se purga cualquier ruta absoluta o valor de `.credentials` que aparezca en un texto.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, HERE)
from arkana_core import datafiles, locate, manifest  # noqa: E402
import credentials  # noqa: E402
import gitstate  # noqa: E402
import transfer  # noqa: E402


def scrubber(home, root):
    vals = [v for v in credentials.secrets(home) if v]
    prefixes = sorted({os.path.realpath(home), os.path.realpath(root), os.path.expanduser("~")}, key=len, reverse=True)

    def clean(t):
        t = str(t)
        for v in vals:
            t = t.replace(v, "***")
        for p in prefixes:
            t = t.replace(p.rstrip("/") + "/", "").replace(p, ".")
        return re.sub(r"(https?://)[^/@\s]*@", r"\1", t)
    return clean


def build(home):
    ws = manifest.load(home)
    root = locate.workspace_root(home)
    clean = scrubber(home, root)
    st = locate.state_dir(home)
    cons, _w = transfer.contracts(home)
    comps = []
    for al in ws.aliases():
        b = ws.get(al)
        p = ws.path(al)
        s = gitstate.state(p) if os.path.isdir(p) else None
        comps.append({
            "alias": manifest.display(al), "type": b.get("type", "arkana"), "path": clean(os.path.relpath(p, root)),
            "remote_host": b.get("remote_host"), "branches": b.get("branches"), "vpn": b.get("vpn"),
            "tools": b.get("tools", []), "token_ref": (b.get("git") or {}).get("token_ref"),
            "git": None if s is None else {k: s[k] for k in ("branch", "untracked", "staged", "modified", "ahead", "behind", "has_remote", "clean")}})
    plans = []
    pd = os.path.join(st, "arkana-agentic", "state", "planes")
    for d in sorted(os.listdir(pd)) if os.path.isdir(pd) else []:
        pl = datafiles.read_json(os.path.join(pd, d, "plan.json"))
        if isinstance(pl, dict):
            plans.append({"id": pl.get("id", d), "asunto": clean(pl.get("asunto", "")), "estado": pl.get("estado"),
                          "gasto_usd": (pl.get("contadores") or {}).get("gasto_usd")})
    data = []
    for plug, c in sorted(cons.items()):
        for d in c["data"]:
            f = os.path.join(st, d["path"])
            n = sum(len(fs) for _d, _s, fs in os.walk(f)) if d["path"].endswith("/") and os.path.isdir(f) else int(os.path.isfile(f))
            data.append({"plugin": plug, "path": d["path"], "class": d["class"], "files": n})
    keys = credentials.load(home) if os.path.isfile(credentials.path(home)) else {}
    refs = sorted({c["token_ref"] for c in comps if c["token_ref"]})
    return {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "workspace": ws_name(home),
            "plugins": {p: c["version"] for p, c in sorted(cons.items())}, "components": comps, "plans": plans, "data": data,
            "credentials": {"refs": refs, "missing": [r for r in refs if not keys.get(r)]}}


def ws_name(home):
    return ((datafiles.read_json(os.path.join(locate.state_dir(home), "arkana.json"), {}) or {}).get("workspace") or {}).get("name", "")


def to_md(h):
    L = [f"# Traspaso del workspace {h['workspace']}", "", f"Generado: {h['generated']}. Sin secretos ni rutas absolutas.", "", "## Plugins", ""]
    L += [f"- `{p}` {v}" for p, v in h["plugins"].items()] or ["- (ninguno)"]
    L += ["", "## Componentes", "", "| Alias | Tipo | Ruta | Host | Rama | Estado git |", "|---|---|---|---|---|---|"]
    for c in h["components"]:
        g = c["git"]
        est = "sin repositorio" if g is None else ("limpio" if g["clean"] else f"◌{g['untracked']} ✚{g['staged']} ●{g['modified']}") + (f" ⇡{g['ahead']}" if g["ahead"] else "")
        L.append(f"| {c['alias']} | {c['type']} | `{c['path']}` | {c['remote_host'] or '-'} | {g['branch'] if g else '-'} | {est} |")
    L += ["", "## Herramientas requeridas", ""]
    tl = [f"- {c['alias']}: " + ", ".join(f"{t['tool']} {t['version']}" for t in c["tools"]) for c in h["components"] if c["tools"]]
    L += tl or ["- (ninguna declarada)"]
    L += ["", "## Planes de agentic", ""]
    L += [f"- `{p['id']}` {p['estado']}: {p['asunto']}" + (f" ({p['gasto_usd']:.2f} USD)" if isinstance(p.get("gasto_usd"), (int, float)) else "") for p in h["plans"]] or ["- (ninguno)"]
    L += ["", "## Credenciales", "", "Referencias usadas: " + (", ".join(f"`{r}`" for r in h["credentials"]["refs"]) or "ninguna") + ".",
          "Sin valor en `.credentials` (hay que pedirlas): " + (", ".join(f"`{r}`" for r in h["credentials"]["missing"]) or "ninguna") + ".",
          "", "## Datos por plugin", "", "| Plugin | Ruta | Clase | Ficheros |", "|---|---|---|---|"]
    L += [f"| {d['plugin']} | `{d['path']}` | {d['class']} | {d['files']} |" for d in h["data"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="handover.py")
    ap.add_argument("--out")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--home")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    home = locate.find_home(os.path.realpath(a.home) if a.home else None)
    if not home:
        print("FAIL|handover|no hay workspace de Arkana (falta .arkana/arkana.json)", file=sys.stderr)
        return 3
    try:
        h = build(home)
    except (manifest.ManifestError, OSError) as e:
        print(f"FAIL|handover|{e}", file=sys.stderr)
        return 1
    txt = (json.dumps(h, ensure_ascii=False, indent=2) + "\n") if a.format == "json" else to_md(h)
    if a.out:
        datafiles.atomic_write(os.path.abspath(a.out), txt)
        print(f"OK|handover|informe escrito en {os.path.basename(a.out)} ({a.format})")
    else:
        sys.stdout.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
