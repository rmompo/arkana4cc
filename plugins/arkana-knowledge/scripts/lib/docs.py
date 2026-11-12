"""Documentos de origen (`arkana-docs/`) y su versión en Markdown (`arkana-docs/md/`, mismo árbol), e ingesta desde `arkana-incoming/`.

  scan      [--from DIR]            lista lo que hay por ingerir: hash, tipo, si está estable, duplicados y cómo se puede convertir
  convert   --file F [--out MD]     convierte con lo que hay en el equipo (md, txt, docx, pptx; pdf con `pdftotext`); si no se puede, avisa
  add       --file F --title T --summary S [...]     ingiere: el original va a arkana-docs/, su Markdown a arkana-docs/md/ y se quita de la cola
  reconvert --id REF                regenera el Markdown de un documento con una herramienta (p. ej. tras instalar `pdftotext`)

El Markdown es la fuente que Arkana lee y consulta: su frontmatter lleva el UUID, el sha256 del original, cómo y cuánto se convirtió (`conversion`: herramienta |
modelo; `cobertura`) y el resumen. El original es la prueba. Lo decide el modelo (qué carpeta, título, resumen, etiquetas); el script valida y escribe.
Nunca se ejecuta contenido del documento, se rechazan enlaces simbólicos y macros, y se limita el tamaño de lo que se descomprime.
"""
import mimetypes
import os
import re
import shutil
import stat
import subprocess
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET

import common as C  # noqa: E402  (añade el núcleo al sys.path)
from arkana_core import datafiles  # noqa: E402
from common import DOCS, INCOMING, KError, MD  # noqa: E402

STABLE_SECONDS = float(os.environ.get("ARKANA_STABLE_SECONDS", "5"))      # un fichero que cambió hace menos es posible que aún se esté copiando
SKIP = (".part", ".crdownload", ".tmp", ".swp", ".download")
MACROS = (".pptm", ".docm", ".xlsm", ".potm", ".dotm")
MAX_ZIP_TOTAL = 200 * 1024 * 1024
MAX_MEMBER = 30 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def tools():
    return {"pdftotext": bool(shutil.which("pdftotext")), "git-lfs": bool(shutil.which("git-lfs"))}


# ---------- documentos existentes ----------
def iter_docs(home):
    """(ruta relativa, meta, cuerpo) de cada Markdown de documento bajo arkana-docs/md."""
    base = os.path.join(home, MD)
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
            if meta and meta.get("id") and meta.get("kind") == "document":
                yield os.path.relpath(p, home), meta, body


def find_doc(home, ref):
    ref = (ref or "").strip()
    for ruta, meta, body in iter_docs(home):
        if ref in (meta["id"], ruta) or ref == meta.get("original") or os.path.basename(meta.get("original", "")) == ref:
            return ruta, meta, body
    return None


# ---------- conversión ----------
def _zip_xml(z, name):
    info = z.getinfo(name)
    if info.file_size > MAX_MEMBER:
        raise KError(f"{name} es demasiado grande para convertirlo ({info.file_size} bytes)")
    return ET.fromstring(z.read(name))


def _open_zip(path):
    z = zipfile.ZipFile(path)
    infos = z.infolist()
    if len(infos) > 5000 or sum(i.file_size for i in infos) > MAX_ZIP_TOTAL:
        z.close()
        raise KError("el fichero comprimido es anómalo (demasiados elementos o demasiado grande descomprimido)")
    return z


def docx_to_md(path):
    with _open_zip(path) as z:
        root = _zip_xml(z, "word/document.xml")
    out = []
    for p in root.iter(W + "p"):
        txt = "".join((t.text or "") if t.tag == W + "t" else ("\t" if t.tag == W + "tab" else "\n" if t.tag == W + "br" else "") for t in p.iter())
        txt = txt.strip()
        if not txt:
            continue
        st = p.find(f"{W}pPr/{W}pStyle")
        m = re.match(r"(?i)^(?:heading|t[ií]tulo)\s*(\d)$", st.get(W + "val", "") if st is not None else "")
        out.append(("#" * int(m.group(1)) + " " if m else "") + txt)
    return "\n\n".join(out)


