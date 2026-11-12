"""b003 · Formato antiguo del conocimiento → notas con `topic`/`components` y `## Changelog`.

Antes: `conocimiento/<tipo>/x.md`, `catalogo.json`, historial en `conocimiento/.historial/<id>/v*.md`, frontmatter con `tipo` y `modulos`.
Ahora: `arkana-knowledge/<topic>/x.md` (con `git mv` si estaba versionada), frontmatter con `topic` y `components`, una línea de Changelog por versión.
Los ids no cambian. Las notas que viven fuera de `conocimiento/` (p. ej. las de referencia de la raíz) se quedan donde están y solo se reescriben.
Se borran `conocimiento/.historial/` y `catalogo.json` (siguen en el historial de git). El catálogo lo reconstruyen las migraciones posteriores.
"""
import datetime
import os
import re
import shutil

import _legacy

ID = "b003"
TITLE = "formato antiguo del conocimiento (conocimiento/ → arkana-knowledge/)"
SCOPE = ("shared",)


def _old_notes(ctx):
    skip = _legacy.SKIP_DIRS - {"conocimiento", ".historial"}
    return [(r, m, b) for r, m, b in _legacy.iter_md(ctx.home, skip) if "topic" not in m]


def _leftovers(ctx):
    res = []
    if os.path.isdir(ctx.path("conocimiento")):
        res.append("conocimiento/")
    if os.path.isfile(ctx.path("catalogo.json")):
        res.append("catalogo.json")
    return res


def touches(ctx):
    return ["conocimiento", "catalogo.json", "arkana-knowledge"]


def detect(ctx):
    return bool(_leftovers(ctx) or _old_notes(ctx))


def _tracked(ctx, rel):
    return ctx.git("ls-files", "--error-unmatch", "--", rel).returncode == 0


def _history(ctx, nid):
    d = ctx.path("conocimiento", ".historial", nid)
    res = []
    for f in sorted(os.listdir(d), key=lambda x: [int(p) for p in re.findall(r"\d+", x)]) if os.path.isdir(d) else []:
        try:
            with open(os.path.join(d, f), encoding="utf-8") as fh:
                m, _ = _legacy.split_note(fh.read())
        except OSError:
            continue
        if m and m.get("version"):
            res.append(_legacy.entry(m["version"], m.get("fecha", "?"), m.get("autor", "?"), m.get("resumen", "versión archivada")))
    return res


def _move(ctx, src, dst):
    os.makedirs(os.path.dirname(ctx.path(dst)), exist_ok=True)
    if _tracked(ctx, src) and ctx.git("mv", "--", src, dst).returncode == 0:
        return
    shutil.move(ctx.path(src), ctx.path(dst))


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    today = datetime.date.today().isoformat()
    n = 0
    for ruta, meta, body in _old_notes(ctx):
        nid = meta["id"]
        tipo = meta.get("tipo") or "reference"
        comps = list(meta.get("modulos", [])) or ["all"]
        new = {"id": nid, "titulo": meta.get("titulo", nid), "topic": tipo if tipo in _legacy.LEGACY_TOPICS else "reference",
               "version": meta.get("version", "1.0"), "fecha": meta.get("fecha", today), "autor": meta.get("autor", "desconocido"),
               "components": comps, "etiquetas": meta.get("etiquetas", []), "resumen": meta.get("resumen", ""), "state": "active"}
        main, entries = _legacy.split_changelog(body)
        if not entries:
            entries = _history(ctx, nid) + [_legacy.entry(new["version"], new["fecha"], new["autor"], new["resumen"] or "versión actual")]
        dest = ruta
        if ruta.startswith("conocimiento" + os.sep):
            dest = os.path.join("arkana-knowledge", new["topic"], os.path.basename(ruta))
        if not ctx.dry:
            if dest != ruta:
                _move(ctx, ruta, dest)
            from arkana_core import datafiles
            datafiles.atomic_write(ctx.path(dest), _legacy.dump_note(new, main, entries))
        rep.add(st, f"{ID}:{nid}", f"{ruta} → {dest} ({len(entries)} entradas de Changelog; componentes {', '.join(comps)})")
        n += 1
    for d in ("conocimiento/.historial", "catalogo.json"):
        full = ctx.path(d)
        if not os.path.exists(full):
            continue
        if not ctx.dry:
            if _tracked(ctx, d) or ctx.git("ls-files", "--", d).stdout.strip():
                ctx.git("rm", "-rq", "--", d)
            if os.path.isdir(full):
                shutil.rmtree(full, ignore_errors=True)
            elif os.path.exists(full):
                os.remove(full)
        rep.add(st, f"{ID}:borrar-{d}", "el historial pasó al Changelog de cada nota (git conserva los ficheros antiguos)" if "historial" in d else "sustituido por el catálogo nuevo")
    cd = ctx.path("conocimiento")
    if not ctx.dry and os.path.isdir(cd) and not any(f for _, _, fs in os.walk(cd) for f in fs):
        shutil.rmtree(cd, ignore_errors=True)
    rep.add(st, ID, f"{n} notas {'se migrarían' if ctx.dry else 'migradas'}")


def verify(ctx):
    return [f"queda formato antiguo: {x}" for x in _leftovers(ctx)] + ([f"{len(_old_notes(ctx))} notas con tipo/modulos"] if _old_notes(ctx) else [])
