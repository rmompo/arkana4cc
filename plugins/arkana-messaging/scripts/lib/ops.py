#!/usr/bin/env python3
"""install | check | fix de arkana-messaging.

  ops.py check   [--component ALIAS|--all] [--json]
  ops.py install [--dry-run] [--json] [--no-settings]
  ops.py fix     [--dry-run] [--json]

check (solo lectura): almacén, plugin habilitado, latido de los hooks (de ESTA sesión por `CLAUDE_CODE_SESSION_ID`; respaldo: latido del
componente en los últimos 15 min) y semilla del componente actual (con --all, la de todos).
install (repetible): crea el almacén, habilita el plugin en `~/.claude/settings.json` (copia .bak) y pone la semilla `arkana:messaging` en el
ARKANA y en cada componente (CLAUDE.md, o CLAUDE.local.md en los que lo declaran como seed_file; copia en `.arkana/arkana-messaging/bak/`). Quita del CLAUDE.md de
ARKANA la importación obsoleta `@.arkana/core/novedades.md`. Tras `install` hay que recargar los plugins de la sesión.
fix: aplica solo lo que `check --all` marca (almacén, plugin, semillas).
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, HERE)
from arkana_core import datafiles, locate, manifest, output, seedblock  # noqa: E402
import messages as M  # noqa: E402

PLUGIN_KEY = "arkana-messaging@arkana"
OLD_IMPORTS = {"@.arkana/core/novedades.md"}
HEARTBEAT_WINDOW = 15 * 60

SEED = """<!-- arkana-messaging: bloque generado por /arkana-messaging:install; no se edita a mano -->
## Mensajería de Arkana

- **En tu primer turno** ejecuta `/arkana-messaging:check`. Si dice que los hooks no han corrido en esta sesión, ejecuta `/arkana-messaging:install` y avisa al usuario de que recargue los plugins (`/reload-plugins`) o reinicie la sesión.
- Los mensajes sin leer para este componente llegan **inyectados** al abrir la sesión y en cada prompt. Propón al usuario atenderlos; nunca los des por hechos ni cierres nada sin su confirmación. Lo pendiente: `/arkana-messaging:get --pending`.
- Al terminar una tarea, revisión o pregunta, propón cerrarla con `/arkana-messaging:put --done <id> --result "..."`. Nunca incluyas credenciales ni datos personales en un mensaje."""


def seed_target(ws, alias):
    a = manifest.canon(alias)
    if a == "arkana":
        return os.path.join(ws.path("arkana"), "CLAUDE.md")
    return os.path.join(ws.path(a), ws.get(a).get("seed_file") or "CLAUDE.md")


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


def findings(ws, home, store, actor, aliases):
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
    for al in aliases:
        p = seed_target(ws, al)
        if not os.path.isdir(os.path.dirname(p)):
            res.append((f"semilla-{al}", "WARN", "no existe la carpeta del componente", None))
            continue
        st = seedblock.state(p, "messaging", SEED)
        rel = os.path.relpath(p, ws.root)
        if st == "OK":
            res.append((f"semilla-{al}", "OK", f"semilla al día en {rel}", None))
        elif st == "SIN-FICHERO" and os.path.basename(p) == "CLAUDE.md":
            res.append((f"semilla-{al}", "WARN", f"falta {rel}: créalo con /arkana-workspace:fix y repite", None))
        else:
            res.append((f"semilla-{al}", "WARN", f"{rel}: {st}", ("seed", al)))
    return res


def do(cmd, a):
    rep = output.Report("arkana-messaging", cmd)
    home, ws, store, actor = M.ctx()
    aliases = ws.aliases() if (cmd != "check" or a.all) else [manifest.canon(a.component) if a.component else actor]
    dry = getattr(a, "dry_run", False)
    todo = findings(ws, home, store, actor, ws.aliases() if cmd != "check" else aliases)
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
        elif (isinstance(fix, tuple) and fix[0] == "seed") or (cmd == "install" and i.startswith("semilla-")):
            al = fix[1] if isinstance(fix, tuple) else i[len("semilla-"):]
            p = seed_target(ws, al)
            if not os.path.isdir(os.path.dirname(p)):
                rep.add("WARN", i, "no existe la carpeta del componente")
                continue
            act = seedblock.apply(p, "messaging", SEED, backup_dir=os.path.join(bak, al), dry=dry, create=os.path.basename(p) != "CLAUDE.md")
            if al == "arkana":
                n = seedblock.drop_lines(p, OLD_IMPORTS, backup_dir=os.path.join(bak, al), dry=dry)
                if n:
                    rep.add("DRY" if dry else "OK", "import-obsoleto", f"quitada la importación @.arkana/core/novedades.md de {os.path.relpath(p, ws.root)}")
            if act == "falta-fichero":
                rep.add("WARN", i, f"falta {os.path.relpath(p, ws.root)}: créalo con /arkana-workspace:fix y repite")
            elif act != "igual":
                rep.add("DRY" if dry else "OK", i, f"semilla {act} en {os.path.relpath(p, ws.root)}")
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