def pptx_to_md(path):
    with _open_zip(path) as z:
        nums = sorted(int(m.group(1)) for n in z.namelist() for m in [re.match(r"ppt/slides/slide(\d+)\.xml$", n)] if m)
        out = []
        for n in nums:
            paras = ["".join(t.text or "" for t in p.iter(A + "t")).strip() for p in _zip_xml(z, f"ppt/slides/slide{n}.xml").iter(A + "p")]
            out.append(f"## Diapositiva {n}\n\n" + "\n\n".join(x for x in paras if x))
            nn = f"ppt/notesSlides/notesSlide{n}.xml"
            if nn in z.namelist():
                notes = ["".join(t.text or "" for t in p.iter(A + "t")).strip() for p in _zip_xml(z, nn).iter(A + "p")]
                notes = [x for x in notes if x and not x.isdigit()]
                if notes:
                    out[-1] += "\n\n> Notas: " + " ".join(notes)
    return "\n\n".join(out)


def convert(path):
    """(texto, conversion, cobertura) con lo que hay en el equipo, o None si no se puede (el modelo debe leerlo y transcribirlo)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in MACROS:
        raise KError(f"{ext}: los ficheros con macros no se ingieren")
    if ext in (".md", ".markdown", ".txt", ".text"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(), "herramienta", "completa"
    if ext == ".docx":
        return docx_to_md(path), "herramienta", "completa"
    if ext == ".pptx":
        return pptx_to_md(path), "herramienta", "completa"
    if ext == ".pdf" and shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout, "herramienta", "completa"
        return None                                        # PDF escaneado o ilegible: lo lee el modelo
    return None


# ---------- scan ----------
def _skippable(name):
    return name.startswith(".") or name.startswith("~$") or name.lower().endswith(SKIP)


def scan(home, src=None):
    base = os.path.realpath(src) if src else os.path.join(home, INCOMING)
    por_sha = {m.get("sha256"): m["id"] for _, m, _ in iter_docs(home)}
    rows = []
    for root, dirs, files in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for f in sorted(files):
            if _skippable(f):
                continue
            p = os.path.join(root, f)
            st = os.lstat(p)
            row = {"ruta": os.path.relpath(p, home) if p.startswith(home + os.sep) else p, "nombre": f, "bytes": st.st_size,
                   "ext": os.path.splitext(f)[1].lower()}
            if stat.S_ISLNK(st.st_mode):
                row["estado"] = "enlace simbólico: se ignora"
                rows.append(row)
                continue
            row["mime"] = mimetypes.guess_type(f)[0] or "application/octet-stream"
            row["estable"] = (time.time() - st.st_mtime) >= STABLE_SECONDS
            row["sha256"] = C.sha256_file(p)
            row["lfs_puntero"] = C.is_lfs_pointer(p)
            row["duplicado_de"] = por_sha.get(row["sha256"])
            if row["ext"] in MACROS:
                row["conversion"] = "no admitido (macros)"
            elif row["ext"] in (".md", ".markdown", ".txt", ".text", ".docx", ".pptx") or (row["ext"] == ".pdf" and shutil.which("pdftotext")):
                row["conversion"] = "script"
            else:
                row["conversion"] = "modelo"
            rows.append(row)
    return rows


# ---------- add ----------
def _inside(home, p):
    h, r = os.path.realpath(home), os.path.realpath(p)
    return r == h or r.startswith(h.rstrip(os.sep) + os.sep)


def _safe_subdir(d):
    d = (d or "").strip().strip("/")
    n = os.path.normpath(d) if d else ""
    if n.startswith("..") or os.path.isabs(d) or n == ".":
        n = "" if n == "." else n
    if n.startswith("..") or os.path.isabs(d):
        raise KError(f"--dest-dir no puede salir de {DOCS}: {d!r}", 2)
    return n


def _tracked(home, rel):
    return subprocess.run(["git", "-C", home, "ls-files", "--error-unmatch", "--", rel], capture_output=True, text=True).returncode == 0


def _move(home, src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    rs, rd = os.path.relpath(src, home), os.path.relpath(dst, home)
    if _tracked(home, rs) and subprocess.run(["git", "-C", home, "mv", "--", rs, rd], capture_output=True, text=True).returncode == 0:
        return
    shutil.move(src, dst)


def cmd_add(a, home, rep):
    src = a.file if os.path.isabs(a.file) else os.path.join(home, a.file)
    if os.path.islink(src):
        raise KError("los enlaces simbólicos no se ingieren")
    if not os.path.isfile(src):
        raise KError(f"no existe el fichero {a.file}")
    if not _inside(home, src):
        raise KError("solo se ingiere lo que está dentro del repo de ARKANA (arkana-incoming/ o una carpeta suya)")
    if C.is_lfs_pointer(src):
        raise KError("el fichero es un puntero de git-lfs, no el contenido: pídele a la persona usuaria que instale git-lfs y ejecute `git lfs pull`")
    st = os.stat(src)
    if time.time() - st.st_mtime < STABLE_SECONDS:
        raise KError(f"{os.path.basename(src)} se ha modificado hace menos de {STABLE_SECONDS} s: espera a que termine de copiarse y repite")
    sha = C.sha256_file(src)
    dup = next((m["id"] for _, m, _ in iter_docs(home) if m.get("sha256") == sha), None)
    if dup:
        raise KError(f"duplicado exacto de un documento ya ingerido ({dup}): no se ingiere dos veces")
    cobertura, conversion = a.coverage, a.conversion
    if a.md_file:
        with open(a.md_file, encoding="utf-8") as f:
            texto = f.read()
        conversion = conversion or "modelo"
        cobertura = cobertura or "no indicada"
    else:
        r = convert(src)
        if r is None:
            raise KError("no se puede convertir con lo que hay en el equipo: lee el documento, redacta su Markdown y pásalo con --md-file (--conversion modelo --coverage \"…\"); "
                         "para PDF se puede pedir a la persona usuaria que instale `poppler-utils` (pdftotext)", 3)
        texto, conversion, cobertura = r
    if conversion not in ("herramienta", "modelo"):
        raise KError("--conversion: herramienta | modelo", 2)
    sub = _safe_subdir(a.dest_dir)
    did = str(uuid.uuid4())
    nombre = os.path.basename(src)
    dst = os.path.join(home, DOCS, sub, nombre)
    if os.path.exists(dst):
        stem, ext = os.path.splitext(nombre)
        nombre = f"{stem}-{did[:8]}{ext}"
        dst = os.path.join(home, DOCS, sub, nombre)
    mdp = os.path.join(home, MD, sub, nombre + ".md")
    original = os.path.join(sub, nombre) if sub else nombre
    meta = {"id": did, "titulo": a.titulo, "kind": "document", "original": original, "sha256": sha, "mime": mimetypes.guess_type(nombre)[0] or "application/octet-stream",
            "bytes": st.st_size, "conversion": conversion, "cobertura": cobertura, "resumen": a.resumen, "etiquetas": C.csv(a.etiquetas),
            "components": C.norm_components(home, a.components), "fecha": C.today(), "autor": a.autor or C.default_author(home), "state": "active"}
    if a.dry_run:
        return rep.add("DRY", "ingest", f"se ingeriría {nombre} → {os.path.relpath(dst, home)} (+ {os.path.relpath(mdp, home)}; conversión {conversion}, {cobertura})")
    datafiles.atomic_write(mdp, C.dump_fm(C.DOC_FIELDS, meta) + "\n" + texto.strip("\n") + "\n")
    if a.keep_source:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    else:
        _move(home, src, dst)                              # el original solo sale de la cola cuando su Markdown ya está escrito
    rep.add("OK", "ingest", f"{did} ingerido: {os.path.relpath(dst, home)} (Markdown en {os.path.relpath(mdp, home)}; conversión {conversion}, {cobertura})")
    return did


def cmd_reconvert(a, home, rep):
    f = find_doc(home, a.id)
    if not f:
        raise KError(f"no existe el documento '{a.id}'")
    ruta, meta, body = f
    original = os.path.join(home, DOCS, meta["original"])
    if not os.path.isfile(original):
        raise KError(f"falta el original {meta['original']}")
    r = convert(original)
    if r is None:
        raise KError("no hay herramienta para reconvertirlo: para PDF, pídele a la persona usuaria que instale `poppler-utils` (pdftotext)", 3)
    texto, conversion, cobertura = r
    meta.update(conversion=conversion, cobertura=cobertura)
    if a.dry_run:
        return rep.add("DRY", "reconvert", f"{meta['id']}: se regeneraría {ruta} ({conversion}, {cobertura})")
    datafiles.atomic_write(os.path.join(home, ruta), C.dump_fm(C.DOC_FIELDS, meta) + "\n" + texto.strip("\n") + "\n")
    rep.add("OK", "reconvert", f"{meta['id']}: Markdown regenerado con {conversion} ({cobertura})")
