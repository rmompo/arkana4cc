#!/usr/bin/env python3
"""Disposición de `.arkana/` de un workspace nuevo o incompleto.

  layout.py init [--dry-run] [--json] [--home <dir>] [--base <dir>]

`init` es idempotente: crea lo que falta y nunca pisa lo que existe. Pasos, en orden:
  1. precondiciones: hay un repo de Arkana (con `plugins/`); no hay un plan activo ni procesos de lanzamiento vivos;
  2. copia de seguridad `.arkana/arkana-workspace/bak/layout-<fecha>.tar.gz` (solo si hay datos y algo que cambiar);
  3. `arkana.json`, `core/workspace.json` (solo con ARKANA: los componentes se dan de alta con `components.py add`, o `/arkana-workspace:component add`),
     `arkana-workspace/local.json` (identidad git y rutas absolutas), `arkana-workspace/tools.json`;
  4. registro del workspace en `~/.arkana-workspaces.json`.
"""
from pathlib import Path
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402

DEFAULT_BASE_REL = ".."
ACTIVE_PLAN_STATES = ("aprobado", "ejecutando", "verificando", "pausado", "borrador", "integrando")


def git(path, *args):
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=15,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def strip_credentials(url):
    """El manifiesto es exportable: nunca lleva usuario ni token incrustados en la URL."""
    return re.sub(r"^(\w+://)[^/@]*@", r"\1", url or "")


def host_of(url):
    m = re.match(r"^\w+://([^/:]+)", url or "")
    return m.group(1) if m else ""


def abs_path(v):
    return os.path.realpath(os.path.expanduser(v))


