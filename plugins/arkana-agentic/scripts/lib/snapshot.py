#!/usr/bin/env python3
"""Instantaneas del estado de los repos y de los ficheros vigilados, antes y despues de una tarea.

No lee el contenido de ningun fichero vigilado (credenciales incluidas): solo tamano, mtime e inodo.

Uso:  snapshot.py take <plan> <tarea> <intento> antes|despues
      snapshot.py diff <plan> <tarea> <intento>        (exit 0 sin violaciones, 4 con violaciones)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import repos  # noqa: E402
import state  # noqa: E402


def watched_files():
    h = os.path.expanduser("~")
    rutas = [f"{h}/.claude/settings.json", f"{h}/.git-credentials", f"{h}/.ia4d/.env", f"{h}/.npmrc", f"{h}/.gitconfig"]
    con_arkana = os.path.join(repos.repo_path("arkana"), ".claude", "settings.local.json")
    return rutas + [con_arkana]


EXCLUDED_DIRS = {".git", "node_modules", "dist", ".angular", "coverage", "target"}


def build_manifest(ruta):
    """Inventario real de ficheros del repo (ruta relativa -> [tamano, mtime_ns]), sin depender de .gitignore.
    Detecta cambios en ficheros ignorados por git (p. ej. .env). Se excluyen carpetas de dependencias y de compilacion."""
    res = {}
    for dp, dns, fns in os.walk(ruta):
        dns[:] = [d for d in dns if d not in EXCLUDED_DIRS]
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            res[os.path.relpath(p, ruta)] = [st.st_size, st.st_mtime_ns]
    return res


def manifest_changes(antes, despues):
    """Rutas anadidas, borradas o modificadas entre dos instantaneas; None si falta el inventario."""
    a, d = antes.get("manifiesto"), despues.get("manifiesto")
    if a is None or d is None:
        return None
    return sorted(k for k in set(a) | set(d) if a.get(k) != d.get(k))


def take(repo_tarea=None):
    snap = {"ts": state.now_iso(), "repos": {}, "vigilados": {}}
    if repo_tarea:
        snap["manifiesto"] = build_manifest(repos.repo_path(repo_tarea))
    for rid, ruta in repos.all_repos().items():
        if not repos.is_repo(ruta):
            snap["repos"][rid] = None
            continue
        remotos = repos.git(ruta, "config", "--get-regexp", r"^remote\..*\.url$").stdout.strip().splitlines()
        ahead = repos.git(ruta, "rev-list", "--count", "@{u}..HEAD")
        snap["repos"][rid] = {
            "ruta": ruta, "rama": repos.current_branch(ruta), "head": repos.head(ruta),
            "estado": repos.porcelain_status(ruta),
            "remotos": sorted(repos.strip_url_credentials(x) for x in remotos),
            "stashes": len(repos.git(ruta, "stash", "list").stdout.splitlines()),
            "sin_subir": int(ahead.stdout.strip()) if ahead.returncode == 0 and ahead.stdout.strip().isdigit() else None,
        }
    for p in watched_files():
        try:
            st = os.stat(p)
            snap["vigilados"][p] = {"existe": True, "size": st.st_size, "mtime_ns": st.st_mtime_ns, "ino": st.st_ino}
        except FileNotFoundError:
            snap["vigilados"][p] = {"existe": False}
    return snap


def _snapshot_path(pid, tid, intento, momento):
    return os.path.join(state.plan_dir(pid), "snapshots", f"{tid}.{intento}.{momento}.json")


def save(pid, tid, intento, momento):
    tarea = state.load_json(os.path.join(state.plan_dir(pid), "tareas", f"{tid}.json"))
    snap = take(tarea["repo"])
    state.save_json(_snapshot_path(pid, tid, intento, momento), snap)
    return snap


def compare(antes, despues, repo_tarea):
    """Violaciones: cualquier cambio fuera del repo de la tarea, y cambios de rama/HEAD/remotos/stashes dentro de el."""
    v = []
    for rid in sorted(set(antes["repos"]) | set(despues["repos"])):
        a, d = antes["repos"].get(rid), despues["repos"].get(rid)
        if a == d:
            continue
        if a is None or d is None:
            v.append({"tipo": "repo_ajeno", "repo": rid, "detalle": "el repo aparece o desaparece"})
        elif rid != repo_tarea:
            cambios = [k for k in a if a[k] != d[k]]
            v.append({"tipo": "repo_ajeno", "repo": rid, "detalle": "cambia " + ", ".join(cambios)})
        else:
            for k, etiqueta in (("rama", "rama_cambiada"), ("head", "head_cambiado"), ("remotos", "remotos_cambiados"),
                                ("stashes", "stash_cambiado")):
                if a[k] != d[k]:
                    v.append({"tipo": etiqueta, "repo": rid, "detalle": f"{a[k]!r} -> {d[k]!r}"})
    for ruta in sorted(set(antes["vigilados"]) | set(despues["vigilados"])):
        if antes["vigilados"].get(ruta) != despues["vigilados"].get(ruta):
            v.append({"tipo": "fichero_vigilado", "ruta": ruta, "detalle": "tamano, fecha o existencia distintos"})
    return v


def main(argv):
    try:
        if len(argv) == 6 and argv[1] == "take":
            save(argv[2], argv[3], argv[4], argv[5])
            print(f"OK|snapshot|{argv[3]}.{argv[4]}.{argv[5]}")
            return 0
        if len(argv) == 5 and argv[1] == "diff":
            plan = argv[2]
            tarea = state.load_json(os.path.join(state.plan_dir(plan), "tareas", f"{argv[3]}.json"))
            a = state.load_json(_snapshot_path(plan, argv[3], argv[4], "antes"))
            d = state.load_json(_snapshot_path(plan, argv[3], argv[4], "despues"))
            v = compare(a, d, tarea["repo"])
            for x in v:
                print(f"FAIL|violacion|{json.dumps(x, ensure_ascii=False)}")
            if not v:
                print("OK|snapshot|sin violaciones")
            return 4 if v else 0
    except (FileNotFoundError, KeyError) as e:
        print(f"FAIL|snapshot|{type(e).__name__}: {e}")
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
