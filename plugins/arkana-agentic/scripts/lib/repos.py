#!/usr/bin/env python3
"""Rutas de los repos del proyecto y utilidades de git (sin credenciales en ninguna salida).

Los repos (componentes) y sus rutas salen del manifiesto del workspace: <arkana>/.arkana/core/workspace.json (y `local.json` para las rutas de esta
instalación). No hay lista de repos en el código: sin manifiesto, arkana-agentic no funciona (se crea con /arkana-workspace:install).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_core"))
from arkana_core import manifest as _manifest, netguard  # noqa: E402


def _workspace():
    """Manifiesto del workspace. Lanza `ManifestError` (con un mensaje claro) si no existe."""
    return _manifest.load(paths.arkana_dir())


def net_hosts():
    """Hosts de los remotos de los componentes (del manifiesto; vacío con $ARKANA_SKIP_NET_PREFLIGHT=1)."""
    if os.environ.get("ARKANA_SKIP_NET_PREFLIGHT") == "1":
        return []
    ws = _workspace()
    hosts = []
    for al in ws.aliases():
        h = (ws.get(al) or {}).get("remote_host")
        if h and h not in hosts:
            hosts.append(h)
    return hosts


def net_preflight():
    """(ok, detalle) de resolver los hosts de los remotos (3 s por host, en serie hasta el primer fallo). Dispara/restablece el cortacircuitos."""
    for h in net_hosts():
        ok, det = netguard.preflight(h)
        if not ok:
            return False, det
    return True, "hosts de los remotos resuelven"


def repo_ids():
    """Alias de todas las piezas del workspace (ARKANA incluida), en el orden del manifiesto."""
    return _workspace().aliases()


def repo_known(repo):
    """¿Es `repo` un componente del manifiesto? (acepta el id histórico `shared` de ARKANA)."""
    return _workspace().has(repo)


def repo_path(repo):
    """Ruta absoluta del repo, del manifiesto. KeyError si no es un componente."""
    return _workspace().path(repo)


def all_repos():
    ws = _workspace()
    return {r: ws.path(r) for r in ws.aliases()}


# Rama de trabajo de un plan: <prefijo>/<plan>. `m3a` es el prefijo que usaron los planes anteriores (siguen siendo válidos).
BRANCH_PREFIX = "arkana-worker"
LEGACY_BRANCH_PREFIXES = ("m3a",)


def plan_branch(plan_id):
    """Rama de trabajo de un plan en cada repo que toca: arkana-worker/<plan>. La crea el script de lanzamiento; el worker no usa git."""
    return f"{BRANCH_PREFIX}/{plan_id}"


def is_plan_branch(nombre):
    """¿Es la rama de trabajo de algún plan (de ahora o de los anteriores)?"""
    return any((nombre or "").startswith(p + "/") for p in (BRANCH_PREFIX,) + LEGACY_BRANCH_PREFIXES)


def git(repo, *args, entrada=None, net=False):
    """git con tiempo límite (30 s en local, 20 s con net=True) y grupo de procesos propio; `net=True` pasa por el cortacircuitos."""
    return netguard.git(repo, *args, net=net, input=entrada, timeout=None if net else 30)


def is_repo(repo):
    return os.path.isdir(repo) and git(repo, "rev-parse", "--git-dir").returncode == 0


def current_branch(repo):
    r = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def branch_exists(repo, rama):
    return git(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{rama}").returncode == 0


def head(repo):
    r = git(repo, "rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def porcelain_status(repo):
    r = git(repo, "status", "--porcelain=v1", "-z", "-uall")
    return sorted(x for x in r.stdout.split("\0") if x) if r.returncode == 0 else []


def is_clean(repo):
    return is_repo(repo) and not porcelain_status(repo)


def strip_url_credentials(u):
    return re.sub(r"(https?://)[^/@\s]*@", r"\1", u)
