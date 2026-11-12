#!/usr/bin/env python3
"""Hooks de arkana-knowledge: avisan de documentos nuevos en `arkana-incoming/`. Solo lectura local (sin git ni red); un error nunca rompe la sesión.

  hooks.py session-start | file-changed | prompt-submit        (el evento llega por stdin como JSON)

- SessionStart: pide a Claude Code vigilar `arkana-incoming/` (`watchPaths`) y, si ya hay ficheros esperando, lo avisa una vez.
- FileChanged: apunta en `.arkana/arkana-knowledge/pending.json` el fichero que ha llegado (no toca el modelo: el aviso va en el siguiente prompt).
- UserPromptSubmit: una sola línea con lo pendiente, y solo cuando hay algo nuevo respecto a lo ya avisado en esa sesión.
Nada de esto ingiere: ingerir exige criterio (conocimiento o documento, a qué componente) y lo hace `/arkana-knowledge:ingest` con la persona usuaria.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "_core"))
from arkana_core import datafiles, locate  # noqa: E402

INCOMING = "arkana-incoming"
PENDING = os.path.join("arkana-knowledge", "pending.json")
NOTICE = ("[arkana-knowledge] {n} documento(s) esperan en arkana-incoming/. Propón ingerirlos con /arkana-knowledge:ingest "
          "(decidir si es conocimiento o documento, a qué componentes afecta y resumirlo); no los ingieras sin la persona usuaria.")


def event():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return {}


def home_of(ev):
    if os.environ.get("ARKANA_WORKER") == "1":
        return None
    try:
        home = locate.find_home(ev.get("cwd"))
    except Exception:
        return None
    return home if home and os.path.isdir(os.path.join(home, INCOMING)) else None


def waiting(home):
    d = os.path.join(home, INCOMING)
    out = []
    for root, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        out += [os.path.join(root, f) for f in files if not f.startswith(".")]
    return sorted(out)


def sid(ev):
    return "".join(c for c in str(ev.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "sin-sesion") if c.isalnum() or c in "-_")[:80]


def notified_path(home, ev):
    return os.path.join(locate.state_dir(home), "arkana-knowledge", "sessions", sid(ev) + ".json")


def say(event_name, text=None, **extra):
    spec = {"hookEventName": event_name, **extra}
    if text:
        spec["additionalContext"] = text
    print(json.dumps({"hookSpecificOutput": spec}, ensure_ascii=False))


def session_start(ev, home):
    n = len(waiting(home))
    datafiles.atomic_write_json(notified_path(home, ev), {"avisados": n})
    say("SessionStart", NOTICE.format(n=n) if n else None, watchPaths=[os.path.join(home, INCOMING)])


def file_changed(ev, home):
    p = os.path.abspath(str(ev.get("file_path") or ""))
    base = os.path.join(home, INCOMING) + os.sep
    if not p.startswith(base) or os.path.basename(p).startswith("."):
        return
    f = os.path.join(locate.state_dir(home), PENDING)
    cur = datafiles.read_json(f, {}) or {}
    files = sorted(set(cur.get("ficheros", [])) | {os.path.relpath(p, home)})
    datafiles.atomic_write_json(f, {"ficheros": files})


def prompt_submit(ev, home):
    n = len(waiting(home))
    f = notified_path(home, ev)
    ya = (datafiles.read_json(f, {}) or {}).get("avisados", 0)
    if n > ya:
        datafiles.atomic_write_json(f, {"avisados": n})
        say("UserPromptSubmit", NOTICE.format(n=n))
    elif n == 0 and ya:
        datafiles.atomic_write_json(f, {"avisados": 0})


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        ev = event()
        home = home_of(ev)
        if home:
            {"session-start": session_start, "file-changed": file_changed, "prompt-submit": prompt_submit}.get(cmd, lambda *a: None)(ev, home)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
