#!/usr/bin/env python3
"""finish: interpreta el resultado de un worker, lo verifica con scripts de confianza y propone las acciones permitidas.

Que un worker diga 'hecha' no cuenta: se comprueban el informe (esquema), las denegaciones de permisos, la instantanea de
los repos y ficheros vigilados, el alcance de los cambios, las rutas protegidas, los comandos de verificacion (lista
cerrada, argv directo, entorno reducido) y cada criterio de aceptacion.

Uso:  verify-task.sh <plan-id> <tarea-id> [--json]
Codigos: 0 resultado registrado (completada, rechazada, parcial, fallida), 3 precondicion, 4 violacion, 5 gate abierto (espera al usuario).
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import launch  # noqa: E402
import matchers  # noqa: E402
import paths  # noqa: E402
import repos  # noqa: E402
import snapshot  # noqa: E402
import state  # noqa: E402
import validate  # noqa: E402

ACTIONS = {
    "completada": ["continue"],
    "rechazada": ["retry", "split", "escalate", "skip", "stop"],
    "parcial": ["retry", "split", "escalate", "skip", "stop"],
    "fallida": ["retry", "split", "escalate", "skip", "stop"],
    "bloqueada": ["escalate", "skip", "stop"],
    "violacion": ["stop"],
}
GATE_KIND = {"permiso": "permiso", "herramienta": "herramienta", "dato": "dato", "decision": "decision", "otro": "decision"}


def interpret(raw, esquema):
    """-> (veredicto del worker, motivo, detalle, informe valido o None)"""
    rc, salida = raw.get("exit_code"), raw.get("salida_json")
    if rc in (124, 137):
        return "fallida", "tiempo", f"el worker excedio su tiempo (exit {rc})", None
    if salida is None:
        return "fallida", "informe_invalido", "la salida del worker no contiene JSON", None
    so = salida.get("structured_output")
    errs = validate.check_schema(so, esquema) if isinstance(so, dict) else ["falta structured_output"]
    informe = so if not errs else None
    denials = salida.get("permission_denials") or []
    sub = salida.get("subtype")
    if sub == "error_max_budget_usd":
        return "fallida", "coste", "se agoto el presupuesto de la tarea", informe
    if sub == "error_max_turns":
        return "parcial", "turnos", "se alcanzo el maximo de turnos", informe
    if denials:
        res = "; ".join(f"{d.get('tool_name')}: {str(d.get('tool_input'))[:80]}" for d in denials[:3])
        return "bloqueada", "permiso", f"el worker intento algo no permitido ({res})", informe
    if salida.get("is_error") and informe is None:
        return "fallida", "error_claude", str(salida.get("result") or salida.get("terminal_reason"))[:200], None
    if errs:
        return "fallida", "informe_invalido", "; ".join(errs[:4]), None
    return informe["estado"], "informe", informe["resumen"][:300], informe


def rutas_cambiadas(repo):
    partes = repos.git(repo, "status", "--porcelain=v1", "-z", "-uall").stdout.split("\0")
    res, i = [], 0
    while i < len(partes):
        e = partes[i]
        i += 1
        if not e:
            continue
        res.append(e[3:])
        if e[0] in "RC":
            i += 1
    return sorted(set(res))


def package_json_cambiado(repo, campos):
    antes = repos.git(repo, "show", "HEAD:package.json")
    try:
        a = json.loads(antes.stdout) if antes.returncode == 0 else {}
        with open(os.path.join(repo, "package.json"), encoding="utf-8") as f:
            d = json.load(f)
    except (ValueError, FileNotFoundError):
        return ["package.json ilegible"]
    return matchers.package_json_sensible(a, d, campos)


def run_command(argv, repo, timeout):
    home = tempfile.mkdtemp(prefix="agentic-verif-")
    npmrc = os.path.join(home, ".npmrc")
    import adapters
    with open(npmrc, "w", encoding="utf-8") as f:
        f.write(adapters.npmrc_lines())                                    # registros por ámbito declarados en tools.json (config tools --registry)
    extra = "".join(d + ":" for d in adapters.tool_bin_dirs())            # node, JDK, Maven… del workspace (tools.json), si los adaptadores los piden
    env = {"PATH": f"{extra}{adapters.VERIFIER_PATH}", "HOME": home,
           "npm_config_userconfig": npmrc, "LANG": "C.UTF-8", "CI": "1", "NO_COLOR": "1"}
    jdk = adapters.tool_home("jdk")
    if jdk:
        env["JAVA_HOME"] = jdk
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, errors="replace", timeout=timeout)
        rc, salida = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        rc, salida = 124, "tiempo agotado"
    except FileNotFoundError:
        rc, salida = 127, "comando no encontrado"
    return {"rc": rc, "duracion_s": round(time.time() - t0, 1), "cola": "\n".join(salida.splitlines()[-40:])[-4000:]}


def close_task(pid, tid, intento, resultado, codigo):
    resultado["acciones_permitidas"] = ACTIONS.get(resultado["veredicto"], ["escalate", "stop"])
    state.save_json(os.path.join(state.plan_dir(pid), "verificacion", f"{tid}.{intento}.json"), resultado)
    state.log_event(pid, "script", "finish", tid, resultado.get("motivo", ""), veredicto=resultado["veredicto"])
    return resultado, codigo


def gate(pid, tid, estado_actual, motivo, detalle, opciones, reanuda, rutas=None):
    """La tarea se detiene y el plan queda esperando al usuario."""
    if estado_actual != "bloqueada":
        state.transition_task(pid, tid, "bloqueada", "script", f"{motivo}: {detalle}"[:200])
    state.transition_task(pid, tid, "esperando_usuario", "script", "gate abierto")
    state.open_gate(pid, motivo, detalle, opciones, tarea=tid, reanuda=reanuda, rutas=rutas)


def protected_denials(raw, repo, repo_id=None):
    """Denegaciones de Edit/Write sobre rutas protegidas DEL REPO de la tarea: [(ruta relativa, texto que el worker queria escribir)]."""
    patrones = state.load_protected_paths(repo_id)["patrones"] if repo_id else state.load_protected_paths()["patrones"]
    base = os.path.realpath(repo)
    res = []
    for d in ((raw.get("salida_json") or {}).get("permission_denials") or []):
        ti = d.get("tool_input") or {}
        ruta = ti.get("file_path")
        if d.get("tool_name") not in ("Edit", "Write", "MultiEdit") or not ruta:
            continue
        rel = os.path.relpath(os.path.realpath(ruta), base)
        if not rel.startswith("..") and matchers.is_protected_path(rel, patrones):
            res.append((rel, str(ti.get("new_string") or ti.get("content") or "").strip()))
    return res


def _gate_ruta_denegada(pid, tid, intento, base, prot, informe):
    """El worker intento escribir en una ruta protegida y sus ajustes se lo impidieron. Si es un fichero de instrucciones (CLAUDE.md) el usuario puede
    autorizarlo para esta tarea (`approve` levanta solo esa denegacion en el siguiente intento); si es .git, .husky, .claude o .env*, no se puede."""
    rutas = sorted({r for r, _ in prot})
    no_autorizables = [r for r in rutas if r not in launch.AUTHORIZABLE_DENIED]
    quiere = "; ".join(f"{r}: «{t[:100]}»" if t else r for r, t in prot[:3])
    if no_autorizables:
        txt = f"el worker intento escribir en {', '.join(no_autorizables)}, que no se puede autorizar ({quiere})"[:300]
        state.transition_task(pid, tid, "bloqueada", "script", f"ruta_protegida: {txt}"[:200])
        gate(pid, tid, "bloqueada", "ruta_protegida", txt, ["omitir la tarea", "detener el plan"], "none")
        return close_task(pid, tid, intento, dict(base, veredicto="bloqueada", gate="ruta_protegida", rutas_protegidas=rutas, autorizable=False, informe=informe), 5)
    txt = f"el worker quiere editar {', '.join(rutas)} (ruta protegida) y sus ajustes se lo impiden: {quiere}"[:300]
    state.transition_task(pid, tid, "bloqueada", "script", f"ruta_protegida: {txt}"[:200])
    gate(pid, tid, "bloqueada", "ruta_protegida", txt, ["autorizar esa edicion y reintentar", "omitir la tarea", "detener el plan"], "retry", rutas=rutas)
    return close_task(pid, tid, intento, dict(base, veredicto="bloqueada", gate="ruta_protegida", rutas_protegidas=rutas, autorizable=True, informe=informe), 5)


def finish(pid, tid):
    plan = state.load_json(os.path.join(state.plan_dir(pid), "plan.json"))
    tarea = state.load_json(os.path.join(state.plan_dir(pid), "tareas", f"{tid}.json"))
    if tarea["estado"] not in ("en_curso", "verificando"):
        return {"veredicto": "error", "motivo": f"la tarea esta en '{tarea['estado']}', no en_curso"}, 3
    if launch.live_worker():
        return {"veredicto": "error", "motivo": "el worker sigue vivo: espera a que termine"}, 3
    intento = tarea["intentos"]
    try:
        raw = state.load_json(os.path.join(state.plan_dir(pid), "informes", f"{tid}.{intento}.raw.json"))
    except FileNotFoundError:
        return {"veredicto": "error", "motivo": "no hay informe crudo: la tarea quedo interrumpida (usa recover)"}, 3
    with open(os.path.join(state.PLUGIN, "schemas", "informe.schema.json"), encoding="utf-8") as f:
        esquema = json.load(f)
    veredicto_w, motivo, detalle, informe = interpret(raw, esquema)
    base = {"plan": pid, "tarea": tid, "intento": intento, "worker": veredicto_w, "motivo": motivo, "detalle": detalle,
            "informe": informe, "coste_usd": (raw.get("salida_json") or {}).get("total_cost_usd")}
    if veredicto_w in ("parcial", "fallida"):
        state.transition_task(pid, tid, veredicto_w, "script", f"{motivo}: {detalle}"[:200])
        return close_task(pid, tid, intento, dict(base, veredicto=veredicto_w), 0)
    if veredicto_w == "bloqueada":
        necesita = (informe or {}).get("necesita") or []
        if motivo == "permiso":
            prot = protected_denials(raw, repos.repo_path(tarea["repo"]), tarea["repo"])
            if prot:
                return _gate_ruta_denegada(pid, tid, intento, base, prot, informe)
        tipo = "permiso" if motivo == "permiso" else GATE_KIND.get(necesita[0]["tipo"] if necesita else "otro", "decision")
        txt = detalle if motivo == "permiso" else "; ".join(n["detalle"] for n in necesita)[:300] or detalle
        state.transition_task(pid, tid, "bloqueada", "script", f"{tipo}: {txt}"[:200])
        opciones = (["reintentar (tu nota llega al worker, pero sus permisos no cambian)", "omitir la tarea", "detener el plan"] if tipo == "permiso"
                    else ["autorizar y reintentar", "omitir la tarea", "detener el plan"])
        gate(pid, tid, "bloqueada", tipo, txt, opciones, "retry")
        return close_task(pid, tid, intento, dict(base, veredicto="bloqueada", gate=tipo, necesita=necesita), 5)
    # --- el worker dice 'hecha': se verifica ---
    if tarea["estado"] == "en_curso":
        state.transition_task(pid, tid, "verificando", "script", "verificando el trabajo del worker")
    autorizado = tarea.get("autorizado") or {}
    repo = repos.repo_path(tarea["repo"])
    try:
        antes = state.load_json(os.path.join(state.plan_dir(pid), "snapshots", f"{tid}.{intento}.antes.json"))
        despues = state.load_json(os.path.join(state.plan_dir(pid), "snapshots", f"{tid}.{intento}.despues.json"))
        violaciones = snapshot.compare(antes, despues, tarea["repo"])
    except FileNotFoundError:
        violaciones = [{"tipo": "sin_snapshot", "detalle": "falta la instantanea antes o despues"}]
    if violaciones:
        gate(pid, tid, "verificando", "violacion", json.dumps(violaciones[0], ensure_ascii=False)[:250], ["detener el plan"], "none")
        return close_task(pid, tid, intento, dict(base, veredicto="violacion", violaciones=violaciones), 4)
    cambiadas = snapshot.manifest_changes(antes, despues)
    if cambiadas is None:
        cambiadas = rutas_cambiadas(repo)
    protegidas = state.load_protected_paths(tarea["repo"])
    tocadas = [r for r in cambiadas if matchers.is_protected_path(r, protegidas["patrones"])]
    if "package.json" in cambiadas:
        campos = package_json_cambiado(repo, protegidas["package_json_campos"])
        if campos:
            tocadas.append("package.json (" + ", ".join(campos) + ")")
    tocadas = [r for r in tocadas if r not in autorizado.get("rutas_protegidas", [])]
    if tocadas:
        gate(pid, tid, "verificando", "ruta_protegida", "el worker toco: " + ", ".join(tocadas)[:250], ["revisar el diff y autorizar", "descartar", "detener el plan"], "reverify")
        return close_task(pid, tid, intento, dict(base, veredicto="bloqueada", gate="ruta_protegida", rutas_protegidas=tocadas, rutas_cambiadas=cambiadas), 5)
    if tarea["perfil"] == "lectura" and cambiadas:
        state.transition_task(pid, tid, "rechazada", "script", "un worker de lectura modifico ficheros")
        return close_task(pid, tid, intento, dict(base, veredicto="rechazada", motivo="perfil_lectura", rutas_cambiadas=cambiadas), 0)
    fuera = matchers.outside_scope(cambiadas, tarea.get("rutas_permitidas") or [])
    if fuera:
        state.transition_task(pid, tid, "rechazada", "script", "cambios fuera de las rutas permitidas")
        return close_task(pid, tid, intento, dict(base, veredicto="rechazada", motivo="alcance", fuera_de_alcance=fuera, rutas_cambiadas=cambiadas), 0)
    permitidos, verifs = state.load_allowed_commands({t["repo"] for t in state.load_tasks(pid)}), tarea.get("verificaciones") or []
    no_permitidos = [v["id"] for v in verifs if not matchers.is_allowed_command(v["comando"], permitidos)
                     and v["id"] not in autorizado.get("verificaciones", [])]
    if no_permitidos:
        gate(pid, tid, "verificando", "herramienta", "comando fuera de la lista cerrada en: " + ", ".join(no_permitidos), ["autorizar el comando", "omitir", "detener el plan"], "reverify")
        return close_task(pid, tid, intento, dict(base, veredicto="bloqueada", gate="herramienta", comandos_no_permitidos=no_permitidos), 5)
    resultados = {v["id"]: dict(run_command(v["comando"], repo, v.get("timeout_s", 600)), comando=v["comando"]) for v in verifs}
    autoeval = {c["id"]: c for c in (informe or {}).get("criterios", [])}
    criterios = []
    for c in tarea["criterios_aceptacion"]:
        vinfo = next((x for x in verifs if x["id"] == c.get("verificacion")), None)
        if c.get("verificacion") and not (vinfo and matchers.is_informative_check(vinfo["comando"])):
            r = resultados.get(c["verificacion"])
            cumplido, origen = (r is not None and r["rc"] == 0), "verificado"
        else:
            cumplido, origen = bool(autoeval.get(c["id"], {}).get("cumplido")), "autoevaluado"
        if c["id"] in autoeval and not autoeval[c["id"]]["cumplido"]:
            cumplido = False   # si el propio worker reconoce que no lo cumple, no se da por cumplido
        criterios.append({"id": c["id"], "cumplido": cumplido, "origen": origen})
    ok = all(c["cumplido"] for c in criterios) and all(r["rc"] == 0 for r in resultados.values())
    destino = "completada" if ok else "rechazada"
    state.transition_task(pid, tid, destino, "script", "criterios y verificaciones " + ("cumplidos" if ok else "no cumplidos"))
    return close_task(pid, tid, intento, dict(base, veredicto=destino, motivo="criterios" if not ok else "ok", criterios=criterios,
                                          verificaciones=resultados, rutas_cambiadas=cambiadas), 0)


def main(argv):
    try:
        return _main(argv)
    except (paths.NoWorkspace, repos._manifest.ManifestError) as e:
        print(f"FAIL|finish|workspace de Arkana: {e}")
        return 3


def _main(argv):
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        res, cod = finish(argv[1], argv[2])
    except (FileNotFoundError, KeyError) as e:
        print(f"FAIL|finish|{type(e).__name__}: {e}")
        return 1
    except state.IllegalTransition as e:
        print(f"FAIL|finish|{e}")
        return 1
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        etiqueta = "OK" if res["veredicto"] in ("completada",) else "FAIL"
        print(f"{etiqueta}|finish|{argv[2]} {res['veredicto']}: {res.get('motivo', '')} {str(res.get('detalle', ''))[:160]}".rstrip())
        if res.get("acciones_permitidas"):
            print("ACCIONES|" + ",".join(res["acciones_permitidas"]))
    return cod


if __name__ == "__main__":
    sys.exit(main(sys.argv))
