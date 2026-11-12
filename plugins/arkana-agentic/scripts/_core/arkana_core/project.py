"""Registro del proyecto (`arkana-project.json`, en la raíz del repo de ARKANA y versionado): la identidad compartida de las piezas.

Cada pieza (ARKANA y los componentes) tiene un `id` (UUID v4) **inmutable** y un `alias` que se puede renombrar. Los documentos que se comparten por git
(notas de conocimiento, documentos) referencian componentes por `id`; a la persona usuaria se le muestra siempre el alias. Renombrar un componente solo
cambia el alias en este fichero (y en el manifiesto local), sin tocar ningún documento.

  {"schema_version": 1, "layout": N, "workspace": {"id", "name"},
   "components": [{"id": "<uuid>", "alias": "arkana"}, {"id": "<uuid>", "alias": "api"}, {"id": "<uuid>", "alias": "viejo", "retired": true}],
   "policies": {"versioned_env": true},
   "history": [{"id": "0001", "date": "…"}]}

Un componente dado de baja se conserva con `retired: true` (su id sigue resolviéndose para mostrarlo; su alias queda libre).

`policies` son decisiones de la instalación que comparte todo el equipo (no del código de los plugins). Hoy: `versioned_env` (bool): los `.env` van versionados por
naturaleza del proyecto, así que `arkana-workspace:check` los trata como información y no como fallo.
"""
import os
import re
import uuid

from . import datafiles

FILE = "arkana-project.json"
LAYOUT_REQUIRED = 4                    # layout mínimo que esperan los plugins (la última migración numérica que necesitan)
UUID_RX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
ALIAS_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ProjectError(Exception):
    pass


class LayoutError(ProjectError):
    pass


def path(home):
    return os.path.join(home, FILE)


def _canon(x):
    return (x or "").strip().lower()


def new_id():
    return str(uuid.uuid4())


def is_id(x):
    return bool(UUID_RX.match(_canon(x)))


def read(home):
    d = datafiles.read_json(path(home))
    return d if isinstance(d, dict) else None


def layout(home):
    d = read(home)
    try:
        return int((d or {}).get("layout", 0) or 0)
    except (TypeError, ValueError):
        return 0


def require_layout(home, n=LAYOUT_REQUIRED):
    """Lanza LayoutError (con la orden a ejecutar) si el layout del repo es inferior a `n`."""
    have = layout(home)
    if have < n:
        raise LayoutError(f"el repo está en layout {have} y esta versión necesita {n}: ejecuta /arkana-evolve:apply")
    return have


class Registry:
    """Alias ↔ id de las piezas. Sin registro (`Registry(None)`) todo se comporta como si los alias fueran la identidad."""

    def __init__(self, data):
        self.data = data or {}
        self._comps = [c for c in self.data.get("components", []) if isinstance(c, dict) and is_id(c.get("id"))]
        self._by_id = {c["id"].lower(): c for c in self._comps}
        self._by_alias = {_canon(c.get("alias")): c for c in self._comps if not c.get("retired")}

    @classmethod
    def load(cls, home):
        return cls(read(home))

    @property
    def present(self):
        return bool(self._comps)

    def aliases(self):
        return [c["alias"] for c in self._comps if not c.get("retired")]

    def id_of(self, x):
        """Id de una pieza dada por alias o por id; None si no se conoce."""
        k = _canon(x)
        if k in self._by_id:
            return self._by_id[k]["id"]
        c = self._by_alias.get(k)
        return c["id"] if c else None

    def alias_of(self, x):
        """Alias vigente de una pieza dada por id o por alias; None si no se conoce."""
        k = _canon(x)
        if k in self._by_id:
            return self._by_id[k]["alias"]
        return self._by_alias[k]["alias"] if k in self._by_alias else None

    def resolve(self, x):
        """Lo que se guarda en un documento compartido: el id si hay registro y la pieza se conoce; si no, el valor tal cual (en minúsculas)."""
        return self.id_of(x) or _canon(x)

    def display(self, x):
        """Lo que se muestra: el alias (ARKANA en mayúsculas); un id desconocido se acorta; `all` se queda como está."""
        k = _canon(x)
        if k == "all":
            return "all"
        a = self.alias_of(k)
        if a is None:
            return k[:8] + "…" if is_id(k) else k
        return "ARKANA" if a == "arkana" else a + (" (retirado)" if self._by_id.get(k, {}).get("retired") else "")


def _write(home, data):
    datafiles.atomic_write_json(path(home), data)


def _must(home):
    d = read(home)
    if d is None:
        raise ProjectError(f"no existe {FILE}: ejecuta /arkana-evolve:apply")
    return d


def policy(home, key, default=None):
    """Valor de una política de la instalación (compartida por git), o `default`."""
    return ((read(home) or {}).get("policies") or {}).get(key, default)


def set_policy(home, key, value):
    d = _must(home)
    d.setdefault("policies", {})[key] = value
    _write(home, d)


def add_component(home, alias, cid=None):
    """Da de alta una pieza en el registro (idempotente por alias). Devuelve su id."""
    a = _canon(alias)
    d = _must(home)
    reg = Registry(d)
    if reg.id_of(a):
        return reg.id_of(a)
    if not ALIAS_RX.match(a):
        raise ProjectError(f"alias no válido: {alias!r}")
    cid = cid or new_id()
    d.setdefault("components", []).append({"id": cid, "alias": a})
    _write(home, d)
    return cid


def rename_component(home, old, new):
    """Cambia el alias de una pieza (por su id). Idempotente: si ya se llama `new`, no hace nada. Devuelve el id."""
    o, n = _canon(old), _canon(new)
    d = _must(home)
    reg = Registry(d)
    cid = reg.id_of(o) or reg.id_of(n)
    if not cid:
        raise ProjectError(f"componente desconocido en el registro: {old}")
    if reg.alias_of(cid) == n:
        return cid
    if not ALIAS_RX.match(n) or n in ("arkana", "all"):
        raise ProjectError(f"alias no válido o reservado: {new!r}")
    if reg.id_of(n):
        raise ProjectError(f"ya existe un componente llamado {new}")
    for c in d["components"]:
        if c["id"] == cid:
            c["alias"] = n
    _write(home, d)
    return cid


def retire_component(home, alias):
    """Da de baja una pieza: se conserva con `retired: true` para que sus referencias sigan mostrándose."""
    d = _must(home)
    reg = Registry(d)
    cid = reg.id_of(alias)
    if not cid:
        return None
    for c in d["components"]:
        if c["id"] == cid:
            c["retired"] = True
    _write(home, d)
    return cid
