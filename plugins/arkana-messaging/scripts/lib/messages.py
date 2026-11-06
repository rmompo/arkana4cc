#!/usr/bin/env python3
"""Mensajes entre componentes de un workspace de Arkana (almacén local, sin git ni red). Lo invoca messaging.sh.

  put     --type notice|task|review|question --subject T [--to LISTA|all|arkana] [--priority normal|high]
          [--body-file F] [--instructions-file F] [--criteria-file F] [--refs "ID.."] [--commits "SHA.."] [--dry-run] [--json]
  put     ... [--repeat]                                  mensaje permanente (directriz): no se cierra, se entrega siempre; se da de baja con delete
  put     --done ID --result T | --discard ID --reason T [--for C] | --comment ID --note T [--dry-run] [--json]
  put     --activate ID                                   (solo ARKANA) un repeat «propuesto» pasa a «vigente»
  put     --set-repeticion ID once|repeat                 (remitente o ARKANA) cambia la clase de un mensaje
  put     --delivered ID --for C [--plan P] [--task T]    (solo ARKANA) anota la entrega a un worker de C
  put     --executed ID --for C [--plan P] [--task T]     (solo ARKANA) anota que se ejecutó para C (en repeat: al menos una vez)
  delete  ID [--dry-run] [--json]                         borrado lógico (queda la marca para que viaje en sync y en export)
  get     [--id ID] [--type T] [--state S] [--to C] [--from C] [--pending] [--user U] [--since AAAA-MM-DD] [--n N]
          [--detail ID] [--include-hidden] [--json]
  query   [--unread] [--pending] [--detail [ID]] [--id ID] [--type T] [--state S] [--to C] [--from C] [--user U] [--since AAAA-MM-DD] [--n N] [--repeat]
          [--include-hidden] [--json]   (SOLO LECTURA: id, remitente, asunto y destinatarios; no marca leído ni cambia estado)
  sync    [--reconcile] [--dry-run] [--json]              reconstruye el índice, repara y, con --reconcile, lista candidatos
  reconcile candidates [--to C] [--json]                  grupos de mensajes abiertos con el mismo destinatario
  reconcile apply --origins "ID ID.." --subject T [--type T] [--priority P] [--body-file F] [--instructions-file F]
          [--criteria-file F] [--dry-run] [--json]        UN mensaje resumen; los originales pasan a `reconciled`
  adopt   [--source DIR] [--dry-run] [--json]             adopta una sola vez las comunicaciones del formato antiguo (novedades/)

Quién actúa lo decide el directorio de trabajo y el manifiesto (el componente que contiene el cwd, o ARKANA), nunca un argumento.
Un componente publica solo como él mismo y solo ve lo dirigido a él o escrito por él; ARKANA lo ve todo y es la única que borra
mensajes ajenos. Estados: open | done | discarded | deleted | reconciled (un `notice` no tiene estado salvo deleted/reconciled).
`para` guarda lo escrito (all, alias, lista) y `destinatarios` los reales en ese momento. La confirmación (done/discarded) es por
destinatario (`confirmaciones`); `estado` solo pasa a done cuando todos confirman. Clase `once` (por defecto) o `repeat`.
Almacén: .arkana/arkana-messaging/state/messages/<id>.json (clase data) e índice local state/index.json (se reconstruye).
Salida: ESTADO|ID|detalle y RESUMEN (o --json). Códigos: 0 ok, 1 fallo, 2 uso, 3 precondición.
"""
import argparse
import contextlib
import fcntl
import json
import os
import random
import re
import string
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, netguard, output  # noqa: E402

TYPES = ["notice", "task", "review", "question"]
STATES = ["open", "done", "discarded", "deleted", "reconciled"]
HIDDEN = ("deleted", "reconciled")
PRIORITIES = ["normal", "high"]
RE_ID = re.compile(r"^N\d{6}-\d{4}-[a-z0-9]{4}$")
SCHEMA = 2
REPEATS = ("once", "repeat")
VIGENCIAS = ("vigente", "propuesto")
STORE = os.path.join("arkana-messaging", "state")


class MessageError(Exception):
    def __init__(self, donde, msg, cod=1):
        super().__init__(msg)
        self.donde, self.cod = donde, cod


# ---------- utilidades ----------
def now_utc():
    return datetime.now(timezone.utc)


def iso(dt=None):
    return (dt or now_utc()).strftime("%Y-%m-%dT%H:%M:%SZ")


def shorten(t, n):
    t = " ".join(str(t).split())
    return t if len(t) <= n else t[:n - 1].rstrip() + "…"


def new_id(store):
    for _ in range(50):
        i = f"N{now_utc().strftime('%y%m%d-%H%M')}-" + "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        if not os.path.exists(store.path(i)):
            return i
    raise MessageError("put", "no se pudo generar un id libre")


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [l.strip() for l in f.read().splitlines() if l.strip()]


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


