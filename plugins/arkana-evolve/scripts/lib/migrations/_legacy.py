"""Conocimiento de los formatos antiguos de Arkana: lo comparten las migraciones de base (`b*`). Los plugins ya no lo llevan."""
import os
import re

LEGACY_ALIASES = {"shared": "arkana"}          # id histórico de la carpeta/alias de ARKANA
LEGACY_TOPICS = ["decision", "lesson", "pending", "contract", "reference"]
CHANGELOG = "## Changelog"
NOTE_FIELDS = ["id", "titulo", "topic", "version", "fecha", "autor", "components", "etiquetas", "resumen", "state"]
LIST_FIELDS = ("components", "etiquetas")
SKIP_DIRS = {".git", "node_modules", "archivo", "plantillas", "plugins", "scripts", ".claude", ".claude-session", ".arkana", "lib",
             "arkana-incoming", "arkana-docs"}


def canon(alias):
    a = (alias or "").strip().lower()
    return LEGACY_ALIASES.get(a, a)


def parse_list(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip().strip("\"'") for x in v.split(",") if x.strip()]


def split_note(text):
    """(meta | None, cuerpo). Reconoce las listas `components`, `etiquetas` y la antigua `modulos`."""
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
        meta[k] = parse_list(v) if (k in LIST_FIELDS or k == "modulos") else (v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'" else v)
    return meta, text[end + 5:]


def split_changelog(body):
    m = re.search(r"(?m)^## Changelog\s*$", body)
    if not m:
        return body.rstrip("\n"), []
    return body[:m.start()].rstrip("\n"), [l.rstrip() for l in body[m.end():].split("\n") if l.strip().startswith("- ")]


def dump_note(meta, main, entries):
    lines = ["---"]
    for k in NOTE_FIELDS:
        v = meta.get(k, [] if k in LIST_FIELDS else "")
        if k in LIST_FIELDS:
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            s = str(v).replace("\n", " ")
            lines.append(f'{k}: "{s}"' if k in ("titulo", "resumen") else f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + (main.strip("\n") + "\n" if main.strip() else "") + "\n" + CHANGELOG + "\n\n" + "\n".join(entries) + "\n"


def entry(ver, fecha, autor, texto):
    return f"- v{ver} · {fecha} · {autor} — {texto}".replace("\n", " ")


def iter_md(home, skip=SKIP_DIRS):
    """(ruta relativa, meta, cuerpo) de cada .md con frontmatter e id bajo `home`, sin las carpetas excluidas."""
    for root, dirs, files in os.walk(home):
        dirs[:] = sorted(d for d in dirs if d not in skip and d != ".historial")
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, encoding="utf-8") as fh:
                    meta, body = split_note(fh.read())
            except (OSError, UnicodeDecodeError):
                continue
            if meta and meta.get("id"):
                yield os.path.relpath(p, home), meta, body
