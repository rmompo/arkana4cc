"""0006 · Layout 6: las tareas de `arkana-todo` usan el modelo de estados nuevo.

Antes: estado `open|done|deleted`, prioridad `high|normal|low` y componente `all` o vacío. Ahora: estado `pending|in-progress|paused|blocked|done|rejected|removed`,
prioridad `critical|high|medium|low` y componente `*` (todos) o el alias. La migración reescribe `.arkana/arkana-todo/todos.json` (local, por máquina):
`open`→`pending`, `deleted`→`removed`, `normal`→`medium`, `all`/vacío→`*`. No toca el resto de campos ni el orden de las tareas. Las versiones nuevas del plugin ya leen los
valores antiguos sin migrar, pero una instalación que solo conoce el modelo anterior no entiende los nuevos: por eso el sello (layout 6) avisa de actualizar el plugin.
"""
import os

from arkana_core import datafiles

ID = "0006"
TITLE = "tareas: estados pending…removed, prioridad critical…low y componente * (desde open, deleted, normal y all)"
SCOPE = ("local",)
LAYOUT = 6
STATE = {"open": "pending", "deleted": "removed"}
PRIORITY = {"normal": "medium"}


def _file(ctx):
    return os.path.join(ctx.state, "arkana-todo", "todos.json")


def _legacy(t):
    return isinstance(t, dict) and (t.get("estado") in STATE or t.get("prioridad") in PRIORITY or ("componente" in t and t["componente"] in ("all", "", None)))


def _data(ctx):
    d = datafiles.read_json(_file(ctx), None)
    return d if isinstance(d, dict) and isinstance(d.get("tareas"), list) else None


def touches(ctx):
    return []                                   # local: lo cubre la copia de seguridad de `.arkana`; nada versionado


def detect(ctx):
    d = _data(ctx)
    return bool(d) and any(_legacy(t) for t in d["tareas"])


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    d = _data(ctx)
    n = 0
    for t in d["tareas"]:
        if not _legacy(t):
            continue
        t["estado"] = STATE.get(t.get("estado"), t.get("estado"))
        t["prioridad"] = PRIORITY.get(t.get("prioridad"), t.get("prioridad"))
        if "componente" in t and t["componente"] in ("all", "", None):
            t["componente"] = "*"
        n += 1
    if n and not ctx.dry:
        datafiles.atomic_write_json(_file(ctx), d)
    rep.add(st, f"{ID}:tareas", f"{n} tareas pasan al modelo nuevo (estado, prioridad y componente)")


def verify(ctx):
    d = _data(ctx)
    malas = [str(t.get("id", "?")) for t in (d or {}).get("tareas", []) if _legacy(t)]
    return [f"tareas con valores antiguos: {', '.join(malas[:5])}"] if malas else []
