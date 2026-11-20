"""Manifiesto del workspace: qué piezas tiene el proyecto y dónde están.

Ficheros (bajo la carpeta `.arkana/` del repo de Arkana):
  arkana.json                       versión de esquema, identidad y `root` del workspace
  core/workspace.json               manifiesto portable: bloque `arkana` y lista `components` (se exporta)
  arkana-workspace/local.json       datos de esta instalación: `paths` absolutas por alias, `git` personal (no se exporta)

Identificadores: el alias canónico va en minúsculas (`arkana`, `app`, `api`…) y se acepta en cualquier caso; **se muestra siempre en MAYÚSCULAS** (`ARKANA`, `APP`…).

Tres nombres por componente (más el `id` UUID del registro): el **alias** (el normal: lo que se guarda y se muestra en la statusline), la **carpeta real**
(último tramo de su ruta) y el **nombre-módulo** (`module` en `arkana-project.json`, compartido; opcional; por defecto cuenta como el alias en los commits).
Cualquiera de los tres sirve para referirse a un componente (`Workspace.key`), sin prefijo se prueba en ese orden, o con prefijo para forzar el tipo:
`alias:webapp`, `dir:md-espacioinquilino-backend`, `mod:viso_rest_inquilino`. Ninguno puede repetirse entre componentes, sin distinguir mayúsculas.
"""
import json
import os
import re

from . import locate, project, schema as _schema

WORKSPACE_JSON = os.path.join("core", "workspace.json")
LOCAL_JSON = os.path.join("arkana-workspace", "local.json")
ALIAS_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RESERVED = ("arkana", "all")          # `all` es un destinatario de --to, no un componente
TYPES = ("node", "maven", "docs", "generic")
MODES = ("work", "reference")
KNOWN_SCHEMA = 2                      # versión del manifiesto que esta instalación entiende (2 = campos mode, ref, watch y checks_skip)
NEW_FIELDS = ("mode", "ref", "watch", "checks_skip")                      # campos de componente que exigen `schema: 2`
CHECK_IDS = ("componente", "carpeta", "arkana-presente", "arkana-escribible", "permisos", "registro", "commits", "git-repo", "gitignore-env",
             "ignore-editor", "ignore-editor-session", "ignore-arkana-local", "env-versionado", "env-historial", "env-example", "git-identidad",
             "gitattributes-eol", "husky-hooks", "rama", "ref", "origin-accesible")        # IDs de `checks/component.py` que se pueden omitir (más `anidado-*`)
REFERENCE_SKIP = ("gitignore-env", "ignore-editor", "ignore-editor-session", "ignore-arkana-local", "env-versionado", "env-historial", "env-example",
                  "git-identidad", "gitattributes-eol", "husky-hooks", "commits")      # lo que no se exige a un repo de referencia (solo se descarga y se ejecuta)
SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")


class ManifestError(Exception):
    pass


def canon(alias):
    """Alias canónico: sin espacios en los extremos y en minúsculas."""
    return (alias or "").strip().lower()


KINDS = ("alias", "dir", "mod")
COMMIT_FORMATS = ("conventional", "ia4d")
_CF_RX = re.compile(r"^(conventional|ia4d)(\((\{alias\}|\{module\})\))?$")


def parse_commit_format(value):
    """`commit_format` → (formato, origen del scope). `ia4d`, `conventional` (scope = alias) o `ia4d({module})`, `conventional({module})` (scope = módulo;
    sin módulo se usa el alias). `{alias}` explícito equivale a no decir nada. ValueError si no se reconoce."""
    v = (value or "conventional").strip().lower()
    m = _CF_RX.match(v)
    if not m:
        raise ValueError(f"commit_format desconocido: {value!r} (usa conventional o ia4d, y opcionalmente `({{module}})`: ia4d({{module}}))")
    return m.group(1), ("module" if m.group(3) == "{module}" else "alias")


