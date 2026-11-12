"""b001 · Layout de `.arkana/arkana-agentic/`: de «todo junto» a `config/ state/ data/`.

Antes:  planes/ run/ sesiones/ actual politica.json comandos-permitidos.json
Ahora:  config/{politica.json, comandos-permitidos.json}   state/{planes, run, sesiones, actual}   data/{ledger, archive}

Mueve lo antiguo sin pisar lo nuevo, se niega con un plan activo o un worker vivo y copia a `data/archive/` los planes de `orquestacion/archivo/` de
ARKANA (no borra el origen). La copia de seguridad de `.arkana/` la hace el motor antes de aplicar.
"""
import json
import os
import shutil

ID = "b001"
TITLE = "layout de arkana-agentic (config/ state/ data/)"
SCOPE = ("local",)

MOVES = [("planes", "state/planes"), ("run", "state/run"), ("sesiones", "state/sesiones"), ("actual", "state/actual"),
         ("politica.json", "config/politica.json"), ("comandos-permitidos.json", "config/comandos-permitidos.json")]
ACTIVE = {"en_ejecucion", "pausado", "esperando_usuario"}


def _base(ctx):
    return os.path.join(ctx.state, "arkana-agentic")


def _archive_src(ctx):
    return os.path.join(ctx.home, "orquestacion", "archivo")


def _moves(ctx):
    b = _base(ctx)
    return [(o, n) for o, n in MOVES if os.path.lexists(os.path.join(b, o)) and not os.path.lexists(os.path.join(b, n))]


def _conflicts(ctx):
    b = _base(ctx)
    return [(o, n) for o, n in MOVES if os.path.lexists(os.path.join(b, o)) and os.path.lexists(os.path.join(b, n))]


def _archives(ctx):
    src = _archive_src(ctx)
    return [p for p in (sorted(os.listdir(src)) if os.path.isdir(src) else []) if not os.path.exists(os.path.join(_base(ctx), "data", "archive", p))]


def touches(ctx):
    return []


def detect(ctx):
    return bool(_moves(ctx) or _archives(ctx))


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _blockers(ctx):
    res, b = [], _base(ctx)
    pd = os.path.join(b, "planes")
    for pid in sorted(os.listdir(pd)) if os.path.isdir(pd) else []:
        est = (_read(os.path.join(pd, pid, "plan.json")) or {}).get("estado")
        if est in ACTIVE:
            res.append(f"el plan {pid} está {est}")
    w = _read(os.path.join(b, "run", "worker.json")) or {}
    try:
        pid = int(w.get("pid", 0))
        if pid > 0:
            os.kill(pid, 0)
            res.append(f"hay un worker vivo (pid {pid})")
    except (OSError, ValueError, TypeError):
        pass
    return res


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    bl = _blockers(ctx)
    if bl:
        rep.add("FAIL", ID, "no se migra ahora: " + "; ".join(bl))
        return
    b = _base(ctx)
    for o, n in _moves(ctx):
        if not ctx.dry:
            os.makedirs(os.path.dirname(os.path.join(b, n)), exist_ok=True)
            shutil.move(os.path.join(b, o), os.path.join(b, n))
        rep.add(st, f"{ID}:{o}", f"{o} → {n}")
    for o, n in _conflicts(ctx):
        rep.add("WARN", f"{ID}:{o}", f"existen {o} y {n}: no se pisa; revisa a mano")
    for pid in _archives(ctx):
        if not ctx.dry:
            os.makedirs(os.path.join(b, "data"), exist_ok=True)
            shutil.copytree(os.path.join(_archive_src(ctx), pid), os.path.join(b, "data", "archive", pid))
        rep.add(st, f"{ID}:archivo-{pid}", "plan archivado copiado a data/archive (el origen en ARKANA no se borra)")
    if not ctx.dry and os.path.isdir(b):
        for d in ("config", "state", "data"):
            os.makedirs(os.path.join(b, d), exist_ok=True)
            os.chmod(os.path.join(b, d), 0o700)


def verify(ctx):
    return [f"existen {o} y {n}: revisa a mano" for o, n in _conflicts(ctx)]
