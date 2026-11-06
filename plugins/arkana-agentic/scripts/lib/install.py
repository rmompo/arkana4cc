#!/usr/bin/env python3
"""install de arkana-agentic (repetible, --dry-run): carpetas, bloque `arkana:agentic` en el CLAUDE.md de ARKANA y plugin habilitado.

- Crea .arkana/arkana-agentic/{config,state,data} (700).
- Pone en el CLAUDE.md de ARKANA el bloque `<!-- arkana:agentic:start -->…end -->` con las reglas del orquestador (plantilla del plugin,
  templates/orquestador.md) y sustituye la referencia antigua `@orquestacion/ORQUESTADOR.md`. Copia previa en `.arkana/arkana-agentic/bak/`.
- Habilita `arkana-agentic@arkana` en ~/.claude/settings.json (copia .bak); hay que recargar los plugins después.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
import paths  # noqa: E402
import state  # noqa: E402
from arkana_core import datafiles, seedblock  # noqa: E402

PLUGIN_KEY = "arkana-agentic@arkana"
OLD_REF = "@orquestacion/ORQUESTADOR.md"
NEW_REF = "el bloque `arkana:agentic` de este fichero (lo pone `/arkana-agentic:install`)."


def template():
    with open(os.path.join(state.PLUGIN, "templates", "orquestador.md"), encoding="utf-8") as f:
        return f.read()


def claude_md():
    return os.path.join(paths.arkana_dir(), "CLAUDE.md")


def block_state():
    return seedblock.state(claude_md(), "agentic", template())


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
    p = claude_md()
    bak = os.path.join(base, "bak")
    if not os.path.isdir(os.path.dirname(p)):
        items.append(("FAIL", "bloque", "no existe la carpeta de ARKANA"))
    else:
        act = seedblock.apply(p, "agentic", template(), backup_dir=bak, dry=dry, create=False)
        if act == "falta-fichero":
            items.append(("WARN", "bloque", "falta el CLAUDE.md de ARKANA: créalo desde la plantilla (arkana-workspace:fix) y repite"))
        else:
            items.append(("DRY" if dry and act != "igual" else "OK", "bloque", f"bloque arkana:agentic {act} en CLAUDE.md"))
            with open(p, encoding="utf-8") as f:
                text = f.read()
            if OLD_REF in text:
                if not dry:
                    new = "\n".join(l.replace(OLD_REF + ".", NEW_REF).replace(OLD_REF, NEW_REF) for l in text.split("\n"))
                    datafiles.atomic_write(p, new)
                items.append(("DRY" if dry else "OK", "referencia", "sustituida la importación @orquestacion/ORQUESTADOR.md"))
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
