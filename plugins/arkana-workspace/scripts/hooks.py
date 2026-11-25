#!/usr/bin/env python3
"""Hook de estado de Arkana al abrir, reanudar, limpiar o compactar una sesión (SessionStart: startup|resume|clear|compact). Solo local: git local, sin red.

Hace dos cosas. (1) Muestra al USUARIO (`systemMessage`) un BRIEF corto, por este orden: QUICK START (comandos útiles según lo pendiente),
MESSAGING (por componente: tareas pendientes, directrices repeat y avisos sin leer), TODO (tareas activas de arkana-todo, hasta 5), NOTES (notas activas de arkana-note, hasta 5), GIT (componentes con cambios o commits sin subir) y ORCHESTRATION (plan activo de arkana-agentic, con su coste).
(2) Inyecta en el contexto del MODELO (`additionalContext`) las directrices de la pieza cuya carpeta contiene el cwd (ver `lib/directives.py`: convención de commits,
reglas comunes y, si existe, `ARKANA.local.md`): así no hace falta ningún fichero de instrucciones en los repos de trabajo.
No hace nada dentro de un worker (`ARKANA_WORKER=1`) ni fuera de un workspace. Nunca falla.
"""
import concurrent.futures
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_core"))
sys.path.insert(0, os.path.join(HERE, "lib"))
from arkana_core import datafiles, locate, manifest, project  # noqa: E402
import directives  # noqa: E402
import gitstate  # noqa: E402


def git_pending(ws, aliases):
    """[(alias, rama)] de los componentes con cambios o commits sin subir, en el orden del manifiesto."""
    def one(a):
        p = ws.path(a)
        return a, (gitstate.state(p, ws.flags(a)["watch"], ws.flags(a)["ref"] or None) if os.path.isdir(p) else None)
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(aliases) or 1)) as ex:
        res = list(ex.map(one, aliases))
    return [(manifest.display(a), s["branch"]) for a, s in res if s is not None and not s["clean"]]


def active_plan(st):
    base = os.path.join(st, "arkana-agentic", "state")
    try:
        with open(os.path.join(base, "actual"), encoding="utf-8") as f:
            pid = f.read().strip()
    except OSError:
        return None
    pl = datafiles.read_json(os.path.join(base, "planes", pid, "plan.json"))
    if not isinstance(pl, dict) or pl.get("estado") in ("completado", "archivado", "cancelado"):
        return None
    c = pl.get("contadores") or {}
    gasto = c.get("gasto_usd")
    return f"plan {pid} ({pl.get('estado')}{', ' + format(gasto, '.2f') + ' USD' if isinstance(gasto, (int, float)) else ''})"


def is_recipient(m, actor):
    """Como messages.is_recipient sin importar messaging: `destinatarios` (o `para` en mensajes antiguos); un repeat a `all` es de alcance vivo."""
    if m.get("repeticion") == "repeat" and "all" in (m.get("para") or []):
        return actor != m.get("de")
    return actor in (m.get("destinatarios") or m.get("para") or [])


def message_counts(st, actor):
    """(tareas, repeat, avisos sin leer) de `actor`: tareas = task/review/question de una vez, abiertas, dirigidas a él y sin confirmar;
    repeat = directrices permanentes vigentes (no propuestas) que le alcanzan; avisos = notices sin leer. Sin borrados ni reconciliados ni propios."""
    idx = (datafiles.read_json(os.path.join(st, "arkana-messaging", "state", "index.json"), {}) or {}).get("messages", {})
    seen = (datafiles.read_json(os.path.join(st, "arkana-messaging", "state", "read", f"{actor}.json"), {}) or {}).get("ids", {})
    tasks = reps = notes = 0
    for i, m in idx.items():
        if m.get("estado") in ("deleted", "reconciled") or m.get("de") == actor or not is_recipient(m, actor):
            continue
        if m.get("repeticion") == "repeat":
            reps += m.get("vigencia") != "propuesto"
        elif m.get("tipo") == "notice":
            notes += i not in seen
        else:
            tasks += m.get("estado") == "open" and actor not in (m.get("confirmaciones") or {})
    return tasks, reps, notes


def messaging_pending(st, aliases):
    """[(alias, tareas, repeat, avisos)] de los componentes con algo en mensajería."""
    return [(manifest.display(a), *c) for a in aliases for c in [message_counts(st, a)] if any(c)]


