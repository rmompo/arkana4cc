#!/usr/bin/env python3
"""agentic.sh: plano de control de arkana-agentic. El modelo propone; este script valida y aplica (maquina de estados y limites).

  plan new <fichero> | show | validate | approve | start        crear, ver, validar, aprobar (hash) e iniciar un plan
  next                    proxima tarea ejecutable, o por que no la hay (puede cerrar el plan o abrir un gate)
  launch <T> | finish <T> lanzar el worker de una tarea | interpretar y verificar su resultado
  act <accion> [<T>]      decision del orquestador: continue | retry | split | investigate | escalate | skip | stop
  status | log <T>        estado legible (o --json) | salida y verificacion de una tarea
  stop [--force] | pause | resume    parada suave, forzosa, pausa y reanudacion
  retry <T> | skip <T>    reintento u omision manual (usuario)
  approve <G> | reject <G>           resolver un gate (parada obligatoria)
  costs [--plan --session --component --since --by plan|session|component|day --purge]   costes del libro de planes y sesiones
  totals                  gasto acumulado de todos los planes y de todas las sesiones de Claude (solo consulta)
  fix [--dry-run] [--task T --action retry|discard]   migra el layout, limpia restos y recupera tareas interrumpidas (antes `recover`)
  install [--dry-run]     carpetas, bloque `arkana:agentic` en el CLAUDE.md de ARKANA y plugin habilitado
  archive | integrate | policy | check (antes `doctor`)
Opciones comunes: --plan <id> (por defecto el plan actual) y --json.
Codigos de salida: 0 ok, 1 error, 2 uso, 3 precondicion, 4 violacion, 5 esperando usuario, 6 limite, 7 detenido/pausado.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import commitmsg  # noqa: E402
import inbox  # noqa: E402
import launch  # noqa: E402
import matchers  # noqa: E402
import paths  # noqa: E402
import repos  # noqa: E402
import snapshot  # noqa: E402
import state  # noqa: E402
import validate  # noqa: E402
import verify  # noqa: E402

OK, ERR, USO, PRE, VIOL, ESPERA, LIM, PARADO = 0, 1, 2, 3, 4, 5, 6, 7
TERMINAL_TASK_STATES = {"completada", "fallida_definitiva", "omitida", "cancelada"}
DECISION_PENDING_STATES = {"rechazada", "parcial", "fallida", "interrumpida"}
ASKS_TO_RUN = re.compile(r"\b(ejecuta(r)?|corre|lanza|run)\b[^.\n]{0,60}\b(npm|ng|git|test|tests|lint|build|comando|verificaci[oó]n|v\d+)\b", re.I)
GATE_REASONS = ["permiso", "herramienta", "dato", "decision", "ruta_protegida", "violacion", "limite", "checkpoint", "plan_modificado", "push", "error"]


# ---------- utilidades ----------
def format_decimal(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def emit(a, datos, humano):
    print(json.dumps(datos, ensure_ascii=False, indent=2) if getattr(a, "json", False) else humano)


def fail_exit(msg, cod=ERR):
    print(f"FAIL|agentic|{msg}")
    return cod


def load_schema(n):
    return state.load_json(os.path.join(state.PLUGIN, "schemas", f"{n}.schema.json"))


def plan_path(pid, *p):
    return os.path.join(state.plan_dir(pid), *p)


def resolve_plan(a):
    if getattr(a, "plan", None):
        return a.plan
    try:
        with open(state.actual_file(), encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        raise KeyError("no hay plan actual: usa --plan <id> o crea uno con 'plan new'")


def load_plan(pid):
    return state.load_json(plan_path(pid, "plan.json")), state.load_tasks(pid)


def save_task(pid, t):
    state.save_json(plan_path(pid, "tareas", f"{t['id']}.json"), t)


def worker_info(pid=None):
    w = launch.live_worker()
    return w if w and (pid is None or w.get("plan") == pid) else None


def effective_limits_of(plan, tarea=None):
    return state.effective_limits(state.load_policy(), plan.get("politica"), (tarea or {}).get("limites"))


def last_verification(pid, t):
    ruta = plan_path(pid, "verificacion", f"{t['id']}.{t['intentos']}.json")
    return state.load_json(ruta) if os.path.exists(ruta) else None


def read_lines(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


def plan_branch_name(plan, rid):
    """Nombre de la rama de trabajo del plan (arkana-worker/<plan>; los planes anteriores usaron m3a/<plan>) en el repo, o None si el plan aun no ha lanzado ninguna tarea alli."""
    return ((plan.get("ramas") or {}).get(rid) or {}).get("nombre")


def discard_changes(plan, t):
    """Vuelve el repo al ultimo commit de la rama del plan (descarta el trabajo no commiteado de un intento; lo ya aceptado, que esta commiteado, se conserva)."""
    rama = plan_branch_name(plan, t["repo"])
    if not rama:
        return True, ""                                             # la tarea nunca llego a lanzarse
    repo = repos.repo_path(t["repo"])
    if repos.current_branch(repo) != rama:
        return False, f"el repo {t['repo']} no esta en la rama del plan ({rama})"
    x = repos.git(repo, "reset", "--hard", "HEAD")
    y = repos.git(repo, "clean", "-fd")
    return (x.returncode == 0 and y.returncode == 0), (x.stderr + y.stderr).strip()[:200]


# ---------- validacion de planes ----------
def validate_plan(plan, tareas):
    errs, avisos = [], []
    errs += [f"plan: {e}" for e in validate.check_schema(plan, load_schema("plan"))]
    ids = {t["id"] for t in tareas}
    for t in tareas:
        errs += [f"{t.get('id')}: {e}" for e in validate.check_schema(t, load_schema("tarea"))]
    if set(plan.get("tareas", [])) != ids:
        errs.append("las tareas del plan no coinciden con los ficheros de tareas")
    for t in tareas:
        for d in t.get("depende_de", []):
            if d not in ids:
                errs.append(f"{t['id']}: depende de {d}, que no existe")
        vids = {v["id"] for v in t.get("verificaciones", [])}
        for c in t.get("criterios_aceptacion", []):
            if c.get("verificacion") and c["verificacion"] not in vids:
                errs.append(f"{t['id']}: el criterio {c['id']} usa la verificacion '{c['verificacion']}', que no esta definida")
        if t["perfil"] == "lectura" and t.get("rutas_permitidas"):
            avisos.append(f"{t['id']}: un worker de lectura no necesita rutas_permitidas")
        if t["perfil"] == "edicion" and t["tipo"] != "tarea":
            errs.append(f"{t['id']}: las tareas de tipo {t['tipo']} deben usar el perfil lectura")
        pat = state.load_protected_paths(t["repo"])["patrones"]
        for rp in t.get("rutas_permitidas", []):
            if matchers.is_protected_path(rp.replace("**", "x").replace("*", "x"), pat):
                avisos.append(f"{t['id']}: la ruta permitida '{rp}' cae en una ruta protegida")
        if t["perfil"] == "edicion" and ASKS_TO_RUN.search(" ".join(t.get("instrucciones", []))):
            avisos.append(f"{t['id']}: una instruccion parece pedir al worker que ejecute comandos o verificaciones; no tiene shell: las verificaciones las ejecuta el script")
        permitidos = state.load_allowed_commands({x["repo"] for x in tareas})
        for v in t.get("verificaciones", []):
            if not matchers.is_allowed_command(v["comando"], permitidos):
                avisos.append(f"{t['id']}: la verificacion '{v['id']}' ({' '.join(v['comando'])}) no esta en la lista cerrada: abrira un gate")
    informativas = {v["id"]: v for t in tareas for v in t.get("verificaciones", []) if matchers.is_informative_check(v["comando"])}
    for t in tareas:
        vm = {v["id"]: v for v in t.get("verificaciones", [])}
        for c in t.get("criterios_aceptacion", []):
            v = vm.get(c.get("verificacion"))
            if v and matchers.is_informative_check(v["comando"]):
                avisos.append(f"{t['id']}: el criterio {c['id']} apunta a '{' '.join(v['comando'])}', que siempre termina con exito y no comprueba nada: se tratara como autoevaluado (quita la verificacion del criterio)")
    ediciones = {}
    for t in tareas:
        if t["perfil"] == "edicion":
            ediciones.setdefault(t["repo"], []).append(t["id"])
    if not (plan.get("autoriza") or {}).get("commits_locales", False):
        for repo, ids in ediciones.items():
            if len(ids) > 1:
                errs.append(f"commits_locales es false y el repo {repo} tiene {len(ids)} tareas de edicion ({', '.join(ids)}): el trabajo de la primera quedaria sin commitear y las siguientes no podrian lanzarse (el repo debe estar limpio)")
        if ediciones:
            avisos.append("commits_locales es false: el trabajo queda SIN commitear en la rama del plan, y 'integrate merge' no podra integrarlo; "
                          "casi siempre conviene true (el commit es local, en la rama arkana-worker/<plan>; develop no se toca y no hay push)")
    # ciclos
    estado = {}

    def visita(x, por):
        if estado.get(x) == 1:
            errs.append("ciclo de dependencias en " + " -> ".join(por + [x]))
            return
        if estado.get(x) == 2:
            return
        estado[x] = 1
        t = next((q for q in tareas if q["id"] == x), None)
        for d in (t or {}).get("depende_de", []):
            if d in ids:
                visita(d, por + [x])
        estado[x] = 2
    for t in tareas:
        visita(t["id"], [])
    pol = state.load_policy()
    ef = effective_limits_of(plan)
    if len(tareas) > ef["max_tasks"]:
        errs.append(f"el plan tiene {len(tareas)} tareas y el maximo efectivo es {int(ef['max_tasks'])}")
    for k, v in (plan.get("politica") or {}).items():
        tope = pol["techos"].get(state.LIMIT_ALIASES.get(k, k))
        if tope is not None and v > tope:
            avisos.append(f"politica del plan: {k}={v} supera el techo {tope}; se aplicara el techo")
    for t in tareas:
        if not repos.repo_known(t["repo"]):
            errs.append(f"{t['id']}: repo desconocido {t['repo']}")
        elif not repos.is_repo(repos.repo_path(t["repo"])):
            avisos.append(f"{t['id']}: la ruta del repo {t['repo']} no es un repositorio git ({repos.repo_path(t['repo'])})")
    return errs, avisos


def show_validation(errs, avisos):
    for e in errs:
        print(f"FAIL|validar|{e}")
    for w in avisos:
        print(f"WARN|validar|{w}")
    if not errs:
        print(f"OK|validar|plan valido ({len(avisos)} avisos)")


# ---------- plan ----------
def cmd_plan(a):
    acc = a.accion
    if acc == "new":
        de_mensaje = getattr(a, "de_mensaje", None) or []
        if a.fichero:
            try:
                spec = state.load_json(a.fichero)
            except (FileNotFoundError, ValueError) as e:
                return fail_exit(f"no se pudo leer {a.fichero}: {e}")
        else:                                                            # sin fichero: el plan sale de los mensajes (--from-message)
            spec, err = plan_spec_from_messages(a)
            if err:
                return fail_exit(err, USO)
        pid = state.new_plan_id()
        lista = spec.get("tareas") or []
        ids = [f"T{i:03d}" for i in range(1, len(lista) + 1)]
        tareas = []
        for tid, ts in zip(ids, lista):
            t = {"version": 1, "tipo": "tarea", "estado": "pendiente", "intentos": 0, "feedback": [], "historial": []}
            t.update(ts)
            t.update(id=tid, plan=pid)
            t.setdefault("perfil", "edicion" if t["tipo"] == "tarea" else "lectura")
            tareas.append(t)
        if de_mensaje and a.fichero:                                     # plan con fichero + --from-message: el mensaje se entrega a las tareas de sus destinatarios
            msgs = inbox.load_all()
            for mid in de_mensaje:
                m = msgs.get(mid)
                if m is None or m.get("estado") in inbox.HIDDEN:
                    return fail_exit(f"el mensaje {mid} no existe o está dado de baja", USO)
                destino = [t for t in tareas if inbox.check_for(mid, t["repo"], msgs)[1] is None]
                if not destino:
                    return fail_exit(f"el mensaje {mid} no va dirigido al repo de ninguna tarea del plan ({', '.join(sorted({t['repo'] for t in tareas}))})", USO)
                for t in destino:
                    if mid not in inbox.extras(t):
                        t["mensajes_extra"] = inbox.extras(t) + [mid]
                        t.setdefault("feedback", []).append(inbox.pointer(m))
            if not spec.get("peticion"):
                spec["peticion"] = "Atender " + ", ".join(f"{i} («{' '.join(str(msgs[i].get('asunto', '')).split())[:80]}»)" for i in de_mensaje)
        autoriza = dict({"commits_locales": True}, **spec.get("autoriza", {}))
        autoriza.setdefault("rama", repos.plan_branch(pid))
        plan = {"id": pid, "version": 1, "asunto": spec.get("asunto", ""), "peticion": spec.get("peticion", ""), "estado": "borrador",
                "autoriza": autoriza, "politica": spec.get("politica", {}), "tareas": ids, "contadores": {}, "gate": None,
                "creado": state.now_iso(), "aprobado": None, "historial": []}
        errs, avisos = validate_plan(plan, tareas)
        show_validation(errs, avisos)
        if errs:
            return ERR
        state.save_json(plan_path(pid, "plan.json"), plan)
        for t in tareas:
            save_task(pid, t)
        state.ensure_base_dir()
        with open(state.actual_file(), "w", encoding="utf-8") as f:
            f.write(pid + "\n")
        state.log_event(pid, "orchestrator", "plan_creado", None, plan["asunto"][:120])
        print(f"OK|plan|{pid} creado con {len(tareas)} tareas (borrador); falta aprobarlo")
        return OK
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    if acc == "validate":
        errs, avisos = validate_plan(plan, tareas)
        show_validation(errs, avisos)
        return ERR if errs else OK
    if acc == "show":
        ef = effective_limits_of(plan)
        l = [f"Plan {pid} · «{plan['asunto']}» · estado: {plan['estado']}", f"Peticion: {plan['peticion'][:300]}",
             f"Autoriza: commits locales={plan['autoriza'].get('commits_locales')} · rama {plan['autoriza'].get('rama')} en cada repo",
             "Limites efectivos: " + ", ".join(f"{k}={format_decimal(v) if isinstance(v, float) else v}" for k, v in ef.items()), ""]
        for t in tareas:
            l += [f"{t['id']} [{t['estado']}] {t['asunto']}", f"   repo {t['repo']} · {t['tipo']}/{t['perfil']} · depende de {t.get('depende_de') or '-'}",
                  f"   objetivo: {t['objetivo']}"] + [f"   {i}" for i in t["instrucciones"]]
            l += [f"   criterio {c['id']}: {c['descripcion']}" + (f" (verifica: {c['verificacion']})" if c.get("verificacion") else "")
                  for c in t["criterios_aceptacion"]]
            ms = inbox.listing(pid, t)
            l += ([f"   mensajes que recibirá el worker ({len(ms)}):"] + [f"     - {inbox.one_line(m)}" for m in ms]) if ms else []
            l += [""]
        emit(a, {"plan": plan, "tareas": tareas}, "\n".join(l))
        return OK
    if acc == "approve":
        if plan["estado"] != "borrador":
            return fail_exit(f"el plan esta en '{plan['estado']}': solo se aprueba un borrador", PRE)
        errs, avisos = validate_plan(plan, tareas)
        show_validation(errs, avisos)
        if errs:
            return ERR
        h = state.approve_plan(pid, "user")
        print(f"OK|plan|{pid} aprobado (hash {h[:12]})")
        return OK
    if acc == "start":
        if plan["estado"] != "aprobado" or not state.plan_approval_ok(pid):
            return fail_exit("el plan debe estar aprobado y sin alteraciones", PRE)
        state.start_plan(pid)
        lista = inbox.freeze(pid, tareas)
        n = sum(len(v) for v in lista.values())
        print(f"OK|plan|{pid} en ejecucion" + (f" ({n} entregas de mensajes congeladas)" if n else ""))
        return OK
    return USO


# ---------- next ----------
def cmd_next(a):
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    run = state.run_dir()
    marca = lambda n: os.path.exists(os.path.join(run, n))
    w = worker_info()

    def res(estado, **kw):
        d = dict({"estado": estado, "plan": pid}, **kw)
        emit(a, d, f"{estado}" + "".join(f" · {k}={v}" for k, v in kw.items() if not isinstance(v, (dict, list))))
        return {"tarea": OK, "terminado": OK, "gate": ESPERA, "pausado": PARADO, "limite": LIM, "worker_en_curso": OK}.get(estado, PRE if estado.startswith(("worker", "fix", "falta", "no_")) else OK)

    if plan["estado"] in state.TERMINAL_PLAN_STATES:
        return res("terminado", detalle=plan["estado"])
    if plan["estado"] == "esperando_usuario":
        return res("gate", gate=plan.get("gate"))
    if plan["estado"] == "pausado":
        return res("pausado")
    if plan["estado"] != "en_ejecucion":
        return res("no_iniciado", detalle=plan["estado"])
    if w and w.get("plan") == pid:
        return res("worker_en_curso", tarea=w["tarea"], pid_worker=w["pid"])
    if marca("PAUSE") or marca("STOP"):
        for n in ("PAUSE", "STOP"):
            if marca(n):
                os.unlink(os.path.join(run, n))
        state.transition_plan(pid, "pausado", "user", "parada suave solicitada")
        return res("pausado")
    sin_informe = [t["id"] for t in tareas if t["estado"] == "en_curso"]
    if sin_informe:
        return res("fix" if not os.path.exists(plan_path(pid, "informes", f"{sin_informe[0]}.{next(t for t in tareas if t['id'] == sin_informe[0])['intentos']}.raw.json")) else "falta_finish", tareas=sin_informe)
    if any(t["estado"] == "verificando" for t in tareas):
        return res("falta_finish", tareas=[t["id"] for t in tareas if t["estado"] == "verificando"])
    ef = effective_limits_of(plan)
    c = plan.get("contadores", {})
    if c.get("gasto_usd", 0) >= ef["total_budget_usd"]:
        state.open_gate(pid, "limite", f"presupuesto total agotado ({format_decimal(c.get('gasto_usd', 0))} de {format_decimal(ef['total_budget_usd'])} USD)", ["subir el limite en tu politica local", "detener"], reanuda="continue")
        return res("limite", motivo="presupuesto_total")
    if c.get("inicio_ts") and (time.time() - c["inicio_ts"]) / 60 >= ef["max_duration_min"]:
        state.open_gate(pid, "limite", f"duracion maxima del plan ({int(ef['max_duration_min'])} min)", ["ampliar el limite", "detener"], reanuda="continue")
        return res("limite", motivo="duracion")
    if all(t["estado"] in ("completada", "omitida") for t in tareas):
        state.transition_plan(pid, "completado", "script", "todas las tareas completadas u omitidas")
        return res("terminado", detalle="completado")
    t = state.next_task(tareas)
    if t is None:
        pend = [x["id"] for x in tareas if x["estado"] in DECISION_PENDING_STATES or x["estado"] in ("bloqueada", "esperando_usuario")]
        if pend:
            return res("decision_pendiente", tareas=pend)
        state.transition_plan(pid, "fallido", "script", "no quedan tareas ejecutables (dependencias fallidas u omitidas)")
        return res("terminado", detalle="fallido")
    cada = int(ef["checkpoint_every"])
    hechas = sum(1 for x in tareas if x["estado"] == "completada")
    if cada > 0 and hechas - c.get("checkpoint_hecho", 0) >= cada:
        state.update_json(plan_path(pid, "plan.json"), lambda o: o.setdefault("contadores", {}).__setitem__("checkpoint_hecho", hechas))
        state.open_gate(pid, "checkpoint", f"{hechas} tareas completadas; confirma que se sigue", ["continuar", "detener"], reanuda="continue")
        return res("gate", gate=load_plan(pid)[0].get("gate"))
    return res("tarea", tarea=t["id"], repo=t["repo"], asunto=t["asunto"], perfil=t["perfil"])


# ---------- act ----------
def cmd_act(a):
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    quien = a.quien
    acc = a.accion
    if getattr(a, "de_mensaje", None) and acc not in ("retry", "investigate"):
        return fail_exit(f"--from-message solo se admite en 'act retry' y 'act investigate', no en '{acc}'", USO)
    if acc == "stop":
        if worker_info(pid):
            return fail_exit("hay un worker vivo: usa 'stop --force'", PRE)
        state.transition_plan(pid, "detenido", quien, a.motivo or "detenido por el orquestador")
        print(f"OK|act|plan {pid} detenido")
        return OK
    if acc == "investigate":
        return act_investigate(a, pid, plan, tareas)
    if not a.tarea:
        return fail_exit(f"la accion {acc} necesita una tarea", USO)
    t = next((x for x in tareas if x["id"] == a.tarea), None)
    if not t:
        return fail_exit(f"no existe la tarea {a.tarea}")
    ver = last_verification(pid, t)
    if quien != "user" and ver and acc in ("retry", "split", "escalate", "skip") and acc not in ver.get("acciones_permitidas", []):
        return fail_exit(f"la accion '{acc}' no esta permitida tras un resultado '{ver['veredicto']}' (permitidas: {', '.join(ver.get('acciones_permitidas', []))})", PRE)
    if acc == "continue":
        return act_continue(a, pid, plan, t)
    if acc == "retry":
        if t["estado"] not in DECISION_PENDING_STATES:
            return fail_exit(f"la tarea esta en '{t['estado']}': solo se reintenta una rechazada, parcial, fallida o interrumpida", PRE)
        ef = effective_limits_of(plan, t)
        if t["intentos"] >= ef["max_attempts_per_task"]:
            return fail_exit(f"la tarea ya uso sus {int(ef['max_attempts_per_task'])} intentos: hay que usar 'escalate', 'split' o 'skip'", LIM)
        if quien != "user" and ver and ver.get("motivo") == _previous_reason(pid, t):
            return fail_exit(f"misma causa que el intento anterior ('{ver['motivo']}'): no se repite; hay que usar 'escalate'", LIM)
        if getattr(a, "de_mensaje", None):                                # antes de tocar nada: si el mensaje no vale, la tarea queda como estaba
            err = attach_messages(pid, t, a.de_mensaje, quien)
            if err:
                return fail_exit(err, PRE)
        ok, err = discard_changes(plan, t)
        if not ok:
            return fail_exit(err, PRE)
        if a.feedback_file:
            t.setdefault("feedback", []).append(open(a.feedback_file, encoding="utf-8").read().strip()[:4000])
        save_task(pid, t)
        state.transition_task(pid, t["id"], "lista", quien, a.motivo or "reintento")
        print(f"OK|act|{t['id']} lista para reintentar (intento {t['intentos'] + 1})")
        return OK
    if acc == "skip":
        if t["estado"] in TERMINAL_TASK_STATES or t["estado"] in ("en_curso", "verificando"):
            return fail_exit(f"la tarea esta en '{t['estado']}'", PRE)
        discard_changes(plan, t)
        state.transition_task(pid, t["id"], "omitida", quien, a.motivo or "omitida")
        print(f"OK|act|{t['id']} omitida")
        return OK
    if acc == "escalate":
        if t["estado"] not in DECISION_PENDING_STATES | {"bloqueada"}:
            return fail_exit(f"la tarea esta en '{t['estado']}'", PRE)
        if t["estado"] != "bloqueada" or True:
            if t["estado"] != "bloqueada":
                state.transition_task(pid, t["id"], "esperando_usuario", quien, a.motivo or "escalada")
        state.open_gate(pid, a.gate or "decision", a.detalle or a.motivo or "el orquestador escala la decision", ["reintentar con tu indicacion", "omitir", "detener"], quien, tarea=t["id"], reanuda="retry")
        print(f"OK|act|{t['id']} escalada al usuario")
        return ESPERA
    if acc == "split":
        return act_split(a, pid, plan, tareas, t)
    return USO


def _previous_reason(pid, t):
    if t["intentos"] < 2:
        return None
    ruta = plan_path(pid, "verificacion", f"{t['id']}.{t['intentos'] - 1}.json")
    return state.load_json(ruta).get("motivo") if os.path.exists(ruta) else None


def plan_spec_from_messages(a):
    """Plan (dict como el de `plan new <fichero>`) con una tarea de edición por mensaje y componente destinatario, con sus instrucciones y criterios copiados del
    mensaje. Necesita `--paths` (las rutas que puede editar el worker) y, si el mensaje va a varios componentes, `--repo`. -> (spec, None) | (None, error)."""
    ids = getattr(a, "de_mensaje", None) or []
    if not ids:
        return None, "plan new necesita un fichero o --from-message"
    if not getattr(a, "rutas", None):
        return None, "plan new sin fichero necesita --paths: las rutas que el worker puede editar (p. ej. --paths 'src/**')"
    msgs = inbox.load_all()
    tareas = []
    for mid in dict.fromkeys(ids):
        m = msgs.get(mid)
        if m is None or m.get("estado") in inbox.HIDDEN:
            return None, f"el mensaje {mid} no existe o está dado de baja"
        destinos = list(a.repos or inbox.recipients(m))
        if not a.repos and len(destinos) != 1:
            return None, f"el mensaje {mid} va a {len(destinos)} componentes ({', '.join(destinos) or '-'}): indica --repo (una vez por componente)"
        for r in destinos:
            _, err = inbox.check_for(mid, r, msgs)
            if err:
                return None, err
            tareas.append({"asunto": str(m["asunto"])[:80], "repo": r, "tipo": "tarea", "objetivo": str(m["asunto"]), "instrucciones": inbox.instruction_lines(m),
                           "criterios_aceptacion": inbox.criteria_of(m), "rutas_permitidas": list(a.rutas), "mensajes_extra": [mid], "feedback": [inbox.pointer(m)]})
    unicos = list(dict.fromkeys(ids))
    asunto = str(msgs[unicos[0]]["asunto"])[:80] if len(unicos) == 1 else f"Atender {len(unicos)} mensajes"
    peticion = "Atender " + ", ".join(f"{i} («{' '.join(str(msgs[i].get('asunto', '')).split())[:80]}»)" for i in unicos)
    return {"asunto": asunto, "peticion": peticion, "tareas": tareas}, None


def attach_messages(pid, t, ids, quien, feedback=True):
    """`--from-message`: valida que cada mensaje existe y va dirigido al componente de la tarea y los registra en `mensajes_extra` (se entregan como los de la
    lista congelada). Con `feedback`, añade al feedback del worker la línea que le pide atenderlos. Devuelve un error (texto) o None; no cambia nada si falla."""
    msgs = inbox.load_all()
    nuevos = []
    for i in ids:
        m, err = inbox.check_for(i, t["repo"], msgs)
        if err:
            return err
        if i not in inbox.extras(t) and i not in nuevos:
            nuevos.append(i)
    if not nuevos:
        return None
    t["mensajes_extra"] = inbox.extras(t) + nuevos
    if feedback:
        t.setdefault("feedback", []).extend(inbox.pointer(msgs[i]) for i in nuevos)
    save_task(pid, t)
    state.log_event(pid, quien, "mensaje_indicado", t["id"], f"{len(nuevos)} mensajes indicados a mano con --from-message", ids=nuevos)
    return None


def mark_messages_executed(pid, t):
    """Tarea aceptada: los mensajes que se le entregaron pasan a ejecutados (una sola vez por tarea)."""
    if t.get("mensajes_marcados"):
        return
    ids = inbox.ids_for(pid, t)
    fallos = [i for i in ids if not inbox.mark("executed", i, t["repo"], pid, t["id"])[0]]
    if ids:
        state.log_event(pid, "script", "mensajes_ejecutados", t["id"], f"{len(ids) - len(fallos)} de {len(ids)} marcados", ids=ids, sin_marcar=fallos)
        if fallos:
            print(f"WARN|mensajes|{len(fallos)} mensajes sin marcar como ejecutados (¿arkana-messaging instalada?)")
    t["mensajes_marcados"] = True
    save_task(pid, t)


def act_continue(a, pid, plan, t):
    if t["estado"] != "completada":
        return fail_exit(f"la tarea esta en '{t['estado']}': solo se continua tras una completada", PRE)
    mark_messages_executed(pid, t)
    if not plan["autoriza"].get("commits_locales") or t.get("commit"):
        motivo = "ya hecho" if t.get("commit") else "el plan no autoriza commits locales"
        state.log_event(pid, a.quien, "continue", t["id"], f"sin commit: {motivo}")
        print(f"OK|act|{t['id']} continue (sin commit: {motivo})")
        return OK
    if not a.mensaje:
        return fail_exit("el plan autoriza commits locales: falta --message con el mensaje del commit", USO)
    repo = repos.repo_path(t["repo"])
    rama = plan_branch_name(plan, t["repo"])
    if not rama or repos.current_branch(repo) != rama:
        return fail_exit(f"el repo no esta en la rama del plan ({rama})", PRE)
    email = repos.git(repo, "config", "user.email").stdout.strip()
    errs = commitmsg.check_message(t["repo"], a.mensaje, email)
    if errs:
        for e in errs:
            print(f"FAIL|commit|{e}")
        return ERR
    ver = last_verification(pid, t) or {}
    rutas = [p for p in ver.get("rutas_cambiadas", []) if repos.git(repo, "check-ignore", "-q", p).returncode != 0]
    if rutas:
        x = repos.git(repo, "add", "-A", "--", *rutas)
        if x.returncode:
            return fail_exit("git add fallo: " + x.stderr.strip()[:200])
    if repos.git(repo, "diff", "--cached", "--quiet").returncode == 0:
        state.log_event(pid, a.quien, "continue", t["id"], "sin commit: no hay nada que commitear")
        print(f"OK|act|{t['id']} continue (no hay nada que commitear)")
        return OK
    c = repos.git(repo, "commit", "-m", a.mensaje)
    if c.returncode:
        return fail_exit("el commit fue rechazado (hooks del repo): " + (c.stdout + c.stderr).strip()[-300:])
    t["commit"] = repos.head(repo)
    save_task(pid, t)
    state.log_event(pid, a.quien, "commit_local", t["id"], a.mensaje[:120], sha=t["commit"])
    print(f"OK|act|{t['id']} commit {t['commit'][:10]} en {rama}")
    return OK


def _new_task(pid, n, spec):
    t = {"version": 1, "tipo": "tarea", "estado": "pendiente", "intentos": 0, "feedback": [], "historial": []}
    t.update(spec)
    t.update(id=f"T{n:03d}", plan=pid)
    t.setdefault("perfil", "edicion" if t["tipo"] == "tarea" else "lectura")
    return t


def _plan_change(a, pid, plan, tareas, nuevas, motivo_gate, silencioso=False):
    ef = effective_limits_of(plan)
    usados = plan.get("contadores", {}).get("cambios_plan", 0)
    if usados + 1 > ef["max_plan_changes"]:
        return fail_exit(f"limite de cambios de plan alcanzado ({int(usados)} de {int(ef['max_plan_changes'])})", LIM)
    errs, _ = validate_plan(dict(plan, tareas=[t["id"] for t in tareas] + [n["id"] for n in nuevas]), tareas + nuevas)
    if errs:
        for e in errs:
            print(f"FAIL|validar|{e}")
        return ERR
    for n in nuevas:
        save_task(pid, n)
    def aplicar(o):
        o["tareas"] = o["tareas"] + [n["id"] for n in nuevas]
        o.setdefault("contadores", {})["cambios_plan"] = usados + 1
    state.update_json(plan_path(pid, "plan.json"), aplicar)
    return None


def act_split(a, pid, plan, tareas, t):
    if t["estado"] not in DECISION_PENDING_STATES | {"pendiente"}:
        return fail_exit(f"la tarea esta en '{t['estado']}'", PRE)
    if not a.tareas_file:
        return fail_exit("split necesita --tasks-file con la lista de tareas nuevas", USO)
    specs = state.load_json(a.tareas_file)
    n0 = max(int(x["id"][1:]) for x in tareas)
    nuevas = [_new_task(pid, n0 + i + 1, s) for i, s in enumerate(specs)]
    for i, n in enumerate(nuevas):
        n.setdefault("depende_de", list(t.get("depende_de", [])) if i == 0 else [nuevas[i - 1]["id"]])
        n["repo"] = n.get("repo", t["repo"])
    ultimo = nuevas[-1]["id"]
    otras = [x for x in tareas if x["id"] != t["id"]]
    for o in otras:
        if t["id"] in o.get("depende_de", []) and o["estado"] not in TERMINAL_TASK_STATES:
            o["depende_de"] = [ultimo if d == t["id"] else d for d in o["depende_de"]]
    r = _plan_change(a, pid, plan, tareas, nuevas, "plan_modificado")
    if r is not None:
        return r
    for o in otras:
        save_task(pid, o)
    discard_changes(plan, t)
    state.transition_task(pid, t["id"], "omitida", a.quien, "dividida en " + ", ".join(n["id"] for n in nuevas))
    state.open_gate(pid, "plan_modificado", f"{t['id']} dividida en {', '.join(n['id'] for n in nuevas)}", ["aprobar el plan modificado", "detener"], a.quien, reanuda="continue")
    print(f"OK|act|{t['id']} dividida en {', '.join(n['id'] for n in nuevas)}; hay que aprobar el plan modificado")
    return ESPERA


def act_investigate(a, pid, plan, tareas):
    repo, asunto, instrucciones, extra, m = a.repo, a.asunto, None, None, None
    if getattr(a, "de_mensaje", None):                                    # --from-message: asunto, repo e instrucciones salen del mensaje (si no se dan aparte)
        if len(a.de_mensaje) != 1:
            return fail_exit("investigate admite un solo --from-message", USO)
        mid = a.de_mensaje[0]
        m = inbox.load_all().get(mid)
        if m is None or m.get("estado") in inbox.HIDDEN:
            return fail_exit(f"el mensaje {mid} no existe o está dado de baja", PRE)
        if not repo:
            cand = inbox.recipients(m)
            if len(cand) != 1:
                return fail_exit(f"el mensaje {mid} va a {len(cand)} componentes ({', '.join(cand) or '-'}): indica --repo", USO)
            repo = cand[0]
        _, err = inbox.check_for(mid, repo, {mid: m})
        if err:
            return fail_exit(err, PRE)
        asunto = asunto or f"Investigar: {m['asunto']}"
        extra = [mid]
    if a.instrucciones_file:
        instrucciones = read_lines(a.instrucciones_file)
    elif m is not None:
        instrucciones = inbox.instruction_lines(m)
    if not (repo and asunto and instrucciones):
        return fail_exit("investigate necesita --repo, --subject y --instructions-file (o --from-message)", USO)
    n0 = max(int(x["id"][1:]) for x in tareas)
    nueva = _new_task(pid, n0 + 1, {"asunto": asunto[:80], "repo": repo, "tipo": "investigacion", "perfil": "lectura",
                                      "objetivo": asunto, "instrucciones": instrucciones, "rutas_permitidas": [],
                                      "criterios_aceptacion": [{"id": "C1", "descripcion": "El informe responde a lo pedido con referencias a ficheros"}]})
    if extra:                                                              # el mensaje se entrega y se marca como los demás; las instrucciones ya van copiadas en la tarea (el usuario las aprueba en el gate)
        nueva["mensajes_extra"] = extra
        nueva["feedback"] = [inbox.pointer(m)]
    if a.para:
        for x in tareas:
            if x["id"] == a.para:
                x["depende_de"] = list(x.get("depende_de", [])) + [nueva["id"]]
                save_task(pid, x)
    r = _plan_change(a, pid, plan, tareas, [nueva], "plan_modificado", True)
    if r is not None:
        return r
    if plan["autoriza"].get("investigate_without_gate"):
        with open(plan_path(pid, "plan.aprobado.sha256"), "w", encoding="utf-8") as f:
            f.write(state.approval_hash(pid) + "\n")
        state.log_event(pid, a.quien, "plan_modificado", nueva["id"], "investigacion preautorizada")
        print(f"OK|act|{nueva['id']} (investigacion) anadida sin gate: el plan lo preautorizaba")
        return OK
    state.open_gate(pid, "plan_modificado", f"se anade {nueva['id']}: {nueva['asunto']}", ["aprobar el plan modificado", "detener"], a.quien, reanuda="continue")
    print(f"OK|act|{nueva['id']} (investigacion) anadida; hay que aprobar el plan modificado")
    return ESPERA


# ---------- gates ----------
def cmd_gate(a):
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    g = plan.get("gate")
    if not g or g["gate"] != a.gate:
        return fail_exit(f"no hay un gate abierto con id {a.gate}" + (f" (el abierto es {g['gate']})" if g else ""), PRE)
    t = next((x for x in tareas if x["id"] == g.get("tarea")), None)
    quien = "user"
    if a.cmd == "reject":
        if a.stop:
            state.close_gate(pid, quien, "rechazado: se detiene el plan")
            state.transition_plan(pid, "detenido", quien, f"gate {g['gate']} rechazado")
            print(f"OK|gate|{g['gate']} rechazado; plan detenido")
            return OK
        if t and t["estado"] == "esperando_usuario":
            discard_changes(plan, t)
            state.transition_task(pid, t["id"], "omitida", quien, f"gate {g['gate']} rechazado")
        state.close_gate(pid, quien, "rechazado" + (f": {a.motivo}" if a.motivo else ""))
        print(f"OK|gate|{g['gate']} rechazado" + (f"; {t['id']} omitida" if t else ""))
        return OK
    r = g.get("reanuda", "continue")
    if r == "none":
        return fail_exit("este gate no se puede aprobar (una violacion solo admite detener): usa 'reject --stop'", PRE)
    if r == "reverify" and t:
        ver = last_verification(pid, t) or {}
        aut = t.setdefault("autorizado", {"rutas_protegidas": [], "verificaciones": []})
        aut["rutas_protegidas"] = sorted(set(aut["rutas_protegidas"]) | set(ver.get("rutas_protegidas", [])))
        aut["verificaciones"] = sorted(set(aut["verificaciones"]) | set(ver.get("comandos_no_permitidos", [])))
        save_task(pid, t)
        state.transition_task(pid, t["id"], "verificando", quien, f"gate {g['gate']} autorizado: se vuelve a verificar")
    elif r == "retry" and t:
        discard_changes(plan, t)
        if g.get("rutas"):                                    # gate ruta_protegida de una denegacion: se autoriza esa edicion para esta tarea
            aut = t.setdefault("autorizado", {"rutas_protegidas": [], "verificaciones": []})
            aut["rutas_protegidas"] = sorted(set(aut.get("rutas_protegidas", [])) | set(g["rutas"]))
        if a.nota:
            t.setdefault("feedback", []).append(f"Respuesta del usuario: {a.nota[:2000]}")
        save_task(pid, t)
        state.transition_task(pid, t["id"], "lista", quien, f"gate {g['gate']} resuelto")
    elif g["motivo"] == "plan_modificado":
        with open(plan_path(pid, "plan.aprobado.sha256"), "w", encoding="utf-8") as f:
            f.write(state.approval_hash(pid) + "\n")
    state.close_gate(pid, quien, "aprobado" + (f": {a.nota}" if a.nota else ""))
    sig = {"reverify": f"ejecuta 'finish {t['id']}'" if t else "", "retry": f"{t['id']} lista para un nuevo intento" if t else ""}.get(r, "el plan sigue")
    print(f"OK|gate|{g['gate']} aprobado; {sig}")
    return OK


# ---------- parada, pausa y reanudacion ----------
def cmd_stop(a):
    pid = resolve_plan(a)
    plan, _ = load_plan(pid)
    run = state.run_dir()
    os.makedirs(run, exist_ok=True)
    w = worker_info()
    if a.force or a.cmd == "force":
        if w:
            launch.kill_worker(w, "stop_force")
            fin = time.time() + 20
            while time.time() < fin and os.path.exists(os.path.join(run, "worker.json")):
                time.sleep(0.2)
            if os.path.exists(os.path.join(run, "worker.json")):          # el lanzador ya no esta: lo deja en orden el control
                launch.cleanup_after_kill(w, "stop_force")
            print(f"OK|stop|worker {w['pid']} ({w['plan']}/{w['tarea']}) detenido; tarea cancelada")
        else:
            print("OK|stop|no habia ningun worker vivo")
        for n in ("PAUSE", "STOP", "STOP-FORCE"):
            if os.path.exists(os.path.join(run, n)):
                os.unlink(os.path.join(run, n))
        plan = load_plan(pid)[0]
        if plan["estado"] not in state.TERMINAL_PLAN_STATES:
            state.transition_plan(pid, "detenido", "user", "stop --force")
        print(f"OK|stop|plan {pid} detenido")
        return OK
    if w:
        open(os.path.join(run, "PAUSE"), "w").close()
        print(f"OK|stop|el worker {w['pid']} terminara su tarea; despues el plan quedara pausado")
        return OK
    if plan["estado"] == "en_ejecucion":
        state.transition_plan(pid, "pausado", "user", "parada suave")
    print(f"OK|stop|plan {pid} pausado")
    return OK


def cmd_resume(a):
    pid = resolve_plan(a)
    plan, _ = load_plan(pid)
    run = state.run_dir()
    for n in ("PAUSE", "STOP"):
        if os.path.exists(os.path.join(run, n)):
            os.unlink(os.path.join(run, n))
    if plan["estado"] == "pausado":
        state.transition_plan(pid, "en_ejecucion", "user", "reanudado")
        print(f"OK|resume|plan {pid} en ejecucion")
        return OK
    print(f"OK|resume|el plan esta en '{plan['estado']}': marcas de pausa retiradas")
    return OK


# ---------- estado y log ----------
def cmd_status(a):
    try:
        pid = resolve_plan(a)
    except KeyError:
        print("Sin plan actual. Crea uno con 'plan new <fichero>'.")
        return OK
    plan, tareas = load_plan(pid)
    ef = effective_limits_of(plan)
    c = plan.get("contadores", {})
    mins = int((time.time() - c["inicio_ts"]) / 60) if c.get("inicio_ts") and plan["estado"] in state.ACTIVE_PLAN_STATES else 0
    hechas = sum(1 for t in tareas if t["estado"] == "completada")
    cada = int(ef["checkpoint_every"])
    resto = max(0, cada - (hechas - int(c.get("checkpoint_hecho", 0)))) if cada else None
    w = worker_info()
    d = {"plan": pid, "asunto": plan["asunto"], "estado": plan["estado"], "gate": plan.get("gate"),
         "gasto_usd": round(c.get("gasto_usd", 0), 4), "total_budget_usd": ef["total_budget_usd"], "minutos": mins,
         "max_duration_min": ef["max_duration_min"], "cambios_plan": int(c.get("cambios_plan", 0)), "max_plan_changes": ef["max_plan_changes"],
         "checkpoint_en": resto, "worker": w,
         "tareas": [{"id": t["id"], "repo": t["repo"], "asunto": t["asunto"], "estado": t["estado"], "intentos": t["intentos"],
                     "max_attempts": effective_limits_of(plan, t)["max_attempts_per_task"], "commit": t.get("commit")} for t in tareas]}
    l = [f"Plan {pid} · «{plan['asunto']}»{' ' * 4}estado: {plan['estado']}",
         f"Gasto {format_decimal(d['gasto_usd'])} / {format_decimal(ef['total_budget_usd'])} USD · {mins} / {int(ef['max_duration_min'])} min · "
         f"cambios de plan {d['cambios_plan']}/{int(ef['max_plan_changes'])}" + (f" · checkpoint en {resto} tarea{'s' if resto != 1 else ''}" if resto is not None else ""),
         "", " Tarea  Repo     Asunto                              Estado             Intentos"]
    for t in d["tareas"]:
        extra = f"   worker {w['pid']} · {int((time.time() - w['inicio_ts']) / 60)} min" if w and w.get("tarea") == t["id"] and w.get("plan") == pid else ""
        l.append(f" {t['id']:<6} {t['repo']:<8} {t['asunto'][:34]:<35} {t['estado']:<18} {t['intentos']}/{int(t['max_attempts'])}{extra}")
    g = plan.get("gate")
    l += ["", "Gate abierto: " + (f"{g['gate']} · {g['motivo']}: {g['detalle'][:160]}  (reanuda: {g.get('reanuda')})" if g else "ninguno")]
    emit(a, d, "\n".join(l))
    return OK


def cmd_log(a):
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    t = next((x for x in tareas if x["id"] == a.tarea), None)
    if not t:
        return fail_exit(f"no existe la tarea {a.tarea}")
    n = a.intento or t["intentos"]
    if not n:
        print(f"{t['id']} todavia no se ha ejecutado")
        return OK
    out = [f"Tarea {t['id']} · intento {n} · estado {t['estado']}"]
    raw = plan_path(pid, "informes", f"{t['id']}.{n}.raw.json")
    if os.path.exists(raw):
        r = state.load_json(raw)
        s = r.get("salida_json") or {}
        out += [f"Worker: exit {r['exit_code']} · {r['duracion_s']} s · parada: {r.get('killed_by') or '-'} · rama {r.get('rama')}",
                f"Resultado del modelo: {s.get('subtype')} · {s.get('num_turns')} turnos · {s.get('total_cost_usd')} USD",
                f"Informe: {json.dumps(s.get('structured_output'), ensure_ascii=False)[:1200]}"]
    ver = plan_path(pid, "verificacion", f"{t['id']}.{n}.json")
    if os.path.exists(ver):
        v = state.load_json(ver)
        out.append(f"Verificacion: {v['veredicto']} ({v.get('motivo')}) · acciones: {', '.join(v.get('acciones_permitidas', []))}")
    err = plan_path(pid, "logs", f"{t['id']}.{n}.error.log")
    if os.path.exists(err):
        out += [f"--- error.log (ultimas {a.tail} lineas)"] + open(err, encoding="utf-8", errors="replace").read().splitlines()[-a.tail:]
    out.append(f"Prompt enviado: {plan_path(pid, 'logs', f'{t[chr(105)+chr(100)]}.{n}.prompt.md')}")
    print("\n".join(out))
    return OK


# ---------- politica ----------
def cmd_policy(a):
    pol = state.load_policy()
    por_defecto = state.load_json(os.path.join(state.PLUGIN, "policy", "politica.default.json"))
    local = {}
    ruta_local = os.path.join(state.config_dir(), "politica.json")
    if os.path.exists(ruta_local):
        local = state.load_json(ruta_local)
    if a.accion == "show":
        filas = []
        for k, v in pol["limites"].items():
            nivel = "local" if k in local.get("limites", {}) else "por defecto"
            filas.append({"clave": k, "valor": v, "nivel": nivel, "defecto": por_defecto["limites"].get(k), "techo": pol["techos"].get(k)})
        emit(a, filas, "\n".join([f"{'clave':<24}{'valor':>10}  {'nivel':<12}{'defecto':>10}{'techo':>10}"] +
                                   [f"{f['clave']:<24}{f['valor']:>10}  {f['nivel']:<12}{f['defecto']:>10}{f['techo']:>10}" for f in filas]))
        return OK
    if a.clave not in pol["limites"]:
        return fail_exit(f"clave desconocida: {a.clave} (validas: {', '.join(pol['limites'])})", USO)
    try:
        v = float(a.valor)
    except ValueError:
        return fail_exit("el valor debe ser un numero", USO)
    if v < 0:
        return fail_exit("el valor no puede ser negativo", USO)
    sec = "techos" if a.techo else "limites"
    if sec == "limites" and v > pol["techos"][a.clave]:
        return fail_exit(f"{a.clave}={v:g} supera el techo ({pol['techos'][a.clave]:g}): sube antes el techo con --ceiling", LIM)
    v = int(v) if v == int(v) else v
    local.setdefault("limites", {})
    local.setdefault("techos", {})
    local[sec][a.clave] = v
    state.ensure_base_dir()
    state.save_json(ruta_local, local)
    print(f"OK|policy|{sec[:-1] if sec == 'techos' else 'limite'} {a.clave} = {v} guardado en {ruta_local.replace(os.path.expanduser('~'), '~')}")
    return OK


# ---------- archivo e integracion ----------
def cmd_totals(a):
    """Total general: suma del gasto de todos los planes (los de planes/ y los archivados en ARKANA) y de todas las sesiones de Claude
    (la statusline anota el ultimo coste visto de cada sesion en sesiones/<id>). Solo lee; no se borra nada."""
    planes = {}
    raices = [state.planes_dir(), state.archive_dir()]
    for raiz in raices:
        if not os.path.isdir(raiz):
            continue
        for pid in sorted(os.listdir(raiz)):
            try:
                d = state.load_json(os.path.join(raiz, pid, "plan.json"))
            except (FileNotFoundError, ValueError):
                continue
            planes.setdefault(pid, {"plan": pid, "estado": d.get("estado"), "gasto_usd": round(float(d.get("contadores", {}).get("gasto_usd", 0)), 4),
                                    "asunto": d.get("asunto", "")})
    sesiones = []
    carpeta = state.sessions_dir()
    if os.path.isdir(carpeta):
        for sid in sorted(os.listdir(carpeta)):
            try:
                with open(os.path.join(carpeta, sid), encoding="utf-8") as f:
                    ts, coste = f.read().split()[:2]
                sesiones.append({"sesion": sid, "ultimo_ts": int(float(ts)), "gasto_usd": round(float(coste), 4)})
            except (OSError, ValueError):
                continue
    total_p = round(sum(x["gasto_usd"] for x in planes.values()), 4)
    total_s = round(sum(x["gasto_usd"] for x in sesiones), 4)
    datos = {"planes": {"cantidad": len(planes), "total_usd": total_p, "detalle": sorted(planes.values(), key=lambda x: x["plan"])},
             "sesiones": {"cantidad": len(sesiones), "total_usd": total_s, "detalle": sesiones}}
    l = [f"Planes:   {len(planes)} · {format_decimal(total_p)} USD", f"Sesiones: {len(sesiones)} · {format_decimal(total_s)} USD (solo las vistas por la statusline)"]
    for x in datos["planes"]["detalle"]:
        l.append(f"  {x['plan']} [{x['estado']}] {format_decimal(x['gasto_usd'])} USD · {x['asunto'][:60]}")
    emit(a, datos, "\n".join(l))
    return OK


def cmd_costs(a):
    """Costes del libro: gasto de los workers por plan/tarea (`plan-task`) y coste real de las sesiones de Claude (`session`, lo que anota la statusline).
    Filtros: --plan, --session, --component, --since AAAA-MM-DD. Agrupa con --by plan|session|component|day. Solo lee (--purge aplica la retención)."""
    import ledger
    if getattr(a, "purge", False):
        n = ledger.purge(dry=getattr(a, "dry_run", False))
        print(f"{'DRY' if getattr(a, 'dry_run', False) else 'OK'}|costs|retención: {n['planes']} planes y {n['sesiones']} sesiones con detalle purgado (se conservan los totales)")
        return OK
    since = a.since or ""
    rows = []
    for pid, p in sorted(ledger.all_plans().items()):
        day = (p.get("creado") or "")[:10]
        tareas = p.get("tareas") or []
        if tareas:
            for t in tareas:
                rows.append({"kind": "plan-task", "plan": pid, "session": None, "component": t.get("repo"), "day": day, "cost_usd": t.get("gasto_usd") or 0.0})
        elif p.get("gasto_usd"):
            rows.append({"kind": "plan-task", "plan": pid, "session": None, "component": None, "day": day, "cost_usd": p["gasto_usd"]})
    sin_coste = 0
    for sid, r in sorted(ledger.all_sessions().items()):
        if r.get("cost_usd") is None:
            sin_coste += 1
        rows.append({"kind": "session", "plan": r.get("plan"), "session": sid, "component": r.get("component"),
                     "day": (r.get("ended") or r.get("started") or "")[:10], "cost_usd": r.get("cost_usd") or 0.0, "duration_s": r.get("duration_s"),
                     "tokens": r.get("tokens")})
    comp = (a.component or "").lower() or None
    rows = [r for r in rows if (not a.plan or r["plan"] == a.plan) and (not a.session or r["session"] == a.session)
            and (not comp or (r["component"] or "").lower() == comp) and (not since or (r["day"] or "") >= since)]
    tot = {k: round(sum(r["cost_usd"] for r in rows if r["kind"] == k), 4) for k in ("plan-task", "session")}
    datos = {"filtros": {"plan": a.plan, "session": a.session, "component": a.component, "since": a.since, "by": a.by}, "total_usd": round(sum(tot.values()), 4),
             "workers_usd": tot["plan-task"], "sesiones_usd": tot["session"], "sesiones_sin_coste": sin_coste}
    if a.by:
        clave = {"plan": lambda r: r["plan"] or "-", "session": lambda r: r["session"] or "-", "component": lambda r: r["component"] or "-", "day": lambda r: r["day"] or "-"}[a.by]
        g = {}
        for r in rows:
            e = g.setdefault(clave(r), {"clave": clave(r), "workers_usd": 0.0, "sesiones_usd": 0.0, "filas": 0})
            e["workers_usd" if r["kind"] == "plan-task" else "sesiones_usd"] += r["cost_usd"]
            e["filas"] += 1
        datos["grupos"] = [dict(e, workers_usd=round(e["workers_usd"], 4), sesiones_usd=round(e["sesiones_usd"], 4)) for e in sorted(g.values(), key=lambda e: e["clave"])]
    else:
        datos["filas"] = rows
    l = [f"Total: {format_decimal(datos['total_usd'])} USD (workers {format_decimal(tot['plan-task'])} · sesiones {format_decimal(tot['session'])})"
         + (f" · {sin_coste} sesiones sin coste (la statusline no lo anotó)" if sin_coste else "")]
    for e in datos.get("grupos", []):
        l.append(f"  {e['clave']:<28} workers {format_decimal(e['workers_usd']):>8} · sesiones {format_decimal(e['sesiones_usd']):>8}")
    if not a.by:
        for r in rows[:50]:
            l.append(f"  {r['kind']:<9} {(r['plan'] or r['session'] or '-')[:26]:<27} {(r['component'] or '-'):<9} {r['day'] or '-':<10} {format_decimal(r['cost_usd']):>8}")
    emit(a, datos, "\n".join(l))
    return OK


def cmd_archive(a):
    pid = resolve_plan(a)
    plan, _ = load_plan(pid)
    if plan["estado"] not in state.TERMINAL_PLAN_STATES:
        return fail_exit(f"el plan esta en '{plan['estado']}': solo se archiva uno terminado", PRE)
    destino = os.path.join(state.archive_dir(), pid)
    if os.path.exists(destino):
        return fail_exit(f"ya existe {destino}", PRE)
    os.makedirs(destino)
    for f in ("plan.json", "registro.jsonl"):
        if os.path.exists(plan_path(pid, f)):
            shutil.copy2(plan_path(pid, f), destino)
    for d in ("tareas", "informes", "verificacion"):
        if os.path.isdir(plan_path(pid, d)):
            shutil.copytree(plan_path(pid, d), os.path.join(destino, d))
    print(f"OK|archive|{pid} archivado en {destino}; datos locales en data/archive; no se versiona)")
    return OK


def _merge_msg(rid, rama, hasta):
    sufijo = f" up to {hasta}" if hasta else ""
    return f"chore({rid}): merge {rama}{sufijo}" if commitmsg.format_of(rid) == "conv" else f"chore({rid}) merge {rama}{sufijo}"


def _save_decision(pid, rid, decision, hasta=None, sha=None):
    def f(o):
        d = o["ramas"][rid]
        d["decision"] = decision
        if hasta:
            d["integrado_hasta"] = hasta
    state.update_json(plan_path(pid, "plan.json"), f)
    extra = {"sha": sha} if sha else {}                      # sha del merge en la rama original: deja traza de que se integro
    state.log_event(pid, "user", "integrate", None, f"{rid}: {decision}" + (f" hasta {hasta}" if hasta else ""), **extra)


def _review(pid, plan, tareas):
    ramas = plan.get("ramas") or {}
    state.log_event(pid, "orchestrator", "review", None, "revision antes de decidir: " + ", ".join(sorted(ramas)))      # deja traza de que se enseno al usuario
    por_commit = {t["commit"]: t["id"] for t in tareas if t.get("commit")}
    for rid in sorted(ramas):
        r, repo = ramas[rid], repos.repo_path(rid)
        rama, orig = r.get("nombre"), r.get("original") or "develop"
        print(f"OK|review|{rid}: rama {rama} (original {orig}) · decision: {r.get('decision') or 'pendiente'}"
              + (f" (hasta {r['integrado_hasta']})" if r.get("integrado_hasta") else ""))
        if not rama or not repos.branch_exists(repo, rama):
            print(f"OK|review|{rid}: la rama ya no existe")
            continue
        log = repos.git(repo, "log", "--reverse", "--format=%H%x09%h%x09%s", f"{orig}..{rama}").stdout.splitlines()
        for linea in log:
            h, corto, asunto = linea.split("\t", 2)
            print(f"OK|review|  {por_commit.get(h, '-')} {corto} {asunto}")
        if not log:
            print("OK|review|  (sin commits)")
        if not repos.is_clean(repo):
            print(f"WARN|review|{rid}: tiene cambios sin commitear")
        stat = repos.git(repo, "diff", "--stat", f"{orig}...{rama}").stdout.strip().splitlines()
        for linea in stat[-6:]:
            print(f"OK|review|  {linea.strip()}")
    por_id = {t["id"]: t for t in tareas}
    cruzadas = sorted({r for t in tareas for d in t.get("depende_de", []) if d in por_id and por_id[d]["repo"] != t["repo"]
                       for r in (t["repo"], por_id[d]["repo"])})
    if len(cruzadas) > 1:
        print(f"WARN|review|hay tareas que dependen de otras de otro repo ({', '.join(cruzadas)}): integra o descarta esos repos de forma coherente")
    print(f"OK|review|gasto del plan: {format_decimal(plan.get('contadores', {}).get('gasto_usd', 0))} USD")
    return OK


def cmd_integrate(a):
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    if worker_info(pid):
        return fail_exit("hay un worker vivo", PRE)
    ramas = plan.get("ramas") or {}
    if not ramas:
        print("OK|integrate|el plan no creo ninguna rama")
        return OK
    if a.destino == "review":
        return _review(pid, plan, tareas)
    if a.hasta and (a.destino != "merge" or not a.repo):
        return fail_exit("--up-to solo se usa con 'merge' y con --repo", USO)
    if a.repo and a.repo not in ramas:
        return fail_exit(f"el plan no creo ninguna rama en {a.repo} (repos con rama: {', '.join(sorted(ramas))})", USO)
    elegidos = [a.repo] if a.repo else [rid for rid in sorted(ramas) if not ramas[rid].get("decision")]
    if not elegidos:
        print("OK|integrate|todos los repos del plan ya tienen decision (usa --repo para cambiar la de uno)")
        return OK
    for rid in elegidos:
        repo, rama = repos.repo_path(rid), ramas[rid].get("nombre")
        if repos.is_clean(repo):
            continue
        actual = repos.current_branch(repo)
        if a.destino == "discard" and actual == rama:
            tarea_repo = next((t for t in tareas if t["repo"] == rid), None)
            if tarea_repo is None:
                return fail_exit(f"{rid}: el plan no tiene tareas en este repo, no hay nada que descartar", PRE)
            ok, err = discard_changes(plan, tarea_repo)   # es el propio trabajo del plan, en su rama: se descarta con ella
            if not ok:
                return fail_exit(f"{rid}: no se pudieron descartar los cambios de la rama {actual}: {err}", PRE)
            state.log_event(pid, "user", "discard_uncommitted", None, f"{rid}: cambios sin commitear de {actual} descartados")
            continue
        if actual == rama:
            return fail_exit(f"el repo {rid} tiene cambios sin commitear en la rama {actual} (el plan no autorizaba commits locales): "
                         f"revisalos y haz commit a mano en esa rama, o usa 'integrate discard'", PRE)
        return fail_exit(f"el repo {rid} tiene cambios sin commitear: no se integra", PRE)
    for rid in elegidos:
        r = ramas[rid]
        repo, orig, rama = repos.repo_path(rid), r.get("original") or "develop", r.get("nombre")
        if not rama or not repos.branch_exists(repo, rama):
            print(f"OK|integrate|{rid}: la rama del plan ya no existe")
            continue
        if a.destino == "merge":
            destino, hasta = rama, None
            if a.hasta:
                t = next((x for x in tareas if x["id"] == a.hasta and x["repo"] == rid), None)
                if not t or not t.get("commit"):
                    return fail_exit(f"{a.hasta} no es una tarea de {rid} con commit en la rama del plan", USO)
                if repos.git(repo, "merge-base", "--is-ancestor", t["commit"], rama).returncode:
                    return fail_exit(f"el commit de {a.hasta} no esta en la rama {rama}", PRE)
                destino, hasta = t["commit"], a.hasta
            if repos.git(repo, "switch", orig).returncode:
                return fail_exit(f"{rid}: no se pudo cambiar a {orig}")
            nuevos = repos.git(repo, "rev-list", "--count", f"{orig}..{destino}").stdout.strip()
            if nuevos in ("", "0"):
                repos.git(repo, "branch", "-D", rama)
                _save_decision(pid, rid, "merge")
                print(f"OK|integrate|{rid}: ninguna tarea hizo commit; nada que integrar en {orig} (rama borrada)")
                continue
            msg = a.mensaje or _merge_msg(rid, rama, hasta)
            errs = commitmsg.check_message(rid, msg)
            if errs:
                repos.git(repo, "switch", rama)
                for e in errs:
                    print(f"FAIL|integrate|{rid}: {e}")
                return ERR
            m = repos.git(repo, "merge", "--no-ff", "-m", msg, destino)
            if m.returncode:
                repos.git(repo, "merge", "--abort")
                repos.git(repo, "switch", rama)
                return fail_exit(f"{rid}: el merge fallo y se aborto: {(m.stdout + m.stderr).strip()[-200:]}")
            completa = repos.git(repo, "rev-list", "--count", f"{orig}..{rama}").stdout.strip() == "0"
            if completa:
                repos.git(repo, "branch", "-d", rama)
            _save_decision(pid, rid, "merge", hasta, repos.head(repo))
            print(f"OK|integrate|{rid}: {rama}{' hasta ' + hasta if hasta else ''} integrada en {orig} (merge local --no-ff; sin push)"
                  + ("" if completa else f"; la rama {rama} se conserva con el resto"))
        elif a.destino == "keep":
            repos.git(repo, "switch", orig)
            _save_decision(pid, rid, "keep")
            print(f"OK|integrate|{rid}: de vuelta en {orig}; queda para revisarla: {rama}")
        else:
            repos.git(repo, "switch", orig)
            repos.git(repo, "branch", "-D", rama)
            _save_decision(pid, rid, "discard")
            print(f"OK|integrate|{rid}: rama {rama} descartada, de vuelta en {orig}")
    return OK


# ---------- fix: layout y recuperacion ----------
def cmd_fix(a):
    import migrate
    base = state.base_dir()
    if migrate.pending(base) or os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(base)), "orquestacion", "archivo")):
        items = migrate.run(base, getattr(a, "dry_run", False), os.path.join(paths_plugins(), "arkana-workspace", "bak"))
        for st, i, d in items:
            print(f"{st}|fix:{i}|{d}")
        if any(st == "FAIL" for st, _, _ in items):
            return PRE
        if getattr(a, "dry_run", False):
            return OK
    elif getattr(a, "dry_run", False):
        print("OK|fix:layout|el layout ya es config/state/data")
    if not os.path.isdir(state.planes_dir()):
        return OK
    try:
        resolve_plan(a)
    except KeyError:                                                  # sin plan actual: solo puede haber un worker.json obsoleto
        if not worker_info():
            for f in ("worker.json", "killed.json"):
                ruta = os.path.join(state.run_dir(), f)
                if os.path.exists(ruta) and not getattr(a, "dry_run", False):
                    os.unlink(ruta)
                    print(f"OK|fix|se limpió {f} obsoleto (no hay plan actual)")
        print("OK|fix|no hay plan actual: nada más que recuperar")
        return OK
    return cmd_recover(a)


def paths_plugins():
    import paths
    return paths.plugins_dir()


def cmd_recover(a):
    pid = resolve_plan(a)
    plan, tareas = load_plan(pid)
    w = worker_info()
    huerfanas = [t for t in tareas if t["estado"] == "en_curso" and not (w and w.get("tarea") == t["id"] and w.get("plan") == pid)]
    if not huerfanas and not a.tarea:
        stale = os.path.exists(os.path.join(state.run_dir(), "worker.json")) and not w
        if stale:
            for f in ("worker.json", "killed.json"):
                if os.path.exists(os.path.join(state.run_dir(), f)):
                    os.unlink(os.path.join(state.run_dir(), f))
        print("OK|fix|no hay tareas interrumpidas" + ("; se limpio un worker.json obsoleto" if stale else ""))
        return OK
    if not a.tarea:
        for t in huerfanas:
            state.transition_task(pid, t["id"], "interrumpida", "script", "worker desaparecido sin informe")
        for f in ("worker.json", "killed.json"):
            if os.path.exists(os.path.join(state.run_dir(), f)) and not w:
                os.unlink(os.path.join(state.run_dir(), f))
        plan = load_plan(pid)[0]
        for t in huerfanas:
            repo = repos.repo_path(t["repo"])
            print(f"WARN|fix|{t['id']} interrumpida (repo {t['repo']}, rama {repos.current_branch(repo)}, "
                  f"{'limpio' if repos.is_clean(repo) else 'con cambios sin commitear'}; rama del plan {plan_branch_name(plan, t['repo']) or '-'})")
        print("OK|fix|decide: 'fix --task <T> --action retry|discard'")
        return ESPERA
    t = next((x for x in tareas if x["id"] == a.tarea), None)
    if not t or t["estado"] != "interrumpida":
        return fail_exit(f"{a.tarea} no esta interrumpida", PRE)
    if a.action == "discard":
        ok, err = discard_changes(plan, t)
        if not ok:
            return fail_exit(err, PRE)
        state.transition_task(pid, t["id"], "cancelada", "user", "recuperacion: descartada")
        print(f"OK|fix|{t['id']} cancelada y cambios descartados")
        return OK
    if a.action == "retry":
        ok, err = discard_changes(plan, t)
        if not ok:
            return fail_exit(err, PRE)
        state.transition_task(pid, t["id"], "lista", "user", "recuperacion: reintento")
        print(f"OK|fix|{t['id']} lista para un nuevo intento")
        return OK
    return fail_exit("indica --action retry|discard", USO)


def cmd_launch(a):
    pid = resolve_plan(a)
    if a.de_mensaje:                                                     # --from-message: el mensaje se entrega a esta tarea (y a sus reintentos)
        plan, tareas = load_plan(pid)
        t = next((x for x in tareas if x["id"] == a.tarea), None)
        if t is None:
            return fail_exit(f"la tarea {a.tarea} no existe en el plan {pid}", USO)
        err = attach_messages(pid, t, a.de_mensaje, "orchestrator")
        if err:
            return fail_exit(err, PRE)
    return launch.main(["launch", pid, a.tarea])


def cmd_finish(a):
    pid = resolve_plan(a)
    return verify.main(["finish", pid, a.tarea] + (["--json"] if a.json else []))


def cmd_manual(a):
    """retry / skip: versiones del usuario de act retry / act skip."""
    a.accion = "retry" if a.cmd == "retry" else "skip"
    a.quien = "user"
    for k, v in (("motivo", None), ("feedback_file", None), ("mensaje", None), ("gate", None), ("detalle", None), ("tareas_file", None),
                 ("repo", None), ("asunto", None), ("instrucciones_file", None), ("para", None), ("de_mensaje", None)):
        setattr(a, k, getattr(a, k, v))
    return cmd_act(a)


def build_parser():
    p = argparse.ArgumentParser(prog="agentic.sh", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def nuevo(nombre, **kw):
        s = sub.add_parser(nombre, **kw)
        s.add_argument("--plan")
        s.add_argument("--json", action="store_true")
        return s
    s = nuevo("plan")
    s.add_argument("accion", choices=["new", "show", "validate", "approve", "start"])
    s.add_argument("fichero", nargs="?", metavar="file")
    s.add_argument("--from-message", dest="de_mensaje", action="append", metavar="ID")
    s.add_argument("--repo", dest="repos", action="append", metavar="REPO")
    s.add_argument("--paths", dest="rutas", action="append", metavar="GLOB")
    nuevo("next")
    nuevo("finish").add_argument("tarea", metavar="task")
    s = nuevo("launch")
    s.add_argument("tarea", metavar="task")
    s.add_argument("--from-message", dest="de_mensaje", action="append", metavar="ID")
    s = nuevo("act")
    s.add_argument("accion", choices=["continue", "retry", "split", "investigate", "escalate", "skip", "stop"])
    s.add_argument("tarea", nargs="?", metavar="task")
    s.add_argument("--message", dest="mensaje", metavar="MESSAGE")
    s.add_argument("--reason", dest="motivo", metavar="REASON")
    s.add_argument("--feedback-file", dest="feedback_file", metavar="FILE")
    s.add_argument("--tasks-file", dest="tareas_file", metavar="FILE")
    s.add_argument("--repo")
    s.add_argument("--from-message", dest="de_mensaje", action="append", metavar="ID")
    s.add_argument("--subject", dest="asunto", metavar="SUBJECT")
    s.add_argument("--instructions-file", dest="instrucciones_file", metavar="FILE")
    s.add_argument("--for", dest="para", metavar="TASK")
    s.add_argument("--gate")
    s.add_argument("--detail", dest="detalle", metavar="DETAIL")
    s.add_argument("--actor", dest="quien", default="orchestrator", choices=["orchestrator", "user"])
    nuevo("status")
    s = nuevo("log")
    s.add_argument("tarea", metavar="task")
    s.add_argument("--attempt", dest="intento", metavar="N", type=int)
    s.add_argument("--tail", type=int, default=40)
    s = nuevo("stop")
    s.add_argument("--force", action="store_true")
    nuevo("pause")
    nuevo("resume")
    for n in ("retry", "skip"):
        s = nuevo(n)
        s.add_argument("tarea", metavar="task")
        if n == "retry":
            s.add_argument("--from-message", dest="de_mensaje", action="append", metavar="ID")
    s = nuevo("approve")
    s.add_argument("gate")
    s.add_argument("--note", dest="nota", metavar="NOTE")
    s = nuevo("reject")
    s.add_argument("gate")
    s.add_argument("--reason", dest="motivo", metavar="REASON")
    s.add_argument("--note", dest="nota", metavar="NOTE")
    s.add_argument("--stop", action="store_true")
    s = nuevo("fix")
    s.add_argument("--dry-run", dest="dry_run", action="store_true")
    s.add_argument("--task", dest="tarea", metavar="TASK")
    s.add_argument("--action", choices=["retry", "discard"])
    nuevo("archive")
    nuevo("totals")
    s = nuevo("costs")
    s.add_argument("--session")
    s.add_argument("--component")
    s.add_argument("--since", metavar="YYYY-MM-DD")
    s.add_argument("--by", choices=["plan", "session", "component", "day"])
    s.add_argument("--purge", action="store_true")
    s.add_argument("--dry-run", dest="dry_run", action="store_true")
    s = nuevo("integrate")
    s.add_argument("destino", choices=["review", "merge", "keep", "discard"], metavar="target")
    s.add_argument("--repo", metavar="REPO")
    s.add_argument("--up-to", dest="hasta", metavar="TASK")
    s.add_argument("--message", dest="mensaje", metavar="MESSAGE")
    s = nuevo("policy")
    s.add_argument("accion", choices=["show", "set"])
    s.add_argument("clave", nargs="?", metavar="key")
    s.add_argument("valor", nargs="?", metavar="value")
    s.add_argument("--ceiling", dest="techo", action="store_true")
    s = nuevo("install")
    s.add_argument("--dry-run", dest="dry_run", action="store_true")
    s.add_argument("--no-settings", dest="no_settings", action="store_true")
    s = nuevo("check")
    s.add_argument("--quick", action="store_true")
    s.add_argument("--deep", action="store_true")
    s.add_argument("--need-network", dest="necesita_red", action="store_true")
    return p


def main(argv):
    a = build_parser().parse_args(argv)
    a.quien = getattr(a, "quien", "user")
    try:
        c = a.cmd
        if c == "plan":
            if a.accion == "new" and not a.fichero and not a.de_mensaje:
                return fail_exit("plan new necesita un fichero o --from-message", USO)
            return cmd_plan(a)
        if c == "next":
            return cmd_next(a)
        if c == "launch":
            return cmd_launch(a)
        if c == "finish":
            return cmd_finish(a)
        if c == "act":
            return cmd_act(a)
        if c == "status":
            return cmd_status(a)
        if c == "log":
            return cmd_log(a)
        if c == "stop":
            return cmd_stop(a)
        if c == "pause":
            a.force = False
            return cmd_stop(a)
        if c == "resume":
            return cmd_resume(a)
        if c in ("retry", "skip"):
            return cmd_manual(a)
        if c in ("approve", "reject"):
            if c == "approve":
                a.stop, a.motivo = False, None
            else:
                a.nota = getattr(a, "nota", None)
            return cmd_gate(a)
        if c == "fix":
            return cmd_fix(a)
        if c == "archive":
            return cmd_archive(a)
        if c == "totals":
            return cmd_totals(a)
        if c == "costs":
            return cmd_costs(a)
        if c == "integrate":
            return cmd_integrate(a)
        if c == "policy":
            if a.accion == "set" and not (a.clave and a.valor):
                return fail_exit("policy set necesita clave y valor", USO)
            return cmd_policy(a)
        if c == "install":
            import install
            return install.main(a)
        if c == "check":
            import doctor
            return doctor.main(a)
    except state.IllegalTransition as e:
        return fail_exit(f"transicion no permitida: {e}", PRE)
    except KeyError as e:
        return fail_exit(str(e).strip("'\""), PRE)
    except FileNotFoundError as e:
        return fail_exit(f"no existe: {e.filename}", PRE)
    except (paths.NoWorkspace, repos._manifest.ManifestError) as e:
        return fail_exit(f"workspace de Arkana: {e}", PRE)
    return USO


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
