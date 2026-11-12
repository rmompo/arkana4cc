#!/usr/bin/env python3
"""install de arkana-agentic (repetible, --dry-run): carpetas y plugin habilitado. No escribe nada en los repos.

- Crea .arkana/arkana-agentic/{config,state,data} (700).
- Habilita `arkana-agentic@arkana` en ~/.claude/settings.json (copia .bak en `.arkana/arkana-agentic/bak/`); hay que recargar los plugins después.
Las reglas del orquestador (templates/orquestador.md) las inyecta el hook de sesión `orchestrator.py` en la sesión de ARKANA: no hay ningún fichero de instrucciones.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
import state  # noqa: E402
from arkana_core import datafiles  # noqa: E402

PLUGIN_KEY = "arkana-agentic@arkana"


def user_settings():
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def plugin_enabled():
    d = datafiles.read_json(user_settings())
    return None if d is None else bool((d.get("enabledPlugins") or {}).get(PLUGIN_KEY))


def run(dry=False, no_settings=False):
    """-> [(estado, id, detalle)]."""
    items = []
    base = state.base_dir()
    falta = [d for d in ("config", "state", "data") if not os.path.isdir(os.path.join(base, d))]
    if falta:
        if not dry:
            state.ensure_base_dir()
        items.append(("DRY" if dry else "OK", "carpetas", "se crean " + ", ".join(falta) if dry else "creadas " + ", ".join(falta)))
    else:
        items.append(("OK", "carpetas", "config, state y data presentes"))
    bak = os.path.join(base, "bak")
    if not no_settings:
        en = plugin_enabled()
        if en:
            items.append(("OK", "plugin", f"{PLUGIN_KEY} habilitado"))
        elif dry:
            items.append(("DRY", "plugin", f"se habilitaría {PLUGIN_KEY} en ~/.claude/settings.json"))
        else:
            f = user_settings()
            cur = datafiles.read_json(f, {}) or {}
            if os.path.isfile(f):
                os.makedirs(bak, exist_ok=True)
                with open(f, "rb") as s, open(os.path.join(bak, "settings.json." + time.strftime("%Y%m%dT%H%M%S")), "wb") as d:
                    d.write(s.read())
            cur.setdefault("enabledPlugins", {})[PLUGIN_KEY] = True
            datafiles.atomic_write_json(f, cur)
            items.append(("OK", "plugin", f"{PLUGIN_KEY} habilitado: recarga los plugins o reinicia la sesión"))
    return items


def main(a):
    items = run(getattr(a, "dry_run", False), getattr(a, "no_settings", False))
    for st, i, d in items:
        print(f"{st}|install:{i}|{d}")
    return 1 if any(st == "FAIL" for st, _, _ in items) else 0


if __name__ == "__main__":
    sys.exit(0)
