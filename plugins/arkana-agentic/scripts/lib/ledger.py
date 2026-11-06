#!/usr/bin/env python3
"""Libro de planes y sesiones de arkana-agentic: solo METADATOS (nunca contenido de conversaciones ni de ficheros).

  data/ledger/plans/<plan>.json      id, fechas, estado, componentes, ramas e integración, gasto total y por tarea/intento
  data/ledger/sessions/<sid>.json    id, inicio/fin, componente, plan, duración, tokens, coste y de dónde sale (`cost_source`)

El **coste real de una sesión lo escribe la statusline** (es lo único que lo recibe): `.arkana/arkana-statusline/state/sessions/<sid>.json`
(`{"session_id","cost_usd","ts"}`; su única escritora) o, mientras la statusline antigua siga instalada, `state/sesiones/<sid>` (`<ts> <coste>`).
Los hooks solo LEEN ese fichero. Los tokens salen del transcript (`message.usage` de cada mensaje del asistente) y la duración, de los hooks.
Sin ese fichero el coste queda vacío (`null`): no se estima nunca.

Retención: pasados `ledger_retention_days` (política; 90 por defecto) se conservan los apuntes (totales) y se purga el detalle (desglose por tarea,
intento y tipo de token), y se marca `detalle_purgado`.

Uso (hooks):  ledger.py hook session-start|session-end   (JSON del evento por stdin; no hace nada en un worker ni fuera de un workspace)
"""
import datetime
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
import paths  # noqa: E402
import state  # noqa: E402
from arkana_core import datafiles, locate, manifest  # noqa: E402

SCHEMA = 1


def _sid(sid):
    return "".join(c for c in str(sid or "") if c.isalnum() or c in "-_")[:80]


def plans_dir():
    return os.path.join(state.ledger_dir(), "plans")


def sessions_dir():
    return os.path.join(state.ledger_dir(), "sessions")


# ---------- coste y tokens ----------
def statusline_cost(sid):
    """(coste, ts) leído de lo que escribe la statusline, o (None, None). Nunca estima."""
    sid = _sid(sid)
    if not sid:
        return None, None
    new = datafiles.read_json(os.path.join(paths.plugins_dir(), "arkana-statusline", "state", "sessions", sid + ".json"))
    if isinstance(new, dict) and isinstance(new.get("cost_usd"), (int, float)):
        return float(new["cost_usd"]), new.get("ts")
    try:
        with open(os.path.join(state.sessions_dir(), sid), encoding="utf-8") as f:
            ts, coste = f.read().split()[:2]
        return float(coste), int(float(ts))
    except (OSError, ValueError):
        return None, None


def transcript_tokens(path):
    """Suma de `message.usage` de los mensajes del asistente del transcript. None si no hay transcript legible."""
    tot = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}
    try:
        with open(path, encoding="utf-8") as f:
            for l in f:
                try:
                    u = (json.loads(l).get("message") or {}).get("usage")
                except ValueError:
                    continue
                if isinstance(u, dict):
                    tot["input"] += int(u.get("input_tokens") or 0)
                    tot["output"] += int(u.get("output_tokens") or 0)
                    tot["cache_creation"] += int(u.get("cache_creation_input_tokens") or 0)
                    tot["cache_read"] += int(u.get("cache_read_input_tokens") or 0)
    except OSError:
        return None
    return tot


