#!/usr/bin/env python3
"""Estado de arkana-agentic: ficheros JSON atomicos, maquina de estados, limites efectivos e indicador de statusline.

Todo cambio de estado pasa por aqui: una transicion que no esta en las tablas se rechaza.
Directorio de ejecucion:  $ARKANA_AGENTIC_DIR  o  <arkana>/.arkana/arkana-agentic  (ver paths.py), con tres carpetas:
  config/   politica.json y comandos-permitidos.json locales (portables: se exportan)
  state/    planes/, run/ (worker, linea.json, marcas), sesiones/ (coste visto por la statusline) y `actual`: estado local de ejecucion
  data/     ledger/ (libro de planes y sesiones) y archive/ (planes archivados): datos del usuario (con --include-data)

Uso (CLI):
  state.py new-id                           identificador de plan nuevo
  state.py validate <plan|tarea|informe|politica> <fichero>
  state.py transition <plan-id> <T001|-> <estado> [--actor X] [--reason "..."]
  state.py approve <plan-id> | start <plan-id>   aprueba (hash) / inicia la ejecucion
  state.py linea <plan-id>                  reescribe run/linea.json (o lo borra si el plan no esta activo)
  state.py limites <plan-id> [<T001>]        limites efectivos (el mas restrictivo de cada nivel)
"""
import contextlib
import datetime
import fcntl
import json
import os
import secrets
import string
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))
import paths  # noqa: E402
import validate  # noqa: E402

TASK_TRANSITIONS = {
    "pendiente": {"lista", "omitida", "cancelada"},
    "lista": {"en_curso", "omitida", "cancelada"},
    "en_curso": {"verificando", "parcial", "fallida", "bloqueada", "interrumpida", "cancelada"},
    "verificando": {"completada", "rechazada", "bloqueada", "cancelada"},
    "rechazada": {"lista", "fallida_definitiva", "esperando_usuario", "omitida"},
    "parcial": {"lista", "fallida_definitiva", "esperando_usuario", "omitida"},
    "fallida": {"lista", "fallida_definitiva", "esperando_usuario", "omitida"},
    "bloqueada": {"esperando_usuario", "lista", "omitida", "cancelada"},
    "esperando_usuario": {"lista", "verificando", "omitida", "cancelada", "fallida_definitiva"},
    "interrumpida": {"lista", "verificando", "cancelada"},
    "completada": set(), "fallida_definitiva": set(), "omitida": set(), "cancelada": set(),
}
PLAN_TRANSITIONS = {
    "borrador": {"aprobado", "detenido"},
    "aprobado": {"en_ejecucion", "borrador", "detenido"},
    "en_ejecucion": {"pausado", "esperando_usuario", "completado", "detenido", "fallido"},
    "pausado": {"en_ejecucion", "detenido"},
    "esperando_usuario": {"en_ejecucion", "pausado", "detenido"},
    "completado": set(), "detenido": set(), "fallido": set(),
}
TERMINAL_PLAN_STATES = {"completado", "detenido", "fallido"}
ACTIVE_PLAN_STATES = {"en_ejecucion", "pausado", "esperando_usuario"}
LIMIT_ALIASES = {"max_attempts": "max_attempts_per_task"}
_USED_IDS = set()


class IllegalTransition(Exception):
    pass


# ---------- rutas y tiempo ----------
def base_dir():
    return os.environ.get("ARKANA_AGENTIC_DIR") or paths.item("arkana-agentic")


def config_dir():
    return os.path.join(base_dir(), "config")


def state_dir():
    return os.path.join(base_dir(), "state")


def data_dir():
    return os.path.join(base_dir(), "data")


def ensure_base_dir():
    b = base_dir()
    for d in (b, config_dir(), state_dir(), data_dir()):
        os.makedirs(d, exist_ok=True)
        os.chmod(d, 0o700)
    return b


def plan_dir(pid):
    return os.path.join(state_dir(), "planes", pid)


def planes_dir():
    return os.path.join(state_dir(), "planes")


def run_dir():
    return os.path.join(state_dir(), "run")


def actual_file():
    return os.path.join(state_dir(), "actual")


def sessions_dir():
    return os.path.join(state_dir(), "sesiones")


def archive_dir():
    return os.path.join(data_dir(), "archive")


def ledger_dir():
    return os.path.join(data_dir(), "ledger")


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_plan_id():
    """P2610311830-abcd: P + AAMMDDHHMI (hora local, 24 h) + guion + 4 letras minusculas al azar. Unico en el proceso y en disco."""
    base = "P" + time.strftime("%y%m%d%H%M", time.localtime())
    while True:
        cand = f"{base}-" + "".join(secrets.choice(string.ascii_lowercase) for _ in range(4))
        if cand in _USED_IDS or os.path.exists(plan_dir(cand)):
            continue
        _USED_IDS.add(cand)
        return cand