def display(alias):
    """Cómo se muestra un alias: siempre en MAYÚSCULAS (ARKANA, WEBAPP…), para distinguirlo de la carpeta y del nombre-módulo, que van en minúsculas.
    Internamente el alias se guarda y se compara en minúsculas (`canon`): se acepta en cualquier caso."""
    return canon(alias).upper()


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
            elif a in RESERVED:
                errs.append(f"componente {a!r}: alias reservado")
            elif a in seen:
                errs.append(f"componente {a!r}: alias repetido")
            seen.add(a)
        if not es_arkana:
            if b.get("ref") and b.get("mode", "work") != "reference":
                errs.append(f"{alias}: `ref` solo se admite con mode: reference")
            malos = [i for i in b.get("checks_skip", []) if not skip_ok(i)]
            if malos:
                errs.append(f"{alias}: checks_skip con IDs que no existen: {', '.join(malos)}")
        p = b.get("path", "")
        n = os.path.normpath(p) if p else ""
        if not p or os.path.isabs(p) or n.startswith("..") or p.startswith("~"):
            errs.append(f"{alias}: la ruta debe ser relativa a la raíz del workspace y no salir de ella ({p!r})")
        elif n in paths:
            errs.append(f"{alias}: la ruta {p!r} ya la usa {paths[n]}")
        else:
            paths[n] = alias
    return errs


def skip_ok(check_id):
    """¿Es `check_id` un ID de check válido para `checks_skip`? (los de `anidado-<alias>` se admiten con el comodín `anidado-*`)."""
    return check_id in CHECK_IDS or check_id == "anidado-*"