# ---------- planes ----------
def plan_record(pid, plan_dir=None):
    d = plan_dir or state.plan_dir(pid)
    plan = state.load_json(os.path.join(d, "plan.json"))
    tareas = []
    td = os.path.join(d, "tareas")
    for f in sorted(os.listdir(td)) if os.path.isdir(td) else []:
        try:
            t = state.load_json(os.path.join(td, f))
        except (OSError, ValueError):
            continue
        intentos, gasto = [], 0.0
        for n in range(1, int(t.get("intentos") or 0) + 1):
            try:
                raw = state.load_json(os.path.join(d, "informes", f"{t['id']}.{n}.raw.json"))
            except (OSError, ValueError):
                continue
            c = float(((raw.get("salida_json") or {}).get("total_cost_usd")) or 0)
            gasto += c
            intentos.append({"intento": n, "gasto_usd": round(c, 4), "duracion_s": raw.get("duracion_s")})
        tareas.append({"id": t["id"], "repo": t.get("repo"), "estado": t.get("estado"), "gasto_usd": round(gasto, 4), "intentos": intentos})
    hist = plan.get("historial") or []
    terminado = hist[-1].get("fecha") if hist and plan.get("estado") in state.TERMINAL_PLAN_STATES else None
    return {"schema_version": SCHEMA, "id": plan.get("id", pid), "asunto": plan.get("asunto", ""), "estado": plan.get("estado"),
            "creado": plan.get("creado"), "aprobado": plan.get("aprobado"), "terminado": terminado,
            "componentes": sorted({t["repo"] for t in tareas if t.get("repo")}),
            "ramas": {k: {x: v.get(x) for x in ("nombre", "original", "decision", "integrado_hasta") if v.get(x)} for k, v in (plan.get("ramas") or {}).items()},
            "gasto_usd": round(float((plan.get("contadores") or {}).get("gasto_usd", 0)), 4), "tareas": tareas}


def snapshot_plan(pid, plan_dir=None):
    rec = plan_record(pid, plan_dir)
    os.makedirs(plans_dir(), exist_ok=True)
    datafiles.atomic_write_json(os.path.join(plans_dir(), rec["id"] + ".json"), rec)
    return rec


def all_plans():
    """Registros de todos los planes: los vivos (leídos ahora de state/planes), los archivados y, si ya no existen, el apunte del libro."""
    res = {}
    for pid in sorted(os.listdir(plans_dir())) if os.path.isdir(plans_dir()) else []:
        r = datafiles.read_json(os.path.join(plans_dir(), pid))
        if isinstance(r, dict) and r.get("id"):
            res[r["id"]] = r
    for base in (state.planes_dir(), state.archive_dir()):
        for pid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            try:
                if not (res.get(pid) or {}).get("detalle_purgado"):
                    res[pid] = plan_record(pid, os.path.join(base, pid))
            except (OSError, ValueError, KeyError):
                continue
    return res


# ---------- sesiones ----------
def session_file(sid):
    return os.path.join(sessions_dir(), _sid(sid) + ".json")


def all_sessions():
    res = {}
    for f in sorted(os.listdir(sessions_dir())) if os.path.isdir(sessions_dir()) else []:
        r = datafiles.read_json(os.path.join(sessions_dir(), f))
        if isinstance(r, dict) and r.get("session_id"):
            if r.get("ended") is None or r.get("cost_usd") is None:             # sesión abierta o sin coste todavía: se refresca con lo último de la statusline
                c, _ = statusline_cost(r["session_id"])
                if c is not None:
                    r = dict(r, cost_usd=round(c, 4), cost_source="statusline")
            res[r["session_id"]] = r
    # sesiones que la statusline vio pero que aun no tienen apunte en el libro (anteriores a los hooks, o sin SessionEnd): solo coste y fecha
    seen = {}
    for base, new in ((os.path.join(paths.plugins_dir(), "arkana-statusline", "state", "sessions"), True), (state.sessions_dir(), False)):
        for f in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            sid = f[:-5] if new and f.endswith(".json") else f
            if sid in res or sid in seen or _sid(sid) != sid:
                continue
            c, ts = statusline_cost(sid)
            if c is not None:
                when = datetime.datetime.fromtimestamp(float(ts), datetime.timezone.utc) if isinstance(ts, (int, float)) else None
                seen[sid] = {"schema_version": SCHEMA, "session_id": sid, "started": _iso(when) if when else None, "ended": None, "component": None, "plan": None,
                             "cost_usd": round(c, 4), "cost_source": "statusline", "sin_apunte": True}
    res.update(seen)
    return res


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt=None):
    return (dt or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts):
    try:
        return datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return None


