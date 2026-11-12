"""0003 · Cada componente lleva su `id` (UUID) del registro del proyecto en el manifiesto local.

El registro compartido (`arkana-project.json`, creado por la 0001) es la fuente de la identidad: cada pieza tiene un id inmutable y un alias que se puede
renombrar (`component edit --rename`). Esta migración:
  - da de alta en el registro (cambio compartido) los componentes del manifiesto local que aún no estén en él, con un UUID nuevo;
  - escribe en cada bloque del manifiesto local (ARKANA y componentes) el `id` que el registro asigna a su alias.
No reescribe ningún id existente. Si un bloque lleva un id que el registro asocia a OTRO alias (alguien renombró y empujó), lo avisa y no lo toca: se alinea
con `component edit --alias <el tuyo> --rename <el del registro>`.
"""
import os

from arkana_core import datafiles, project
import _legacy

ID = "0003"
TITLE = "id de cada componente en el manifiesto local (desde el registro del proyecto)"
SCOPE = ("shared", "local")


def _manifest(ctx):
    return os.path.join(ctx.state, "core", "workspace.json")


def _blocks(mf):
    """[(alias, bloque)] de ARKANA y los componentes."""
    return [("arkana", mf.get("arkana") or {})] + [(str(c.get("alias", "")).strip().lower(), c) for c in mf.get("components", []) if isinstance(c, dict)]


def _plan(ctx):
    """(sin_registro, sin_id, desalineados, mf): alias que faltan en el registro, bloques sin id y bloques con un id que el registro asocia a otro alias."""
    mf = datafiles.read_json(_manifest(ctx), {}) or {}
    reg = project.Registry.load(ctx.home)
    sin_registro, sin_id, desalineados = [], [], []
    for alias, b in _blocks(mf):
        if not alias:
            continue
        if reg.id_of(alias) is None and not (b.get("id") and reg.alias_of(b["id"])):
            sin_registro.append(alias)
        bid = b.get("id")
        if not bid:
            sin_id.append(alias)
        elif reg.alias_of(bid) and reg.alias_of(bid) != alias:
            desalineados.append((alias, reg.alias_of(bid)))
    return sin_registro, sin_id, desalineados, mf


def touches(ctx):
    return []


def detect(ctx):
    if not os.path.isfile(_manifest(ctx)):
        return False
    sin_registro, sin_id, _, _ = _plan(ctx)
    return bool(sin_registro or sin_id)


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    sin_registro, sin_id, desalineados, mf = _plan(ctx)
    for alias in sin_registro:
        if not ctx.dry:
            project.add_component(ctx.home, alias)
        rep.add(st, f"{ID}:registro", f"{alias} dado de alta en el registro compartido (UUID nuevo)")
    reg = project.Registry.load(ctx.home)
    n = 0
    for alias, b in _blocks(mf):
        if alias and not b.get("id"):
            cid = reg.id_of(alias) if not ctx.dry else (reg.id_of(alias) or "(nuevo)")
            if cid:
                b["id"] = cid
                n += 1
    for alias, otro in desalineados:
        rep.add("WARN", f"{ID}:{alias}", f"el registro compartido llama {otro} a este componente: alinea con `component edit --alias {alias} --rename {otro}`")
    if n and not ctx.dry:
        datafiles.atomic_write_json(_manifest(ctx), mf)
    rep.add(st, f"{ID}:manifiesto", f"{n} bloques del manifiesto local reciben su id")


def verify(ctx):
    sin_registro, sin_id, _, _ = _plan(ctx)
    return ([f"sin id en el manifiesto: {', '.join(sin_id)}"] if sin_id else []) + ([f"fuera del registro: {', '.join(sin_registro)}"] if sin_registro else [])