# ---------- almacén ----------
class Store:
    def __init__(self, home):
        self.dir = os.path.join(locate.state_dir(home), STORE)
        self.msgs = os.path.join(self.dir, "messages")
        self.index_file = os.path.join(self.dir, "index.json")
        self.lock_file = os.path.join(self.dir, ".lock")

    def path(self, nid):
        return os.path.join(self.msgs, nid + ".json")

    @contextlib.contextmanager
    def lock(self):
        """Exclusión entre procesos para toda mutación (varias sesiones publicando o cerrando a la vez)."""
        os.makedirs(self.dir, exist_ok=True)
        with open(self.lock_file, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def load(self, nid):
        d = datafiles.read_json(self.path(nid))
        return d if isinstance(d, dict) else None

    def all(self):
        res, bad = [], []
        for f in sorted(os.listdir(self.msgs)) if os.path.isdir(self.msgs) else []:
            if not f.endswith(".json"):
                continue
            d = datafiles.read_json(os.path.join(self.msgs, f))
            if isinstance(d, dict) and d.get("id") == f[:-5] and RE_ID.match(d["id"]):
                res.append(d)
            else:
                bad.append(f)
        return res, bad

    def save(self, m, touch=True):
        if touch:
            m["updated"] = iso()
        datafiles.atomic_write_json(self.path(m["id"]), m)

    def reindex(self):
        msgs, bad = self.all()
        idx = {"schema_version": SCHEMA, "generated": iso(),
               "messages": {m["id"]: index_entry(m) for m in msgs}}
        datafiles.atomic_write_json(self.index_file, idx)
        return msgs, bad


def read_ids(store, actor):
    d = datafiles.read_json(os.path.join(store.dir, "read", f"{actor}.json"), {})
    return d.get("ids", {}) if isinstance(d, dict) else {}


def mark_read(store, actor, ids):
    """Anota como leídos (para `actor`) los mensajes cuyo texto completo se inyectó o se recuperó con get --detail."""
    if not ids:
        return
    with store.lock():
        cur = read_ids(store, actor)
        for i in ids:
            cur.setdefault(i, iso())
        datafiles.atomic_write_json(os.path.join(store.dir, "read", f"{actor}.json"), {"schema_version": SCHEMA, "ids": cur})


def ctx(cwd=None):
    """(home, workspace, almacén, actor). Precondición (exit 3) si no hay workspace o el cwd no es de ningún componente."""
    home = locate.find_home(cwd)
    if not home:
        raise MessageError("workspace", "no hay workspace de Arkana (falta .arkana/arkana.json)", 3)
    try:
        ws = manifest.load(home)
    except manifest.ManifestError as e:
        raise MessageError("workspace", str(e), 3)
    who = ws.owner_of(cwd or os.getcwd())
    if not who:
        raise MessageError("actor", "el directorio actual no pertenece a ningún componente ni a ARKANA: ejecuta desde uno", 3)
    return home, ws, Store(home), who


def is_repeat(m):
    return m.get("repeticion") == "repeat"


def recipients_of(m, ws=None):
    """Destinatarios reales de un mensaje (o de su entrada del índice). Un `repeat` a `all` es de alcance vivo: con `ws`, los componentes
    de ahora. Los mensajes antiguos (sin `destinatarios`) usan `para`."""
    if is_repeat(m) and "all" in (m.get("para") or []) and ws is not None:
        return [a for a in ws.aliases() if a != m.get("de")]
    return list(m.get("destinatarios") or m.get("para") or [])


def is_recipient(m, actor, ws=None):
    if is_repeat(m) and "all" in (m.get("para") or []) and ws is None:
        return actor != m.get("de")
    return actor in recipients_of(m, ws)


def visible(m, actor, ws=None):
    return actor == "arkana" or m.get("de") == actor or is_recipient(m, actor, ws)


def confirmations(m):
    """{alias: estado} de las confirmaciones por destinatario (done|discarded)."""
    c = m.get("confirmaciones") or {}
    return {a: (v.get("estado") if isinstance(v, dict) else v) for a, v in c.items()}


def actor_state(m, actor):
    """Estado de este mensaje para `actor`: su confirmación, o el estado global (mensajes antiguos y avisos)."""
    return confirmations(m).get(actor) or m.get("estado")


def index_entry(m):
    e = {k: m.get(k) for k in ("asunto", "tipo", "de", "para", "destinatarios", "estado", "prioridad", "fecha", "updated", "repeticion", "vigencia")}
    e["confirmaciones"] = confirmations(m)
    e["ejecutados"] = sorted((m.get("ejecuciones") or {}))
    return e


def recipients(ws, spec, sender):
    """(para, destinatarios): lo escrito (canónico, `all` conservado) y los destinatarios reales de este momento."""
    items = [manifest.canon(x) for x in re.split(r"[,\s]+", spec or "all") if x]
    if not items:
        raise MessageError("put", "--to vacío", 2)
    para = ["all"] if "all" in items else sorted(dict.fromkeys(items))
    if "all" in items:
        res = [a for a in ws.aliases() if a != sender]
    else:
        res = []
        for a in items:
            if not ws.has(a):
                raise MessageError("put", f"destinatario desconocido: {a} (componentes: {' '.join(ws.aliases())}, o all)", 2)
            if a != sender and a not in res:
                res.append(a)
    if not res:
        raise MessageError("put", "no queda ningún destinatario distinto del remitente", 2)
    return para, sorted(res)


def author(home):
    email = netguard.git(home, "config", "user.email").stdout.strip()
    u = (email.split("@")[0] if email else "") or os.environ.get("USER", "") or "anon"
    return re.sub(r"[^A-Za-z0-9._-]", "_", u)


def branch_of(ws, alias):
    p = ws.path(alias)
    if os.path.isdir(p):
        r = netguard.git(p, "branch", "--show-current").stdout.strip()
        return r or "desconocida"
    return "desconocida"


def validate(m):
    e = []
    if not RE_ID.match(str(m.get("id", ""))):
        e.append("id no válido")
    a = m.get("asunto", "")
    if not isinstance(a, str) or not 3 <= len(a) <= 80 or "\n" in a:
        e.append("asunto: de 3 a 80 caracteres y una sola línea")
    if m.get("tipo") not in TYPES:
        e.append(f"tipo debe ser uno de: {' '.join(TYPES)}")
    if m.get("prioridad", "normal") not in PRIORITIES:
        e.append("prioridad: normal | high")
    dest = recipients_of(m)
    if not isinstance(m.get("para"), list) or not m["para"] or not dest:
        e.append("para y destinatarios deben ser listas no vacías")
    elif m.get("de") in dest:
        e.append("el remitente no puede ser destinatario")
    if m.get("repeticion", "once") not in REPEATS:
        e.append("repeticion: once | repeat")
    if m.get("vigencia") is not None and (not is_repeat(m) or m["vigencia"] not in VIGENCIAS):
        e.append("vigencia solo en un repeat: vigente | propuesto")
    est = m.get("estado")
    if m.get("tipo") == "notice":
        if est not in (None, *HIDDEN):
            e.append("un 'notice' no tiene estado")
    elif est not in STATES:
        e.append(f"estado debe ser uno de: {' '.join(STATES)}")
    if m.get("tipo") == "task" and not (m.get("instrucciones") and m.get("criterios")):
        e.append("una 'task' necesita --instructions-file y --criteria-file")
    if m.get("tipo") == "review" and not (m.get("cuerpo") or m.get("instrucciones")):
        e.append("una 'review' necesita --body-file o --instructions-file (qué se revisa y qué se espera)")
    if m.get("tipo") == "question" and not m.get("cuerpo") and len(m.get("asunto", "")) < 10:
        e.append("una 'question' necesita --body-file o un asunto que la formule")
    for r in m.get("refs", []):
        if not RE_ID.match(r):
            e.append(f"ref no válida: {r}")
    return e


def build(a, ws, home, store, who, origins=None):
    dt = now_utc()
    for f in (a.cuerpo_file, a.instrucciones_file, a.criterios_file):
        if f and not os.path.isfile(f):
            raise MessageError("put", f"no existe el fichero: {f}", 2)
    para, dest = recipients(ws, a.para, who) if origins is None else (a.para_list, a.para_list)
    m = {"schema_version": SCHEMA, "id": new_id(store), "asunto": (a.asunto or "").strip(), "tipo": a.tipo, "de": who, "para": para,
         "destinatarios": dest, "autor": author(home), "fecha": iso(dt), "rama": branch_of(ws, who), "prioridad": a.prioridad,
         "repeticion": "repeat" if getattr(a, "repetir", False) else "once"}
    if m["repeticion"] == "repeat":
        m["vigencia"] = "vigente" if who == "arkana" else "propuesto"
    if a.cuerpo_file:
        m["cuerpo"] = read_text(a.cuerpo_file)
    if a.instrucciones_file:
        m["instrucciones"] = read_lines(a.instrucciones_file)
    if a.criterios_file:
        m["criterios"] = read_lines(a.criterios_file)
    if getattr(a, "refs", None):
        m["refs"] = a.refs.split()
    if getattr(a, "commits", None):
        m["commits"] = a.commits.split()
    if origins:
        m["origins"] = origins
    if a.tipo != "notice":
        m["estado"] = "open"
    m["historial"] = [{"fecha": m["fecha"], "autor": m["autor"], "accion": "reconciled" if origins else "created", "nota": ""}]
    m["updated"] = m["fecha"]
    errs = validate(m)
    if errs:
        raise MessageError("put", "; ".join(errs), 2)
    return m


def open_groups(msgs, actor, to=None):
    """Grupos (mismo destinatario) de mensajes abiertos visibles: candidatos a reconciliar."""
    g = {}
    for m in msgs:
        if m.get("estado") in (None, "open") and not is_repeat(m) and visible(m, actor) and (not to or manifest.canon(to) in recipients_of(m)):
            g.setdefault(tuple(recipients_of(m)), []).append(m)
    return {k: sorted(v, key=lambda x: x["id"]) for k, v in g.items() if len(v) >= 2}


# ---------- comandos ----------
def cmd_put(a, rep):
    home, ws, store, who = ctx()
    if a.done or a.discard or a.comment or a.activate or a.set_repeticion or a.delivered or a.executed:
        return put_mutate(a, rep, store, who, home, ws)
    if not a.tipo or not a.asunto:
        raise MessageError("put", "faltan --type y --subject", 2)
    with store.lock():
        m = build(a, ws, home, store, who)
        dest = ",".join(m["destinatarios"])
        clase = " repeat" + ("" if m["vigencia"] == "vigente" else " propuesto: ARKANA debe activarlo (put --activate)") if is_repeat(m) else ""
        if a.dry_run:
            rep.add("DRY", "put", f"se guardaría {m['id']} ({m['tipo']}{clase}, {who}→{dest}): {m['asunto']}")
            return
        store.save(m, touch=False)
        store.reindex()
        rep.add("OK", "put", f"{m['id']} guardada ({m['tipo']}{clase}, {who}→{dest}): {m['asunto']}")
        msgs, _ = store.all()
        grp = open_groups(msgs, who).get(tuple(m["destinatarios"]))
        if grp and any(x["id"] == m["id"] for x in grp):
            rep.add("INFO", "reconcile", f"{len(grp)} mensajes abiertos para {dest}: evalúa si se solapan (reconcile candidates --to {m['destinatarios'][0]})")


def put_mutate(a, rep, store, who, home, ws):
    acciones = [x for x in ("done", "discard", "comment", "activate", "set_repeticion", "delivered", "executed") if getattr(a, x)]
    if len(acciones) != 1:
        raise MessageError("put", "usa solo una de --done, --discard, --comment, --activate, --set-repeticion, --delivered o --executed", 2)
    accion = acciones[0]
    nid = a.set_repeticion[0] if accion == "set_repeticion" else getattr(a, accion)
    if not RE_ID.match(nid):
        raise MessageError("put", f"id no válido: {nid}", 2)
    for flag, val, msg in (("done", a.resultado, '--done necesita --result "..."'), ("discard", a.motivo, '--discard necesita --reason "..."'),
                           ("comment", a.nota, '--comment necesita --note "..."'), ("delivered", a.para_alias, "--delivered necesita --for <componente>"),
                           ("executed", a.para_alias, "--executed necesita --for <componente>")):
        if accion == flag and not val:
            raise MessageError("put", msg, 2)
    if accion == "set_repeticion" and a.set_repeticion[1] not in REPEATS:
        raise MessageError("put", "--set-repeticion ID once|repeat", 2)
    if accion in ("activate", "delivered", "executed") and who != "arkana":
        raise MessageError("put", f"solo ARKANA puede usar --{accion.replace('_', '-')}")
    nota = {"done": a.resultado, "discard": a.motivo, "comment": a.nota}.get(accion) or ""
    nota = nota.strip()
    with store.lock():
        m = store.load(nid)
        if not m or not visible(m, who, ws):
            raise MessageError("put", f"no existe la comunicación {nid} (para {who})")
        if m.get("estado") in HIDDEN:
            raise MessageError("put", f"{nid} está {m['estado']}: no admite cambios")
        etiqueta = {"discard": "discarded", "set_repeticion": "repeticion"}.get(accion, accion)
        msg = None
        if accion in ("done", "discard"):
            msg = confirm(m, a, who, ws, accion, nota)
            if msg:
                return rep.add("OK", "put", msg)
        elif accion == "activate":
            if not is_repeat(m):
                raise MessageError("put", f"{nid} no es un repeat: no hay nada que activar")
            if m.get("vigencia") == "vigente":
                return rep.add("OK", "put", f"{nid} ya estaba vigente")
            m["vigencia"] = "vigente"
        elif accion == "set_repeticion":
            nuevo = a.set_repeticion[1]
            if who != "arkana" and m.get("de") != who:
                raise MessageError("put", "solo ARKANA o el componente que lo escribió puede cambiar la clase de un mensaje")
            if m.get("repeticion", "once") == nuevo:
                return rep.add("OK", "put", f"{nid} ya era {nuevo}")
            if nuevo == "repeat":
                if m.get("estado") in ("done", "discarded"):
                    raise MessageError("put", f"{nid} ya está {m['estado']}: un repeat no se cierra")
                m["vigencia"] = "vigente" if who == "arkana" else "propuesto"
            else:
                m.pop("vigencia", None)
            m["repeticion"] = nuevo
            nota = nuevo
        elif accion in ("delivered", "executed"):
            alias = manifest.canon(a.para_alias)
            if alias not in recipients_of(m, ws):
                raise MessageError("put", f"{alias} no es destinatario de {nid}")
            clave = "entregas" if accion == "delivered" else "ejecuciones"
            reg = m.setdefault(clave, {}).setdefault(alias, {"n": 0, "primera": iso()})
            reg.update(n=reg["n"] + 1, ultima=iso(), plan=a.plan or reg.get("plan"), tarea=a.tarea or reg.get("tarea"))
            nota = f"{alias} {a.plan or ''} {a.tarea or ''}".strip()
        m.setdefault("historial", []).append({"fecha": iso(), "autor": author(home), "accion": etiqueta if accion != "discard" else "discarded", "nota": nota})
        if a.dry_run:                                          # el ensayo recorre las mismas validaciones que la ejecución real (sobre una copia en memoria) y solo se salta la escritura
            return rep.add("DRY", "put", f"{nid}: se registraría «{etiqueta}» ({nota[:80]})")
        store.save(m)
        store.reindex()
        rep.add("OK", "put", {"done": f"{nid} marcada como done" + (f" por {a.para_alias}" if a.para_alias else ""),
                               "discard": f"{nid} marcada como discarded" + (f" por {a.para_alias}" if a.para_alias else ""),
                               "comment": f"comentario añadido a {nid}", "activate": f"{nid} vigente", "set_repeticion": f"{nid} pasa a {nota}",
                               "delivered": f"{nid}: entrega anotada ({nota})", "executed": f"{nid}: ejecución anotada ({nota})"}[accion])


def confirm(m, a, who, ws, accion, nota):
    """done/discarded POR DESTINATARIO. Devuelve un texto si no hay nada que escribir (idempotencia); None si ha modificado `m`."""
    nid, nuevo = m["id"], "done" if accion == "done" else "discarded"
    if m["tipo"] == "notice":
        raise MessageError("put", f"{nid} es un notice: no tiene estado, no se puede marcar como {nuevo}")
    if is_repeat(m):
        raise MessageError("put", f"{nid} es un repeat: no se cierra (se da de baja con delete y se sustituye con adopt/reconcile)")
    dest = recipients_of(m, ws)
    if a.para_alias:
        alias = manifest.canon(a.para_alias)
        if alias != who and who != "arkana" and m.get("de") != who:
            raise MessageError("put", "solo ARKANA o el remitente pueden confirmar por otro componente")
    elif who in dest:
        alias = who
    elif len(dest) == 1:
        alias = dest[0]
    else:
        raise MessageError("put", f"{nid} tiene varios destinatarios ({', '.join(dest)}): indica --for <componente>")
    if alias not in dest:
        raise MessageError("put", f"{alias} no es destinatario de {nid}")
    conf = m.setdefault("confirmaciones", {})
    previo = (conf.get(alias) or {}).get("estado") if isinstance(conf.get(alias), dict) else conf.get(alias)
    if previo == nuevo:
        return f"{nid} ya estaba {nuevo} para {alias}"
    if previo or m.get("estado") not in ("open", None):
        raise MessageError("put", f"{nid} ya estaba {previo or m.get('estado')} para {alias}: no se puede marcar como {nuevo}")
    conf[alias] = {"estado": nuevo, ("resultado" if nuevo == "done" else "motivo"): nota, "fecha": iso(), "autor": who}
    if all(d in conf for d in dest):                           # todos han confirmado: el estado global se deriva
        m["estado"] = "done" if any(confirmations(m)[d] == "done" for d in dest) else "discarded"
        m["resultado" if m["estado"] == "done" else "motivo_descarte"] = nota
    return None


def cmd_delete(a, rep):
    home, ws, store, who = ctx()
    if not RE_ID.match(a.id):
        raise MessageError("delete", f"id no válido: {a.id}", 2)
    with store.lock():
        m = store.load(a.id)
        if not m or not visible(m, who, ws):
            raise MessageError("delete", f"no existe la comunicación {a.id} (para {who})")
        if who != "arkana" and m["de"] != who:
            raise MessageError("delete", "solo ARKANA o el componente que la escribió puede borrar un mensaje")
        if m.get("estado") == "deleted":
            return rep.add("OK", "delete", f"{a.id} ya estaba borrada")
        if a.dry_run:
            return rep.add("DRY", "delete", f"{a.id}: se marcaría como borrada")
        m["estado_previo"] = m.get("estado")
        m["estado"] = "deleted"
        m.setdefault("historial", []).append({"fecha": iso(), "autor": author(home), "accion": "deleted", "nota": ""})
        store.save(m)
        store.reindex()
        rep.add("OK", "delete", f"{a.id} borrada (borrado lógico: se conserva la marca)")


def human_detail(d):
    clase = f" · repeat {d.get('vigencia', 'vigente')}" if is_repeat(d) else ""
    l = [f"{d['id']} · {d['tipo']}{' · ' + d['estado'] if d.get('estado') else ''}{clase} · {d['de']}→{','.join(d['para'])}" + (" · PRIORIDAD ALTA" if d.get("prioridad") == "high" else ""),
         f"Asunto: {d['asunto']}", f"Autor: {d.get('autor')} · {d.get('fecha')} · rama {d.get('rama')}"]
    if d.get("destinatarios") and d["destinatarios"] != d["para"]:
        l.append("Destinatarios: " + ", ".join(d["destinatarios"]))
    for k, t in (("refs", "Refs"), ("commits", "Commits"), ("origins", "Resume")):
        if d.get(k):
            l.append(f"{t}: " + " ".join(d[k]))
    if d.get("reconciled_into"):
        l.append("Reconciliada en: " + d["reconciled_into"])
    if d.get("cuerpo"):
        l += ["", d["cuerpo"]]
    for t, k in (("Instrucciones", "instrucciones"), ("Criterios", "criterios")):
        if d.get(k):
            l += ["", f"{t}:"] + [f"  - {x}" for x in d[k]]
    for t, k in (("Resultado", "resultado"), ("Motivo del descarte", "motivo_descarte")):
        if d.get(k):
            l += ["", f"{t}: {d[k]}"]
    for t, k in (("Confirmaciones", "confirmaciones"), ("Entregas a workers", "entregas"), ("Ejecuciones", "ejecuciones")):
        if d.get(k):
            l += ["", f"{t}:"] + [f"  {al}: " + (f"{v.get('estado')} {v.get('resultado') or v.get('motivo') or ''}".strip() if k == "confirmaciones"
                                               else f"{v.get('n')} vez/veces, primera {v.get('primera')}, última {v.get('ultima')} {v.get('plan') or ''} {v.get('tarea') or ''}".rstrip())
                                  for al, v in sorted(d[k].items())]
    l += ["", "Historial:"] + [f"  {h['fecha']} · {h['autor']} · {h['accion']}" + (f": {h['nota']}" if h.get("nota") else "") for h in d.get("historial", [])]
    return "\n".join(l)


def select_msgs(a, msgs, who, ws):
    """Filtros comunes de `get` y `query` (todo en memoria: no escribe nada)."""
    para, de = (manifest.canon(a.para) if a.para else None), (manifest.canon(a.de) if a.de else None)
    sel = []
    for d in msgs:
        est = d.get("estado")
        if est in HIDDEN and not (a.include_hidden or a.estado == est):
            continue
        if (a.id and d["id"] != a.id) or (a.tipo and d["tipo"] != a.tipo) or (a.estado and est != a.estado):
            continue
        if (para and not is_recipient(d, para, ws)) or (de and d["de"] != de) or (a.user and d.get("autor") != a.user):
            continue
        if a.repetir and not is_repeat(d):
            continue
        if a.since and d.get("fecha", "")[:10] < a.since:
            continue
        if a.pendientes and not (d["tipo"] != "notice" and not is_repeat(d) and est == "open" and is_recipient(d, who, ws) and who not in confirmations(d)):
            continue
        sel.append(d)
    return sel


def cmd_get(a):
    home, ws, store, who = ctx()
    msgs, bad = store.all()
    if bad:
        print(f"WARN|get|{len(bad)} ficheros ilegibles en el almacén (sync los lista)", file=sys.stderr if a.json else sys.stdout)
    msgs = [m for m in msgs if visible(m, who, ws)]
    if a.detalle:
        d = next((m for m in msgs if m["id"] == a.detalle), None)
        if not d:
            raise MessageError("get", f"no existe la comunicación {a.detalle} (para {who})")
        print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else human_detail(d))
        mark_read(store, who, [d["id"]])                       # recuperado con get: leído
        return 0
    sel = select_msgs(a, msgs, who, ws)
    sel.sort(key=lambda d: (d.get("fecha", ""), d["id"]), reverse=True)
    sel = sel[:a.n]
    if a.json:
        print(json.dumps(sel, ensure_ascii=False, indent=2))
        return 0
    if not sel:
        print("OK|get|no hay comunicaciones" + (" pendientes" if a.pendientes else "") + f" para {manifest.display(who)}")
        return 0
    print(f"{'ID':<18} {'TIPO':<9} {'ESTADO':<10} {'DE→PARA':<22} {'PRI':<5} ASUNTO")
    for d in sel:
        ruta = d["de"] + "→" + ",".join(d["para"])
        est = (d.get("vigencia") or "repeat") if is_repeat(d) else d.get("estado", "-")
        print(f"{d['id']:<18} {d['tipo']:<9} {est:<10} {shorten(ruta, 21):<22} {'ALTA' if d.get('prioridad') == 'high' else '':<5} {shorten(d['asunto'], 70)}")
    return 0