def active_plan_of(sid):
    """Plan que gobierna esta sesión (linea.json guarda el session_id), o None."""
    try:
        l = state.load_json(os.path.join(state.run_dir(), "linea.json"))
    except (OSError, ValueError):
        return None
    return l.get("plan") if l.get("session_id") == sid else None


def record_session(ev, phase):
    sid = _sid(ev.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if not sid:
        return None
    f = session_file(sid)
    cur = datafiles.read_json(f, {}) or {}
    cwd = ev.get("cwd") or os.getcwd()
    comp = cur.get("component")
    if not comp:
        try:
            comp = manifest.load(locate.find_home(cwd)).owner_of(cwd)
        except Exception:
            comp = None
    rec = dict({"schema_version": SCHEMA, "session_id": sid, "started": _iso(), "ended": None, "component": comp, "plan": None,
                "duration_s": None, "tokens": None, "cost_usd": None, "cost_source": None}, **cur)
    rec["component"] = rec.get("component") or comp
    plan = active_plan_of(sid)
    if plan:
        rec["plan"] = plan
        try:
            snapshot_plan(plan)
        except (OSError, ValueError, KeyError):
            pass
    if phase == "end":
        t0 = _parse(rec.get("started"))
        rec["ended"] = _iso()
        rec["duration_s"] = int((_now() - t0).total_seconds()) if t0 else None
        if ev.get("transcript_path"):
            rec["tokens"] = transcript_tokens(ev["transcript_path"])
        c, _ = statusline_cost(sid)
        if c is not None:
            rec["cost_usd"], rec["cost_source"] = round(c, 4), "statusline"
        rec["end_reason"] = ev.get("reason")
    os.makedirs(sessions_dir(), exist_ok=True)
    datafiles.atomic_write_json(f, rec)
    return rec


# ---------- retención ----------
def purge(days=None, dry=False):
    """Conserva los apuntes y purga el detalle de lo anterior a `days`. -> {planes, sesiones} purgados."""
    days = days if days is not None else state.load_policy()["limites"].get("ledger_retention_days", 90)
    lim = _now() - datetime.timedelta(days=days)
    n = {"planes": 0, "sesiones": 0}
    for d, kind in ((plans_dir(), "planes"), (sessions_dir(), "sesiones")):
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            p = os.path.join(d, f)
            r = datafiles.read_json(p)
            if not isinstance(r, dict) or r.get("detalle_purgado"):
                continue
            when = _parse(r.get("terminado") or r.get("creado") if kind == "planes" else r.get("ended") or r.get("started"))
            if when is None or when >= lim:
                continue
            n[kind] += 1
            if dry:
                continue
            if kind == "planes":
                r["tareas"] = [{"id": t["id"], "repo": t.get("repo"), "gasto_usd": t.get("gasto_usd")} for t in r.get("tareas", [])]
            elif r.get("tokens"):
                r["tokens"] = {"total": sum(r["tokens"].values())}
            r["detalle_purgado"] = True
            datafiles.atomic_write_json(p, r)
    return n


def purge_daily():
    """Una vez al día como mucho (marca en el propio libro); nunca falla."""
    mark = os.path.join(state.ledger_dir(), ".purga")
    try:
        if os.path.exists(mark) and time.time() - os.path.getmtime(mark) < 86400:
            return
        purge()
        os.makedirs(state.ledger_dir(), exist_ok=True)
        with open(mark, "w") as f:
            f.write(_iso())
    except Exception:
        pass


# ---------- hooks ----------
def hook_main(argv):
    if os.environ.get("ARKANA_WORKER") == "1" or len(argv) < 2:
        return 0
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        home = locate.find_home(ev.get("cwd") or None)
        if not home:
            return 0
        os.environ.setdefault("ARKANA_HOME", home)
        record_session(ev, "end" if argv[1] == "session-end" else "start")
        if argv[1] == "session-end":
            purge_daily()
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "hook":
        sys.exit(hook_main(sys.argv[1:]))
