#!/usr/bin/env python3
"""Lanza UN worker (claude -p sin shell) para una tarea y espera a que termine. Es el unico camino para ejecutar workers.

Uso:  launch-worker.sh <plan-id> <tarea-id>
Salida: lineas ESTADO|ID|detalle.  Codigos: 0 el worker corrio (el informe crudo queda guardado; falta 'finish'),
        1 error, 2 uso, 3 precondicion (worker vivo, plan sin aprobar o alterado, repo sucio...), 6 limite, 7 parada/pausa.

Variables: ARKANA_AGENTIC_CLAUDE_BIN (por defecto 'claude'; las pruebas usan un claude falso), ARKANA_AGENTIC_OWNER_PID
(pid que debe seguir vivo; 'none' lo desactiva), ARKANA_AGENTIC_MODEL, ARKANA_AGENTIC_EFFORT.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inbox  # noqa: E402
import paths  # noqa: E402
import repos  # noqa: E402
import snapshot  # noqa: E402
import state  # noqa: E402

PLUGIN = state.PLUGIN
# Semilla de mensajería de un repo (el worker no la ve)
SEED_BLOCK = re.compile(r"<!-- arkana:messaging:start -->.*?<!-- arkana:messaging:end -->", re.S)
_signal_state = {"pgid": None, "recibida": False}


def fail_exit(codigo, msg):
    print(f"FAIL|launch|{msg}")
    return codigo


def pid_alive(pid, marcador=None):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            if f.read().rsplit(") ", 1)[-1].split()[0] == "Z":
                return False
        if marcador:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                return marcador in f.read().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return True


def live_worker():
    try:
        w = state.load_json(os.path.join(state.run_dir(), "worker.json"))
    except (FileNotFoundError, ValueError):
        return None
    return w if pid_alive(w.get("pid", 0), w.get("marcador")) else None


def detect_owner():
    v = os.environ.get("ARKANA_AGENTIC_OWNER_PID")
    if v:
        return None if v == "none" else int(v)
    pid = os.getppid()
    for _ in range(12):
        try:
            with open(f"/proc/{pid}/comm", encoding="utf-8") as f:
                if f.read().strip() == "claude":
                    return pid
            with open(f"/proc/{pid}/status", encoding="utf-8") as f:
                ppid = int(next(l for l in f if l.startswith("PPid:")).split()[1])
        except (OSError, StopIteration, ValueError):
            return None
        if ppid in (0, 1):
            return None
        pid = ppid
    return None


def path_rule(abs_path, herramienta):
    return f"{herramienta}(/{abs_path}/**)"


# Rutas protegidas que el worker tiene denegadas en sus ajustes y que el usuario puede autorizar para UNA tarea (ficheros de instrucciones, no codigo que
# se ejecute). El resto (.git, .husky, .claude, .env*) nunca se levanta: un gate sobre ellas solo admite omitir o detener.
AUTHORIZABLE_DENIED = ("CLAUDE.md", "CLAUDE.local.md")


def worker_settings(repo, perfil, lectura_extra, authorized=()):
    home = os.path.expanduser("~")
    meta = paths.plugins_dir().lstrip("/")
    allow = [f"Read(/{repo}/**)"] + [f"Read(/{r}/**)" for r in lectura_extra]
    if perfil == "edicion":
        allow.append(f"Edit(/{repo}/**)")
    deny = [f"Edit(/{repo}/.git/**)", f"Edit(/{repo}/.husky/**)", f"Edit(/{repo}/.claude/**)", f"Edit(/{repo}/CLAUDE.md)",
            f"Edit(/{repo}/CLAUDE.local.md)", f"Edit(/{repo}/.env*)", f"Read(/{repo}/.env*)",
            f"Read(/{home}/.git-credentials)", f"Read(/{home}/.ia4d/**)", f"Read(/{home}/.claude/**)", f"Read(/{home}/.npmrc)",
            f"Read(/{meta}/**)", f"Edit(/{meta}/**)",
            f"Read(/{meta}/.credentials)", f"Edit(/{meta}/.credentials)"]       # explicitas: las credenciales no se tocan aunque cambie la regla general
    levantar = {f"Edit(/{repo}/{rel})" for rel in authorized if rel in AUTHORIZABLE_DENIED}
    deny = [d for d in deny if d not in levantar]                        # lo autorizado en un gate para esta tarea
    for r in lectura_extra:
        deny += [f"Read(/{r}/.env*)", f"Edit(/{r}/**)"]
    # Los hooks de usuario (mensajería, estado…) no corren dentro de un worker: disableAllHooks (verificado en la Fase 0, E4) y ARKANA_WORKER=1
    return {"permissions": {"allow": allow, "deny": deny}, "disableAllHooks": True}


def bullet_list(items, vacio="(ninguno)"):
    return "\n".join(f"- {x}" for x in items) if items else vacio


def build_prompt(plan, tarea, intento, repo_ruta, efectivos, rama="", mensajes=()):
    ctx = tarea.get("contexto") or {}
    try:
        with open(os.path.join(repo_ruta, "CLAUDE.md"), encoding="utf-8") as f:
            normas = SEED_BLOCK.sub("", f.read()).strip()[:20000] or "(sin normas)"
    except FileNotFoundError:
        normas = "(el repo no tiene CLAUDE.md)"
    extractos = "\n\n".join(f"[{e['origen']}{(' ' + e['lineas']) if e.get('lineas') else ''}]\n{e['texto']}"
                            for e in ctx.get("extractos", [])) or "(ninguno)"
    criterios = [f"{c['id']}: {c['descripcion']}" + (f" (se verifica automaticamente: {c['verificacion']})" if c.get("verificacion") else "")
                 for c in tarea["criterios_aceptacion"]]
    valores = {
        "tarea_id": tarea["id"], "plan_id": plan["id"], "asunto": tarea["asunto"], "repo": tarea["repo"],
        "perfil": tarea["perfil"], "rama": rama, "intento": str(intento), "max_attempts": str(efectivos["max_attempts_per_task"]),
        "objetivo": tarea["objetivo"], "instrucciones": "\n".join(tarea["instrucciones"]), "criterios": bullet_list(criterios),
        "ficheros": bullet_list(ctx.get("ficheros", [])), "extractos": extractos,
        "rutas_permitidas": bullet_list(tarea.get("rutas_permitidas") or ["todo el repositorio (salvo rutas protegidas)"]),
        "mensajes": inbox.render(mensajes), "normas": normas, "feedback": bullet_list(tarea.get("feedback", []), "(primer intento)"),
    }
    with open(os.path.join(PLUGIN, "templates", "worker-prompt.md.tpl"), encoding="utf-8") as f:
        tpl = f.read()
    return re.sub(r"\{\{(\w+)\}\}", lambda m: valores.get(m.group(1), m.group(0)), tpl)


def kill_group(pgid, senal=signal.SIGTERM):
    try:
        os.killpg(pgid, senal)
    except (ProcessLookupError, PermissionError):
        pass


def kill_worker(w, motivo, gracia=None):
    """Mata el grupo de procesos de un worker (SIGTERM, y SIGKILL tras la gracia) dejando constancia del motivo."""
    gracia = float(os.environ.get("ARKANA_AGENTIC_KILL_GRACE", "10")) if gracia is None else gracia
    state.save_json(os.path.join(state.run_dir(), "killed.json"),
                       {"pid": w["pid"], "pgid": w["pgid"], "motivo": motivo, "ts": state.now_iso()})
    kill_group(w["pgid"], signal.SIGTERM)
    fin = time.time() + gracia
    while time.time() < fin:
        try:
            os.killpg(w["pgid"], 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    kill_group(w["pgid"], signal.SIGKILL)


def cleanup_after_kill(w, motivo):
    """Si el lanzador ya no esta para hacerlo, deja la tarea y los ficheros de ejecucion en orden."""
    nuevo = "cancelada" if motivo == "stop_force" else "interrumpida"
    try:
        state.transition_task(w["plan"], w["tarea"], nuevo, "script", f"worker detenido: {motivo}")
    except (state.IllegalTransition, FileNotFoundError):
        pass
    for f in ("worker.json", "killed.json") + (("STOP-FORCE",) if motivo == "stop_force" else ()):
        try:
            os.unlink(os.path.join(state.run_dir(), f))
        except FileNotFoundError:
            pass


def _signal_handler(signum, _frame):
    _signal_state["recibida"] = True
    if _signal_state["pgid"]:
        kill_group(_signal_state["pgid"])


def json_from_output(ruta):
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            texto = f.read()
    except FileNotFoundError:
        return None, ""
    for cand in [texto] + texto.strip().splitlines()[::-1][:3]:
        try:
            d = json.loads(cand)
            if isinstance(d, dict):
                return d, texto
        except ValueError:
            continue
    return None, texto


def prepare_branch(plan, tarea, repo_ruta):
    """Todo el trabajo de un plan en un repo va en UNA rama, arkana-worker/<plan>, que crea este script (el worker no tiene git) antes de lanzarlo.
    La primera tarea del repo la crea desde develop y guarda la rama original; las siguientes (y los reintentos) solo se colocan en ella."""
    rama = repos.plan_branch(plan["id"])
    rid = tarea["repo"]
    if repos.branch_exists(repo_ruta, rama):
        if repos.current_branch(repo_ruta) != rama:
            r = repos.git(repo_ruta, "switch", rama)
            if r.returncode:
                return None, f"no se pudo cambiar a {rama}: {r.stderr.strip()[:200]}"
        return rama, None
    if not repos.branch_exists(repo_ruta, "develop"):
        return None, "no existe la rama develop local desde la que crear la rama del plan"
    actual = repos.current_branch(repo_ruta) or "develop"
    original = "develop" if repos.is_plan_branch(actual) else actual          # no tomar como original la rama de otro plan
    r = repos.git(repo_ruta, "switch", "-c", rama, "develop")
    if r.returncode:
        return None, f"no se pudo crear {rama}: {r.stderr.strip()[:200]}"
    def en_plan(o):
        d = o.setdefault("ramas", {}).setdefault(rid, {})
        d.setdefault("original", original)
        d["nombre"] = rama
    state.update_json(os.path.join(state.plan_dir(plan["id"]), "plan.json"), en_plan)
    return rama, None


def main(argv):
    try:
        return _main(argv)
    except (paths.NoWorkspace, repos._manifest.ManifestError) as e:
        return fail_exit(3, f"workspace de Arkana: {e}")


def _main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    pid, tid = argv[1], argv[2]
    try:
        plan = state.load_json(os.path.join(state.plan_dir(pid), "plan.json"))
        tarea = state.load_json(os.path.join(state.plan_dir(pid), "tareas", f"{tid}.json"))
    except FileNotFoundError:
        return fail_exit(3, f"no existe el plan {pid} o la tarea {tid}")
    # --- precondiciones ---
    for marca, cod, msg in (("STOP", 7, "hay una parada pedida (run/STOP)"), ("PAUSE", 7, "el pipeline esta en pausa (run/PAUSE)"),
                            ("STOP-FORCE", 7, "hay una parada forzosa pendiente (run/STOP-FORCE)")):
        if os.path.exists(os.path.join(state.run_dir(), marca)):
            return fail_exit(cod, msg)
    if plan["estado"] != "en_ejecucion":
        return fail_exit(3, f"el plan esta en estado '{plan['estado']}', debe estar en_ejecucion")
    if not state.plan_approval_ok(pid):
        return fail_exit(3, "el contenido del plan no coincide con el aprobado (hay que volver a aprobarlo)")
    net_ok, net_det = repos.net_preflight()
    if not net_ok:                                                       # el trabajo y el commit son locales (rama del plan, sin fetch ni push): se avisa y se sigue
        print(f"WARN|red|sin VPN o sin DNS ({net_det}): el worker se lanza igual, el trabajo y el commit son locales; sin red no habra fetch ni push", file=sys.stderr)
    w = live_worker()
    if w:
        return fail_exit(3, f"ya hay un worker vivo (pid {w['pid']}, tarea {w['plan']}/{w['tarea']}): solo se ejecuta uno a la vez")
    if tarea["estado"] not in ("pendiente", "lista"):
        return fail_exit(3, f"la tarea {tid} esta en estado '{tarea['estado']}'")
    if not state.task_ready(tarea, state.load_tasks(pid)):
        return fail_exit(3, f"la tarea {tid} tiene dependencias sin completar")
    pol = state.load_policy()
    ef = state.effective_limits(pol, plan.get("politica"), tarea.get("limites"))
    cont = plan.get("contadores", {})
    if len(plan["tareas"]) > ef["max_tasks"]:
        return fail_exit(6, f"el plan tiene {len(plan['tareas'])} tareas (maximo {ef['max_tasks']})")
    if tarea["intentos"] >= ef["max_attempts_per_task"]:
        return fail_exit(6, f"la tarea {tid} ya uso sus {ef['max_attempts_per_task']} intentos")
    restante = ef["total_budget_usd"] - cont.get("gasto_usd", 0)
    if restante <= 0:
        return fail_exit(6, f"presupuesto total agotado ({cont.get('gasto_usd', 0):.2f} de {ef['total_budget_usd']} USD)")
    if cont.get("inicio_ts") and (time.time() - cont["inicio_ts"]) / 60 >= ef["max_duration_min"]:
        return fail_exit(6, f"duracion maxima del plan alcanzada ({ef['max_duration_min']} min)")
    repo_ruta = repos.repo_path(tarea["repo"])
    if not repos.is_repo(repo_ruta):
        return fail_exit(3, f"la ruta del repo {tarea['repo']} no es un repositorio git: {repo_ruta}")
    if not repos.is_clean(repo_ruta):
        return fail_exit(3, f"el repo {tarea['repo']} tiene cambios sin commitear: se necesita el arbol limpio")
    lectura_extra = [repos.repo_path(r) for r in (tarea.get("contexto") or {}).get("repos_lectura", []) if r != tarea["repo"]]
    # --- preparacion (a partir de aqui se modifican cosas) ---
    rama, err = prepare_branch(plan, tarea, repo_ruta)
    if err:
        return fail_exit(3, err)
    if tarea["estado"] == "pendiente":
        state.transition_task(pid, tid, "lista", "script", "dependencias cumplidas")
    intento = tarea["intentos"] + 1
    state.update_json(os.path.join(state.plan_dir(pid), "tareas", f"{tid}.json"), lambda o: o.update(intentos=intento))
    snapshot.save(pid, tid, intento, "antes")
    logs = os.path.join(state.plan_dir(pid), "logs")
    os.makedirs(logs, exist_ok=True)
    mensajes = inbox.for_task(pid, tarea)
    prompt = build_prompt(plan, tarea, intento, repo_ruta, ef, rama, mensajes)
    with open(os.path.join(logs, f"{tid}.{intento}.prompt.md"), "w", encoding="utf-8") as f:
        f.write(prompt)
    if mensajes:                                                         # entrega registrada: en el estado del plan y en cada mensaje
        fallos = [m["id"] for m in mensajes if not inbox.mark("delivered", m["id"], tarea["repo"], pid, tid)[0]]
        state.log_event(pid, "script", "mensajes_entregados", tid, f"{len(mensajes)} mensajes al worker", ids=[m["id"] for m in mensajes], sin_marcar=fallos)
        if fallos:
            print(f"WARN|mensajes|entrega no anotada en la mensajería para {len(fallos)} mensajes (¿arkana-messaging instalada?)", file=sys.stderr)
    with open(os.path.join(PLUGIN, "schemas", "informe.schema.json"), encoding="utf-8") as f:
        esquema = json.dumps(json.load(f), ensure_ascii=False)
    presupuesto = round(max(0.01, min(ef["budget_usd"], restante)), 4)
    tools = "Read,Glob,Grep" if tarea["perfil"] == "lectura" else "Read,Edit,Write,Glob,Grep"
    claude = os.environ.get("ARKANA_AGENTIC_CLAUDE_BIN", "claude")
    args = [claude, "-p", prompt, "--output-format", "json", "--json-schema", esquema, "--restricted",
            "--permission-mode", "dontAsk", "--permission-prompts", "none", "--tools", tools,
            "--disallowedTools", "Agent", "WebSearch", "Skill",
            "--settings", json.dumps(worker_settings(repo_ruta, tarea["perfil"], lectura_extra, (tarea.get("autorizado") or {}).get("rutas_protegidas", []))),
            "--append-system-prompt-file", os.environ.get("ARKANA_AGENTIC_RULES_FILE") or os.path.join(PLUGIN, "templates", "worker-rules.md"),   # el override es solo para pruebas (modo adversario)
            "--max-turns", str(int(ef["max_turns"])), "--max-budget-usd", str(presupuesto), "--no-session-persistence"]
    for d in lectura_extra:
        args += ["--add-dir", d]
    if os.environ.get("ARKANA_AGENTIC_MODEL"):
        args += ["--model", os.environ["ARKANA_AGENTIC_MODEL"]]
    if os.environ.get("ARKANA_AGENTIC_EFFORT"):
        args += ["--effort", os.environ["ARKANA_AGENTIC_EFFORT"]]
    cmd = ["timeout", "--kill-after=10", str(int(ef["timeout_s"]))] + args
    ruta_salida, ruta_error = os.path.join(logs, f"{tid}.{intento}.salida.log"), os.path.join(logs, f"{tid}.{intento}.error.log")
    state.ensure_base_dir()
    os.makedirs(state.run_dir(), exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, _signal_handler)
    inicio = time.time()
    with open(ruta_salida, "wb") as so, open(ruta_error, "wb") as se:
        env = dict(os.environ, NO_COLOR="1", ARKANA_WORKER="1")
        proc = subprocess.Popen(cmd, cwd=repo_ruta, stdin=subprocess.DEVNULL, stdout=so, stderr=se, start_new_session=True, env=env)
        _signal_state["pgid"] = proc.pid
        worker = {"pid": proc.pid, "pgid": proc.pid, "plan": pid, "tarea": tid, "intento": intento, "inicio": state.now_iso(),
                  "inicio_ts": inicio, "owner_pid": detect_owner(), "launcher_pid": os.getpid(),
                  "marcador": os.path.basename(claude), "limite_s": int(ef["timeout_s"]) + 15, "repo": tarea["repo"]}
        state.save_json(os.path.join(state.run_dir(), "worker.json"), worker)
        state.transition_task(pid, tid, "en_curso", "script", f"worker lanzado (intento {intento}, pid {proc.pid}, rama {rama})")
        state.add_counter(pid, "tareas_lanzadas")
        subprocess.Popen([sys.executable, os.path.join(HERE, "watchdog.py")], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, env=dict(os.environ))
        rc = proc.wait()
    dur = round(time.time() - inicio, 1)
    # --- despues de la ejecucion ---
    matada = None
    try:
        k = state.load_json(os.path.join(state.run_dir(), "killed.json"))
        if k.get("pid") == proc.pid:
            matada = k.get("motivo")
    except (FileNotFoundError, ValueError):
        pass
    if _signal_state["recibida"] and not matada:
        matada = "senal_al_lanzador"
    salida, texto = json_from_output(ruta_salida)
    try:
        with open(ruta_error, encoding="utf-8", errors="replace") as f:
            cola_error = f.read()[-500:]
    except OSError:
        cola_error = ""
    snapshot.save(pid, tid, intento, "despues")
    raw = {"intento": intento, "exit_code": rc, "killed_by": matada, "duracion_s": dur, "salida_json": salida,
           "salida_texto_inicio": None if salida else texto[:500], "stderr_cola": cola_error, "rama": rama}
    state.save_json(os.path.join(state.plan_dir(pid), "informes", f"{tid}.{intento}.raw.json"), raw)
    if salida and isinstance(salida.get("total_cost_usd"), (int, float)):
        state.add_counter(pid, "gasto_usd", float(salida["total_cost_usd"]))
    for f in ("worker.json", "killed.json") + (("STOP-FORCE",) if matada == "stop_force" else ()):
        try:
            os.unlink(os.path.join(state.run_dir(), f))
        except FileNotFoundError:
            pass
    if matada == "stop_force":
        state.transition_task(pid, tid, "cancelada", "script", "parada forzosa del worker")
        print(f"OK|launch|{tid} cancelada por stop --force ({dur}s)")
        return 7
    if matada in ("dueno_muerto", "senal_al_lanzador", "tiempo_watchdog"):
        state.transition_task(pid, tid, "interrumpida", "script", f"worker detenido: {matada}")
        print(f"OK|launch|{tid} interrumpida ({matada}, {dur}s)")
        return 0
    state.render_status_line(pid)
    print(f"OK|launch|{tid} intento {intento} termino (exit {rc}, {dur}s); falta 'finish'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