QUERY_NOTE = ("Consulta de solo lectura: no se ha marcado ningún mensaje como leído ni se ha cambiado ningún estado.\n"
              "Para consumir un mensaje (leerlo y que deje de contar como sin leer) usa /arkana-messaging:get --detail <id>.")


def message_text(d):
    """El mensaje propiamente dicho: cuerpo, instrucciones y criterios (sin metadatos ni historial)."""
    l = [d["cuerpo"]] if d.get("cuerpo") else []
    for t, k in (("Instrucciones", "instrucciones"), ("Criterios", "criterios")):
        if d.get(k):
            l += [f"{t}:"] + [f"  - {x}" for x in d[k]]
    return "\n".join(l)


def cmd_query(a):
    """Lista de SOLO LECTURA: id, remitente, asunto y destinatarios (`para`, como se escribió). Con --detail, también el mensaje.
    No marca nada como leído ni cambia ningún estado (ni siquiera con --detail): no escribe en el almacén."""
    if a.mensaje and a.mensaje != "*":                       # --detail <id>: equivale a --id <id> --detail
        a.id = a.mensaje
    home, ws, store, who = ctx()
    msgs, bad = store.all()
    if bad:
        print(f"WARN|query|{len(bad)} ficheros ilegibles en el almacén (sync los lista)", file=sys.stderr if a.json else sys.stdout)
    sel = select_msgs(a, [m for m in msgs if visible(m, who, ws)], who, ws)
    if a.sin_leer:                                           # los mismos que cuenta el hook: sin leer, de otros, para este actor y no propuestos
        seen = read_ids(store, who)
        sel = [d for d in sel if d["id"] not in seen and d.get("de") != who and is_recipient(d, who, ws) and d.get("vigencia") != "propuesto"]
    sel.sort(key=lambda d: (d.get("fecha", ""), d["id"]), reverse=True)
    sel = sel[:a.n]
    if a.json:
        out = [dict({"id": d["id"], "de": d["de"], "asunto": d["asunto"], "para": d["para"]},
                    **({k: d[k] for k in ("cuerpo", "instrucciones", "criterios") if d.get(k)} if a.mensaje else {})) for d in sel]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if not sel:
        print("OK|query|no hay comunicaciones" + (" sin leer" if a.sin_leer else "") + f" para {manifest.display(who)}")
    else:
        print(f"{'ID':<18} {'DE':<10} {'PARA':<24} ASUNTO")
        for d in sel:
            print(f"{d['id']:<18} {d['de']:<10} {shorten(','.join(d['para']), 23):<24} {shorten(d['asunto'], 70)}")
            if a.mensaje:
                txt = message_text(d)
                print("\n".join("    " + l for l in (txt.splitlines() or ["(sin texto)"])) + "\n")
    print("\n" + QUERY_NOTE)
    return 0


