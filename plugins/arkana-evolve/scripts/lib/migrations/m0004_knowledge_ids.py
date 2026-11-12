"""0004 · Conocimiento con identidad UUID y sin catálogo versionado.

Antes, la identidad de una nota era `<topic>-<slug>` y los componentes se guardaban por alias, con un `catalog.json` versionado que producía conflictos. Ahora:
  - cada nota recibe un `id` UUID v4 (inmutable) y conserva el antiguo identificador como `slug` (si llevaba el prefijo `<topic>-`, se quita);
  - `components` pasa de alias a los ids del registro del proyecto (`all` se queda): renombrar un componente ya no obliga a tocar ninguna nota;
  - gana el campo `fuentes` (procedencia: UUID de los documentos de origen), vacío;
  - las notas sueltas fuera de `arkana-knowledge/` se mueven a `arkana-knowledge/<topic>/<slug>.md` (con `git mv` si estaban versionadas);
  - se retira `arkana-knowledge/catalog.json` (sigue en el historial de git): el índice es ahora local y derivado.
No cambia la versión ni el Changelog de ninguna nota. Un alias que no esté en el registro se deja como estaba (`check` lo avisará).
"""
import os
import re
import shutil
import uuid

from arkana_core import datafiles, project
import _legacy

ID = "0004"
TITLE = "conocimiento con UUID, componentes por id y sin catálogo versionado"
SCOPE = ("shared",)

ROOT = "arkana-knowledge"
CATALOG = os.path.join(ROOT, "catalog.json")
TOPICS = ["decision", "lesson", "pending", "contract", "reference", "methodology"]
FIELDS = ["id", "slug", "titulo", "topic", "version", "fecha", "autor", "components", "etiquetas", "fuentes", "resumen", "state"]
LISTS = ("components", "etiquetas", "fuentes")


def _is_uuid(x):
    return project.is_id(x)


def _old_notes(ctx):
    """Notas con frontmatter, `topic` válido y un id que no es UUID (las de ARKANA, estén donde estén)."""
    return [(r, m, b) for r, m, b in _legacy.iter_md(ctx.home) if m.get("topic") in TOPICS and not _is_uuid(m.get("id", ""))]


def _tracked(ctx, rel):
    return ctx.git("ls-files", "--error-unmatch", "--", rel).returncode == 0


def touches(ctx):
    return [ROOT] + [r for r, _, _ in _old_notes(ctx) if not r.startswith(ROOT + os.sep)]


def detect(ctx):
    return bool(_old_notes(ctx) or os.path.isfile(ctx.path(CATALOG)))


def _slug(meta, rel):
    old = str(meta.get("id", "")).strip()
    pre = f"{meta.get('topic')}-"
    s = old[len(pre):] if old.startswith(pre) and len(old) > len(pre) else old
    s = re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")
    return s or re.sub(r"[^a-z0-9-]+", "-", os.path.splitext(os.path.basename(rel))[0].lower()).strip("-") or "nota"


def _dump(meta, body):
    lines = ["---"]
    for k in FIELDS:
        v = meta.get(k, [] if k in LISTS else "")
        if k in LISTS:
            lines.append(f"{k}: [{', '.join(v)}]")
        else:
            s = str(v).replace("\n", " ")
            lines.append(f'{k}: "{s}"' if k in ("titulo", "resumen") else f"{k}: {s}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip("\n") + "\n"


def _components(ctx, reg, comps, rep, rel):
    out = []
    for c in comps:
        k = _legacy.canon(c)
        if k == "all" or _is_uuid(k):
            out.append(k)
        elif reg.id_of(k):
            out.append(reg.id_of(k))
        else:
            out.append(c)
            rep.add("WARN", f"{ID}:{rel}", f"el componente '{c}' no está en el registro del proyecto: se deja como estaba")
    return out


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    reg = project.Registry.load(ctx.home)
    notes = _old_notes(ctx)
    for rel, meta, body in notes:
        slug = _slug(meta, rel)
        nid = str(uuid.uuid4())
        new = dict(meta, id=nid, slug=slug, fuentes=meta.get("fuentes") or [], state=meta.get("state") or "active",
                   components=_components(ctx, reg, meta.get("components", []), rep, rel))
        dest = os.path.join(ROOT, meta["topic"], f"{slug}.md")
        mover = os.path.normpath(rel) != os.path.normpath(dest)
        if mover and os.path.exists(ctx.path(dest)):
            rep.add("WARN", f"{ID}:{rel}", f"ya existe {dest}: la nota se queda en su sitio")
            mover = False
        rep.add(st, f"{ID}:nota", f"{meta['id']} → {nid}" + (f" ({rel} → {dest})" if mover else f" ({rel})"))
        if ctx.dry:
            continue
        datafiles.atomic_write(ctx.path(rel), _dump(new, body))
        if mover:
            os.makedirs(os.path.dirname(ctx.path(dest)), exist_ok=True)
            if _tracked(ctx, rel):
                r = ctx.git("mv", "--", rel, dest)
                if r.returncode != 0:
                    rep.add("FAIL", f"{ID}:{rel}", "git mv falló: " + r.stderr.strip()[:200])
                    return
            else:
                shutil.move(ctx.path(rel), ctx.path(dest))
    cat = ctx.path(CATALOG)
    if os.path.isfile(cat):
        rep.add(st, f"{ID}:catalogo", f"{CATALOG} retirado (el índice ahora es local y derivado)")
        if not ctx.dry:
            if _tracked(ctx, CATALOG):
                ctx.git("rm", "-q", "--", CATALOG)
            if os.path.isfile(cat):
                os.remove(cat)
    if not notes and not os.path.isfile(cat):
        rep.add("OK", ID, "nada que migrar")


def verify(ctx):
    problems = []
    viejas = [r for r, _, _ in _old_notes(ctx)]
    if viejas:
        problems.append("notas con id que no es UUID: " + ", ".join(viejas[:5]))
    if os.path.isfile(ctx.path(CATALOG)):
        problems.append(f"sigue existiendo {CATALOG}")
    return problems
