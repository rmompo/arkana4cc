#!/usr/bin/env python3
"""Hooks de arkana-messaging: SessionStart (startup|resume|clear|compact), UserPromptSubmit y Stop. Solo lectura local: sin git ni red.

  hooks.py session-start | prompt-submit | stop        (el evento llega por stdin como JSON)

- Nunca hacen nada dentro de un worker (`ARKANA_WORKER=1`), fuera de un workspace o si el cwd no es de ningún componente.
- Leen el índice local pequeño (state/index.json) y, solo de lo que van a inyectar, el mensaje completo. Nada de git ni de red.
- SessionStart: inyecta los mensajes sin leer y un recordatorio de las tareas, revisiones y preguntas abiertas que tocan a este componente.
- UserPromptSubmit: inyecta solo lo nuevo sin leer.
- Stop: bloquea UNA sola vez por mensaje (y nunca si `stop_hook_active`) y solo si queda sin leer algo de prioridad alta, una tarea o una pregunta.
- Un mensaje está `leído` cuando se inyectó completo o se recuperó con `get --detail`. Si no cabe, se da asunto + id y `get --detail <id>`.
- Cada ejecución escribe un latido en state/sessions/<session_id>.json (lo usa `check`). Cualquier error se traga: un hook nunca rompe la sesión.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))
import messages as M  # noqa: E402
from arkana_core import datafiles  # noqa: E402

MAX_ONE, MAX_TOTAL = 1500, 6000
SESSIONS_KEEP_DAYS = 14


def sid(ev):
    return "".join(c for c in str(ev.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "sin-sesion") if c.isalnum() or c in "-_")[:80]


def heartbeat(store, ev, actor, name, reminded=None, extra=None):
    f = os.path.join(store.dir, "sessions", sid(ev) + ".json")
    cur = datafiles.read_json(f, {}) or {}
    cur.update(ts=M.iso(), event=name, actor=actor)
    cur.update(extra or {})
    if reminded is not None:
        cur["reminded"] = sorted(set(cur.get("reminded", [])) | set(reminded))
    datafiles.atomic_write_json(f, cur)
    return cur


def prune(store):
    import time
    d = os.path.join(store.dir, "sessions")
    lim = time.time() - SESSIONS_KEEP_DAYS * 86400
    for f in os.listdir(d) if os.path.isdir(d) else []:
        p = os.path.join(d, f)
        try:
            if os.path.getmtime(p) < lim:
                os.remove(p)
        except OSError:
            pass


def index(store):
    idx = datafiles.read_json(store.index_file)
    if not isinstance(idx, dict) or "messages" not in idx:
        idx = {"messages": {}}
        if os.path.isdir(store.msgs):
            store.reindex()
            idx = datafiles.read_json(store.index_file, {"messages": {}})
    return idx["messages"]


def unread(idx, store, actor, ws=None):
    seen = M.read_ids(store, actor)
    res = [dict(v, id=i) for i, v in idx.items()
           if i not in seen and v.get("estado") not in M.HIDDEN and v.get("de") != actor and M.is_recipient(v, actor, ws)
           and v.get("vigencia") != "propuesto"]
    return sorted(res, key=lambda m: (m.get("prioridad") != "high", m.get("fecha", ""), m["id"]))


def open_for(idx, actor, ws=None):
    """Tareas, revisiones y preguntas (de una vez) que este componente aún no ha confirmado."""
    return sorted([dict(v, id=i) for i, v in idx.items() if v.get("tipo") != "notice" and v.get("repeticion") != "repeat" and v.get("estado") == "open"
                   and M.is_recipient(v, actor, ws) and actor not in (v.get("confirmaciones") or {})], key=lambda m: m["id"])


def repeat_for(idx, actor, ws=None):
    """Directrices (repeat) vigentes para este componente."""
    return sorted([dict(v, id=i) for i, v in idx.items() if v.get("repeticion") == "repeat" and v.get("vigencia", "vigente") == "vigente"
                   and v.get("estado") not in M.HIDDEN and v.get("de") != actor and M.is_recipient(v, actor, ws)], key=lambda m: m["id"])


def one_line(m):
    return f"{m['id']} · {m['tipo']}{' · ALTA' if m.get('prioridad') == 'high' else ''} · {m['de']}→{','.join(m['para'])} · {M.shorten(m['asunto'], 80)}"


def full_text(store, m):
    d = store.load(m["id"])
    if not d:
        return None
    t = one_line(d)
    if d.get("cuerpo"):
        t += "\n" + d["cuerpo"]
    for lab, k in (("Instrucciones", "instrucciones"), ("Criterios", "criterios")):
        if d.get(k):
            t += f"\n{lab}:\n" + "\n".join(f"- {x}" for x in d[k])
    return t


def render(store, actor, new, reminders, directivas=()):
    """-> (texto|None, ids inyectados completos)."""
    parts, injected, used = [], [], 0
    short = []
    for m in new:
        t = full_text(store, m)
        if t is not None and len(t) <= MAX_ONE and used + len(t) <= MAX_TOTAL:
            parts.append(t)
            injected.append(m["id"])
            used += len(t)
        else:
            short.append(f"- {one_line(m)} → /arkana-messaging:get --detail {m['id']}")
    out = []
    if parts or short:
        out.append(f"[arkana-messaging] Mensajes sin leer para {M.manifest.display(actor)} ({len(new)}). Propón al usuario atenderlos; no los des por hecho "
                   "ni cierres nada sin su confirmación.")
        out += ["", *[f"--- {p}" for p in parts]] if parts else []
        if short:
            out += ["", "Demasiado largos para inyectarlos (consúltalos con get):", *short]
    dirs = [m for m in directivas if m["id"] not in injected]
    if dirs:
        out += ["", f"[arkana-messaging] Directrices vigentes para {M.manifest.display(actor)} (repeat: aplícalas siempre):",
                *[f"- {one_line(m)} → /arkana-messaging:get --detail {m['id']}" for m in dirs]]
    pend = [m for m in reminders if m["id"] not in injected]
    if pend:
        out += ["", f"[arkana-messaging] Siguen abiertos para {M.manifest.display(actor)}:", *[f"- {one_line(m)}" for m in pend]]
    return ("\n".join(out).strip() or None), injected


def summary(idx, store, actor, new, prev_seen, injected, ws=None):
    """Línea para el USUARIO (`systemMessage`): lecturas pendientes, leídas en el último turno y estado de las tareas pedidas por messaging.
    None si a este componente no le ha escrito nadie ni ha pedido nada."""
    seen = set(M.read_ids(store, actor)) | set(injected)
    vis = [(i, v) for i, v in idx.items() if v.get("estado") not in M.HIDDEN]
    mine = [(i, v) for i, v in vis if v.get("de") != actor and M.is_recipient(v, actor, ws) and v.get("vigencia") != "propuesto"]
    asked = [v for _, v in vis if v.get("de") == actor and v.get("tipo") != "notice" and v.get("repeticion") != "repeat"]
    given = sum(1 for _, v in vis if v.get("de") == actor and v.get("repeticion") == "repeat")
    if not mine and not asked and not given:
        return None, None, None
    ids = {i for i, _ in mine}
    leidos = len((seen - set(prev_seen)) & ids)
    tareas = [v for _, v in mine if v.get("tipo") != "notice" and v.get("repeticion") != "repeat"]
    est = [(v.get("confirmaciones") or {}).get(actor) or v.get("estado") for v in tareas]
    ab, he, ds = est.count("open"), est.count("done"), est.count("discarded")
    directrices = sum(1 for _, v in mine if v.get("repeticion") == "repeat")
    parts = [f"{len(new)} sin leer", f"{leidos} leídos en el último turno"]
    if tareas:
        parts.append(f"tareas para ti: {ab} abiertas · {he} hechas" + (f" · {ds} descartadas" if ds else ""))
    if directrices:
        parts.append(f"directrices vigentes para ti: {directrices}")
    if asked:
        parts.append(f"tareas pedidas por ti: {sum(1 for v in asked if v.get('estado') == 'done')} hechas de {len(asked)}")
    if given:
        parts.append(f"directrices dadas por ti: {given}")
    line = f"[ARKANA messaging] {M.manifest.display(actor)}: " + " · ".join(parts) + (" → /arkana-messaging:query --unread" if new else " → /arkana-messaging:get --pending" if ab else "")
    sig = [ab, he, ds, directrices, sum(1 for v in asked if v.get("estado") == "done"), len(asked), given]
    return line, sig, bool(new or leidos)


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))


def main(argv):
    if os.environ.get("ARKANA_WORKER") == "1" or len(argv) < 2:
        return 0
    name = argv[1]
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        home, ws, store, actor = M.ctx(ev.get("cwd") or None)
    except Exception:
        return 0
    try:
        idx = index(store)
        sess = heartbeat(store, ev, actor, name)
        if name in ("session-start", "prompt-submit"):
            event = "SessionStart" if name == "session-start" else "UserPromptSubmit"
            new = unread(idx, store, actor, ws)
            sess_start = name == "session-start"
            text, injected = render(store, actor, new, open_for(idx, actor, ws) if sess_start else [], repeat_for(idx, actor, ws) if sess_start else [])
            prev_seen = sess.get("seen")
            if prev_seen is None:
                prev_seen = M.read_ids(store, actor)
            line, sig, activity = summary(idx, store, actor, new, prev_seen, [m["id"] for m in new if m["id"] in injected], ws)
            if injected:
                M.mark_read(store, actor, injected)
            if name == "session-start":
                prune(store)
            if line and ((name == "session-start" and ev.get("source") not in ("startup", "resume")) or (name == "prompt-submit" and (activity or sig != sess.get("sig")))):
                out = {"systemMessage": line}
            else:
                out = {}
            heartbeat(store, ev, actor, name, extra={"seen": sorted(M.read_ids(store, actor)), "sig": sig})
            if text:
                out["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": text}
            if out:
                emit(out)
        elif name == "stop" and not ev.get("stop_hook_active"):
            reminded = set(sess.get("reminded", []))
            urgent = [m for m in unread(idx, store, actor, ws) if m["id"] not in reminded and (m.get("prioridad") == "high" or m.get("tipo") in ("task", "question"))]
            if urgent:
                heartbeat(store, ev, actor, name, reminded=[m["id"] for m in urgent])
                emit({"decision": "block", "reason": "Hay mensajes sin leer de prioridad alta, tareas o preguntas para este componente. Ejecuta "
                      "/arkana-messaging:get --pending y propón al usuario atenderlos:\n" + "\n".join(f"- {one_line(m)}" for m in urgent)})
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
