#!/usr/bin/env python3
"""Hook SessionStart: inyecta las reglas del orquestador en la sesión de ARKANA (`templates/orquestador.md`, a través de `hookSpecificOutput.additionalContext`).

Solo actúa cuando el cwd está dentro de la carpeta de ARKANA (el orquestador es la sesión de ARKANA; las de los componentes no lo son). No hace nada dentro de
un worker (`ARKANA_WORKER=1`) ni fuera de un workspace, y nunca falla. Sustituye al antiguo bloque que `install` escribía en un fichero de instrucciones:
ya no hay nada de Arkana que mantener en los repos.

  orchestrator.py hook       (el evento llega por stdin como JSON)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
import paths  # noqa: E402
import state  # noqa: E402


def template():
    with open(os.path.join(state.PLUGIN, "templates", "orquestador.md"), encoding="utf-8") as f:
        return f.read()


def inside(cwd, home):
    c, h = os.path.realpath(cwd), os.path.realpath(home)
    return c == h or c.startswith(h.rstrip(os.sep) + os.sep)


def main(argv):
    if os.environ.get("ARKANA_WORKER") == "1" or len(argv) < 2 or argv[1] != "hook":
        return 0
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        cwd = ev.get("cwd") or os.getcwd()
        if not inside(cwd, paths.arkana_dir(cwd)):
            return 0
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": template()}}, ensure_ascii=False))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