def cmd_sync(a, rep):
    home, ws, store, who = ctx()
    with store.lock():
        msgs, bad = store.all()
        for b in bad:
            rep.add("WARN", f"sync:{b}", "fichero ilegible o con id distinto del nombre")
        healed = 0
        by_id = {m["id"]: m for m in msgs}
        for m in msgs:                      # repara una reconciliación cortada a medias
            for o in m.get("origins") or []:
                x = by_id.get(o)
                if x and x.get("estado") not in HIDDEN:
                    healed += 1
                    if not a.dry_run:
                        x["estado"], x["reconciled_into"] = "reconciled", m["id"]
                        x.setdefault("historial", []).append({"fecha": iso(), "autor": "sync", "accion": "reconciled", "nota": f"completada ({m['id']})"})
                        store.save(x)
        if healed:
            rep.add("DRY" if a.dry_run else "OK", "sync-reparar", f"{healed} mensajes originales pasados a reconciled")
        if not a.dry_run:
            msgs, _ = store.reindex()
        cuenta = {}
        for m in msgs:
            cuenta[m.get("estado") or "notice"] = cuenta.get(m.get("estado") or "notice", 0) + 1
        rep.add("DRY" if a.dry_run else "OK", "sync", f"{len(msgs)} mensajes; índice {'(no escrito)' if a.dry_run else 'reconstruido'}: " + ", ".join(f"{k} {v}" for k, v in sorted(cuenta.items())))
        if a.reconcile:
            groups = open_groups(msgs, who)
            rep.add("INFO" if groups else "OK", "reconcile", f"{len(groups)} grupos con candidatos" + ("" if not groups else ": reconcile candidates --json"))