TODO_MAX = 5
PRIO = {"critical": 0, "high": 1, "medium": 2, "normal": 2, "low": 3}      # `normal` = valor antiguo de medium
TODO_ACTIVE = ("pending", "open", "in-progress", "paused", "blocked")             # `open` = valor antiguo de pending


def todo_pending(st):
    """Tareas activas de arkana-todo (pending, in-progress, paused, blocked), por prioridad, vencimiento e id: [(id, título, prioridad, vence, componente, vencida, estado)].
    Lectura local sin importar el plugin; cualquier dato raro se ignora."""
    d = datafiles.read_json(os.path.join(st, "arkana-todo", "todos.json"), {}) or {}
    hoy = datetime.date.today().isoformat()
    res = []
    for t in d.get("tareas", []) if isinstance(d, dict) else []:
        if not isinstance(t, dict) or t.get("estado") not in TODO_ACTIVE or not t.get("titulo"):
            continue
        vence = str(t.get("vence") or "")
        cv = t.get("componente")                                                # texto (versiones anteriores) o lista de alias; en la tupla va como «a,b»
        comps = ",".join(x for x in (cv if isinstance(cv, list) else [cv]) if isinstance(x, str) and x)
        res.append((str(t.get("id", "")), str(t["titulo"]), str(t.get("prioridad") or "medium"), vence, comps, bool(vence) and vence < hoy, str(t["estado"])))
    return sorted(res, key=lambda r: (PRIO.get(r[2], 2), r[3] or "9999", r[0]))


NOTE_MAX = 5


def note_pending(st):
    """Notas activas de arkana-note, las modificadas más recientemente primero: [(id, título, componente)]. Lectura local sin importar el plugin; cualquier dato raro se ignora."""
    d = datafiles.read_json(os.path.join(st, "arkana-note", "notes.json"), {}) or {}
    res = []
    for n in d.get("notas", []) if isinstance(d, dict) else []:
        if not isinstance(n, dict) or n.get("estado") != "active" or not n.get("titulo"):
            continue
        res.append((str(n.get("modificada") or ""), str(n.get("id", "")), str(n["titulo"]), str(n.get("componente") or "")))
    return [(i, t, c) for _, i, t, c in sorted(res, reverse=True)]


def note_line(i, n):
    id_, titulo, comp = n
    return f"{i}. {titulo} [{id_}]" + (f" ({manifest.display(comp)})" if comp not in ("", "*", "all") else "")


def statusline_installed():
    """¿`statusLine` de ~/.claude/settings.json apunta a arkana-statusline? Lectura local barata."""
    cfg = datafiles.read_json(os.path.join(os.path.expanduser("~"), ".claude", "settings.json"), {}) or {}
    return "arkana-statusline" in str((cfg.get("statusLine") or {}).get("command", ""))


def todo_line(i, t):
    id_, titulo, prio, vence, comp, vencida, estado = t
    extra = [x for x in (prio if prio not in ("medium", "normal") else "", estado if estado not in ("pending", "open") else "",
                         ("⚠ vencida " if vencida else "vence ") + vence if vence else "", ", ".join(manifest.display(c) for c in comp.split(",") if c not in ("", "*", "all"))) if x]
    return f"{i}. {titulo} [{id_}]" + (f" ({', '.join(extra)})" if extra else "")


