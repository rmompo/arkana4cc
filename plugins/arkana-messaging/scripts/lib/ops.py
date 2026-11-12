#!/usr/bin/env python3
"""install | check | fix de arkana-messaging.

  ops.py check   [--component ALIAS|--all] [--json]
  ops.py install [--dry-run] [--json] [--no-settings]
  ops.py fix     [--dry-run] [--json]

check (solo lectura): almacén, plugin habilitado y latido de los hooks (de ESTA sesión por `CLAUDE_CODE_SESSION_ID`; respaldo: latido del
componente en los últimos 15 min). `--all` y `--component` se aceptan por compatibilidad con el contrato; no cambian nada.
install (repetible): crea el almacén y habilita el plugin en `~/.claude/settings.json` (copia .bak en `.arkana/arkana-messaging/bak/`). No escribe
nada en los repos: las instrucciones de uso las inyecta el hook de sesión. Tras `install` hay que recargar los plugins de la sesión.
fix: aplica solo lo que `check` marca (almacén, plugin).
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, HERE)
from arkana_core import datafiles, locate, manifest, output  # noqa: E402
import messages as M  # noqa: E402

PLUGIN_KEY = "arkana-messaging@arkana"
HEARTBEAT_WINDOW = 15 * 60

def user_settings():
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def plugin_enabled():
    d = datafiles.read_json(user_settings())
    if d is None:
        return None
    return bool((d.get("enabledPlugins") or {}).get(PLUGIN_KEY))


def heartbeat_ok(store, actor):
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if sid and os.path.isfile(os.path.join(store.dir, "sessions", sid + ".json")):
        return True, "los hooks han corrido en esta sesión"
    d = os.path.join(store.dir, "sessions")
    best = 0
    for f in os.listdir(d) if os.path.isdir(d) else []:
        hb = datafiles.read_json(os.path.join(d, f), {}) or {}
        if hb.get("actor") == actor:
            best = max(best, os.path.getmtime(os.path.join(d, f)))
    if best and time.time() - best < HEARTBEAT_WINDOW:
        return True, "hay un latido reciente de este componente (respaldo; no se pudo comprobar la sesión exacta)"
    return False, "los hooks no han corrido en esta sesión"


def findings(ws, home, store, actor):
    """[(id, estado, detalle, arreglo|None)]."""
    res = []
    ok = os.path.isdir(os.path.join(store.dir, "messages"))
    res.append(("almacen", "OK" if ok else "WARN", "almacén de mensajes presente" if ok else "falta el almacén (install lo crea)", "store"))
    en = plugin_enabled()
    res.append(("plugin", "OK" if en else "WARN" if en is False else "INFO",
                "arkana-messaging habilitado" if en else "arkana-messaging no está habilitado en ~/.claude/settings.json" if en is False
                else "no se encuentra ~/.claude/settings.json (¿instalado a nivel de proyecto?)", "plugin" if en is False else None))
    hb, det = heartbeat_ok(store, actor)
    res.append(("latido", "OK" if hb else "WARN", det + ("" if hb else ": ejecuta /arkana-messaging:install y recarga los plugins"), None))
    return res


def do(cmd, a):
    rep = output.Report("arkana-messaging", cmd)
    home, ws, store, actor = M.ctx()
    dry = getattr(a, "dry_run", False)
    todo = findings(ws, home, store, actor)
    if cmd == "check":
        for i, st, d, _ in todo:
            rep.add(st, i, d)
        return rep
    bak = os.path.join(locate.state_dir(home), "arkana-messaging", "bak")
    for i, st, d, fix in todo:
        if cmd == "fix" and st == "OK":
            continue
        if fix == "store" or (cmd == "install" and i == "almacen"):
            if st != "OK" or cmd == "install":
                if not dry:
                    os.makedirs(os.path.join(store.dir, "messages"), exist_ok=True)
                if st != "OK":
                    rep.add("DRY" if dry else "OK", i, "se crea el almacén" if dry else "almacén creado")
        elif i == "plugin" and (fix == "plugin" or cmd == "install") and not a.__dict__.get("no_settings"):
            f = user_settings()
            cur = datafiles.read_json(f, {}) or {}
            if (cur.get("enabledPlugins") or {}).get(PLUGIN_KEY):
                continue
            if dry:
                rep.add("DRY", i, f"se habilitaría {PLUGIN_KEY} en ~/.claude/settings.json")
            else:
                if os.path.isfile(f):
                    os.makedirs(bak, exist_ok=True)
                    with open(f, "rb") as src, open(os.path.join(bak, "settings.json." + time.strftime("%Y%m%dT%H%M%S")), "wb") as dst:
                        dst.write(src.read())
                cur.setdefault("enabledPlugins", {})[PLUGIN_KEY] = True
                datafiles.atomic_write_json(f, cur)
                rep.add("OK", i, f"{PLUGIN_KEY} habilitado: recarga los plugins (/reload-plugins) o reinicia la sesión")
    if cmd == "fix":                                        # lo que `check` marca y `fix` no sabe arreglar se sigue avisando
        hechos = {it["id"] for it in rep.items}
        for i, st, d, _ in todo:
            if st != "OK" and i not in hechos:
                rep.add(st, i, f"{d} (sin arreglo automático)")
    if not rep.items:
        rep.add("OK", cmd, "nada que hacer: todo está al día")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ops.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("check", "install", "fix"):
        p = sub.add_parser(n)
        p.add_argument("--json", action="store_true")
        if n == "check":
            p.add_argument("--component")
            p.add_argument("--all", action="store_true")
        else:
            p.add_argument("--dry-run", dest="dry_run", action="store_true")
            p.add_argument("--no-settings", dest="no_settings", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        rep = do(a.cmd, a)
    except M.MessageError as e:
        rep = output.Report("arkana-messaging", a.cmd).add("FAIL", e.donde, str(e))
        sys.stdout.write(rep.render(a.json))
        return e.cod
    except (OSError, KeyError) as e:
        rep = output.Report("arkana-messaging", a.cmd).add("FAIL", a.cmd, str(e))
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
