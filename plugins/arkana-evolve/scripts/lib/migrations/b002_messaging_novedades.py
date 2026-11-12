"""b002 · `novedades/` (formato antiguo de comunicaciones) → almacén de `arkana-messaging`.

Convierte cada JSON de `novedades/` de ARKANA al esquema actual y lo escribe en `.arkana/arkana-messaging/state/messages/`, sin sobrescribir los que
ya están y sin tocar el origen. Los `.md` y los JSON que no se pueden convertir se avisan. Después, `/arkana-messaging:sync` reconstruye el índice.
"""
import datetime
import os
import re

from arkana_core import datafiles, manifest
import _legacy

ID = "b002"
TITLE = "novedades/ → mensajes de arkana-messaging"
SCOPE = ("local",)

RE_ID = re.compile(r"^N\d{6}-\d{4}-[a-z0-9]{4}$")
TYPES = ("notice", "task", "review", "question")
ESTADOS = ("open", "done", "discarded", "deleted", "reconciled")


def _src(ctx):
    return os.path.join(ctx.home, "novedades")


def _store(ctx):
    return os.path.join(ctx.state, "arkana-messaging", "state", "messages")


def _aliases(ctx):
    try:
        return set(manifest.load(ctx.home).aliases())
    except manifest.ManifestError:
        return None


def _iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def convert(d, aliases):
    """Mensaje del formato antiguo → esquema actual; None si no es convertible."""
    de = _legacy.canon(d.get("de", ""))
    if not RE_ID.match(str(d.get("id", ""))) or not d.get("asunto") or d.get("tipo") not in TYPES:
        return None
    if aliases is not None and de not in aliases:
        return None
    para = d.get("para")
    para = [_legacy.canon(p) for p in (para if isinstance(para, list) else [para] if para else [])]
    pool = para or sorted((aliases or set()) - {de})
    para = sorted({p for p in pool if p != de and (aliases is None or p in aliases)})
    if not para:
        return None
    m = dict(d, de=de, para=para)
    if d.get("tipo") == "task" and not (m.get("instrucciones") and m.get("criterios")):
        return None
    est = m.get("estado")
    if m["tipo"] == "notice":
        if est not in (None, "deleted", "reconciled"):
            return None
    elif est not in ESTADOS:
        return None
    hist = m.get("historial") or []
    m["updated"] = (hist[-1].get("fecha") if hist else None) or m.get("fecha") or _iso()
    m.pop("_ruta", None)
    return m


def _scan(ctx):
    """([(origen relativo, mensaje convertido)], [(origen, motivo)])."""
    ok, bad, al = [], [], _aliases(ctx)
    src = _src(ctx)
    for dp, dns, fns in os.walk(src):
        dns.sort()
        for f in sorted(fns):
            rel = os.path.relpath(os.path.join(dp, f), src)
            if f.endswith(".md"):
                if f != "LEEME.md":
                    bad.append((rel, "formato .md antiguo: no se adopta (conviértela a mano o ignórala)"))
                continue
            if not f.endswith(".json"):
                continue
            d = datafiles.read_json(os.path.join(dp, f))
            m = convert(d, al) if isinstance(d, dict) else None
            if m:
                ok.append((rel, m))
            else:
                bad.append((rel, "no convertible: JSON o campos no válidos"))
    return ok, bad


def _pending(ctx):
    return [(rel, m) for rel, m in _scan(ctx)[0] if not os.path.exists(os.path.join(_store(ctx), m["id"] + ".json"))]


def touches(ctx):
    return []


def detect(ctx):
    return os.path.isdir(_src(ctx)) and bool(_pending(ctx))


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    ok, bad = _scan(ctx)
    for rel, why in bad:
        rep.add("WARN", f"{ID}:{rel}", why)
    n_new = n_old = 0
    for rel, m in ok:
        dest = os.path.join(_store(ctx), m["id"] + ".json")
        if os.path.exists(dest):
            n_old += 1
            continue
        n_new += 1
        rep.add(st, f"{ID}:{m['id']}", f"{m['tipo']} {m['de']}→{','.join(m['para'])}: {m['asunto'][:60]}")
        if not ctx.dry:
            datafiles.atomic_write_json(dest, m)
    rep.add(st, ID, f"{n_new} comunicaciones adoptadas, {n_old} ya estaban en el almacén (después: /arkana-messaging:sync)")


def verify(ctx):
    return []
