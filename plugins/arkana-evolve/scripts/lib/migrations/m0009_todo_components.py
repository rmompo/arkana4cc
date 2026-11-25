"""0009 · Layout 9: el componente de una tarea de `arkana-todo` es siempre una lista.

Una tarea puede afectar a varios componentes (`--component M3WA,M3MF`), así que `componente` pasa de ser un texto (`"api"`, `"*"`) a una lista (`["api"]`, `["m3wa", "m3mf"]`,
`["*"]` para todos). La migración reescribe `.arkana/arkana-todo/todos.json` (local, por máquina): un texto pasa a lista de un elemento, y `all`, vacío o sin valor, a `["*"]`.
No toca el resto de campos ni el orden. Las versiones nuevas del plugin ya leen ambas formas, pero una instalación que solo conoce el texto falla al leer una lista: por eso el sello
(layout 9) avisa de actualizar el plugin.
"""
import os

from arkana_core import datafiles

ID = "0009"
TITLE = "tareas: componente como lista (varios componentes por tarea; * = todos)"
SCOPE = ("local",)
LAYOUT = 9


def _file(ctx):
    return os.path.join(ctx.state, "arkana-todo", "todos.json")


def _data(ctx):
    d = datafiles.read_json(_file(ctx), None)
    return d if isinstance(d, dict) and isinstance(d.get("tareas"), list) else None


def _necesita(t):
    return isinstance(t, dict) and "componente" in t and not isinstance(t["componente"], list)


def _lista(valor):
    v = str(valor).strip().lower() if isinstance(valor, str) else ""
    return ["*"] if v in ("", "all", "none") else [v]


def touches(ctx):
    return []                                   # local: lo cubre la copia de seguridad de `.arkana`; nada versionado


def detect(ctx):
    d = _data(ctx)
    return bool(d) and any(_necesita(t) for t in d["tareas"])


def apply(ctx, rep):
    d = _data(ctx)
    n = 0
    for t in d["tareas"]:
        if _necesita(t):
            t["componente"] = _lista(t["componente"])
            n += 1
    if n and not ctx.dry:
        datafiles.atomic_write_json(_file(ctx), d)
    rep.add("DRY" if ctx.dry else "OK", f"{ID}:tareas", f"{n} tareas pasan a componente como lista")


def verify(ctx):
    d = _data(ctx)
    malas = [str(t.get("id", "?")) for t in (d or {}).get("tareas", []) if _necesita(t)]
    return [f"tareas con el componente como texto: {', '.join(malas[:5])}"] if malas else []