def cmd_reconcile(a, rep=None):
    home, ws, store, who = ctx()
    msgs, _ = store.all()
    if a.sub == "candidates":
        groups = open_groups(msgs, who, a.para)
        out = [{"para": list(k), "mensajes": [{"id": m["id"], "tipo": m["tipo"], "de": m["de"], "asunto": m["asunto"], "prioridad": m.get("prioridad", "normal"),
                                              "fecha": m["fecha"], "cuerpo": shorten(m.get("cuerpo", ""), 400)} for m in v]} for k, v in sorted(groups.items())]
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        elif not out:
            print("OK|reconcile|no hay mensajes abiertos que compartan destinatario")
        for g in (out if not a.json else []):
            print(f"GRUPO|{','.join(g['para'])}|{len(g['mensajes'])} mensajes abiertos")
            for m in g["mensajes"]:
                print(f"  {m['id']} {m['tipo']:<8} {m['de']}: {m['asunto']}")
        return 0
    ids = a.origins.split()
    if len(ids) < 2 or not all(RE_ID.match(i) for i in ids) or len(set(ids)) != len(ids):
        raise MessageError("reconcile", "--origins necesita al menos dos ids distintos y válidos", 2)
    a.tipo = a.tipo or "notice"
    with store.lock():
        by = {m["id"]: m for m in store.all()[0]}
        orig = []
        for i in ids:
            m = by.get(i)
            if not m or not visible(m, who, ws):
                raise MessageError("reconcile", f"no existe {i} (para {who})")
            if is_repeat(m):
                raise MessageError("reconcile", f"{i} es un repeat: no se reconcilia (usa delete y crea el nuevo)")
            if m.get("estado") not in (None, "open"):
                raise MessageError("reconcile", f"{i} está {m.get('estado')}: solo se reconcilian mensajes abiertos")
            orig.append(m)
        if len({tuple(recipients_of(m)) for m in orig}) != 1:
            raise MessageError("reconcile", "los mensajes deben tener el mismo destinatario")
        a.para_list = [p for p in recipients_of(orig[0]) if p != who]
        if not a.para_list:
            raise MessageError("reconcile", "el resumen se quedaría sin destinatarios (el actor es el destinatario)")
        a.refs = a.commits = None
        if any(m.get("prioridad") == "high" for m in orig):
            a.prioridad = "high"
        new = build(a, ws, home, store, who, origins=ids)
        if a.dry_run:
            return rep.add("DRY", "reconcile", f"se crearía {new['id']} resumiendo {len(ids)} mensajes")
        store.save(new, touch=False)                        # primero el resumen; si se corta aquí, sync completa lo demás
        for m in orig:
            m["estado"], m["reconciled_into"] = "reconciled", new["id"]
            m.setdefault("historial", []).append({"fecha": iso(), "autor": new["autor"], "accion": "reconciled", "nota": f"resumido en {new['id']}"})
            store.save(m)
        store.reindex()
        rep.add("OK", "reconcile", f"{new['id']} resume {len(ids)} mensajes (pasan a reconciled; conserva origins)")


