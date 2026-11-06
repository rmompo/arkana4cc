#!/usr/bin/env python3
"""install | check | fix de arkana-statusline. La statusline es de Claude Code (un comando por usuario): se instala en ~/.claude/arkana-statusline/.

  ops.py install [--replace] [--dry-run] [--json]    copia statusline.sh, statusline.py y arkana_core/ y activa `statusLine` en ~/.claude/settings.json
  ops.py check   [--json]                            solo lectura: copia al día, `statusLine` activa y nuestra, sin otra statusline, prueba de humo
  ops.py fix     [--dry-run] [--json]                reinstala lo desactualizado y activa `statusLine` si falta (nunca sustituye la de otro: eso es --replace)

Una `statusLine` ajena (otro script o plugin) solo se sustituye con `install --replace`, con copia de los ajustes en `~/.claude/arkana-statusline/bak/`.
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
from arkana_core import datafiles, output  # noqa: E402

PLUGIN_KEY = "arkana-statusline@arkana"
COMMAND = "bash ~/.claude/arkana-statusline/statusline.sh"
SAMPLE = {"workspace": {"project_dir": "/tmp"}, "model": {"display_name": "Test"}, "session_id": "check"}


def dest():
    return os.path.join(os.path.expanduser("~"), ".claude", "arkana-statusline")


def settings_path():
    return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")


def sources():
    """{ruta relativa instalada: ruta fuente} de todo lo que se copia."""
    res = {"statusline.sh": os.path.join(PLUGIN, "statusline", "statusline.sh"), "statusline.py": os.path.join(PLUGIN, "statusline", "statusline.py")}
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
    return isinstance(sl, dict) and "arkana-statusline/statusline.sh" in str(sl.get("command", ""))


def other_statusline_plugins():
    d = datafiles.read_json(settings_path(), {}) or {}
    return sorted(k for k, v in (d.get("enabledPlugins") or {}).items() if v and "statusline" in k.lower() and k != PLUGIN_KEY)


def smoke():
    f = os.path.join(dest(), "statusline.sh")
    if not os.path.isfile(f):
        return False, "no está instalada"
    try:
        p = subprocess.run(["bash", f], input=json.dumps(SAMPLE), capture_output=True, text=True, timeout=10, env=dict(os.environ, COLUMNS="120"))
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"no se pudo ejecutar: {e}"
    n = len(p.stdout.strip().splitlines())
    return (p.returncode == 0 and n >= 1 and "arkana-statusline:" not in p.stdout), f"{n} líneas, rc {p.returncode}"


def check():
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
        rep.add("OK", "statusline", "statusLine apunta a arkana-statusline")
    elif not sl:
        rep.add("WARN", "statusline", "no hay statusLine: /arkana-statusline:install")
    else:
        rep.add("WARN", "statusline", "hay otra statusLine activa (" + str(sl.get("command", sl))[:60] + "): /arkana-statusline:install --replace")
    otros = other_statusline_plugins()
    rep.add("WARN" if otros else "OK", "otros-plugins", ("plugins de statusline habilitados que pueden pisarla: " + ", ".join(otros)) if otros else "ningún otro plugin de statusline")
    ok, det = smoke()
    rep.add("OK" if ok else "WARN", "humo", det if ok else f"prueba de humo fallida ({det})")
    return rep


def install(replace=False, dry=False, only_if_missing=False):
    rep = output.Report("arkana-statusline", "fix" if only_if_missing else "install")
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
        rep.add("OK", "statusline", "statusLine ya apunta a arkana-statusline")
    elif sl and not replace:
        rep.add("WARN", "statusline", "hay otra statusLine activa (" + str(sl.get("command", sl))[:60] + "): usa install --replace para sustituirla")
    else:
        cambia = True
        d["statusLine"] = {"type": "command", "command": COMMAND}
        rep.add("DRY" if dry else "OK", "statusline", ("sustituye la statusLine anterior" if sl else "activa la statusLine") + " (copia de los ajustes en ~/.claude/arkana-statusline/bak/)")
    if not (d.get("enabledPlugins") or {}).get(PLUGIN_KEY):
        cambia = True
        d.setdefault("enabledPlugins", {})[PLUGIN_KEY] = True
        rep.add("DRY" if dry else "OK", "plugin", f"{PLUGIN_KEY} habilitado")
    if cambia and not dry:
        if os.path.isfile(settings_path()):
            bak = os.path.join(dest(), "bak")
            os.makedirs(bak, exist_ok=True)
            shutil.copy2(settings_path(), os.path.join(bak, "settings.json." + time.strftime("%Y%m%dT%H%M%S")))
        datafiles.atomic_write_json(settings_path(), d)
        rep.add("INFO", "recarga", "reinicia Claude Code o recarga los plugins para ver la nueva statusline")
    if not dry:
        ok, det = smoke()
        rep.add("OK" if ok else "WARN", "humo", det if ok else f"prueba de humo fallida ({det})")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ops.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("install", "check", "fix"):
        p = sub.add_parser(n)
        p.add_argument("--json", action="store_true")
        if n != "check":
            p.add_argument("--dry-run", dest="dry_run", action="store_true")
        if n == "install":
            p.add_argument("--replace", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = check() if a.cmd == "check" else install(getattr(a, "replace", False), a.dry_run, a.cmd == "fix")
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