def brief(git, msgs, plan, todos=(), notes=(), force=False):
    """Texto del BRIEF, o None si no hay nada pendiente (salvo `force`: tras un compact o un resume se da siempre, aunque solo lleve el QUICK START).
    Orden de las secciones: QUICK START, MESSAGING, TODO, NOTES, GIT y ORCHESTRATION."""
    if not (git or msgs or plan or todos or notes or force):
        return None
    qs = []                                                                      # primero la puesta a punto (config → check → fix), luego el trabajo del día
    if not statusline_installed():
        qs.append("- Use '/arkana-statusline:install' - show the Arkana status bar (git, plan, cost, usage)")
    qs += ["- Use '/arkana-workspace:config' - set tool versions (and optional Jira)",
           "- Use '/arkana-workspace:check' - diagnose the workspace and the environment",
           "- Use '/arkana-workspace:fix' - repair what check reports, step by step"]
    if msgs:
        qs.append("- Use '/arkana-messaging:query --unread' - list what is waiting for this component (read-only: it does not mark anything as read)")
    qs.append("- Use '/arkana-workspace:sync' - fetch the remotes so the commits to pull (⇣) are up to date")
    if git:
        qs.append("- Use '/arkana-workspace:status' - git state of every component")
    if plan:
        qs.append("- Use '/arkana-agentic:status' - progress and cost of the active plan")
    if todos:
        qs.append("- Use '/arkana-todo:list' - active tasks grouped by status, with priority and due date")
    if notes:
        qs.append("- Use '/arkana-note:list' - your notes (add one with '/arkana-note:add')")
    qs.append("- Use '/arkana-knowledge:ingest' - turn what is waiting in arkana-incoming/ into notes and documents")
    qs.append("- Use '/arkana-evolve:check' - check whether this installation needs migrations (then '/arkana-evolve:apply')")
    out = ["****** [ARKANA] BRIEF ******", "", "### QUICK START", *qs]
    if msgs:
        out += ["", "### MESSAGING:", *[f"{i}. {a} ({', '.join(x for x in (f'{t} tasks' if t else '', f'{r} repeat' if r else '', f'{n} unread notices' if n else '') if x)})"
                                          for i, (a, t, r, n) in enumerate(msgs, 1)]]
    if todos:
        out += ["", "### TODO:", *[todo_line(i, t) for i, t in enumerate(todos[:TODO_MAX], 1)]]
        if len(todos) > TODO_MAX:
            out.append(f"... and {len(todos) - TODO_MAX} more")
    if notes:
        out += ["", "### NOTES:", *[note_line(i, n) for i, n in enumerate(notes[:NOTE_MAX], 1)]]
        if len(notes) > NOTE_MAX:
            out.append(f"... and {len(notes) - NOTE_MAX} more")
    if git:
        out += ["", "### GIT (pending):", *[f"{i}. {a} ({b})" for i, (a, b) in enumerate(git, 1)]]
    if plan:
        out += ["", "### ORCHESTRATION:", f"- {plan}"]
    return "\n".join(out + [""])


def main(argv):
    if os.environ.get("ARKANA_WORKER") == "1":
        return 0
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        home = locate.find_home(ev.get("cwd") or None)
        if not home:
            return 0
        ws = manifest.load(home)
        st = locate.state_dir(home)
        aliases = ws.aliases()
        source = str(ev.get("source") or "")                                    # startup | resume | clear | compact
        repetir = source in ("resume", "compact")                               # el contexto se perdió o se recuperó: el BRIEF se vuelve a dar siempre
        text = brief(git_pending(ws, aliases), messaging_pending(st, aliases), active_plan(st), todo_pending(st), note_pending(st), force=repetir)
        have = project.layout(home)
        if have < project.LAYOUT_REQUIRED:                                      # instalación sin migrar: lo primero que debe ver la persona usuaria
            aviso = f"[ARKANA] ⚠ Instalación en layout {have}; esta versión necesita {project.LAYOUT_REQUIRED}. Ejecuta /arkana-evolve:apply."
            text = aviso + ("\n\n" + text if text else "\n")
        elif have > project.LAYOUT_KNOWN:                                       # otra persona migró a un layout más nuevo: hay que actualizar el plugin, no aplicar nada
            aviso = f"[ARKANA] ⚠ El repo está en layout {have} y esta instalación solo conoce hasta {project.LAYOUT_KNOWN}: actualiza el plugin (/plugin)."
            text = aviso + ("\n\n" + text if text else "\n")
        out = {}
        if text:
            out["systemMessage"] = text
        actor = ws.owner_of(ev.get("cwd") or os.getcwd())                       # la pieza cuya carpeta contiene el cwd (ARKANA incluida)
        contexto = directives.render(ws, actor) if actor else ""
        if repetir and text:                                                    # tras un compact o un resume el modelo ve también el BRIEF, no solo la persona usuaria
            contexto = f"[Arkana] Estado del workspace tras {'compactar' if source == 'compact' else 'reanudar'} la sesión:\n\n{text}\n" + (("\n" + contexto) if contexto else "")
        if contexto:
            out["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": contexto}
        if out:
            sys.stdout.write(json.dumps(out, ensure_ascii=False))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