def migrate_legacy(d, ws):
    """Mensaje del formato antiguo (de/para sueltos, sin `updated`) → esquema actual; None si no es convertible."""
    de = manifest.canon(d.get("de", ""))
    if not RE_ID.match(str(d.get("id", ""))) or not ws.has(de) or not d.get("asunto") or d.get("tipo") not in TYPES:
        return None
    para = d.get("para")
    para = [manifest.canon(p) for p in (para if isinstance(para, list) else [para] if para else [])]
    para = sorted(p for p in (para or [x for x in ws.aliases() if x != de]) if p != de and ws.has(p))
    if not para:
        return None
    m = dict(d, de=de, para=para)
    hist = m.get("historial") or []
    m["updated"] = (hist[-1].get("fecha") if hist else None) or m.get("fecha") or iso()
    m.pop("_ruta", None)
    return m


def cmd_adopt(a, rep):
    home, ws, store, who = ctx()
    src = os.path.abspath(a.source or os.path.join(home, "novedades"))
    if not os.path.isdir(src):
        raise MessageError("adopt", f"no existe la carpeta de origen: {os.path.basename(src)}", 3)
    n_new = n_old = 0
    with store.lock():
        for dp, dns, fns in os.walk(src):
            dns.sort()
            for f in sorted(fns):
                rel = os.path.relpath(os.path.join(dp, f), src)
                if f.endswith(".md"):
                    if f != "LEEME.md":
                        rep.add("WARN", f"adopt:{rel}", "formato .md antiguo: no se adopta (conviértela a mano o ignórala)")
                    continue
                if not f.endswith(".json"):
                    continue
                d = datafiles.read_json(os.path.join(dp, f))
                m = migrate_legacy(d, ws) if isinstance(d, dict) else None
                if not m or validate(m):
                    rep.add("WARN", f"adopt:{rel}", "no convertible: " + ("; ".join(validate(m)) if m else "JSON o campos no válidos"))
                    continue
                if os.path.exists(store.path(m["id"])):
                    n_old += 1
                    continue
                n_new += 1
                rep.add("DRY" if a.dry_run else "OK", f"adopt:{m['id']}", f"{m['tipo']} {m['de']}→{','.join(m['para'])}: {shorten(m['asunto'], 60)}")
                if not a.dry_run:
                    store.save(m, touch=False)
        if not a.dry_run:
            store.reindex()
    rep.add("DRY" if a.dry_run else "OK", "adopt", f"{n_new} adoptadas, {n_old} ya estaban en el almacén")