def component_flags(block, is_arkana=False):
    """Valores efectivos de un componente: `mode`, `ref`, `statusline`, `watch` y `checks_skip`. Un único sitio para todos los plugins.
    Orden: campo explícito del componente > defecto de su `mode` > defecto de su `type` (`docs` y `reference` se ocultan en la statusline).
    Un campo explícito siempre manda, también `checks_skip: []` (ejecuta todos los checks aunque sea `reference`). ARKANA nunca es `reference`."""
    reference = not is_arkana and block.get("mode", "work") == "reference"
    statusline = bool(block["statusline"]) if "statusline" in block else not (reference or block.get("type") == "docs")
    skip = list(block["checks_skip"]) if "checks_skip" in block else (list(REFERENCE_SKIP) if reference else [])
    return {"mode": "reference" if reference else "work", "ref": block.get("ref") or "", "statusline": statusline,
            "watch": bool(block["watch"]) if "watch" in block else not reference, "checks_skip": skip}


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
        self._ids = {str(b["id"]).lower(): a for a, b in self._blocks.items() if b.get("id")}     # id → alias (los bloques pueden llevar el `id` del registro)
        self._reg = None
        self._names = None

    def _registry(self):
        if self._reg is None:
            self._reg = project.Registry.load(self.home)
        return self._reg

    def module(self, alias):
        """Nombre-módulo de una pieza (del registro compartido); "" si no tiene."""
        a = self.key(alias)
        b = self._blocks.get(a, {})
        reg = self._registry()
        return reg.module_of(b.get("id") or a)

    def folder(self, alias):
        """Carpeta real de una pieza: el último tramo de su ruta."""
        return os.path.basename(os.path.normpath(self.path(alias)))

    def _name_maps(self):
        if self._names is None:
            dirs, mods = {}, {}
            for a in self._blocks:
                dirs.setdefault(self.folder(a).lower(), a)
                m = self.module(a)
                if m:
                    mods.setdefault(m, a)
            self._names = (dirs, mods)
        return self._names

    def match(self, x):
        """(alias, tipo) de una pieza dada por alias, id, carpeta o módulo (tipo: alias, id, dir o mod); (None, None) si no se conoce.
        Con prefijo (`alias:`, `dir:`, `mod:`) solo se mira ese tipo."""
        k = canon(x)
        kind = None
        head, sep, rest = k.partition(":")
        if sep and head in KINDS:
            kind, k = head, rest.strip()
        if kind in (None, "alias"):
            if k in self._blocks:
                return k, "alias"
            if kind is None and k in self._ids:
                return self._ids[k], "id"
        dirs, mods = self._name_maps()
        if kind in (None, "dir") and k in dirs:
            return dirs[k], "dir"
        if kind in (None, "mod") and k in mods:
            return mods[k], "mod"
        return None, None

    def name_conflicts(self):
        """Nombres repetidos entre componentes (alias, carpeta y módulo, sin distinguir mayúsculas): lista de textos; vacía si no hay."""
        users = {}
        for a in self._blocks:
            for kind, n in (("alias", a), ("carpeta", self.folder(a).lower()), ("módulo", self.module(a))):
                if n:
                    users.setdefault(n, {}).setdefault(a, kind)
        return [f"el nombre '{n}' lo usan varios componentes: " + ", ".join(f"{a} ({k})" for a, k in sorted(u.items()))
                for n, u in sorted(users.items()) if len(u) > 1]

    def commit_scope(self, alias):
        """Scope de los commits de una pieza: su módulo si su `commit_format` lo pide con `({module})` y lo tiene; si no, el alias."""
        a = self.key(alias)
        try:
            _, kind = parse_commit_format(self._blocks[a].get("commit_format"))
        except (KeyError, ValueError):
            return a
        return (self.module(a) if kind == "module" else "") or a

    def flags(self, alias):
        """`component_flags` de una pieza (alias o id)."""
        k = self.key(alias)
        return component_flags(self.get(k), k == "arkana")

    def key(self, x):
        """Alias canónico de una pieza dada por alias, id, carpeta o módulo (el valor tal cual, en minúsculas, si no se conoce)."""
        a, _ = self.match(x)
        return a if a else canon(x)

    def id_of(self, alias):
        return self._blocks.get(self.key(alias), {}).get("id")

    def alias_of(self, x):
        k = self.key(x)
        return k if k in self._blocks else None

    def aliases(self, include_arkana=True):
        res = list(self._blocks)
        return res if include_arkana else [a for a in res if a != "arkana"]

    def has(self, alias):
        return self.key(alias) in self._blocks

    def get(self, alias):
        a = self.key(alias)
        if a not in self._blocks:
            raise KeyError(f"componente desconocido: {alias}")
        return self._blocks[a]

    def path(self, alias):
        """Ruta absoluta: la de `local.json` si existe para ese alias; si no, la relativa del manifiesto bajo la raíz."""
        a = self.key(alias)
        self.get(a)
        ov = (self.local.get("paths") or {}).get(a)
        if ov:
            return os.path.expanduser(ov)
        return os.path.normpath(os.path.join(self.root, self._blocks[a]["path"]))

    def nested_in(self, alias):
        """Alias de las piezas cuya carpeta cuelga de la de `alias` (p. ej. app-web y app-ui dentro de app)."""
        base = self.path(alias).rstrip(os.sep) + os.sep
        return [a for a in self._blocks if a != self.key(alias) and (self.path(a).rstrip(os.sep) + os.sep).startswith(base)]

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
    sc = data.get("schema") if isinstance(data, dict) else None
    if isinstance(sc, int) and not isinstance(sc, bool) and sc > KNOWN_SCHEMA:             # lo ha escrito una versión más reciente: se dice antes de listar claves «no permitidas»
        raise ManifestError(f"el manifiesto es de esquema {sc} y esta versión de Arkana conoce hasta {KNOWN_SCHEMA}: actualiza el plugin (/plugin) y repite")
    errs = validate(data)
    if errs:
        hint = " (parece una instalación anterior: ejecuta /arkana-evolve:apply para migrarla)" if any("seed_file" in e for e in errs) else ""
        if not hint and all("clave no permitida" in e for e in errs):
            hint = " (puede venir de una versión más reciente de Arkana: actualiza el plugin)"
        raise ManifestError("manifiesto no válido: " + "; ".join(errs[:5]) + hint)
    local = {}
    try:
        with open(os.path.join(locate.state_dir(home), LOCAL_JSON), encoding="utf-8") as f:
            local = json.load(f)
    except (OSError, ValueError):
        pass
    return Workspace(home, data, local)