# ---------- JSON atomico ----------
def load_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def save_json(ruta, obj):
    d = os.path.dirname(ruta)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, ruta)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def file_lock(ruta):
    """flock corto para leer-modificar-escribir. No es un candado de orquestador: dura milisegundos."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta + ".lock", "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def update_json(ruta, fn):
    with file_lock(ruta):
        obj = load_json(ruta)
        nuevo = fn(obj)
        nuevo = obj if nuevo is None else nuevo
        save_json(ruta, nuevo)
        return nuevo


def log_event(pid, quien, accion, tarea=None, motivo="", **extra):
    """Linea de registro.jsonl: una por decision (orquestador, script o usuario)."""
    ruta = os.path.join(plan_dir(pid), "registro.jsonl")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    reg = {"ts": now_iso(), "quien": quien, "accion": accion, "tarea": tarea, "motivo": motivo}
    reg.update(extra)
    with file_lock(ruta), open(ruta, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")


# ---------- transiciones ----------
def check_transition(obj, tipo, nuevo, quien="script", motivo=""):
    tabla = TASK_TRANSITIONS if tipo == "tarea" else PLAN_TRANSITIONS
    actual = obj.get("estado")
    if nuevo not in tabla.get(actual, set()):
        raise IllegalTransition(f"{tipo} {obj.get('id')}: {actual} -> {nuevo} no esta permitida")
    obj["estado"] = nuevo
    obj.setdefault("historial", []).append(
        {"fecha": now_iso(), "quien": quien, "accion": f"{actual}->{nuevo}", "detalle": motivo})
    return obj


def transition_task(pid, tid, nuevo, quien="script", motivo=""):
    ruta = os.path.join(plan_dir(pid), "tareas", f"{tid}.json")
    t = update_json(ruta, lambda o: check_transition(o, "tarea", nuevo, quien, motivo))
    log_event(pid, quien, f"tarea->{nuevo}", tid, motivo)
    render_status_line(pid)
    return t


def transition_plan(pid, nuevo, quien="script", motivo=""):
    ruta = os.path.join(plan_dir(pid), "plan.json")
    p = update_json(ruta, lambda o: check_transition(o, "plan", nuevo, quien, motivo))
    log_event(pid, quien, f"plan->{nuevo}", None, motivo)
    render_status_line(pid)
    if nuevo in TERMINAL_PLAN_STATES:                    # el libro conserva el apunte del plan (metadatos) aunque luego se archive o se purgue
        try:
            import ledger
            ledger.snapshot_plan(pid)
        except Exception:
            pass
    return p


def load_tasks(pid):
    d = os.path.join(plan_dir(pid), "tareas")
    if not os.path.isdir(d):
        return []
    return [load_json(os.path.join(d, f)) for f in sorted(os.listdir(d)) if f.endswith(".json")]


def task_ready(tarea, tareas):
    """Todas sus dependencias estan completadas."""
    estados = {t["id"]: t["estado"] for t in tareas}
    return all(estados.get(d) == "completada" for d in tarea.get("depende_de", []))


def next_task(tareas):
    """Primera tarea pendiente o lista cuyas dependencias estan completadas, o None."""
    for t in tareas:
        if t["estado"] in ("pendiente", "lista") and task_ready(t, tareas):
            return t
    return None


# ---------- politica y limites ----------
def load_policy():
    pol = load_json(os.path.join(PLUGIN, "policy", "politica.default.json"))
    local = os.path.join(config_dir(), "politica.json")
    if os.path.exists(local):
        loc = load_json(local)
        for sec in ("limites", "techos"):
            pol[sec].update(loc.get(sec, {}))
    return pol


def _norm(d):
    return {LIMIT_ALIASES.get(k, k): v for k, v in (d or {}).items()}


def effective_limits(politica, plan_pol=None, tarea_lim=None):
    """Para cada limite: el minimo entre politica (nivel 1 y 2), plan (3) y tarea (4); nunca por encima del techo."""
    res = {}
    plan_pol, tarea_lim = _norm(plan_pol), _norm(tarea_lim)
    for k, v in politica["limites"].items():
        cands = [v] + [x[k] for x in (plan_pol, tarea_lim) if k in x]
        val = min(cands)
        if k in politica["techos"]:
            val = min(val, politica["techos"][k])
        res[k] = val
    return res


# ---------- aprobacion, contadores y gates ----------
APPROVED_PLAN_FIELDS = ("asunto", "peticion", "autoriza", "politica", "tareas")
APPROVED_TASK_FIELDS = ("id", "version", "asunto", "repo", "tipo", "perfil", "objetivo", "instrucciones",
                         "criterios_aceptacion", "contexto", "rutas_permitidas", "verificaciones", "depende_de", "limites")


def approval_hash(pid):
    """Hash del contenido que el usuario aprueba (no incluye estado, intentos, feedback ni historial)."""
    import hashlib
    plan = load_json(os.path.join(plan_dir(pid), "plan.json"))
    carga = {"plan": {k: plan.get(k) for k in APPROVED_PLAN_FIELDS},
             "tareas": [{k: t.get(k) for k in APPROVED_TASK_FIELDS} for t in load_tasks(pid)]}
    return hashlib.sha256(json.dumps(carga, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def approve_plan(pid, quien="user"):
    transition_plan(pid, "aprobado", quien, "plan aprobado")
    h = approval_hash(pid)
    with open(os.path.join(plan_dir(pid), "plan.aprobado.sha256"), "w", encoding="utf-8") as f:
        f.write(h + "\n")
    update_json(os.path.join(plan_dir(pid), "plan.json"), lambda o: o.update(aprobado=now_iso()))
    return h


def plan_approval_ok(pid):
    """El contenido actual coincide con el aprobado (un plan alterado a mano o sin reaprobar no se ejecuta)."""
    try:
        with open(os.path.join(plan_dir(pid), "plan.aprobado.sha256"), encoding="utf-8") as f:
            return f.read().strip() == approval_hash(pid)
    except FileNotFoundError:
        return False


def start_plan(pid, quien="script"):
    p = transition_plan(pid, "en_ejecucion", quien, "inicio de la ejecucion")
    add_counter(pid, "inicio_ts", time.time() - (p.get("contadores", {}).get("inicio_ts", 0) or 0))
    return p


def add_counter(pid, clave, valor=1):
    def f(o):
        c = o.setdefault("contadores", {})
        c[clave] = round(c.get(clave, 0) + valor, 6)
    return update_json(os.path.join(plan_dir(pid), "plan.json"), f)["contadores"][clave]


def open_gate(pid, motivo, detalle="", opciones=None, quien="script", tarea=None, reanuda="continue", rutas=None):
    """Parada obligatoria: el plan pasa a esperando_usuario con el gate descrito.
    reanuda: reverify (autoriza y vuelve a verificar) | retry (nuevo intento) | continue (solo se cierra) | none (solo detener)."""
    ruta = os.path.join(plan_dir(pid), "plan.json")
    n = len(load_json(ruta).get("historial", [])) + 1
    gate = {"gate": f"G{n:02d}", "motivo": motivo, "detalle": detalle, "opciones": opciones or [], "desde": now_iso(),
            "tarea": tarea, "reanuda": reanuda}
    if rutas:
        gate["rutas"] = list(rutas)            # rutas protegidas que `approve` autorizara para esta tarea (solo con reanuda=retry)
    update_json(ruta, lambda o: o.update(gate=gate))
    if load_json(ruta)["estado"] == "en_ejecucion":
        transition_plan(pid, "esperando_usuario", quien, f"gate {motivo}: {detalle}"[:200])
    log_event(pid, quien, "gate_abierto", None, f"{motivo}: {detalle}"[:300])
    render_status_line(pid)
    return gate


def close_gate(pid, quien="user", resolucion=""):
    ruta = os.path.join(plan_dir(pid), "plan.json")
    update_json(ruta, lambda o: o.update(gate=None))
    if load_json(ruta)["estado"] == "esperando_usuario":
        transition_plan(pid, "en_ejecucion", quien, f"gate resuelto: {resolucion}"[:200])
    log_event(pid, quien, "gate_cerrado", None, resolucion[:300])
    render_status_line(pid)


def load_allowed_commands(repo_ids=None):
    """Lista cerrada de comandos del verificador: la UNION de los adaptadores de los repos del plan (todos los conocidos si no se dan)
    mas lo que el usuario anada en config/comandos-permitidos.json."""
    import adapters
    lista = [list(c) for c in adapters.commands_for(repo_ids)]
    local = os.path.join(config_dir(), "comandos-permitidos.json")
    if os.path.exists(local):
        lista += [list(c) for c in load_json(local).get("permitidos", [])]
    return lista


def load_protected_paths(repo=None):
    """Rutas protegidas del adaptador del repo (o la union de todos si no se indica)."""
    import adapters
    return adapters.protected_for(repo) if repo else adapters.protected_union()


# ---------- indicador de statusline ----------
def short_subject(texto, n=40):
    t = " ".join(str(texto).split())
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def render_status_line(pid):
    """Escribe run/linea.json (lo lee la tercera linea de la statusline). Con el plan activo, con la tarea y el worker; con el plan terminado
    (completado, detenido o fallido) lo conserva con ese estado para que la statusline lo muestre un rato; lo borra si el plan no existe
    o aun es un borrador o esta aprobado sin ejecutar."""
    destino = os.path.join(run_dir(), "linea.json")
    try:
        plan = load_json(os.path.join(plan_dir(pid), "plan.json"))
    except FileNotFoundError:
        plan = None
    if not plan or plan["estado"] not in ACTIVE_PLAN_STATES | TERMINAL_PLAN_STATES:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(destino)
        return None
    tareas = load_tasks(pid)
    activa = None
    if plan["estado"] in ACTIVE_PLAN_STATES:
        activa = next((t for t in tareas if t["estado"] in ("en_curso", "verificando")), None)
        if activa is None:
            activa = next((t for t in tareas if t["estado"] in ("esperando_usuario", "bloqueada", "interrumpida")), None)
    worker = None
    with contextlib.suppress(FileNotFoundError, ValueError):
        worker = load_json(os.path.join(run_dir(), "worker.json"))
    hechas = sum(1 for t in tareas if t["estado"] == "completada")
    omitidas = sum(1 for t in tareas if t["estado"] == "omitida")
    orden = plan.get("tareas") or [t["id"] for t in tareas]
    actual = orden.index(activa["id"]) + 1 if activa and activa["id"] in orden else hechas + omitidas   # posicion de la tarea en curso; sin ella, las resueltas (hechas + omitidas)
    datos = {
        "ts": now_iso(), "plan": pid, "estado": plan["estado"],
        "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID") or None,      # la sesion de Claude que gobierna el plan: la statusline solo lo muestra en ella
        "tarea": activa["id"] if activa else None,
        "tareas": {"actual": actual, "hechas": hechas, "omitidas": omitidas, "total": len(tareas)},
        "repo": activa["repo"] if activa else None,
        "asunto_corto": short_subject(activa["asunto"]) if activa else None,
        "worker_pid": worker.get("pid") if worker else None,
        "inicio": worker.get("inicio") if worker else None,
        "gasto_usd": round(float(plan.get("contadores", {}).get("gasto_usd", 0)), 2),
        "gate": (plan.get("gate") or {}).get("motivo") if plan.get("gate") else None,
    }
    ensure_base_dir()
    save_json(destino, datos)
    return datos


# ---------- CLI ----------
def _schema_path(nombre):
    return os.path.join(PLUGIN, "schemas", f"{nombre}.schema.json")


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "new-id" and len(argv) == 2:
            print(new_plan_id())
        elif cmd == "validate" and len(argv) == 4:
            errs = validate.check_schema(load_json(argv[3]), load_json(_schema_path(argv[2])))
            for e in errs:
                print(f"FAIL|esquema|{e}")
            print("OK|esquema|valido" if not errs else f"FAIL|esquema|{len(errs)} errores")
            return 1 if errs else 0
        elif cmd == "transition" and len(argv) >= 5:
            quien, motivo = "script", ""
            rest = argv[5:]
            while rest:
                if rest[0] == "--actor":
                    quien = rest[1]
                elif rest[0] == "--reason":
                    motivo = rest[1]
                rest = rest[2:]
            if argv[3] == "-":
                transition_plan(argv[2], argv[4], quien, motivo)
            else:
                transition_task(argv[2], argv[3], argv[4], quien, motivo)
            print(f"OK|transicion|{argv[2]} {argv[3]} -> {argv[4]}")
        elif cmd == "approve" and len(argv) == 3:
            print(f"OK|plan|{argv[2]} aprobado (hash {approve_plan(argv[2])[:12]})")
        elif cmd == "start" and len(argv) == 3:
            start_plan(argv[2])
            print(f"OK|plan|{argv[2]} en ejecucion")
        elif cmd == "linea" and len(argv) == 3:
            d = render_status_line(argv[2])
            print(json.dumps(d, ensure_ascii=False) if d else "OK|linea|sin plan activo (fichero borrado)")
        elif cmd == "limites" and len(argv) in (3, 4):
            plan = load_json(os.path.join(plan_dir(argv[2]), "plan.json"))
            tl = None
            if len(argv) == 4:
                tl = load_json(os.path.join(plan_dir(argv[2]), "tareas", f"{argv[3]}.json")).get("limites")
            print(json.dumps(effective_limits(load_policy(), plan.get("politica"), tl), indent=2))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except IllegalTransition as e:
        print(f"FAIL|transicion|{e}")
        return 1
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"FAIL|estado|{type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
