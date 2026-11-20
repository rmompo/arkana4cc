#!/usr/bin/env python3
"""Plan de instalación de Arkana: localiza los plugins hermanos y calcula, en solo lectura, los pasos del pipeline.

  pipeline.py plan [--home <dir>] [--json]

No instala nada ni escribe ficheros: el skill `/arkana:install` ejecuta cada paso (primero `dry`, luego `apply`) y pide
confirmación. Este script existe porque el plugin `arkana` no puede referirse a la raíz de los demás (cada plugin instalado
vive en su propia copia de la caché): aquí se resuelve dónde está cada uno y se devuelven las órdenes con rutas absolutas.

Resolución de la carpeta de Arkana (`home`): --home, $ARKANA_HOME, un ancestro del directorio actual con `.arkana/arkana.json`
(ya hay workspace) o, si no hay ninguno, la raíz git del directorio actual (el workspace se creará ahí).
Resolución de cada plugin: hermano de este plugin (checkout del repo) o la versión más reciente de
`~/.claude/plugins/cache/arkana/<plugin>/<versión>/`.

Salida: `ESTADO|ID|detalle` (OK, INFO, WARN, FAIL) y una línea `PASO|id|plugin|ensayo|aplicar` por paso. Con --json, un objeto.
Código de salida: 0 plan completo, 1 falta algún plugin o no hay carpeta donde crear el workspace.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
MARKETPLACE = "arkana"
REQUIRED = ["arkana-workspace", "arkana-evolve", "arkana-statusline", "arkana-messaging",
            "arkana-agentic", "arkana-knowledge", "arkana-todo"]


def _version_key(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v))


def plugin_version(root):
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "?")
    except (OSError, ValueError):
        return None


def plugin_root(name, plugins_parent=None, cache=None):
    """Raíz de un plugin hermano: junto a este (repo) o la versión más reciente de la caché; None si no está."""
    parent = plugins_parent or os.path.dirname(PLUGIN_ROOT)
    cand = os.path.join(parent, name)
    if plugin_version(cand) is not None:
        return cand
    base = os.path.join(cache or os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache", MARKETPLACE), name)
    try:
        versions = sorted((v for v in os.listdir(base) if plugin_version(os.path.join(base, v)) is not None), key=_version_key)
    except OSError:
        return None
    return os.path.join(base, versions[-1]) if versions else None


def _git_root(cwd):
    try:
        r = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def find_home(explicit=None, cwd=None):
    """(home, existe): carpeta de Arkana y si ya tiene `.arkana/arkana.json`; (None, False) si no hay dónde crearla."""
    def has(d):
        return os.path.isfile(os.path.join(d, ".arkana", "arkana.json"))
    for c in (explicit, os.environ.get("ARKANA_HOME")):
        if c and os.path.isdir(c):
            c = os.path.realpath(c)
            return c, has(c)
    cur = os.path.realpath(cwd or os.getcwd())
    d = cur
    while True:
        if has(d):
            return d, True
        if os.path.dirname(d) == d:
            break
        d = os.path.dirname(d)
    return _git_root(cur), False


def build_steps(home, roots, dry_flag=True):
    """Pasos del pipeline, en orden. Cada uno: id, plugin, título, ensayo y aplicar (órdenes con rutas absolutas)."""
    q = shlex.quote
    env = f"ARKANA_HOME={q(home)} "

    def py(plugin, rel, *args):
        return f"{env}python3 {q(os.path.join(roots[plugin], rel))} " + " ".join(args)

    def sh(plugin, rel, *args):
        return f"{env}bash {q(os.path.join(roots[plugin], rel))} " + " ".join(args)

    spec = [
        ("layout", "arkana-workspace", "Disposición de .arkana/, manifiesto, registro del workspace",
         lambda f: py("arkana-workspace", "scripts/lib/layout.py", "init", "--home", q(home), *f)),
        ("evolve", "arkana-evolve", "Migraciones: registro del proyecto y carpetas fijas",
         lambda f: py("arkana-evolve", "scripts/lib/evolve.py", "apply", *f)),
        ("statusline", "arkana-statusline", "Statusline en ~/.claude y statusLine en settings.json",
         lambda f: py("arkana-statusline", "scripts/lib/ops.py", "install", *f)),
        ("messaging", "arkana-messaging", "Mensajería: almacén y plugin habilitado",
         lambda f: sh("arkana-messaging", "scripts/messaging.sh", "install", *f)),
        ("agentic", "arkana-agentic", "Orquestación: carpetas y plugin habilitado",
         lambda f: sh("arkana-agentic", "scripts/agentic.sh", "install", *f)),
        ("knowledge", "arkana-knowledge", "Conocimiento: carpetas fijas e índice",
         lambda f: py("arkana-knowledge", "scripts/lib/knowledge.py", "install", *f)),
        ("todo", "arkana-todo", "Tareas: lista local",
         lambda f: py("arkana-todo", "scripts/lib/todo.py", "install", *f)),
        ("permisos", "arkana-workspace", "Permisos de ARKANA (R/E/W)",
         lambda f: py("arkana-workspace", "scripts/lib/permissions.py", "apply", "--home", q(home), *f)),
        ("credenciales", "arkana-workspace", "Credenciales: solo diagnóstico",
         lambda f: py("arkana-workspace", "scripts/lib/credentials.py", "check", "--home", q(home))),
        ("herramientas", "arkana-workspace", "Herramientas del proyecto declaradas (solo lista; no se instala nada)",
         lambda f: py("arkana-workspace", "scripts/lib/config.py", "tools", "--home", q(home))),
        ("verificacion", "arkana-workspace", "Diagnóstico final del workspace",
         lambda f: py("arkana-workspace", "scripts/checks/all.py", "--home", q(home))),
    ]
    readonly = {"credenciales", "herramientas", "verificacion"}
    steps = []
    for sid, plugin, title, cmd in spec:
        if plugin not in roots or roots[plugin] is None:
            continue
        ro = sid in readonly
        steps.append({"id": sid, "plugin": plugin, "title": title,
                      "dry": cmd([] if ro else ["--dry-run"]), "apply": cmd([])})
    return steps


def plan(home_arg=None, cwd=None, plugins_parent=None, cache=None):
    res = {"status": [], "steps": [], "home": None, "new_workspace": None, "plugins": {}}
    add = lambda s, i, d: res["status"].append([s, i, d])
    roots = {}
    for name in REQUIRED:
        root = plugin_root(name, plugins_parent, cache)
        if root:
            roots[name] = root
            res["plugins"][name] = {"root": root, "version": plugin_version(root)}
            add("OK", f"plugin:{name}", f"{plugin_version(root)}")
        else:
            res["plugins"][name] = None
            add("FAIL", f"plugin:{name}", f"no instalado: /plugin install {name}@{MARKETPLACE} y /reload-plugins")
    home, exists = find_home(home_arg, cwd)
    res["home"], res["new_workspace"] = home, (None if home is None else not exists)
    if home is None:
        add("FAIL", "home", "no hay repo git en el directorio actual ni un workspace existente: crea o clona el repo de Arkana y entra en él (o pasa --home)")
    elif exists:
        add("OK", "home", f"workspace existente en {home} (la instalación es repetible: solo se añade lo que falta)")
    else:
        add("INFO", "home", f"no hay workspace: se creará en {home}")
    if home is not None and not os.path.isdir(os.path.join(home, ".git")) and not _git_root(home):
        add("WARN", "git", f"{home} no es un repo git: las migraciones de evolve lo necesitan (`git init` y un primer commit)")
    if home is not None:
        res["steps"] = build_steps(home, roots)
    return res


def render(res, as_json=False):
    if as_json:
        return json.dumps(res, ensure_ascii=False, indent=2) + "\n"
    L = [f"{s}|{i}|{d}" for s, i, d in res["status"]]
    for st in res["steps"]:
        L.append(f"PASO|{st['id']}|{st['plugin']}|{st['dry']}|{st['apply']}")
    return "\n".join(L) + "\n"


def exit_code(res):
    return 1 if any(s == "FAIL" for s, _, _ in res["status"]) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="pipeline.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--home")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res = plan(a.home)
    sys.stdout.write(render(res, a.json))
    return exit_code(res)


if __name__ == "__main__":
    sys.exit(main())
