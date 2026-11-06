#!/usr/bin/env python3
"""Adaptadores por tipo de componente (`node`, `maven`, `docs`, `generic`): herramientas requeridas, comandos de verificación permitidos y rutas protegidas.

El tipo sale del manifiesto del workspace (`components[].type`); uno desconocido se trata como `generic`. La lista de verificación de un plan es la UNIÓN de los adaptadores de los componentes de sus tareas; las rutas
protegidas son las del adaptador del repo de cada tarea (nunca la unión: lo protegido en `maven` no tiene por qué serlo en `node`).
Cada adaptador se suma a `policy/adapters/common.json`. El usuario puede añadir comandos en `config/comandos-permitidos.json` (aditivo).
"""
import json
import os

import repos
import state

DIR = os.path.join(state.PLUGIN, "policy", "adapters")
VERIFIER_PATH = "/usr/local/bin:/usr/bin:/bin"                       # lo único que ve el verificador además de las herramientas declaradas
TYPES = ("node", "maven", "docs", "generic")


def _load(name):
    with open(os.path.join(DIR, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def repo_type(repo):
    ws = repos._workspace()
    try:
        t = ws.get(repo).get("type")
    except KeyError:
        return "generic"
    return t if t in TYPES else "generic"


def adapter(tipo):
    """Adaptador efectivo de un tipo (común + propio): dict con herramientas, comandos, rutas_protegidas, package_json_campos."""
    c, a = _load("common"), _load(tipo if tipo in TYPES else "generic")
    uniq = lambda xs: [x for i, x in enumerate(xs) if x not in xs[:i]]
    return {"tipo": a.get("tipo", tipo), "herramientas": a.get("herramientas", []),
            "comandos": uniq(c.get("comandos", []) + a.get("comandos", [])),
            "rutas_protegidas": uniq(c.get("rutas_protegidas", []) + a.get("rutas_protegidas", [])),
            "package_json_campos": a.get("package_json_campos", [])}


def known_repos():
    return repos.repo_ids()


def types_of(repo_ids=None):
    ids = list(repo_ids) if repo_ids else known_repos()
    return sorted({repo_type(r) for r in ids})


def commands_for(repo_ids=None):
    """Unión de los comandos permitidos de los adaptadores de esos repos (todos los conocidos si no se dan)."""
    res = []
    for t in types_of(repo_ids):
        for c in adapter(t)["comandos"]:
            if c not in res:
                res.append(c)
    return res


def protected_for(repo):
    """{'patrones': [...], 'package_json_campos': [...]} del adaptador de ese repo."""
    a = adapter(repo_type(repo))
    return {"patrones": a["rutas_protegidas"], "package_json_campos": a["package_json_campos"]}


def protected_union():
    pat, campos = [], []
    for t in types_of():
        a = adapter(t)
        pat += [p for p in a["rutas_protegidas"] if p not in pat]
        campos += [c for c in a["package_json_campos"] if c not in campos]
    return {"patrones": pat, "package_json_campos": campos}


def tools_required(repo_ids=None):
    res = []
    for t in types_of(repo_ids):
        res += [x for x in adapter(t)["herramientas"] if x not in res]
    return res


def _tools_json():
    """Herramientas declaradas en .arkana/arkana-workspace/tools.json (`/arkana-workspace:config tools`): [{tool, version, path?, packages?, registries?}]."""
    import paths
    try:
        with open(os.path.join(paths.plugins_dir(), "arkana-workspace", "tools.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError, paths.NoWorkspace):
        return []
    return [t for t in (d.get("tools", []) if isinstance(d, dict) else d) if isinstance(t, dict)]


def tool_home(tool):
    """Carpeta de una herramienta declarada (su `path`), o None."""
    for t in _tools_json():
        if t.get("tool") == tool and t.get("path"):
            return os.path.expanduser(t["path"])
    return None


def tool_bin_dirs(repo_ids=None):
    """Carpetas bin de las herramientas del adaptador (las que piden node, maven…) según tools.json, para el PATH del verificador."""
    want = set(tools_required(repo_ids))
    out = []
    for t in _tools_json():
        if t.get("tool") in want and t.get("path"):
            b = os.path.join(os.path.expanduser(t["path"]), "bin")
            if os.path.isdir(b) and b not in out:
                out.append(b)
    return out


def npmrc_lines():
    """Líneas de .npmrc con los registros por ámbito declarados en tools.json (`scope:registry=url`); vacío si no hay ninguno."""
    lineas = []
    for t in _tools_json():
        for scope, url in sorted((t.get("registries") or {}).items()):
            linea = f"{scope}:registry={url}\n"
            if linea not in lineas:
                lineas.append(linea)
    return "".join(lineas)