def make_parser():
    p = argparse.ArgumentParser(prog="messaging.sh", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)

    def common(x, dry=True):
        x.add_argument("--json", action="store_true")
        if dry:
            x.add_argument("--dry-run", dest="dry_run", action="store_true")
        return x

    pp = common(s.add_parser("put"))
    pp.add_argument("--type", dest="tipo", choices=TYPES)
    pp.add_argument("--subject", dest="asunto")
    pp.add_argument("--to", dest="para", default="all")
    pp.add_argument("--priority", dest="prioridad", choices=PRIORITIES, default="normal")
    for f in ("body", "instructions", "criteria"):
        pp.add_argument(f"--{f}-file", dest={"body": "cuerpo", "instructions": "instrucciones", "criteria": "criterios"}[f] + "_file")
    pp.add_argument("--refs")
    pp.add_argument("--commits")
    pp.add_argument("--done")
    pp.add_argument("--result", dest="resultado")
    pp.add_argument("--discard")
    pp.add_argument("--reason", dest="motivo")
    pp.add_argument("--comment")
    pp.add_argument("--note", dest="nota")
    pp.add_argument("--repeat", dest="repetir", action="store_true")
    pp.add_argument("--activate")
    pp.add_argument("--set-repeticion", dest="set_repeticion", nargs=2, metavar=("ID", "once|repeat"))
    pp.add_argument("--delivered")
    pp.add_argument("--executed")
    pp.add_argument("--for", dest="para_alias")
    pp.add_argument("--plan")
    pp.add_argument("--task", dest="tarea")
    d = common(s.add_parser("delete"))
    d.add_argument("id")
    g = common(s.add_parser("get"), dry=False)
    g.add_argument("--id")
    g.add_argument("--type", dest="tipo", choices=TYPES)
    g.add_argument("--state", dest="estado", choices=STATES)
    g.add_argument("--to", dest="para")
    g.add_argument("--from", dest="de")
    g.add_argument("--user")
    g.add_argument("--since")
    g.add_argument("--n", type=int, default=20)
    g.add_argument("--pending", dest="pendientes", action="store_true")
    g.add_argument("--detail", dest="detalle")
    g.add_argument("--include-hidden", dest="include_hidden", action="store_true")
    g.add_argument("--repeat", dest="repetir", action="store_true")
    qy = common(s.add_parser("query"), dry=False)
    qy.add_argument("--id")
    qy.add_argument("--type", dest="tipo", choices=TYPES)
    qy.add_argument("--state", dest="estado", choices=STATES)
    qy.add_argument("--to", dest="para")
    qy.add_argument("--from", dest="de")
    qy.add_argument("--user")
    qy.add_argument("--since")
    qy.add_argument("--n", type=int, default=20)
    qy.add_argument("--pending", dest="pendientes", action="store_true")
    qy.add_argument("--unread", dest="sin_leer", action="store_true")
    qy.add_argument("--detail", dest="mensaje", nargs="?", const="*", metavar="ID")       # solo: añade el texto a lo listado; con id: ese mensaje, con su texto
    qy.add_argument("--include-hidden", dest="include_hidden", action="store_true")
    qy.add_argument("--repeat", dest="repetir", action="store_true")
    sy = common(s.add_parser("sync"))
    sy.add_argument("--reconcile", action="store_true")
    r = s.add_parser("reconcile")
    rs = r.add_subparsers(dest="sub", required=True)
    rc = common(rs.add_parser("candidates"), dry=False)
    rc.add_argument("--to", dest="para")
    ra = common(rs.add_parser("apply"))
    ra.add_argument("--origins", required=True)
    ra.add_argument("--subject", dest="asunto", required=True)
    ra.add_argument("--type", dest="tipo", choices=TYPES)
    ra.add_argument("--priority", dest="prioridad", choices=PRIORITIES, default="normal")
    for f, k in (("body", "cuerpo"), ("instructions", "instrucciones"), ("criteria", "criterios")):
        ra.add_argument(f"--{f}-file", dest=k + "_file")
    ad = common(s.add_parser("adopt"))
    ad.add_argument("--source")
    return p


def main(argv):
    try:
        a = make_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    skill = a.cmd + (f" {a.sub}" if a.cmd == "reconcile" else "")
    rep = output.Report("arkana-messaging", skill)
    try:
        if a.cmd in ("get", "query") or (a.cmd == "reconcile" and a.sub == "candidates"):
            return {"get": cmd_get, "query": cmd_query}[a.cmd](a) if a.cmd != "reconcile" else cmd_reconcile(a)
        {"put": cmd_put, "delete": cmd_delete, "sync": cmd_sync, "reconcile": cmd_reconcile, "adopt": cmd_adopt}[a.cmd](a, rep)
    except MessageError as e:
        rep.add("FAIL", e.donde, str(e))
        sys.stdout.write(rep.render(a.json))
        return e.cod
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(rep.render(getattr(a, "json", False)))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
