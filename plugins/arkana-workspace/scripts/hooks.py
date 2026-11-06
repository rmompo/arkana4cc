#!/usr/bin/env python3
"""Hook de estado de Arkana al abrir, reanudar, limpiar o compactar una sesión (SessionStart: startup|resume|clear|compact). Solo local: git local, sin red.

Muestra al USUARIO (`systemMessage`; no se inyecta en el contexto del modelo) un BRIEF corto: GIT (componentes con cambios o commits sin subir),
MESSAGING (por componente: tareas pendientes, directrices repeat y avisos sin leer), ORCHESTRATION (plan activo de arkana-agentic, con su coste) y QUICK START (comandos útiles según lo pendiente).
No hace nada dentro de un worker (`ARKANA_WORKER=1`), fuera de un workspace, ni si todo está limpio y no hay plan ni mensajes. Nunca falla.
"""
import concurrent.futures
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_core"))
sys.path.insert(0, os.path.join(HERE, "lib"))
from arkana_core import datafiles, locate, manifest  # noqa: E402
import gitstate  # noqa: E402


def git_pending(ws, aliases):
    """[(alias, rama)] de los componentes con cambios o commits sin subir, en el orden del manifiesto."""
    def one(a):
        p = ws.path(a)
        return a, (gitstate.state(p) if os.path.isdir(p) else None)
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


def statusline_installed():
    """¿`statusLine` de ~/.claude/settings.json apunta a arkana-statusline? Lectura local barata."""
    cfg = datafiles.read_json(os.path.join(os.path.expanduser("~"), ".claude", "settings.json"), {}) or {}
    return "arkana-statusline" in str((cfg.get("statusLine") or {}).get("command", ""))


def brief(git, msgs, plan):
    """Texto del BRIEF, o None si no hay nada pendiente."""
    if not (git or msgs or plan):
        return None
    out = ["****** [ARKANA] BRIEF ******"]
    if git:
        out += ["", "### GIT (pending):", *[f"{i}. {a} ({b})" for i, (a, b) in enumerate(git, 1)]]
    if msgs:
        out += ["", "### MESSAGING:", *[f"{i}. {a} ({', '.join(x for x in (f'{t} tasks' if t else '', f'{r} repeat' if r else '', f'{n} unread notices' if n else '') if x)})"
                                          for i, (a, t, r, n) in enumerate(msgs, 1)]]
    if plan:
        out += ["", "### ORCHESTRATION:", f"- {plan}"]
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
    return "\n".join(out + ["", "### QUICK START", *qs, ""])


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
        text = brief(git_pending(ws, aliases), messaging_pending(st, aliases), active_plan(st))
        if text:
            sys.stdout.write(json.dumps({"systemMessage": text}, ensure_ascii=False))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