def active_plan(state):
    base = os.path.join(state, "arkana-agentic")
    for sub in ("state", ""):                                   # layout nuevo (state/) y antiguo
        try:
            pid = Path(os.path.join(base, sub, "actual")).read_text(encoding="utf-8").strip()
            plan = json.loads(Path(os.path.join(base, sub, "planes", pid, "plan.json")).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return pid if plan.get("estado") in ACTIVE_PLAN_STATES else None
    return None


def live_processes():
    try:
        r = subprocess.run(["pgrep", "-af", r"(launch|watchdog)\.py"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    me = str(os.getpid())
    return any(l.split()[0] != me and "pgrep" not in l for l in r.stdout.splitlines() if l.strip())


def build_manifest(home, root):
    """Manifiesto inicial: solo ARKANA (con su remoto, si lo tiene). Devuelve (manifiesto, rutas absolutas por alias)."""
    def rel(p):
        return os.path.relpath(abs_path(p), root)

    ark = {"alias": "ARKANA", "path": rel(home), "branches": {"main": "main", "develop": "develop"}}
    r = strip_credentials(git(home, "remote", "get-url", "origin"))
    if r:
        ark["remote"], ark["remote_host"] = r, host_of(r)
    data = {"schema": 1, "workspace": {"name": os.path.basename(os.path.dirname(home)) or "workspace"}, "arkana": ark, "components": []}
    return data, {"arkana": home}


def backup(state, dry):
    name = datetime.datetime.now().strftime("layout-%Y%m%d%H%M%S.tar.gz")
    dest = os.path.join(state, "arkana-workspace", "bak", name)
    if dry:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with tarfile.open(dest, "w:gz") as t:
        for sub in ("core", "arkana-workspace"):
            p = os.path.join(state, sub)
            if os.path.isdir(p):
                t.add(p, arcname=sub, filter=lambda ti: None if "/bak" in ti.name else ti)
    os.chmod(dest, 0o600)
    return dest


def init(home, root=None, dry=False):
    rep = output.Report("arkana-workspace", "layout-init")
    state = locate.state_dir(home)
    if not os.path.isdir(os.path.join(home, "plugins")):
        return rep.add("FAIL", "home", f"{home} no parece el repo de Arkana (no tiene plugins/)")
    pid = active_plan(state)
    if pid:
        return rep.add("FAIL", "plan-activo", f"hay un plan activo ({pid}): termínalo o deténlo antes de inicializar")
    if live_processes():
        return rep.add("FAIL", "procesos", "hay procesos de arkana-agentic (launch/watchdog) en marcha")
    root = root or os.path.abspath(os.path.join(home, DEFAULT_BASE_REL))

    arkana_json = os.path.join(state, locate.ARKANA_JSON)
    ws_json = os.path.join(state, manifest.WORKSPACE_JSON)
    local_json = os.path.join(state, manifest.LOCAL_JSON)
    tools_json = os.path.join(state, "arkana-workspace", "tools.json")
    registered = any(os.path.realpath(e.get("arkana", "")) == os.path.realpath(home) for e in locate.read_registry())

    todo = []
    if not os.path.isfile(arkana_json): todo.append(("arkana.json", arkana_json))
    if not os.path.isfile(ws_json): todo.append(("core/workspace.json", ws_json))
    if not os.path.isfile(local_json): todo.append(("arkana-workspace/local.json", local_json))
    if not os.path.isfile(tools_json): todo.append(("arkana-workspace/tools.json", tools_json))
    if not registered: todo.append(("registro", locate.registry_path()))
    if not todo:
        return rep.add("OK", "layout", "ya está inicializado")

    hay_datos = os.path.isdir(os.path.join(state, "core")) or os.path.isdir(os.path.join(state, "arkana-workspace"))
    if hay_datos:
        rep.add("DRY" if dry else "OK", "backup", backup(state, dry))

    data, abs_paths = (json.loads(Path(ws_json).read_text(encoding="utf-8")), None) if os.path.isfile(ws_json) else build_manifest(home, root)
    if abs_paths is None:
        abs_paths = {a: manifest.Workspace(home, data).path(a) for a in manifest.Workspace(home, data).aliases()}
    errs = manifest.validate(data)
    if errs:
        return rep.add("FAIL", "manifiesto", "; ".join(errs[:3]))

    def write(label, path, obj, mode=None):
        if dry:
            rep.add("DRY", label, f"crearía {os.path.relpath(path, home)}")
        else:
            datafiles.atomic_write_json(path, obj, mode=mode)
            rep.add("OK", label, f"creado {os.path.relpath(path, home)}")

    rootrel = os.path.relpath(root, home)
    if ("arkana.json", arkana_json) in todo:
        write("arkana.json", arkana_json, {"schema_version": 1, "workspace": {"name": data["workspace"]["name"]}, "root": rootrel})
    if ("core/workspace.json", ws_json) in todo:
        write("workspace.json", ws_json, data)
    if ("arkana-workspace/local.json", local_json) in todo:
        ident = {}
        for alias in manifest.Workspace(home, data).aliases():
            p = abs_paths.get(alias)
            if p and os.path.isdir(p):
                n, e = git(p, "config", "user.name"), git(p, "config", "user.email")
                if n or e:
                    ident[alias] = {k: v for k, v in (("name", n), ("email", e)) if v}
        write("local.json", local_json, {"schema_version": 1, "paths": {a: p for a, p in abs_paths.items()}, "git": ident}, mode=0o644)
    if ("arkana-workspace/tools.json", tools_json) in todo:
        write("tools.json", tools_json, {"schema_version": 1, "tools": []})
    if ("registro", locate.registry_path()) in todo:
        if dry:
            rep.add("DRY", "registro", f"registraría el workspace en {locate.registry_path()}")
        else:
            locate.register(home, data["workspace"]["name"])
            rep.add("OK", "registro", f"workspace registrado en {locate.registry_path()}")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="layout.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("init")
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--json", action="store_true")
    m.add_argument("--home")
    m.add_argument("--base", help="raíz del workspace (por defecto, el directorio padre del repo de Arkana)")
    a = ap.parse_args(argv)
    home = os.path.realpath(a.home) if a.home else (locate.find_home() or os.path.realpath(os.path.join(HERE, "..", "..", "..", "..")))
    rep = init(home, os.path.realpath(a.base) if a.base else None, a.dry_run)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
