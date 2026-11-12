"""b004 · Alias histórico `shared` → `arkana` en los datos persistidos.

Antes solo se aceptaba `shared` como sinónimo al leer; ahora se reescribe donde está guardado, para poder retirar el sinónimo:
mensajes (`de`, `para`, `destinatarios` y las claves de `confirmaciones`, `entregas`, `ejecuciones`), `read/shared.json`, tareas de planes (`repo`),
libro de sesiones (`component`), tareas personales (`componente`), `local.json` (claves de `paths`, `git`, `tool_paths`) y `components` de las notas.
Borra el índice derivado de mensajes (se reconstruye solo).
"""
import glob
import os

from arkana_core import datafiles
import _legacy

ID = "b004"
TITLE = "alias histórico shared → arkana en los datos"
SCOPE = ("local", "shared")
OLD = "shared"


def _fix_list(v):
    if not isinstance(v, list):
        return v, False
    out, ch = [], False
    for x in v:
        y = _legacy.canon(x) if isinstance(x, str) and x == OLD else x
        ch = ch or y != x
        if y not in out:
            out.append(y)
    return out, ch


def _fix_keys(d):
    if not isinstance(d, dict) or OLD not in d:
        return d, False
    d = dict(d)
    val = d.pop(OLD)
    d.setdefault("arkana", val)
    return d, True


def _fix_message(m):
    ch = False
    for k in ("de",):
        if m.get(k) == OLD:
            m[k], ch = "arkana", True
    for k in ("para", "destinatarios"):
        if k in m:
            m[k], c = _fix_list(m[k]); ch = ch or c
    for k in ("confirmaciones", "entregas", "ejecuciones"):
        if k in m:
            m[k], c = _fix_keys(m[k]); ch = ch or c
    return m, ch


def _fix_task(t):
    if t.get("repo") == OLD:
        t["repo"] = "arkana"
        return t, True
    return t, False


def _fix_plan(p):
    ch = False
    if isinstance(p.get("ramas"), dict):
        p["ramas"], c = _fix_keys(p["ramas"]); ch = ch or c
    return p, ch


def _fix_ledger(d):
    ch = False
    if d.get("component") == OLD:
        d["component"], ch = "arkana", True
    if isinstance(d.get("componentes"), list):
        d["componentes"], c = _fix_list(d["componentes"]); ch = ch or c
    return d, ch


def _fix_todos(d):
    ch = False
    for t in d.get("tareas", []):
        if isinstance(t, dict) and t.get("componente") == OLD:
            t["componente"], ch = "arkana", True
    return d, ch


def _fix_local(d):
    ch = False
    for k in ("paths", "git", "tool_paths"):
        if k in d:
            d[k], c = _fix_keys(d[k]); ch = ch or c
    return d, ch


def _json_targets(ctx):
    s = ctx.state
    g = lambda pat: sorted(glob.glob(os.path.join(s, pat)))
    return ([(f, _fix_message) for f in g("arkana-messaging/state/messages/*.json")]
            + [(f, _fix_task) for f in g("arkana-agentic/state/planes/*/tareas/*.json")]
            + [(f, _fix_plan) for f in g("arkana-agentic/state/planes/*/plan.json")]
            + [(f, _fix_ledger) for f in g("arkana-agentic/data/ledger/*/*.json")]
            + [(f, _fix_todos) for f in g("arkana-todo/todos.json")]
            + [(f, _fix_local) for f in g("arkana-workspace/local.json")])


def _changes(ctx):
    res = []
    for f, fn in _json_targets(ctx):
        d = datafiles.read_json(f)
        if isinstance(d, dict):
            new, ch = fn(d)
            if ch:
                res.append((f, new))
    return res


def _read_files(ctx):
    return sorted(glob.glob(os.path.join(ctx.state, "arkana-messaging", "state", "read", OLD + ".json")))


def _note_changes(ctx):
    res = []
    for ruta, meta, body in _legacy.iter_md(ctx.home):
        comps = meta.get("components") or meta.get("modulos") or []
        if OLD in comps:
            res.append(ruta)
    return res


def touches(ctx):
    return _note_changes(ctx)


def detect(ctx):
    return bool(_changes(ctx) or _read_files(ctx) or _note_changes(ctx))


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    n = 0
    for f, new in _changes(ctx):
        n += 1
        if not ctx.dry:
            datafiles.atomic_write_json(f, new)
    rep.add(st, f"{ID}:datos", f"{n} ficheros de .arkana con el alias reescrito")
    for f in _read_files(ctx):
        dest = os.path.join(os.path.dirname(f), "arkana.json")
        if not ctx.dry:
            cur = datafiles.read_json(dest, {}) or {}
            old = datafiles.read_json(f, {}) or {}
            ids = dict(old.get("ids", {}))
            ids.update(cur.get("ids", {}))
            datafiles.atomic_write_json(dest, {"schema_version": old.get("schema_version", 1), "ids": ids})
            os.remove(f)
        rep.add(st, f"{ID}:read", "read/shared.json → read/arkana.json")
    idx = os.path.join(ctx.state, "arkana-messaging", "state", "index.json")
    if os.path.isfile(idx) and (n or _read_files(ctx)):
        if not ctx.dry:
            os.remove(idx)
        rep.add(st, f"{ID}:indice", "índice de mensajes derivado eliminado (se reconstruye solo)")
    for ruta in _note_changes(ctx):
        if not ctx.dry:
            p = ctx.path(ruta)
            with open(p, encoding="utf-8") as fh:
                meta, body = _legacy.split_note(fh.read())
            key = "components" if "components" in meta else "modulos"
            comps, _ = _fix_list(meta[key])
            text = open(p, encoding="utf-8").read()
            import re
            text = re.sub(r"(?m)^(%s:\s*)\[.*\]\s*$" % key, lambda m: m.group(1) + "[" + ", ".join(comps) + "]", text, count=1)
            datafiles.atomic_write(p, text)
        rep.add(st, f"{ID}:{ruta}", "components: shared → arkana")


def verify(ctx):
    return [f"queda el alias shared en {os.path.relpath(f, ctx.home)}" for f, _ in _changes(ctx)][:5]
