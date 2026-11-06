#!/usr/bin/env python3
"""Conocimiento común de un workspace de Arkana: notas Markdown versionadas con catálogo (RAG ligero, solo biblioteca estándar).

  add      --topic T --title X --summary R [--components a,b|all|arkana] [--tags x,y] [--author A] [--slug S] [--body-file F | --body TEXTO]
  modify   --id ID [--body-file F | --body TEXTO] [--title X] [--summary R] [--components ..] [--tags ..] [--author A] [--major] [--change TEXTO] [--restore]
  delete   --id ID [--reason TEXTO]                        borrado lógico: la nota queda con `state: deleted`, se oculta y su catálogo lo conserva
  query    --q "palabras" [--topic T] [--component C] [--limit N] [--include-deleted] [--json]      |   query --id ID   (muestra la nota)
  validate                                                  solo lectura (lo usa `check`)
  reindex                                                   reconstruye el catálogo
  install                                                   crea arkana-knowledge/ y el catálogo si faltan
  migrate                                                   pasa el formato antiguo (conocimiento/, catalogo.json, .historial, tipo/modulos) al actual (lo usa `fix`)
  Opciones comunes: --home DIR (carpeta del repo de Arkana; por defecto se localiza)  --dry-run (add, modify, delete, install, migrate)  --json

Una nota es un `.md` con frontmatter (`id`, `titulo`, `topic`, `version`, `fecha`, `autor`, `components`, `etiquetas`, `resumen`, `state`) y, al final, una sección
`## Changelog` con una línea por versión (la mantiene la herramienta; `modify` nunca la pisa). Las notas nuevas van en `arkana-knowledge/<topic>/<slug>.md`;
el catálogo es `arkana-knowledge/catalog.json` (índice que se lee primero). `components` son alias del manifiesto, `arkana` o `all`. Topics: decision, lesson,
pending, contract, reference. `state`: active | deleted. Los ids no cambian al migrar.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402

TOPICS = ["decision", "lesson", "pending", "contract", "reference"]
STATES = ["active", "deleted"]
FIELDS = ["id", "titulo", "topic", "version", "fecha", "autor", "components", "etiquetas", "resumen", "state"]
LIST_FIELDS = ("components", "etiquetas")
ROOT = "arkana-knowledge"
CATALOG = os.path.join(ROOT, "catalog.json")
EXCLUDED = {".git", "node_modules", "archivo", "plantillas", "plugins", "scripts", ".claude", ".claude-session", ".arkana", "lib", ".historial", "conocimiento"}
VERSION_RE = re.compile(r"^\d+\.\d+$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
CHANGELOG = "## Changelog"


class KError(Exception):
    def __init__(self, msg, cod=1):
        super().__init__(msg)
        self.cod = cod


# ---------- frontmatter y Changelog ----------
def parse_list(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    return [x.strip().strip("\"'") for x in v.split(",") if x.strip()]


def split_note(text):
    """(meta dict | None, cuerpo). El cuerpo incluye el Changelog."""
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
        if k in LIST_FIELDS or k == "modulos":
            meta[k] = parse_list(v)
        else:
            meta[k] = v[1:-1] if len(v) > 1 and v[0] == v[-1] and v[0] in "\"'" else v
    return meta, text[end + 5:]


def dump_meta(meta):
    lines = ["---"]
    for k in FIELDS:
        v = meta.get(k, [] if k in LIST_FIELDS else "")
        if k in LIST_FIELDS:
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            s = str(v).replace("\n", " ")
            lines.append(f'{k}: "{s}"' if k in ("titulo", "resumen") else f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def split_changelog(body):
    """(cuerpo sin changelog, [líneas del changelog])."""
    m = re.search(r"(?m)^## Changelog\s*$", body)
    if not m:
        return body.rstrip("\n"), []
    return body[:m.start()].rstrip("\n"), [l.rstrip() for l in body[m.end():].split("\n") if l.strip().startswith("- ")]


def join_note(meta, main, entries):
    return dump_meta(meta) + "\n" + (main.strip("\n") + "\n" if main.strip() else "") + "\n" + CHANGELOG + "\n\n" + "\n".join(entries) + "\n"


def entry(ver, fecha, autor, texto):
    return f"- v{ver} · {fecha} · {autor} — {texto}".replace("\n", " ")


def slugify(s):
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n"), ("ü", "u")):
        s = s.replace(a, b)
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:60] or "nota"


def default_author(home):
    try:
        n = subprocess.run(["git", "-C", home, "config", "user.name"], capture_output=True, text=True, timeout=10).stdout.strip()
        if n:
            return n
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("USER", "desconocido")


def today():
    return datetime.date.today().isoformat()


def bump(ver, major=False):
    a, b = (int(x) for x in ver.split("."))
    return f"{a + 1}.0" if major else f"{a}.{b + 1}"


def csv(v):
    return [x.strip() for x in (v or "").split(",") if x.strip()]


# ---------- workspace y catálogo ----------
def find_home(arg):
    home = os.path.abspath(arg) if arg else locate.find_home()
    if not home or not os.path.isdir(home):
        raise KError("no hay workspace de Arkana (usa --home o ejecuta dentro de uno)", 3)
    return home


def aliases(home):
    try:
        return manifest.load(home).aliases()
    except Exception:
        return None


def check_components(home, comps):
    al = aliases(home)
    if al is None:
        return
    bad = [c for c in comps if c not in ("all", "arkana") and manifest.canon(c) not in al]
    if bad:
        raise KError(f"componentes desconocidos: {', '.join(bad)} (válidos: {', '.join(al)}, arkana, all)", 2)


def norm_components(home, value):
    comps = [manifest.canon(x) if x not in ("all",) else x for x in csv(value)] if value is not None else []
    check_components(home, comps)
    return comps or ["all"]


def iter_notes(home):
    """(ruta relativa, meta, cuerpo) de cada .md con frontmatter e id bajo el repo (sin las carpetas excluidas)."""
    for root, dirs, files in os.walk(home):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for f in sorted(files):
            if f.endswith(".md"):
                p = os.path.join(root, f)
                try:
                    with open(p, encoding="utf-8") as fh:
                        meta, body = split_note(fh.read())
                except (OSError, UnicodeDecodeError):
                    continue
                if meta and meta.get("id"):
                    yield os.path.relpath(p, home), meta, body


def entry_of(ruta, meta):
    e = {k: meta.get(k, [] if k in LIST_FIELDS else "") for k in FIELDS}
    e["state"] = e["state"] or "active"
    e["ruta"] = ruta
    return e


def build_catalog(home):
    entries = sorted((entry_of(r, m) for r, m, _ in iter_notes(home) if "topic" in m), key=lambda e: e["id"])
    return {"version": 2, "actualizado": today(), "notas": entries}


def write_catalog(home, dry=False):
    cat = build_catalog(home)
    if not dry:
        datafiles.atomic_write_json(os.path.join(home, CATALOG), cat)
    return cat


def load_catalog(home):
    p = os.path.join(home, CATALOG)
    return datafiles.read_json(p) if os.path.isfile(p) else build_catalog(home)        # sin catálogo no se escribe nada aquí (lo hace reindex)


def find_entry(home, nid):
    return next((e for e in load_catalog(home)["notas"] if e["id"] == nid), None)


def read_body(a):
    if getattr(a, "body_file", None):
        with open(a.body_file, encoding="utf-8") as f:
            return f.read()
    if getattr(a, "body", None) is not None:
        return a.body
    return None


# ---------- comandos con informe ----------
def cmd_add(a, home, rep):
    if a.topic not in TOPICS:
        raise KError(f"topic inválido '{a.topic}'. Válidos: {', '.join(TOPICS)}", 2)
    slug = a.slug or slugify(a.titulo)
    nid = f"{a.topic}-{slug}"
    if not ID_RE.match(nid):
        raise KError(f"id inválido '{nid}'", 2)
    if find_entry(home, nid):
        raise KError(f"ya existe la nota '{nid}': usa modify para versionarla")
    ruta = os.path.join(ROOT, a.topic, f"{slug}.md")
    comps = norm_components(home, a.components)
    meta = {"id": nid, "titulo": a.titulo, "topic": a.topic, "version": "1.0", "fecha": today(), "autor": a.autor or default_author(home),
            "components": comps, "etiquetas": csv(a.etiquetas), "resumen": a.resumen, "state": "active"}
    body = (read_body(a) or "").strip("\n")
    if a.dry_run:
        return rep.add("DRY", "add", f"se crearía {nid} v1.0 → {ruta}")
    datafiles.atomic_write(os.path.join(home, ruta), join_note(meta, body or f"# {a.titulo}", [entry("1.0", meta["fecha"], meta["autor"], "creada")]))
    write_catalog(home)
    rep.add("OK", "add", f"creada {nid} v1.0 → {ruta}")


def load_note(home, nid):
    e = find_entry(home, nid)
    if not e:
        raise KError(f"no existe la nota '{nid}'")
    full = os.path.join(home, e["ruta"])
    with open(full, encoding="utf-8") as f:
        meta, body = split_note(f.read())
    main, entries = split_changelog(body)
    return e, full, meta, main, entries


def cmd_modify(a, home, rep):
    e, full, meta, main, entries = load_note(home, a.id)
    if meta.get("state") == "deleted" and not a.restore:
        raise KError(f"{a.id} está borrada (borrado lógico): usa --restore para recuperarla")
    new_body = read_body(a)
    if new_body is not None:
        main = new_body.strip("\n")
    for k in ("titulo", "resumen", "autor"):
        if getattr(a, k, None):
            meta[k] = getattr(a, k)
    if a.components is not None:
        meta["components"] = norm_components(home, a.components)
    if a.etiquetas is not None:
        meta["etiquetas"] = csv(a.etiquetas)
    prev = meta["version"]
    meta["version"] = bump(prev, a.major)
    meta["fecha"] = today()
    if not a.autor:
        meta["autor"] = default_author(home)
    if a.restore:
        meta["state"] = "active"
    meta.setdefault("topic", e["topic"])
    entries.append(entry(meta["version"], meta["fecha"], meta["autor"], ("restaurada. " if a.restore else "") + (a.change or "actualizada")))
    if a.dry_run:
        return rep.add("DRY", "modify", f"{a.id}: v{prev} → v{meta['version']}")
    datafiles.atomic_write(full, join_note(meta, main, entries))
    write_catalog(home)
    rep.add("OK", "modify", f"{a.id}: v{prev} → v{meta['version']} (el Changelog de la nota lo recoge)")


def cmd_delete(a, home, rep):
    e, full, meta, main, entries = load_note(home, a.id)
    if meta.get("state") == "deleted":
        return rep.add("OK", "delete", f"{a.id} ya estaba borrada")
    prev = meta["version"]
    meta["version"], meta["fecha"], meta["state"] = bump(prev), today(), "deleted"
    meta["autor"] = default_author(home)
    entries.append(entry(meta["version"], meta["fecha"], meta["autor"], "borrada (borrado lógico)" + (f": {a.reason}" if a.reason else "")))
    if a.dry_run:
        return rep.add("DRY", "delete", f"{a.id}: se marcaría como borrada (v{prev} → v{meta['version']})")
    datafiles.atomic_write(full, join_note(meta, main, entries))
    write_catalog(home)
    rep.add("OK", "delete", f"{a.id} borrada (borrado lógico: se oculta de query y se conserva; modify --restore la recupera)")


def cmd_reindex(a, home, rep):
    cat = write_catalog(home, a.dry_run)
    rep.add("DRY" if a.dry_run else "OK", "reindex", f"catálogo {'(no escrito) ' if a.dry_run else ''}reconstruido: {len(cat['notas'])} notas")


def cmd_install(a, home, rep):
    d = os.path.join(home, ROOT)
    if not os.path.isdir(d):
        if not a.dry_run:
            os.makedirs(d, exist_ok=True)
        rep.add("DRY" if a.dry_run else "OK", "carpeta", f"{ROOT}/ {'se crearía' if a.dry_run else 'creada'}")
    else:
        rep.add("OK", "carpeta", f"{ROOT}/ presente")
    if not os.path.isfile(os.path.join(home, CATALOG)):
        write_catalog(home, a.dry_run)
        rep.add("DRY" if a.dry_run else "OK", "catalogo", "catálogo " + ("se generaría" if a.dry_run else "generado"))
    else:
        rep.add("OK", "catalogo", "catálogo presente")
    if legacy(home):
        rep.add("WARN", "formato-antiguo", "hay conocimiento en el formato antiguo: ejecuta /arkana-knowledge:fix")


def legacy(home):
    """Qué queda del formato antiguo: carpeta conocimiento/, catalogo.json y notas con tipo/modulos."""
    res = []
    if os.path.isdir(os.path.join(home, "conocimiento")):
        res.append("conocimiento/")
    if os.path.isfile(os.path.join(home, "catalogo.json")):
        res.append("catalogo.json")
    n = sum(1 for r, m, _ in iter_notes_legacy(home) if "topic" not in m)
    if n:
        res.append(f"{n} notas con tipo/modulos")
    return res


def iter_notes_legacy(home):
    ex = EXCLUDED - {"conocimiento", ".historial"}
    for root, dirs, files in os.walk(home):
        dirs[:] = sorted(d for d in dirs if d not in ex and d != ".historial")
        for f in sorted(files):
            if f.endswith(".md"):
                p = os.path.join(root, f)
                try:
                    with open(p, encoding="utf-8") as fh:
                        meta, body = split_note(fh.read())
                except (OSError, UnicodeDecodeError):
                    continue
                if meta and meta.get("id"):
                    yield os.path.relpath(p, home), meta, body


def history_entries(home, nid):
    """Líneas de Changelog de las versiones archivadas en conocimiento/.historial/<id>/v*.md."""
    d = os.path.join(home, "conocimiento", ".historial", nid)
    res = []
    for f in sorted(os.listdir(d), key=lambda x: [int(p) for p in re.findall(r"\d+", x)]) if os.path.isdir(d) else []:
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                m, _ = split_note(fh.read())
        except OSError:
            continue
        if m and m.get("version"):
            res.append(entry(m["version"], m.get("fecha", "?"), m.get("autor", "?"), m.get("resumen", "versión archivada")))
    return res


def git_tracked(home, rel):
    return subprocess.run(["git", "-C", home, "ls-files", "--error-unmatch", rel], capture_output=True, text=True).returncode == 0


def move(home, src, dst, dry):
    if dry:
        return
    os.makedirs(os.path.dirname(os.path.join(home, dst)), exist_ok=True)
    if git_tracked(home, src):
        r = subprocess.run(["git", "-C", home, "mv", src, dst], capture_output=True, text=True)
        if r.returncode == 0:
            return
    shutil.move(os.path.join(home, src), os.path.join(home, dst))


def cmd_migrate(a, home, rep):
    """Formato antiguo → actual. Las notas de conocimiento/<tipo>/ pasan a arkana-knowledge/<tipo>/ (git mv); las que viven en otra parte (p. ej. las de
    referencia en la raíz) se quedan donde están. El historial pasa al Changelog de cada nota y las carpetas .historial y el catalogo.json antiguo se borran."""
    n = 0
    hist_ids = set()
    for ruta, meta, body in list(iter_notes_legacy(home)):
        if "topic" in meta:
            continue
        nid = meta["id"]
        tipo = meta.get("tipo") or "reference"
        comps = list(meta.get("modulos", [])) or ["all"]
        new = {"id": nid, "titulo": meta.get("titulo", nid), "topic": tipo if tipo in TOPICS else "reference", "version": meta.get("version", "1.0"),
               "fecha": meta.get("fecha", today()), "autor": meta.get("autor", "desconocido"), "components": comps, "etiquetas": meta.get("etiquetas", []),
               "resumen": meta.get("resumen", ""), "state": "active"}
        main, entries = split_changelog(body)
        if not entries:
            entries = history_entries(home, nid) + [entry(new["version"], new["fecha"], new["autor"], new["resumen"] or "versión actual")]
        hist_ids.add(nid)
        dest = ruta
        if ruta.startswith("conocimiento" + os.sep):
            dest = os.path.join(ROOT, new["topic"], os.path.basename(ruta))
        text = join_note(new, main, entries)
        if not a.dry_run:
            if dest != ruta:
                move(home, ruta, dest, False)
            datafiles.atomic_write(os.path.join(home, dest), text)
        rep.add("DRY" if a.dry_run else "OK", f"migrar:{nid}", f"{ruta} → {dest} ({len(entries)} entradas de Changelog; componentes {', '.join(comps)})")
        n += 1
    for d in ("conocimiento/.historial", "catalogo.json"):
        full = os.path.join(home, d)
        if os.path.exists(full):
            if not a.dry_run:
                if git_tracked(home, d) or subprocess.run(["git", "-C", home, "ls-files", d], capture_output=True, text=True).stdout.strip():
                    subprocess.run(["git", "-C", home, "rm", "-rq", "--", d], capture_output=True, text=True)
                if os.path.isdir(full):
                    shutil.rmtree(full, ignore_errors=True)
                elif os.path.exists(full):
                    os.remove(full)
            rep.add("DRY" if a.dry_run else "OK", f"borrar:{d}", "el historial pasó al Changelog de cada nota (el de git conserva los ficheros antiguos)" if "historial" in d else "sustituido por arkana-knowledge/catalog.json")
    cd = os.path.join(home, "conocimiento")
    if not a.dry_run and os.path.isdir(cd) and not any(f for _, _, fs in os.walk(cd) for f in fs):
        shutil.rmtree(cd, ignore_errors=True)
    if not a.dry_run:
        write_catalog(home)
    rep.add("DRY" if a.dry_run else "OK", "migrate", f"{n} notas {'se migrarían' if a.dry_run else 'migradas'}" if n else "no hay notas del formato antiguo")


def cmd_validate(a, home, rep):
    al = aliases(home)
    ids, errs = {}, 0
    for ruta, meta, body in iter_notes(home):
        if "topic" not in meta:
            rep.add("WARN", f"nota:{meta.get('id')}", f"{ruta}: formato antiguo (tipo/modulos): /arkana-knowledge:fix")
            continue
        i = meta["id"]
        pro = []
        for c in ("id", "titulo", "topic", "version", "fecha", "autor", "resumen", "state"):
            if not meta.get(c):
                pro.append(f"falta '{c}'")
        if i and not ID_RE.match(i):
            pro.append(f"id inválido '{i}'")
        if meta.get("topic") not in TOPICS:
            pro.append(f"topic inválido '{meta.get('topic')}'")
        if meta.get("state") not in STATES:
            pro.append(f"state inválido '{meta.get('state')}'")
        if not VERSION_RE.match(str(meta.get("version", ""))):
            pro.append(f"versión inválida '{meta.get('version')}' (formato N.N)")
        if al is not None:
            bad = [c for c in meta.get("components", []) if c not in ("all", "arkana") and manifest.canon(c) not in al]
            if bad:
                pro.append("componentes desconocidos: " + ", ".join(bad))
        if i in ids:
            pro.append(f"id duplicado con {ids[i]}")
        ids[i] = ruta
        _, entries = split_changelog(body)
        if not entries:
            pro.append("sin sección ## Changelog")
        elif not entries[-1].startswith(f"- v{meta.get('version')} "):
            pro.append("la última entrada del Changelog no es la versión actual")
        if pro:
            errs += 1
            rep.add("FAIL", f"nota:{i}", f"{ruta}: " + "; ".join(pro))
    cat = os.path.join(home, CATALOG)
    if not os.path.isfile(cat):
        rep.add("WARN", "catalogo", f"falta {CATALOG}: /arkana-knowledge:fix")
    else:
        ce = {e["id"]: e for e in (datafiles.read_json(cat, {}) or {}).get("notas", [])}
        desinc = [i for i, r in ids.items() if i not in ce or ce[i].get("ruta") != r] + [i for i in ce if i not in ids]
        rep.add("WARN" if desinc else "OK", "catalogo", f"catálogo desincronizado ({', '.join(sorted(set(desinc))[:3])}): /arkana-knowledge:fix" if desinc else f"catálogo al día ({len(ce)} notas)")
    if legacy(home):
        rep.add("WARN", "formato-antiguo", "queda formato antiguo (" + ", ".join(legacy(home)) + "): /arkana-knowledge:fix")
    if not errs:
        rep.add("OK", "notas", f"{len(ids)} notas válidas")


# ---------- query (salida propia) ----------
def cmd_query(a, home):
    comp = manifest.canon(a.component) if a.component else None
    if a.id:
        e = find_entry(home, a.id)
        if not e:
            raise KError(f"no existe la nota '{a.id}'")
        with open(os.path.join(home, e["ruta"]), encoding="utf-8") as f:
            sys.stdout.write(f.read())
        return 0
    words = [w for w in re.findall(r"\w+", (a.q or "").lower()) if len(w) > 1]
    if not words:
        raise KError("consulta vacía (usa --q o --id)", 2)
    res = []
    for ruta, meta, body in iter_notes(home):
        if "topic" not in meta:
            continue
        if meta.get("state") == "deleted" and not a.include_deleted:
            continue
        if a.topic and meta.get("topic") != a.topic:
            continue
        comps = meta.get("components", [])
        if comp and comp != "all" and comp not in comps and "all" not in comps:
            continue
        score = 0
        for txt, peso in ((meta.get("titulo", ""), 5), (" ".join(meta.get("etiquetas", [])), 4), (meta.get("resumen", ""), 3), (meta.get("id", ""), 2), (body, 1)):
            t = txt.lower()
            for w in words:
                score += peso * min(t.count(w), 5)
        if score:
            res.append((score, ruta, meta))
    res.sort(key=lambda r: (-r[0], r[2]["id"]))
    res = res[:a.limit]
    if a.json:
        print(json.dumps([{"score": s, "id": m["id"], "version": m["version"], "topic": m["topic"], "state": m.get("state", "active"), "components": m.get("components", []),
                           "titulo": m["titulo"], "ruta": r, "resumen": m["resumen"]} for s, r, m in res], ensure_ascii=False, indent=2))
    else:
        for s, r, m in res:
            print(f"{s}|{m['id']}|v{m['version']}|{m['topic']}|{r}|{m['titulo']}")
        if not res:
            print("sin resultados")
    return 0


def make_parser():
    p = argparse.ArgumentParser(prog="knowledge.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, dry=True):
        s.add_argument("--json", action="store_true")
        if dry:
            s.add_argument("--dry-run", dest="dry_run", action="store_true")
        return s

    def meta_args(s, req=False):
        s.add_argument("--title", dest="titulo", required=req)
        s.add_argument("--summary", dest="resumen", required=req)
        s.add_argument("--components", default=None)
        s.add_argument("--tags", dest="etiquetas", default=None)
        s.add_argument("--author", dest="autor")
        s.add_argument("--body-file")
        s.add_argument("--body")

    s = common(sub.add_parser("add")); s.add_argument("--topic", required=True); s.add_argument("--slug"); meta_args(s, True)
    s = common(sub.add_parser("modify")); s.add_argument("--id", required=True); meta_args(s); s.add_argument("--major", action="store_true")
    s.add_argument("--change"); s.add_argument("--restore", action="store_true")
    s = common(sub.add_parser("delete")); s.add_argument("--id", required=True); s.add_argument("--reason")
    s = common(sub.add_parser("query"), dry=False); s.add_argument("--q"); s.add_argument("--id"); s.add_argument("--topic"); s.add_argument("--component")
    s.add_argument("--limit", type=int, default=8); s.add_argument("--include-deleted", dest="include_deleted", action="store_true")
    common(sub.add_parser("validate"), dry=False)
    common(sub.add_parser("reindex"))
    common(sub.add_parser("install"))
    common(sub.add_parser("migrate"))
    return p


def main(argv=None):
    try:
        a = make_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-knowledge", a.cmd)
    try:
        home = find_home(a.home)
        if a.cmd == "query":
            return cmd_query(a, home)
        {"add": cmd_add, "modify": cmd_modify, "delete": cmd_delete, "reindex": cmd_reindex, "install": cmd_install, "migrate": cmd_migrate,
         "validate": cmd_validate}[a.cmd](a, home, rep)
    except KError as e:
        rep.add("FAIL", a.cmd, str(e))
        sys.stdout.write(rep.render(getattr(a, "json", False)))
        return e.cod
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(rep.render(getattr(a, "json", False)))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
