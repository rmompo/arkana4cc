#!/usr/bin/env python3
"""Hooks de arkana-statusline (SessionStart y UserPromptSubmit). Solo local, rápidos y sin red.

1. Recuperación del hueco (en los dos eventos): si hay un despachador instalado y otra herramienta pisó la `statusLine` de usuario, la deja como proveedor y recoloca el
   despachador (`ops.reclaim`), para que la jerarquía de Arkana (Arkana → plugin4cc → otra) mande aunque la otra herramienta no la conozca. Se desactiva con
   `/arkana-statusline:provider auto off`.
2. Pregunta por componente (solo SessionStart): al abrir Claude Code en un COMPONENTE gobernado por ARKANA sin elección guardada, pide a Claude que pregunte a la
   persona usuaria qué statusline quiere ver ahí (un hook no puede preguntar: inyecta la instrucción y la respuesta se guarda con `/arkana-statusline:choose`).
   En la carpeta de ARKANA no pregunta (siempre se ve la de Arkana) y fuera de ARKANA tampoco."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lib"))


def main(argv):
    if os.environ.get("ARKANA_WORKER") == "1":
        return 0
    evento = argv[1] if len(argv) > 1 else "session-start"
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        import ops
        dispatch = ops.dispatch
        out = {}
        cambio, msg = ops.reclaim()
        if cambio:
            out["systemMessage"] = "[ARKANA statusline] " + msg
        if evento == "session-start" and ops.is_ours(ops.status_line()):
            home, owner = dispatch.context({"cwd": ev.get("cwd") or os.getcwd()})
            if home and owner not in (None, "arkana") and not dispatch.load_prefs()["components"].get(dispatch.choice_key(home, owner)):
                out["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": (
                    f"[ARKANA statusline] This folder is the component '{owner}' of an Arkana workspace and no statusline choice is stored for it yet. "
                    "Before anything else, ask the user (AskUserQuestion) whether to see the Arkana statusline here or the one already configured, then run "
                    f"/arkana-statusline:choose with --component {owner} and --use arkana or --use other, as they answer.")}
        if out:
            sys.stdout.write(json.dumps(out, ensure_ascii=False))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
