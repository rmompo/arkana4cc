"""Localizador del workspace de Arkana.

Un workspace es Arkana (su repo, que contiene `.arkana/`) más el proyecto (los componentes, repos hermanos o no).
La carpeta de Arkana se reconoce porque tiene `.arkana/arkana.json`. Orden de resolución:
  1. $ARKANA_HOME (la carpeta del repo de Arkana)
  2. un ancestro del directorio actual que sea una carpeta de Arkana
  3. el registro por usuario `~/.arkana-workspaces.json`: el primer workspace cuya raíz contiene el directorio actual
     (así se localiza desde la carpeta de un componente, que no cuelga de Arkana)
  4. ninguno: quien llama no debe hacer nada (los hooks de un plugin instalado a nivel de usuario corren en cualquier proyecto)

Registro: {"workspaces": [{"name": "...", "arkana": "/ruta/absoluta/arkana", "root": "/ruta/absoluta/raiz"}]}
"""
import json
import os

STATE_DIR = ".arkana"
ARKANA_JSON = "arkana.json"
REGISTRY_NAME = ".arkana-workspaces.json"


def registry_path():
    return os.path.join(os.path.expanduser("~"), REGISTRY_NAME)


def is_home(d):
    return os.path.isfile(os.path.join(d, STATE_DIR, ARKANA_JSON))


def read_registry():
    try:
        with open(registry_path(), encoding="utf-8") as f:
            ws = json.load(f).get("workspaces", [])
        return [w for w in ws if isinstance(w, dict) and w.get("arkana") and w.get("root")]
    except (OSError, ValueError, AttributeError):
        return []


def _contains(root, d):
    root = os.path.realpath(root)
    return d == root or d.startswith(root.rstrip(os.sep) + os.sep)


def find_home(cwd=None):
    """Carpeta del repo de Arkana (con `.arkana/arkana.json`) o None."""
    env = os.environ.get("ARKANA_HOME")
    if env and os.path.isdir(env):
        return os.path.realpath(env)
    d = os.path.realpath(cwd or os.getcwd())
    cur = d
    while True:
        if is_home(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    for w in read_registry():
        if _contains(w["root"], d) and is_home(w["arkana"]):
            return os.path.realpath(w["arkana"])
    return None


def state_dir(home):
    return os.path.join(home, STATE_DIR)


def workspace_root(home):
    """Raíz del workspace: `root` de arkana.json (relativa a la carpeta de Arkana; por defecto `..`)."""
    root = ".."
    try:
        with open(os.path.join(state_dir(home), ARKANA_JSON), encoding="utf-8") as f:
            root = json.load(f).get("root") or ".."
    except (OSError, ValueError):
        pass
    return os.path.realpath(root if os.path.isabs(root) else os.path.join(home, root))


def register(home, name=None):
    """Anota esta carpeta de Arkana en el registro por usuario (idempotente). Devuelve True si cambió algo."""
    home = os.path.realpath(home)
    reg = {"workspaces": read_registry()}
    root = workspace_root(home)
    entry = {"name": name or os.path.basename(root), "arkana": home, "root": root}
    for i, w in enumerate(reg["workspaces"]):
        if os.path.realpath(w["arkana"]) == home:
            if w == entry:
                return False
            reg["workspaces"][i] = entry
            break
    else:
        reg["workspaces"].append(entry)
    from . import datafiles
    datafiles.atomic_write_json(registry_path(), reg, mode=0o644)
    return True
