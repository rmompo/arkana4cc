#!/usr/bin/env python3
"""Conocimiento común de un workspace de Arkana: notas Markdown versionadas y documentos de origen con su versión en Markdown (RAG ligero, solo biblioteca estándar).

  add      --topic T --title X --summary R [--components a,b|all] [--tags x,y] [--sources UUID,..] [--author A] [--slug S] [--body-file F | --body TEXTO]
  modify   --id REF [--body-file F | --body TEXTO] [--title X] [--summary R] [--components ..] [--tags ..] [--sources ..] [--author A] [--major] [--change TEXTO] [--restore]
  delete   --id REF [--reason TEXTO]                      borrado lógico: la nota queda con `state: deleted` y se oculta
  query    --q "palabras" [--topic T] [--component C] [--kind note|document|all] [--limit N] [--include-deleted] [--json]   |   query --id REF   (muestra la nota o el documento)
  validate                                                solo lectura (lo usa `check`)
  reindex                                                 reconstruye el índice local derivado
  install                                                 crea las carpetas fijas (con .gitkeep) y el índice
  ingest scan|convert|add|reconvert ...                   documentos: ver `docs.py`
  Opciones comunes: --home DIR (carpeta del repo de Arkana; por defecto se localiza)  --dry-run (add, modify, delete, reindex, install, ingest add|reconvert)  --json

Carpetas fijas del repo de ARKANA: `arkana-incoming/` (cola local; solo se versiona su `.gitkeep`), `arkana-knowledge/<topic>/<slug>.md` (decisiones, lecciones,
metodología…) y `arkana-docs/` (documentos de origen) con `arkana-docs/md/` (su versión en Markdown, que es lo que se consulta).
La identidad de una nota o de un documento es su UUID (`id`); el slug es solo el nombre del fichero. `components` guarda los componentes por su id del registro del
proyecto (o `all`): renombrar un componente no toca ningún documento; `query` y los informes muestran siempre el alias. Una nota termina en `## Changelog`
(una línea por versión; `modify` nunca la pisa). Topics: decision, lesson, pending, contract, reference, methodology. El catálogo ya no se versiona: el índice es
local y derivado (`.arkana/arkana-knowledge/index.json`), se reconstruye solo cuando cambian los ficheros y nunca produce conflictos de git.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as C  # noqa: E402  (añade el núcleo al sys.path)
import docs  # noqa: E402
from arkana_core import datafiles, locate, output, project  # noqa: E402
from common import DOCS, INCOMING, KError, MD, ROOT, TOPICS  # noqa: E402

INDEX_REL = os.path.join("arkana-knowledge", "index.json")
FOLDERS = [ROOT, DOCS, MD, INCOMING]
INCOMING_GITIGNORE = "*\n!.gitignore\n!.gitkeep\n"
MAX_BODY = 400_000


def index_path(home):
    return os.path.join(locate.state_dir(home), INDEX_REL)


# ---------- notas ----------
def iter_notes(home):
    """(ruta relativa, meta, cuerpo) de cada nota bajo arkana-knowledge/."""
    base = os.path.join(home, ROOT)
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, encoding="utf-8") as fh:
                    meta, body = C.split_note(fh.read())
            except (OSError, UnicodeDecodeError):
                continue
            if meta and meta.get("id"):
                yield os.path.relpath(p, home), meta, body


def find_note(home, ref):
    """(ruta, meta, cuerpo) de una nota por UUID, slug, `<topic>-<slug>` (id antiguo) o ruta."""
    ref = (ref or "").strip()
    for ruta, meta, body in iter_notes(home):
        slug = meta.get("slug") or os.path.splitext(os.path.basename(ruta))[0]
        if ref in (meta["id"], slug, f"{meta.get('topic')}-{slug}", ruta):
            return ruta, meta, body
    return None


def read_body(a):
    if getattr(a, "body_file", None):
        with open(a.body_file, encoding="utf-8") as f:
            return f.read()
    if getattr(a, "body", None) is not None:
        return a.body
    return None


def norm_sources(home, value):
    ids = C.csv(value)
    existentes = {m["id"] for _, m, _ in docs.iter_docs(home)}
    falta = [i for i in ids if i not in existentes]
    if falta:
        raise KError(f"fuentes desconocidas (no son UUID de documentos ingeridos): {', '.join(falta)}", 2)
    return ids


# ---------- índice local derivado ----------
def fingerprint(home):
    h = hashlib.sha1()
    for base in (os.path.join(home, ROOT), os.path.join(home, MD)):
        for root, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for f in sorted(files):
                if f.endswith(".md"):
                    p = os.path.join(root, f)
                    st = os.stat(p)
                    h.update(f"{os.path.relpath(p, home)}|{st.st_mtime_ns}|{st.st_size}\n".encode())
    h.update(project.read(home).__repr__().encode() if project.read(home) else b"")             # el registro cambia cómo se muestran los componentes
    return h.hexdigest()


def entries(home):
    res = []
    for ruta, m, _ in iter_notes(home):
        res.append({"id": m["id"], "kind": "note", "slug": m.get("slug", ""), "titulo": m.get("titulo", ""), "topic": m.get("topic", ""), "version": m.get("version", ""),
                    "fecha": m.get("fecha", ""), "autor": m.get("autor", ""), "components": m.get("components", []), "etiquetas": m.get("etiquetas", []),
                    "fuentes": m.get("fuentes", []), "resumen": m.get("resumen", ""), "state": m.get("state") or "active", "ruta": ruta})
    for ruta, m, _ in docs.iter_docs(home):
        res.append({"id": m["id"], "kind": "document", "titulo": m.get("titulo", ""), "fecha": m.get("fecha", ""), "autor": m.get("autor", ""),
                    "components": m.get("components", []), "etiquetas": m.get("etiquetas", []), "resumen": m.get("resumen", ""), "state": m.get("state") or "active",
                    "ruta": ruta, "original": os.path.join(DOCS, m.get("original", "")), "sha256": m.get("sha256", ""), "mime": m.get("mime", ""),
                    "conversion": m.get("conversion", ""), "cobertura": m.get("cobertura", "")})
    return sorted(res, key=lambda e: (e["kind"], e["id"]))


def load_index(home, force=False):
    """Índice local: se reutiliza mientras no cambien los ficheros y se reconstruye si cambian (o con force)."""
    fp = fingerprint(home)
    cur = datafiles.read_json(index_path(home))
    if not force and isinstance(cur, dict) and cur.get("fingerprint") == fp:
        return cur
    idx = {"schema_version": 1, "fingerprint": fp, "generado": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "entradas": entries(home)}
    try:
        datafiles.atomic_write_json(index_path(home), idx)
    except OSError:
        pass                                                                                     # solo lectura: se usa en memoria
    return idx


# ---------- comandos con informe ----------
def cmd_add(a, home, rep):
    if a.topic not in TOPICS:
        raise KError(f"topic inválido '{a.topic}'. Válidos: {', '.join(TOPICS)}", 2)
    slug = a.slug or C.slugify(a.titulo)
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", slug):
        raise KError(f"slug inválido '{slug}'", 2)
    ruta = os.path.join(ROOT, a.topic, f"{slug}.md")
    if os.path.exists(os.path.join(home, ruta)):
        raise KError(f"ya existe una nota '{a.topic}/{slug}': usa modify para versionarla")
    meta = {"id": str(uuid.uuid4()), "slug": slug, "titulo": a.titulo, "topic": a.topic, "version": "1.0", "fecha": C.today(), "autor": a.autor or C.default_author(home),
            "components": C.norm_components(home, a.components), "etiquetas": C.csv(a.etiquetas), "fuentes": norm_sources(home, a.sources),
            "resumen": a.resumen, "state": "active"}
    body = (read_body(a) or "").strip("\n")
    if a.dry_run:
        return rep.add("DRY", "add", f"se crearía {a.topic}/{slug} v1.0 → {ruta}")
    datafiles.atomic_write(os.path.join(home, ruta), C.join_note(meta, body or f"# {a.titulo}", [C.entry("1.0", meta["fecha"], meta["autor"], "creada")]))
    rep.add("OK", "add", f"creada {meta['id']} ({a.topic}/{slug}) v1.0 → {ruta}")


def load_note(home, ref):
    f = find_note(home, ref)
    if not f:
        raise KError(f"no existe la nota '{ref}'")
    ruta, meta, body = f
    main, ents = C.split_changelog(body)
    return ruta, os.path.join(home, ruta), meta, main, ents


def cmd_modify(a, home, rep):
    ruta, full, meta, main, ents = load_note(home, a.id)
    if meta.get("state") == "deleted" and not a.restore:
        raise KError(f"{a.id} está borrada (borrado lógico): usa --restore para recuperarla")
    new_body = read_body(a)
    if new_body is not None:
        main = new_body.strip("\n")
    for k in ("titulo", "resumen", "autor"):
        if getattr(a, k, None):
            meta[k] = getattr(a, k)
    if a.components is not None:
        meta["components"] = C.norm_components(home, a.components)
    if a.etiquetas is not None:
        meta["etiquetas"] = C.csv(a.etiquetas)
    if a.sources is not None:
        meta["fuentes"] = norm_sources(home, a.sources)
    prev = meta["version"]
    meta["version"] = C.bump(prev, a.major)
    meta["fecha"] = C.today()
    if not a.autor:
        meta["autor"] = C.default_author(home)
    if a.restore:
        meta["state"] = "active"
    ents.append(C.entry(meta["version"], meta["fecha"], meta["autor"], ("restaurada. " if a.restore else "") + (a.change or "actualizada")))
    if a.dry_run:
        return rep.add("DRY", "modify", f"{a.id}: v{prev} → v{meta['version']}")
    datafiles.atomic_write(full, C.join_note(meta, main, ents))
    rep.add("OK", "modify", f"{a.id}: v{prev} → v{meta['version']} (el Changelog de la nota lo recoge)")


def cmd_delete(a, home, rep):
    ruta, full, meta, main, ents = load_note(home, a.id)
    if meta.get("state") == "deleted":
        return rep.add("OK", "delete", f"{a.id} ya estaba borrada")
    prev = meta["version"]
    meta["version"], meta["fecha"], meta["state"] = C.bump(prev), C.today(), "deleted"
    meta["autor"] = C.default_author(home)
    ents.append(C.entry(meta["version"], meta["fecha"], meta["autor"], "borrada (borrado lógico)" + (f": {a.reason}" if a.reason else "")))
    if a.dry_run:
        return rep.add("DRY", "delete", f"{a.id}: se marcaría como borrada (v{prev} → v{meta['version']})")
    datafiles.atomic_write(full, C.join_note(meta, main, ents))
    rep.add("OK", "delete", f"{a.id} borrada (borrado lógico: se oculta de query y se conserva; modify --restore la recupera)")


def cmd_reindex(a, home, rep):
    if a.dry_run:
        return rep.add("DRY", "reindex", f"índice (no escrito): {len(entries(home))} entradas")
    idx = load_index(home, force=True)
    rep.add("OK", "reindex", f"índice local reconstruido: {len(idx['entradas'])} entradas")


def cmd_install(a, home, rep):
    for d in FOLDERS:
        full = os.path.join(home, d)
        gk = os.path.join(full, ".gitkeep")
        if os.path.isfile(gk) or (os.path.isdir(full) and d != INCOMING and any(f for f in os.listdir(full))):
            rep.add("OK", "carpeta", f"{d}/ presente")
            continue
        if not a.dry_run:
            os.makedirs(full, exist_ok=True)
            if not os.path.exists(gk):
                datafiles.atomic_write(gk, "")
        rep.add("DRY" if a.dry_run else "OK", "carpeta", f"{d}/ {'se crearía' if a.dry_run else 'creada'}")
    gi = os.path.join(home, INCOMING, ".gitignore")
    if not os.path.isfile(gi):
        if not a.dry_run:
            datafiles.atomic_write(gi, INCOMING_GITIGNORE)
        rep.add("DRY" if a.dry_run else "OK", "carpeta", f"{INCOMING}/.gitignore {'se crearía' if a.dry_run else 'creado'} (ignora el contenido; solo se versionan .gitignore y .gitkeep)")
    if not a.dry_run:
        load_index(home, force=True)
    rep.add("OK", "indice", "índice local " + ("(se generaría)" if a.dry_run else "generado"))


def cmd_validate(a, home, rep):
    ids, errs = {}, 0
    doc_ids = {m["id"] for _, m, _ in docs.iter_docs(home)}
    for ruta, meta, body in iter_notes(home):
        i = meta["id"]
        pro = []
        for c in ("id", "titulo", "topic", "version", "fecha", "autor", "resumen", "state"):
            if not meta.get(c):
                pro.append(f"falta '{c}'")
        if i and not project.is_id(i):
            pro.append(f"id '{i}' no es un UUID: migra con /arkana-evolve:apply")
        if meta.get("topic") not in TOPICS:
            pro.append(f"topic inválido '{meta.get('topic')}'")
        if meta.get("state") not in C.STATES:
            pro.append(f"state inválido '{meta.get('state')}'")
        if not C.VERSION_RE.match(str(meta.get("version", ""))):
            pro.append(f"versión inválida '{meta.get('version')}' (formato N.N)")
        bad = [c for c in meta.get("components", []) if not C.component_ok(home, c)]
        if bad:
            pro.append("componentes desconocidos: " + ", ".join(bad))
        sin = [f for f in meta.get("fuentes", []) if f not in doc_ids]
        if sin:
            rep.add("WARN", f"nota:{i}", f"{ruta}: fuentes que no están entre los documentos ingeridos: {', '.join(sin)}")
        if i in ids:
            pro.append(f"id duplicado con {ids[i]}")
        ids[i] = ruta
        _, ents = C.split_changelog(body)
        if not ents:
            pro.append("sin sección ## Changelog")
        elif not ents[-1].startswith(f"- v{meta.get('version')} "):
            pro.append("la última entrada del Changelog no es la versión actual")
        if pro:
            errs += 1
            rep.add("FAIL", f"nota:{i}", f"{ruta}: " + "; ".join(pro))
    n_docs = 0
    originales = set()
    for ruta, meta, body in docs.iter_docs(home):
        n_docs += 1
        i = meta["id"]
        pro = []
        for c in ("titulo", "original", "sha256", "conversion", "resumen", "state"):
            if not meta.get(c):
                pro.append(f"falta '{c}'")
        if not project.is_id(i):
            pro.append("el id no es un UUID")
        if i in ids:
            pro.append(f"id duplicado con {ids[i]}")
        ids[i] = ruta
        if meta.get("conversion") not in ("herramienta", "modelo"):
            pro.append("conversion: herramienta | modelo")
        bad = [c for c in meta.get("components", []) if not C.component_ok(home, c)]
        if bad:
            pro.append("componentes desconocidos: " + ", ".join(bad))
        orig = os.path.join(home, DOCS, meta.get("original", "-"))
        originales.add(os.path.normpath(orig))
        if not os.path.isfile(orig):
            pro.append(f"falta el original {meta.get('original')}")
        elif C.is_lfs_pointer(orig):
            rep.add("WARN", f"doc:{i}", f"{meta.get('original')} es un puntero de git-lfs: pídele a la persona usuaria que instale git-lfs y ejecute `git lfs pull`")
        elif C.sha256_file(orig) != meta.get("sha256"):
            pro.append(f"el sha256 del original no coincide ({meta.get('original')} cambió desde que se ingirió)")
        if pro:
            errs += 1
            rep.add("FAIL", f"doc:{i}", f"{ruta}: " + "; ".join(pro))
        elif meta.get("conversion") == "modelo" and meta.get("cobertura") not in ("completa",):
            rep.add("INFO", f"doc:{i}", f"{meta.get('original')}: Markdown hecho por el modelo ({meta.get('cobertura')}); `ingest reconvert` lo mejora si hay herramienta")
    base = os.path.join(home, DOCS)
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d != "md" and not d.startswith("."))
        for f in files:
            p = os.path.normpath(os.path.join(root, f))
            if f.startswith(".") or p in originales:
                continue
            rep.add("WARN", "huerfano", f"{os.path.relpath(p, home)} está en {DOCS}/ sin su Markdown: ingiérelo con /arkana-knowledge:ingest")
    for d in FOLDERS:
        if not os.path.isdir(os.path.join(home, d)):
            rep.add("WARN", "carpeta", f"falta {d}/: /arkana-knowledge:install (o un git pull: llevan su .gitkeep)")
    if os.path.isfile(os.path.join(home, ROOT, "catalog.json")):
        rep.add("WARN", "catalogo", f"{ROOT}/catalog.json es el catálogo antiguo (ya no se versiona): /arkana-evolve:apply lo retira")
    ga = os.path.join(home, ".gitattributes")
    try:
        usa_lfs = "filter=lfs" in open(ga, encoding="utf-8").read() if os.path.isfile(ga) else False
    except OSError:
        usa_lfs = False
    if usa_lfs and not docs.tools()["git-lfs"]:
        rep.add("WARN", "git-lfs", "el repo usa git-lfs pero no está instalado: pídele a la persona usuaria que lo instale (p. ej. `sudo apt install git-lfs`)")
    pend = [r for r in docs.scan(home) if r.get("estable") is not False] if os.path.isdir(os.path.join(home, INCOMING)) else []
    viejos = [r for r in pend if os.path.getmtime(os.path.join(home, r["ruta"])) < datetime.datetime.now().timestamp() - 7 * 86400] if pend else []
    if viejos:
        rep.add("WARN", "incoming", f"{len(viejos)} documentos llevan más de 7 días en {INCOMING}/: /arkana-knowledge:ingest")
    elif pend:
        rep.add("INFO", "incoming", f"{len(pend)} documentos pendientes de ingerir en {INCOMING}/")
    if not errs:
        rep.add("OK", "notas", f"{len(ids) - n_docs} notas y {n_docs} documentos válidos")


# ---------- ingesta ----------
def cmd_ingest(a, home, rep):
    if a.sub == "add":
        docs.cmd_add(a, home, rep)
    elif a.sub == "reconvert":
        docs.cmd_reconvert(a, home, rep)


def cmd_ingest_scan(a, home):
    rows = docs.scan(home, a.src)
    if a.json:
        print(json.dumps({"herramientas": docs.tools(), "ficheros": rows}, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            est = r.get("estado") or ("estable" if r.get("estable") else "se está copiando")
            print(f"{r['ruta']}|{r.get('bytes')}|{r.get('mime', '-')}|{est}|conversión {r.get('conversion', '-')}" + (f"|DUPLICADO de {r['duplicado_de']}" if r.get("duplicado_de") else ""))
        if not rows:
            print("nada pendiente")
    return 0


def cmd_ingest_convert(a, home):
    p = a.file if os.path.isabs(a.file) else os.path.join(home, a.file)
    if not os.path.isfile(p) or os.path.islink(p):
        raise KError(f"no existe el fichero {a.file}")
    r = docs.convert(p)
    if r is None:
        raise KError("no se puede convertir con lo que hay en el equipo: léelo y transcribe su contenido (y, para PDF, pide `poppler-utils`)", 3)
    texto, conv, cob = r
    if a.out:
        datafiles.atomic_write(a.out, texto)
        print(f"OK|convert|{conv}, {cob}: {len(texto)} caracteres en {a.out}")
    else:
        sys.stdout.write(texto)
    return 0


# ---------- query (salida propia) ----------
def cmd_query(a, home):
    if a.id:
        n = find_note(home, a.id)
        if n:
            ruta = n[0]
        else:
            d = docs.find_doc(home, a.id)
            if not d:
                raise KError(f"no existe la nota ni el documento '{a.id}'")
            ruta = d[0]
        with open(os.path.join(home, ruta), encoding="utf-8") as f:
            sys.stdout.write(f.read())
        return 0
    words = [w for w in re.findall(r"\w+", (a.q or "").lower()) if len(w) > 1]
    if not words:
        raise KError("consulta vacía (usa --q o --id)", 2)
    res = []
    for e in load_index(home)["entradas"]:
        if a.kind != "all" and e["kind"] != a.kind:
            continue
        if e.get("state") == "deleted" and not a.include_deleted:
            continue
        if a.topic and e.get("topic") != a.topic:
            continue
        if not C.matches_component(home, e.get("components", []), a.component):
            continue
        try:
            with open(os.path.join(home, e["ruta"]), encoding="utf-8") as f:
                body = f.read(MAX_BODY)
        except OSError:
            body = ""
        score = 0
        for txt, peso in ((e.get("titulo", ""), 5), (" ".join(e.get("etiquetas", [])), 4), (e.get("resumen", ""), 3), (e.get("slug", "") or e.get("id", ""), 2), (body, 1)):
            t = txt.lower()
            for w in words:
                score += peso * min(t.count(w), 5)
        if score:
            res.append((score, e))
    res.sort(key=lambda r: (-r[0], r[1]["id"]))
    res = res[:a.limit]
    if a.json:
        print(json.dumps([{"score": s, "id": e["id"], "kind": e["kind"], "version": e.get("version"), "topic": e.get("topic"), "state": e.get("state", "active"),
                           "components": C.shown(home, e.get("components", [])), "titulo": e["titulo"], "ruta": e["ruta"], "resumen": e["resumen"],
                           **({"original": e["original"], "conversion": e["conversion"], "cobertura": e["cobertura"]} if e["kind"] == "document" else {"slug": e.get("slug", "")})}
                          for s, e in res], ensure_ascii=False, indent=2))
    else:
        for s, e in res:
            print(f"{s}|{e['id']}|{'v' + e['version'] if e['kind'] == 'note' else 'doc'}|{e.get('topic') or '-'}|{e['ruta']}|{e['titulo']}")
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
        s.add_argument("--sources", default=None)
        s.add_argument("--author", dest="autor")
        s.add_argument("--body-file")
        s.add_argument("--body")

    s = common(sub.add_parser("add")); s.add_argument("--topic", required=True); s.add_argument("--slug"); meta_args(s, True)
    s = common(sub.add_parser("modify")); s.add_argument("--id", required=True); meta_args(s); s.add_argument("--major", action="store_true")
    s.add_argument("--change"); s.add_argument("--restore", action="store_true")
    s = common(sub.add_parser("delete")); s.add_argument("--id", required=True); s.add_argument("--reason")
    s = common(sub.add_parser("query"), dry=False); s.add_argument("--q"); s.add_argument("--id"); s.add_argument("--topic"); s.add_argument("--component")
    s.add_argument("--kind", choices=("note", "document", "all"), default="all")
    s.add_argument("--limit", type=int, default=8); s.add_argument("--include-deleted", dest="include_deleted", action="store_true")
    common(sub.add_parser("validate"), dry=False)
    common(sub.add_parser("reindex"))
    common(sub.add_parser("install"))
    ing = sub.add_parser("ingest")
    isub = ing.add_subparsers(dest="sub", required=True)
    s = common(isub.add_parser("scan"), dry=False); s.add_argument("--from", dest="src")
    s = common(isub.add_parser("convert"), dry=False); s.add_argument("--file", required=True); s.add_argument("--out")
    s = common(isub.add_parser("add")); s.add_argument("--file", required=True); s.add_argument("--title", dest="titulo", required=True)
    s.add_argument("--summary", dest="resumen", required=True); s.add_argument("--tags", dest="etiquetas"); s.add_argument("--components"); s.add_argument("--author", dest="autor")
    s.add_argument("--md-file"); s.add_argument("--conversion"); s.add_argument("--coverage"); s.add_argument("--dest-dir"); s.add_argument("--keep-source", action="store_true")
    s = common(isub.add_parser("reconvert")); s.add_argument("--id", required=True)
    return p


def main(argv=None):
    try:
        a = make_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-knowledge", a.cmd + (f" {a.sub}" if a.cmd == "ingest" else ""))
    try:
        home = C.find_home(a.home)
        if a.cmd == "query":
            return cmd_query(a, home)
        if a.cmd == "ingest" and a.sub == "scan":
            return cmd_ingest_scan(a, home)
        if a.cmd == "ingest" and a.sub == "convert":
            return cmd_ingest_convert(a, home)
        {"add": cmd_add, "modify": cmd_modify, "delete": cmd_delete, "reindex": cmd_reindex, "install": cmd_install, "validate": cmd_validate,
         "ingest": cmd_ingest}[a.cmd](a, home, rep)
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
