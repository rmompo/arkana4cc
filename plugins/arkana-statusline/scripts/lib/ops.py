#!/usr/bin/env python3
"""install | check | fix | choose | uninstall de arkana-statusline. La `statusLine` de Claude Code es una por ámbito: Arkana ocupa la de usuario con un despachador
(statusline.sh → dispatch.py) que decide en cada render qué statusline se ve según el cwd (ver statusline/dispatch.py). Se instala en ~/.claude/arkana-statusline/.

  ops.py install [--dry-run] [--json]                  copia statusline.sh, dispatch.py, statusline.py y arkana_core/ y activa `statusLine` en ~/.claude/settings.json;
                                                       la statusLine ajena que hubiera pasa a ser un proveedor (~/.arkana/statusline.json): con Arkana instalada, Arkana gobierna
  ops.py check   [--home DIR] [--json]                 solo lectura: copia al día, `statusLine` de usuario del despachador, proveedores, elecciones por componente, humo
  ops.py fix     [--dry-run] [--json]                  reinstala lo desactualizado y activa `statusLine` si falta (nunca sustituye la de otro: eso es --replace)
  ops.py choose  --component ALIAS --use arkana|other|ask [--home DIR] [--json]
                                                       qué se ve al entrar en ese componente: la de Arkana, la que haya (proveedores) o volver a preguntar
  ops.py uninstall [--dry-run] [--json]                devuelve la `statusLine` de usuario al proveedor de mayor prioridad (o la quita) y borra la copia de Arkana
  ops.py provider list|add|remove|auto on|off          proveedores (otras statuslines) y recuperación automática del hueco (ver `reclaim`)
  ops.py reclaim [--dry-run] [--json]                  si otra herramienta pisó la `statusLine` de usuario, la deja como proveedor y recoloca el despachador (lo hace también el hook)

Con Arkana instalada, Arkana gobierna las statuslines y su jerarquía: `install` ocupa el hueco de usuario y la `statusLine` ajena que hubiera queda como proveedor (con copia de los ajustes en `~/.claude/arkana-statusline/bak/`).
Sin Arkana instalada no existe nada de esto y las demás statuslines siguen su tratamiento habitual. `--replace` se acepta por compatibilidad y ya no hace falta.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, os.path.join(PLUGIN, "statusline"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402
import dispatch  # noqa: E402

PLUGIN_KEY = "arkana-statusline@arkana"
COMMAND = "bash ~/.claude/arkana-statusline/statusline.sh"
MARK = "arkana-statusline/statusline.sh"
SAMPLE = {"workspace": {"project_dir": "/tmp"}, "model": {"display_name": "Test"}, "session_id": "check"}
PROGRAM = ("statusline.sh", "dispatch.py", "statusline.py", "arkana_core")


def dest():
    return os.path.join(os.path.expanduser("~"), ".claude", "arkana-statusline")


def settings_path():
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def sources():
    """{ruta relativa instalada: ruta fuente} de todo lo que se copia."""
    res = {n: os.path.join(PLUGIN, "statusline", n) for n in ("statusline.sh", "dispatch.py", "statusline.py")}
    core = os.path.join(PLUGIN, "scripts", "_core", "arkana_core")
    for dp, dns, fns in os.walk(core):
        dns[:] = sorted(d for d in dns if d not in ("tests", "__pycache__"))
        for f in sorted(fns):
            if not f.endswith(".pyc"):
                res[os.path.join("arkana_core", os.path.relpath(os.path.join(dp, f), core))] = os.path.join(dp, f)
    return res


def sha(p):
    try:
        with open(p, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def outdated():
    return [rel for rel, src in sources().items() if sha(os.path.join(dest(), rel)) != sha(src)]


def status_line():
    d = datafiles.read_json(settings_path())
    return None if d is None else d.get("statusLine")


def is_ours(sl):
    return isinstance(sl, dict) and MARK in str(sl.get("command", ""))


def other_statusline_plugins():
    d = datafiles.read_json(settings_path(), {}) or {}
    return sorted(k for k, v in (d.get("enabledPlugins") or {}).items() if v and "statusline" in k.lower() and k != PLUGIN_KEY)


def save_prefs(prefs):
    datafiles.atomic_write_json(dispatch.prefs_path(), prefs, mode=0o600)


P4CC_SCRIPT = os.path.join("~", ".claude", "statusline-command.sh")


def provider_id(command):
    """(id, prioridad) del proveedor que corresponde a una statusLine ajena: plugin4cc (20) antes que cualquier otra (30, con un id por comando para que convivan varias)."""
    if "statusline-command.sh" in command:
        return "plugin4cc", 20
    return "other-" + hashlib.sha1(command.encode("utf-8")).hexdigest()[:8], 30


def add_provider(prefs, pid, command, priority):
    """Añade o reemplaza (mismo id o mismo comando) un proveedor; no duplica."""
    prefs["providers"] = [p for p in prefs["providers"] if not (isinstance(p, dict) and (p.get("id") == pid or p.get("command") == command))] + [{"id": pid, "command": command, "priority": priority}]


def backup_settings():
    if os.path.isfile(settings_path()):
        bak = os.path.join(dest(), "bak")
        os.makedirs(bak, exist_ok=True)
        shutil.copy2(settings_path(), os.path.join(bak, "settings.json." + time.strftime("%Y%m%dT%H%M%S")))


def installed():
    return os.path.isfile(os.path.join(dest(), "statusline.sh"))


def claimed():
    """¿Arkana ha ocupado alguna vez el hueco de usuario? Solo entonces puede recuperarlo (copiar los ficheros sin tomar el hueco no cuenta)."""
    return dispatch.load_prefs().get("claimed") is True


def set_claimed(valor):
    prefs = dispatch.load_prefs()
    if prefs.get("claimed") is not valor:
        prefs["claimed"] = valor
        save_prefs(prefs)


def smoke():
    f = os.path.join(dest(), "statusline.sh")
    if not os.path.isfile(f):
        return False, "no está instalada"
    try:
        r = subprocess.run([sys.executable, "-I", os.path.join(dest(), "statusline.py")], input=json.dumps(SAMPLE), capture_output=True, text=True, timeout=10,
                           env=dict(os.environ, COLUMNS="120"))
        d = subprocess.run(["bash", f], input=json.dumps(SAMPLE), capture_output=True, text=True, timeout=10, env=dict(os.environ, COLUMNS="120"))
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"no se pudo ejecutar: {e}"
    n = len(r.stdout.strip().splitlines())
    return (r.returncode == 0 and n >= 1 and "arkana-statusline:" not in r.stdout and d.returncode == 0), f"{n} líneas, rc {r.returncode}/{d.returncode}"


def check(home=None):
    rep = output.Report("arkana-statusline", "check")
    rep.add("OK" if shutil.which("python3") else "FAIL", "python3", "disponible" if shutil.which("python3") else "falta python3")
    rep.add("OK" if shutil.which("git") else "FAIL", "git", "disponible" if shutil.which("git") else "falta git")
    if not os.path.isdir(dest()):
        rep.add("WARN", "instalada", "no hay copia en ~/.claude/arkana-statusline: /arkana-statusline:install")
    else:
        old = outdated()
        rep.add("OK" if not old else "WARN", "copia", "copia al día" if not old else f"desactualizada ({len(old)} ficheros: {', '.join(old[:3])}): /arkana-statusline:fix")
    sl = status_line()
    if sl is None:
        rep.add("INFO", "statusline", "no hay ~/.claude/settings.json")
    elif is_ours(sl):
        rep.add("OK", "statusline", "la statusLine de usuario es el despachador de arkana-statusline")
    elif not sl:
        rep.add("WARN", "statusline", "no hay statusLine de usuario: /arkana-statusline:install")
    else:
        rep.add("WARN", "statusline", "la statusLine de usuario es de otro (" + str(sl.get("command", sl))[:60] + ") y el despachador no se ejecuta: /arkana-statusline:install (o fix) recoloca el despachador y la deja como proveedor")
    prefs = dispatch.load_prefs()
    provs = dispatch.providers(prefs)
    rep.add("INFO", "proveedores", ("; ".join(f"{p.get('id', '?')} (prioridad {p.get('priority', '?')})" for p in provs)) if provs else "ninguno: fuera de ARKANA y sin elegir la de Arkana no se ve ninguna statusline")
    home = home or locate.find_home()
    if home:
        try:
            comps = manifest.load(home).aliases(False)
        except Exception:
            comps = []
        el = {a: prefs["components"].get(dispatch.choice_key(home, a)) for a in comps}
        if comps:
            rep.add("INFO", "elecciones", ", ".join(f"{a}: {el[a] or 'sin elegir'}" for a in comps))
    otros = other_statusline_plugins()
    rep.add("INFO" if otros else "OK", "otros-plugins", ("plugins de statusline habilitados (deben registrarse como proveedor y no pisar la de usuario): " + ", ".join(otros)) if otros else "ningún otro plugin de statusline")
    ok, det = smoke()
    rep.add("OK" if ok else "WARN", "humo", det if ok else f"prueba de humo fallida ({det})")
    return rep


def install(replace=False, dry=False, only_if_missing=False):
    rep = output.Report("arkana-statusline", "fix" if only_if_missing else "install")
    if not only_if_missing or (claimed() and dispatch.load_prefs().get("auto_reclaim") is not False):
        replace = True                                           # install, o fix sobre una instalación existente: con Arkana instalada, su jerarquía manda (como `reclaim`)
    old = outdated()
    if old:
        if not dry:
            for rel, src in sources().items():
                t = os.path.join(dest(), rel)
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(src, t)
            os.chmod(os.path.join(dest(), "statusline.sh"), 0o755)
        rep.add("DRY" if dry else "OK", "copia", f"{len(old)} ficheros {'se copiarían a' if dry else 'copiados a'} ~/.claude/arkana-statusline")
    else:
        rep.add("OK", "copia", "copia al día")
    sl = status_line()
    d = datafiles.read_json(settings_path(), {}) or {}
    cambia = False
    if is_ours(sl):
        rep.add("OK", "statusline", "la statusLine de usuario ya es el despachador de arkana-statusline")
    elif sl and not replace:
        rep.add("WARN", "statusline", "hay otra statusLine de usuario (" + str(sl.get("command", sl))[:60] + "): fix no la sustituye sin una instalación previa de Arkana; /arkana-statusline:install ocupa el hueco y la actual pasa a ser un proveedor (se sigue viendo fuera de ARKANA)")
    else:
        cambia = True
        if sl and sl.get("command"):
            pid, prio = provider_id(str(sl["command"]))
            if not dry:
                prefs = dispatch.load_prefs()
                add_provider(prefs, pid, str(sl["command"]), prio)
                save_prefs(prefs)
            rep.add("DRY" if dry else "OK", "proveedor", f"la statusLine anterior queda como proveedor «{pid}» (prioridad {prio}) en ~/.arkana/statusline.json")
        d["statusLine"] = {"type": "command", "command": COMMAND}
        rep.add("DRY" if dry else "OK", "statusline", ("sustituye la statusLine anterior" if sl else "activa la statusLine") + " (copia de los ajustes en ~/.claude/arkana-statusline/bak/)")
    script = os.path.expanduser(P4CC_SCRIPT)
    if os.path.isfile(script) and not any(isinstance(p, dict) and p.get("id") == "plugin4cc" for p in dispatch.load_prefs()["providers"]) and (cambia or is_ours(sl)):
        if not dry:
            prefs = dispatch.load_prefs()
            add_provider(prefs, "plugin4cc", "bash " + P4CC_SCRIPT, 20)
            save_prefs(prefs)
        rep.add("DRY" if dry else "OK", "proveedor", "detectado el script de plugin4cc (~/.claude/statusline-command.sh): registrado como proveedor «plugin4cc» (prioridad 20)")
    if not (d.get("enabledPlugins") or {}).get(PLUGIN_KEY):
        cambia = True
        d.setdefault("enabledPlugins", {})[PLUGIN_KEY] = True
        rep.add("DRY" if dry else "OK", "plugin", f"{PLUGIN_KEY} habilitado")
    if cambia and not dry:
        backup_settings()
        datafiles.atomic_write_json(settings_path(), d)
    if not dry and is_ours(d.get("statusLine")):
        set_claimed(True)
        rep.add("INFO", "recarga", "reinicia Claude Code o recarga los plugins para ver la nueva statusline")
    if not dry:
        ok, det = smoke()
        rep.add("OK" if ok else "WARN", "humo", det if ok else f"prueba de humo fallida ({det})")
    return rep


def choose(component, use, home=None, dry=False):
    rep = output.Report("arkana-statusline", "choose")
    home = home or locate.find_home()
    if not home:
        rep.add("FAIL", "workspace", "no hay un workspace de Arkana (usa --home o ejecuta dentro de uno)")
        return rep, 3
    try:
        comps = manifest.load(home).aliases(False)
    except Exception as e:
        rep.add("FAIL", "manifiesto", f"no se pudo leer el manifiesto: {e}")
        return rep, 1
    alias = manifest.canon(component)
    if alias == "arkana":
        rep.add("FAIL", "componente", "en la carpeta de ARKANA se ve siempre la statusline de Arkana; la elección es solo para componentes")
        return rep, 2
    if alias not in comps:
        rep.add("FAIL", "componente", f"componente desconocido: {component} (válidos: {', '.join(comps)})")
        return rep, 2
    prefs = dispatch.load_prefs()
    key = dispatch.choice_key(home, alias)
    if use == "ask":
        prefs["components"].pop(key, None)
        txt = "se volverá a preguntar la próxima vez que se abra Claude Code en ese componente"
    else:
        prefs["components"][key] = use
        txt = "se verá la statusline de Arkana" if use == "arkana" else "se verá la que haya configurada (proveedores)"
    if not dry:
        save_prefs(prefs)
    rep.add("DRY" if dry else "OK", alias, txt, component=alias)
    return rep, None


def reclaim(dry=False):
    """Si hay un despachador instalado y otra herramienta pisó la `statusLine` de usuario, la captura como proveedor y recoloca el despachador. (cambió, mensaje)."""
    prefs = dispatch.load_prefs()
    sl = status_line()
    if is_ours(sl):
        if not dry and installed() and prefs.get("claimed") is not True:        # instalación anterior a esta marca: se anota una vez
            set_claimed(True)
        return False, None
    if prefs.get("auto_reclaim") is False or not installed() or prefs.get("claimed") is not True:
        return False, None
    cmd = str(sl.get("command", "")) if isinstance(sl, dict) else ""
    pid = None
    if cmd:
        pid, prio = provider_id(cmd)
    if not dry:
        if pid:
            add_provider(prefs, pid, cmd, prio)
            save_prefs(prefs)
        d = datafiles.read_json(settings_path(), {}) or {}
        backup_settings()
        d["statusLine"] = {"type": "command", "command": COMMAND}
        datafiles.atomic_write_json(settings_path(), d)
    msg = "Arkana's statusline dispatcher was restored" + (f"; the statusLine another tool had written ({cmd[:60]}) is kept as provider '{pid}'" if pid else "") + " (/arkana-statusline:provider to review)"
    return True, msg


def provider_cmd(a):
    rep = output.Report("arkana-statusline", "provider")
    prefs = dispatch.load_prefs()
    if a.action == "list":
        provs = dispatch.providers(prefs)
        for p in provs:
            rep.add("INFO", p.get("id", "?"), f"prioridad {p.get('priority', '?')} · {p['command']}")
        rep.add("INFO", "auto-reclaim", "activada" if prefs.get("auto_reclaim") is not False else "desactivada")
        if not provs:
            rep.add("INFO", "proveedores", "ninguno")
    elif a.action == "add":
        if not a.id or not a.command:
            rep.add("FAIL", "provider", "add necesita --id y --command")
            return rep
        prio = a.priority if a.priority is not None else (provider_id(a.command)[1])
        add_provider(prefs, a.id, a.command, prio)
        if not a.dry_run:
            save_prefs(prefs)
        rep.add("DRY" if a.dry_run else "OK", a.id, f"proveedor registrado (prioridad {prio})")
    elif a.action == "remove":
        n = len(prefs["providers"])
        prefs["providers"] = [p for p in prefs["providers"] if not (isinstance(p, dict) and p.get("id") == a.id)]
        if len(prefs["providers"]) == n:
            rep.add("FAIL", a.id or "provider", "no existe ese proveedor")
            return rep
        if not a.dry_run:
            save_prefs(prefs)
        rep.add("DRY" if a.dry_run else "OK", a.id, "proveedor quitado")
    else:
        prefs["auto_reclaim"] = a.value == "on"
        if not a.dry_run:
            save_prefs(prefs)
        rep.add("DRY" if a.dry_run else "OK", "auto-reclaim", "activada: si otra herramienta pisa la statusLine de usuario, Arkana la recupera y la deja como proveedor" if a.value == "on" else "desactivada: solo se avisa con check")
    return rep


def uninstall(dry=False):
    rep = output.Report("arkana-statusline", "uninstall")
    sl = status_line()
    d = datafiles.read_json(settings_path(), {}) or {}
    if is_ours(sl):
        provs = dispatch.providers(dispatch.load_prefs())
        if provs:
            nuevo = {"type": "command", "command": provs[0]["command"]}
            txt = f"la statusLine de usuario vuelve a «{provs[0].get('id', '?')}»"
        else:
            nuevo, txt = None, "se quita la statusLine de usuario (no hay proveedores)"
        if not dry:
            backup_settings()
            if nuevo:
                d["statusLine"] = nuevo
            else:
                d.pop("statusLine", None)
            datafiles.atomic_write_json(settings_path(), d)
            set_claimed(False)
        rep.add("DRY" if dry else "OK", "statusline", txt + " (copia de los ajustes en ~/.claude/arkana-statusline/bak/)")
    else:
        rep.add("OK", "statusline", "la statusLine de usuario no es del despachador: no se toca")
    presentes = [n for n in PROGRAM if os.path.exists(os.path.join(dest(), n))]
    if presentes and not dry:
        for n in presentes:
            p = os.path.join(dest(), n)
            shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.unlink(p)
    if presentes:
        rep.add("DRY" if dry else "OK", "copia", ("se borrarían" if dry else "borrados") + " los ficheros de la statusline de ~/.claude/arkana-statusline (las copias bak/ y las elecciones en ~/.arkana/statusline.json se conservan)")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ops.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("install", "check", "fix", "choose", "uninstall", "provider", "reclaim"):
        p = sub.add_parser(n)
        p.add_argument("--json", action="store_true")
        if n == "provider":
            p.add_argument("action", choices=("list", "add", "remove", "auto"))
            p.add_argument("value", nargs="?", choices=("on", "off"))
            p.add_argument("--id")
            p.add_argument("--command")
            p.add_argument("--priority", type=int)
        if n in ("install", "fix", "uninstall", "choose", "provider", "reclaim"):
            p.add_argument("--dry-run", dest="dry_run", action="store_true")
        if n == "install":
            p.add_argument("--replace", action="store_true")
        if n in ("check", "choose"):
            p.add_argument("--home")
        if n == "choose":
            p.add_argument("--component", required=True)
            p.add_argument("--use", required=True, choices=("arkana", "other", "ask"))
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if a.cmd == "choose":
        rep, code = choose(a.component, a.use, os.path.abspath(a.home) if a.home else None, a.dry_run)
        sys.stdout.write(rep.render(a.json))
        return code if code is not None else rep.exit_code()
    if a.cmd == "provider":
        if a.action == "auto" and not a.value:
            ap.error("provider auto necesita on u off")
        rep = provider_cmd(a)
    elif a.cmd == "reclaim":
        rep = output.Report("arkana-statusline", "reclaim")
        cambio, msg = reclaim(a.dry_run)
        rep.add("DRY" if a.dry_run and cambio else ("OK"), "reclaim", msg if cambio else "nada que recuperar")
    elif a.cmd == "check":
        rep = check(os.path.abspath(a.home) if a.home else None)
    elif a.cmd == "uninstall":
        rep = uninstall(a.dry_run)
    else:
        rep = install(getattr(a, "replace", False), a.dry_run, a.cmd == "fix")
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
