"""Manifiesto del workspace: qué piezas tiene el proyecto y dónde están.

Ficheros (bajo la carpeta `.arkana/` del repo de Arkana):
  arkana.json                       versión de esquema, identidad y `root` del workspace
  core/workspace.json               manifiesto portable: bloque `arkana` y lista `components` (se exporta)
  arkana-workspace/local.json       datos de esta instalación: `paths` absolutas por alias, `git` personal (no se exporta)

Identificadores: el alias canónico va en minúsculas (`arkana`, `app`, `api`…); ` ARKANA ` es solo cómo se muestra.
El id histórico `shared` se acepta como sinónimo de entrada de `arkana` (planes y mensajes anteriores a la reorganización).
"""
import json
import os
import re

from . import locate, schema as _schema

WORKSPACE_JSON = os.path.join("core", "workspace.json")
LOCAL_JSON = os.path.join("arkana-workspace", "local.json")
ALIAS_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RESERVED = ("arkana", "all")          # `all` es un destinatario de --to, no un componente
SYNONYMS = {"shared": "arkana"}       # id histórico del repo de Arkana
TYPES = ("node", "maven", "docs", "generic")
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")


class ManifestError(Exception):
    pass


def canon(alias):
    """Alias canónico: minúsculas y sin sinónimos históricos."""
    a = (alias or "").strip().lower()
    return SYNONYMS.get(a, a)


def display(alias):
    """Cómo se muestra un alias (ARKANA en mayúsculas; el resto tal cual)."""
    a = canon(alias)
    return "ARKANA" if a == "arkana" else a


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def validate(data):
    """Errores del manifiesto (esquema + reglas semánticas); lista vacía si es válido."""
    errs = _schema.check_schema(data, load_schema("workspace.schema.json"))
    if errs:
        return errs
    seen = {"arkana"}
    paths = {}
    bloques = [("arkana", data["arkana"], True)] + [(c.get("alias", "?"), c, False) for c in data.get("components", [])]
    for alias, b, es_arkana in bloques:
        if not es_arkana:
            a = (b.get("alias") or "")
            if not ALIAS_RX.match(a):
                errs.append(f"componente {a!r}: el alias debe cumplir {ALIAS_RX.pattern}")
            elif a in RESERVED or a in SYNONYMS:
                errs.append(f"componente {a!r}: alias reservado")
            elif a in seen:
                errs.append(f"componente {a!r}: alias repetido")
            seen.add(a)
        p = b.get("path", "")
        n = os.path.normpath(p) if p else ""
        if not p or os.path.isabs(p) or n.startswith("..") or p.startswith("~"):
            errs.append(f"{alias}: la ruta debe ser relativa a la raíz del workspace y no salir de ella ({p!r})")
        elif n in paths:
            errs.append(f"{alias}: la ruta {p!r} ya la usa {paths[n]}")
        else:
            paths[n] = alias
    return errs


class Workspace:
    """Manifiesto cargado: alias → bloque, rutas absolutas y relaciones de anidamiento."""

    def __init__(self, home, data, local=None):
        self.home = home
        self.state = locate.state_dir(home)
        self.root = locate.workspace_root(home)
        self.data = data
        self.local = local or {}
        self._blocks = {"arkana": data["arkana"]}
        for c in data.get("components", []):
            self._blocks[c["alias"]] = c

    def aliases(self, include_arkana=True):
        res = list(self._blocks)
        return res if include_arkana else [a for a in res if a != "arkana"]

    def has(self, alias):
        return canon(alias) in self._blocks

    def get(self, alias):
        a = canon(alias)
        if a not in self._blocks:
            raise KeyError(f"componente desconocido: {alias}")
        return self._blocks[a]

    def path(self, alias):
        """Ruta absoluta: la de `local.json` si existe para ese alias; si no, la relativa del manifiesto bajo la raíz."""
        a = canon(alias)
        self.get(a)
        ov = (self.local.get("paths") or {}).get(a)
        if ov:
            return os.path.expanduser(ov)
        return os.path.normpath(os.path.join(self.root, self._blocks[a]["path"]))

    def nested_in(self, alias):
        """Alias de las piezas cuya carpeta cuelga de la de `alias` (p. ej. app-web y app-ui dentro de app)."""
        base = self.path(alias).rstrip(os.sep) + os.sep
        return [a for a in self._blocks if a != canon(alias) and (self.path(a).rstrip(os.sep) + os.sep).startswith(base)]

    def owner_of(self, path):
        """Alias de la pieza más específica que contiene `path` (la de ruta más larga), o None."""
        p = os.path.realpath(path)
        best, blen = None, -1
        for a in self._blocks:
            b = os.path.realpath(self.path(a))
            if (p == b or p.startswith(b.rstrip(os.sep) + os.sep)) and len(b) > blen:
                best, blen = a, len(b)
        return best


def load(home=None, cwd=None):
    """Carga el workspace. `home` es la carpeta de Arkana; si falta se localiza (ver locate.find_home)."""
    home = home or locate.find_home(cwd)
    if not home:
        raise ManifestError("no se encontró un workspace de Arkana (ni ARKANA_HOME, ni .arkana/arkana.json, ni registro)")
    path = os.path.join(locate.state_dir(home), WORKSPACE_JSON)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        raise ManifestError(f"no se puede leer {path}: {e.strerror}")
    except ValueError as e:
        raise ManifestError(f"{path} no es JSON válido: {e}")
    errs = validate(data)
    if errs:
        raise ManifestError("manifiesto no válido: " + "; ".join(errs[:5]))
    local = {}
    try:
        with open(os.path.join(locate.state_dir(home), LOCAL_JSON), encoding="utf-8") as f:
            local = json.load(f)
    except (OSError, ValueError):
        pass
    return Workspace(home, data, local)
