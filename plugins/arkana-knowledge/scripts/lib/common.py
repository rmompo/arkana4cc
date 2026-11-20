"""Utilidades comunes de arkana-knowledge: frontmatter, componentes por id, hashes y autor. Solo biblioteca estándar."""
import datetime
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import locate, manifest, project  # noqa: E402

TOPICS = ["decision", "lesson", "pending", "contract", "reference", "methodology"]
STATES = ["active", "deleted"]
ROOT = "arkana-knowledge"                          # notas: decisiones, lecciones, metodología…
DOCS = "arkana-docs"                               # documentos de origen
MD = os.path.join(DOCS, "md")                      # su versión en Markdown (lo que Arkana lee), con el mismo árbol que los originales
INCOMING = "arkana-incoming"                       # cola local de entrada
NOTE_FIELDS = ["id", "slug", "titulo", "topic", "version", "fecha", "autor", "components", "etiquetas", "fuentes", "resumen", "state"]
DOC_FIELDS = ["id", "titulo", "kind", "original", "sha256", "mime", "bytes", "conversion", "cobertura", "resumen", "etiquetas", "components", "fecha", "autor", "state"]
LIST_FIELDS = ("components", "etiquetas", "fuentes")
QUOTED = ("titulo", "resumen", "original", "cobertura")
CHANGELOG = "## Changelog"
VERSION_RE = re.compile(r"^\d+\.\d+$")
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"


class KError(Exception):
    def __init__(self, msg, cod=1):
        super().__init__(msg)
        self.cod = cod


# ---------- frontmatter ----------
def parse_list(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip().strip("\"'") for x in v.split(",") if x.strip()]


def split_note(text):
    """(meta dict | None, cuerpo)."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return None, text
    meta = {}
    for line in text[4:end].split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if k in LIST_FIELDS:
            meta[k] = parse_list(v)
        else:
            meta[k] = v[1:-1].replace('\\"', '"') if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'" else v
    return meta, text[end + 5:]


def dump_fm(fields, meta):
    lines = ["---"]
    for k in fields:
        v = meta.get(k, [] if k in LIST_FIELDS else "")
        if k in LIST_FIELDS:
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            s = str(v).replace("\n", " ")
            lines.append(f'{k}: "{s.replace(chr(34), chr(92) + chr(34))}"' if k in QUOTED else f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def split_changelog(body):
    m = re.search(r"(?m)^## Changelog\s*$", body)
    if not m:
        return body.rstrip("\n"), []
    return body[:m.start()].rstrip("\n"), [l.rstrip() for l in body[m.end():].split("\n") if l.strip().startswith("- ")]


def join_note(meta, main, entries):
    return dump_fm(NOTE_FIELDS, meta) + "\n" + (main.strip("\n") + "\n" if main.strip() else "") + "\n" + CHANGELOG + "\n\n" + "\n".join(entries) + "\n"


def entry(ver, fecha, autor, texto):
    return f"- v{ver} · {fecha} · {autor} — {texto}".replace("\n", " ")


def slugify(s):
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n"), ("ü", "u")):
        s = s.replace(a, b)
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:60] or "nota"


def today():
    return datetime.date.today().isoformat()


def bump(ver, major=False):
    a, b = (int(x) for x in ver.split("."))
    return f"{a + 1}.0" if major else f"{a}.{b + 1}"


def csv(v):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def default_author(home):
    try:
        n = subprocess.run(["git", "-C", home, "config", "user.name"], capture_output=True, text=True, timeout=10).stdout.strip()
        if n:
            return n
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("USER", "desconocido")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_lfs_pointer(path):
    try:
        with open(path, "rb") as f:
            return f.read(len(LFS_POINTER)) == LFS_POINTER
    except OSError:
        return False


# ---------- workspace y componentes ----------
def find_home(arg):
    home = os.path.abspath(arg) if arg else locate.find_home()
    if not home or not os.path.isdir(home):
        raise KError("no hay workspace de Arkana (usa --home o ejecuta dentro de uno)", 3)
    return home


def registry(home):
    return project.Registry.load(home)


def aliases(home):
    try:
        return manifest.load(home).aliases()
    except Exception:
        return None


def resolve_name(home, x):
    """Alias canónico de un componente dado por alias, carpeta o módulo (o con `alias:`, `dir:`, `mod:`); sin manifiesto, el valor en minúsculas."""
    try:
        return manifest.load(home).key(x)
    except Exception:
        return manifest.canon(x)


def norm_components(home, value):
    """Lista de componentes para guardar en un documento compartido: ids del registro (o `all`). Sin registro, alias (comprobados contra el manifiesto)."""
    reg = registry(home)
    out = []
    for x in csv(value) if value is not None else []:
        k = resolve_name(home, x)
        if k == "all":
            out.append("all")
            continue
        cid = reg.id_of(k)
        if cid:
            out.append(cid)
            continue
        al = reg.aliases() if reg.present else aliases(home)
        if al is not None:
            raise KError(f"componentes desconocidos: {x} (válidos: {', '.join(al)}, all)", 2)
        out.append(k)
    return out or ["all"]


def shown(home, comps):
    """Componentes de un documento como los ve la persona usuaria: alias."""
    reg = registry(home)
    return [reg.display(c) if c != "all" else "all" for c in comps]


def component_ok(home, c):
    if c == "all":
        return True
    reg = registry(home)
    if reg.present:
        return reg.alias_of(c) is not None
    al = aliases(home)
    return al is None or manifest.canon(c) in al


def matches_component(home, comps, wanted):
    """¿Un documento con `comps` aplica al componente pedido (alias o id)? `all` aplica a todos."""
    if not wanted:
        return True
    w = resolve_name(home, wanted)
    if w == "all" or "all" in comps:
        return True
    reg = registry(home)
    wid = reg.id_of(w) or w
    return wid in comps or w in comps
