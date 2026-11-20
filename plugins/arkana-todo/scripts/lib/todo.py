#!/usr/bin/env python3
"""Lista de tareas de la persona usuaria en un workspace de Arkana (local, sin red, solo biblioteca estándar).

  add      --title X [--priority critical|high|medium|low] [--due AAAA-MM-DD] [--component C|*] [--notes TEXTO]
  list     [--status pending,in-progress,...|all] [--component C] [--priority P] [--overdue] [--json]
           por defecto muestra pending, in-progress, paused y blocked; done, rejected y removed solo si se piden
           salida: una tabla por estado (identificador|prioridad|componente|descripcion|estado), ordenadas por prioridad
  done     --id ID [--reopen]                                   cierra la tarea (done); --reopen la vuelve a pending
  modify   --id ID [--title X] [--status S] [--priority P] [--due D|none] [--component C|*] [--notes T] [--restore]
  delete   --id ID                                              borrado lógico: queda en `removed` (modify --restore la recupera)
  validate                                                      solo lectura (lo usa `check`)
  install                                                       crea .arkana/arkana-todo/todos.json si falta
  fix                                                           repara el contador y los campos que faltan; migra los valores antiguos
  rename   --from A --to B                                      cambia el alias de un componente en las tareas (lo invoca `component edit --rename`)
  Opciones comunes: --home DIR (carpeta del repo de Arkana; por defecto se localiza)  --dry-run (add, done, modify, delete, install, fix)  --json

Estados: pending, in-progress, paused, blocked, done, rejected, removed. Componente: el alias o `*` (todos).
Los valores de versiones anteriores (open, deleted, normal, all, vacío) se leen como pending, removed, medium y `*`; `fix` los reescribe.

Los datos viven en `.arkana/arkana-todo/todos.json` (local, no se versiona); `export --include-data` los lleva a otra máquina.
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402

STATES = ("pending", "in-progress", "paused", "blocked", "done", "rejected", "removed")
ACTIVE = ("pending", "in-progress", "paused", "blocked")            # lo que `list` muestra por defecto
PRIORITIES = ("critical", "high", "medium", "low")
ALL = "*"                                                           # componente: todos
LEGACY_STATE = {"open": "pending", "deleted": "removed"}
LEGACY_PRIORITY = {"normal": "medium"}
FIELDS = ("id", "titulo", "estado", "prioridad", "vence", "componente", "creada", "cerrada", "notas")
ID_RE = re.compile(r"^t-\d{3,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REL = os.path.join("arkana-todo", "todos.json")


class TError(Exception):
    def __init__(self, msg, cod=1):
        super().__init__(msg)
        self.cod = cod


def today():
    return datetime.date.today().isoformat()


def find_home(arg):
    home = os.path.abspath(arg) if arg else locate.find_home()
    if not home or not os.path.isdir(home):
        raise TError("no hay workspace de Arkana (usa --home o ejecuta dentro de uno)", 3)
    return home


def store(home):
    return os.path.join(locate.state_dir(home), REL)


def legacy(t):
    """¿La tarea usa valores de versiones anteriores?"""
    return (t.get("estado") in LEGACY_STATE or t.get("prioridad") in LEGACY_PRIORITY
            or t.get("componente") in ("all", "") and "componente" in t)


def normalize(t):
    """Lleva una tarea a los valores actuales (open→pending, deleted→removed, normal→medium, all/vacío→*)."""
    if not isinstance(t, dict):
        return t
    t["estado"] = LEGACY_STATE.get(t.get("estado"), t.get("estado"))
    t["prioridad"] = LEGACY_PRIORITY.get(t.get("prioridad"), t.get("prioridad"))
    if "componente" in t and t["componente"] in ("all", "", None):
        t["componente"] = ALL
    return t


def load(home, raw=False):
    d = datafiles.read_json(store(home), None)
    if d is None:
        return {"version": 1, "next": 1, "tareas": []}
    if not raw and isinstance(d.get("tareas"), list):
        for t in d["tareas"]:
            normalize(t)
    return d


def save(home, d):
    datafiles.atomic_write_json(store(home), d)


def check_date(v):
    if not DATE_RE.match(v):
        raise TError(f"fecha inválida '{v}' (formato AAAA-MM-DD)", 2)
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        raise TError(f"fecha inexistente '{v}'", 2)
    return v


def check_priority(v):
    v = LEGACY_PRIORITY.get(v, v)
    if v not in PRIORITIES:
        raise TError(f"prioridad inválida '{v}' (válidas: {', '.join(PRIORITIES)})", 2)
    return v


def check_state(v):
    v = LEGACY_STATE.get(v, v)
    if v not in STATES:
        raise TError(f"estado inválido '{v}' (válidos: {', '.join(STATES)})", 2)
    return v


def check_component(home, v):
    if v in (None, "", "none", "all", ALL):
        return ALL
    if v == "arkana":
        return v
    try:
        al = manifest.load(home).aliases()
    except Exception:
        return v                                                  # sin manifiesto no se puede validar
    c = manifest.canon(v)
    if c not in al:
        raise TError(f"componente desconocido: {v} (válidos: {', '.join(al)}, arkana, *)", 2)
    return c


def find(d, id_):
    for t in d["tareas"]:
        if t["id"] == id_:
            return t
    raise TError(f"no existe la tarea {id_}", 2)


def overdue(t):
    return t["estado"] in ACTIVE and bool(t.get("vence")) and t["vence"] < today()


# ---------- comandos ----------
def cmd_install(a, home, rep):
    p = store(home)
    if os.path.isfile(p):
        return rep.add("OK", "almacen", f"{REL} presente")
    if not a.dry_run:
        save(home, load(home))
    rep.add("DRY" if a.dry_run else "OK", "almacen", f"{REL} {'se crearía' if a.dry_run else 'creado'}")


def cmd_add(a, home, rep):
    if not a.titulo.strip():
        raise TError("el título no puede estar vacío", 2)
    d = load(home)
    t = {"id": f"t-{d['next']:03d}", "titulo": a.titulo.strip(), "estado": "pending", "prioridad": check_priority(a.priority),
         "vence": check_date(a.due) if a.due else "", "componente": check_component(home, a.component), "creada": today(),
         "cerrada": "", "notas": a.notes or ""}
    if a.dry_run:
        return rep.add("DRY", "add", f"{t['id']}: se añadiría «{t['titulo']}»")
    d["tareas"].append(t)
    d["next"] += 1
    save(home, d)
    rep.add("OK", t["id"], f"añadida «{t['titulo']}» (prioridad {t['prioridad']}" + (f", vence {t['vence']}" if t["vence"] else "") + ")")


def parse_status(v):
    """`--status`: lista separada por comas, `all` o vacío (= los activos)."""
    if not v:
        return list(ACTIVE)
    if v == "all":
        return list(STATES)
    res = [check_state(x.strip()) for x in v.split(",") if x.strip()]
    if not res:
        raise TError("--status vacío", 2)
    return res


def esc(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def table(tareas, estado):
    """Tabla Markdown de las tareas de un estado, ya ordenadas."""
    L = [f"### {estado} ({len(tareas)})", "", "| identificador | prioridad | componente | descripcion | estado |", "|---|---|---|---|---|"]
    for t in tareas:
        desc = esc(t["titulo"])
        if t.get("vence"):
            desc += f" ({'⚠ vencida ' if overdue(t) else 'vence '}{t['vence']})"
        L.append(f"| {t['id']} | {t.get('prioridad', 'medium')} | {t.get('componente') or ALL} | {desc} | {t['estado']} |")
    return L


def sorted_tasks(tareas):
    orden = {p: i for i, p in enumerate(PRIORITIES)}
    return sorted(tareas, key=lambda t: (orden.get(t.get("prioridad"), 2), t.get("vence") or "9999", t["id"]))


def cmd_list(a, home, rep):
    if a.priority:
        check_priority(a.priority)                                # se valida siempre, aunque no haya tareas
    estados = parse_status(a.status)
    tareas = [t for t in load(home)["tareas"] if t["estado"] in estados]
    if a.component:
        c = check_component(home, a.component)
        tareas = [t for t in tareas if t.get("componente") in (c, ALL)]   # una tarea para `*` afecta a todos
    if a.priority:
        p = check_priority(a.priority)
        tareas = [t for t in tareas if t.get("prioridad") == p]
    if a.overdue:
        tareas = [t for t in tareas if overdue(t)]
    rep.tables = []
    for e in STATES:
        grupo = sorted_tasks([t for t in tareas if t["estado"] == e])
        if grupo:
            rep.tables += table(grupo, e) + [""]
        for t in grupo:
            rep.add("INFO", t["id"], f"[{e}] {t['titulo']} · {t.get('prioridad')} · {t.get('componente') or ALL}"
                    + (f" · vence {t['vence']}" if t.get("vence") else ""))
    if not tareas:
        rep.add("INFO", "list", "sin tareas con ese filtro")
        rep.tables = ["Sin tareas con ese filtro."]


def cmd_done(a, home, rep):
    d = load(home)
    t = find(d, a.id)
    if t["estado"] == "removed":
        raise TError(f"{a.id} está borrada: restáurala antes con modify --restore", 2)
    nuevo = "pending" if a.reopen else "done"
    if t["estado"] == nuevo:
        return rep.add("OK", a.id, f"ya estaba {'pendiente' if a.reopen else 'cerrada'}")
    if a.dry_run:
        return rep.add("DRY", a.id, f"pasaría de {t['estado']} a {nuevo}")
    t["estado"], t["cerrada"] = nuevo, ("" if nuevo != "done" else today())
    save(home, d)
    rep.add("OK", a.id, f"{'reabierta' if a.reopen else 'cerrada'}: «{t['titulo']}»")


def cmd_modify(a, home, rep):
    d = load(home)
    t = find(d, a.id)
    cambios = {}
    if a.titulo is not None:
        if not a.titulo.strip():
            raise TError("el título no puede estar vacío", 2)
        cambios["titulo"] = a.titulo.strip()
    if a.priority is not None:
        cambios["prioridad"] = check_priority(a.priority)
    if a.status is not None:
        e = check_state(a.status)
        if t["estado"] == "removed" and e != "removed" and not a.restore:
            raise TError(f"{a.id} está borrada: usa --restore", 2)
        cambios["estado"] = e
        cambios["cerrada"] = today() if e == "done" else ""
    if a.due is not None:
        cambios["vence"] = "" if a.due == "none" else check_date(a.due)
    if a.component is not None:
        cambios["componente"] = check_component(home, a.component)
    if a.notes is not None:
        cambios["notas"] = a.notes
    if a.restore:
        if t["estado"] != "removed":
            raise TError(f"{a.id} no está borrada", 2)
        cambios.setdefault("estado", "pending")
    if not cambios:
        raise TError("nada que modificar (indica algún campo, --status o --restore)", 2)
    if a.dry_run:
        return rep.add("DRY", a.id, "cambiaría: " + ", ".join(sorted(cambios)))
    t.update(cambios)
    save(home, d)
    rep.add("OK", a.id, "modificada: " + ", ".join(sorted(cambios)))


def cmd_delete(a, home, rep):
    d = load(home)
    t = find(d, a.id)
    if t["estado"] == "removed":
        return rep.add("OK", a.id, "ya estaba borrada")
    if a.dry_run:
        return rep.add("DRY", a.id, "se marcaría como borrada (removed)")
    t["estado"] = "removed"
    save(home, d)
    rep.add("OK", a.id, f"borrada (borrado lógico): «{t['titulo']}»; modify --restore la recupera")


def problems(d):
    """Lista de (id, problema) del almacén."""
    res, vistos = [], set()
    if not isinstance(d.get("tareas"), list):
        return [("almacen", "falta la lista 'tareas'")]
    for t in d["tareas"]:
        normalize(t)
        i = t.get("id", "?")
        pro = [f"falta '{c}'" for c in ("id", "titulo", "estado", "prioridad", "creada") if not t.get(c)]
        if t.get("id") and not ID_RE.match(t["id"]):
            pro.append(f"id inválido '{t['id']}'")
        if t.get("id") in vistos:
            pro.append("id duplicado")
        vistos.add(t.get("id"))
        if t.get("estado") and t["estado"] not in STATES:
            pro.append(f"estado inválido '{t['estado']}'")
        if t.get("prioridad") and t["prioridad"] not in PRIORITIES:
            pro.append(f"prioridad inválida '{t['prioridad']}'")
        for c in ("vence", "creada", "cerrada"):
            if t.get(c) and not DATE_RE.match(t[c]):
                pro.append(f"fecha inválida en '{c}'")
        if t.get("estado") == "done" and not t.get("cerrada"):
            pro.append("cerrada sin fecha de cierre")
        res += [(i, p) for p in pro]
    nums = [int(t["id"][2:]) for t in d["tareas"] if isinstance(t.get("id"), str) and ID_RE.match(t["id"])]
    if nums and d.get("next", 0) <= max(nums):
        res.append(("almacen", f"el contador 'next' ({d.get('next')}) no supera el mayor id: /arkana-todo:fix"))
    return res


def cmd_validate(a, home, rep):
    p = store(home)
    if not os.path.isfile(p):
        return rep.add("WARN", "almacen", f"falta {REL}: /arkana-todo:install")
    d = datafiles.read_json(p, None)
    if not isinstance(d, dict):
        return rep.add("FAIL", "almacen", f"{REL} no es un JSON válido")
    raw = json.loads(json.dumps(d))                                # copia sin normalizar, para detectar valores antiguos
    pro = problems(d)
    for i, m in pro:
        rep.add("FAIL", f"tarea:{i}", m)
    if not pro:
        abiertas = sum(1 for t in d["tareas"] if t["estado"] in ACTIVE)
        vencidas = sum(1 for t in d["tareas"] if overdue(t))
        rep.add("OK", "almacen", f"{len(d['tareas'])} tareas, {abiertas} activas")
        viejas = [t.get("id", "?") for t in raw["tareas"] if isinstance(t, dict) and legacy(t)]
        if viejas:
            rep.add("WARN", "valores-antiguos", f"{len(viejas)} tareas con estado, prioridad o componente de una versión anterior ({', '.join(viejas[:5])}…): /arkana-todo:fix")
        if vencidas:
            rep.add("WARN", "vencidas", f"{vencidas} tareas abiertas vencidas")


def cmd_fix(a, home, rep):
    p = store(home)
    if not os.path.isfile(p):
        return cmd_install(a, home, rep)
    d = load(home, raw=True)
    if not isinstance(d, dict) or not isinstance(d.get("tareas"), list):
        raise TError(f"{REL} no es reparable automáticamente: revísalo a mano", 1)
    cambios = []
    for t in d["tareas"]:
        if isinstance(t, dict) and legacy(t):
            antes = (t.get("estado"), t.get("prioridad"), t.get("componente"))
            normalize(t)
            cambios.append(f"{t.get('id', '?')}: {antes[0]}/{antes[1]}/{antes[2] or '-'} → {t['estado']}/{t['prioridad']}/{t['componente']}")
        for c in FIELDS:
            if c not in t:
                t[c] = {"estado": "pending", "prioridad": "medium", "creada": today(), "componente": ALL}.get(c, "")
                cambios.append(f"{t.get('id', '?')}: añadido '{c}'")
    nums = [int(t["id"][2:]) for t in d["tareas"] if isinstance(t.get("id"), str) and ID_RE.match(t["id"])]
    nuevo = max(nums + [0]) + 1
    if d.get("next", 0) < nuevo:
        d["next"] = nuevo
        cambios.append(f"contador 'next' = {nuevo}")
    if not cambios:
        return rep.add("OK", "fix", "nada que reparar")
    if not a.dry_run:
        save(home, d)
    for c in cambios:
        rep.add("DRY" if a.dry_run else "OK", "fix", c)


def cmd_rename(a, home, rep):
    old, new = manifest.canon(a.frm), manifest.canon(a.to)
    d = load(home)
    n = 0
    for t in d.get("tareas", []):
        if isinstance(t, dict) and manifest.canon(t.get("componente")) == old:
            t["componente"] = new
            n += 1
    if n and not a.dry_run:
        save(home, d)
    rep.add("DRY" if a.dry_run else "OK", "rename", f"{n} tareas pasan de {old} a {new}")


def make_parser():
    p = argparse.ArgumentParser(prog="todo.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, dry=True):
        s.add_argument("--json", action="store_true")
        if dry:
            s.add_argument("--dry-run", dest="dry_run", action="store_true")
        return s

    s = common(sub.add_parser("add")); s.add_argument("--title", dest="titulo", required=True); s.add_argument("--priority", default="medium")
    s.add_argument("--due"); s.add_argument("--component"); s.add_argument("--notes")
    s = common(sub.add_parser("list"), dry=False); s.add_argument("--status", "--state", dest="status", default="")
    s.add_argument("--component"); s.add_argument("--priority"); s.add_argument("--overdue", action="store_true")
    s = common(sub.add_parser("done")); s.add_argument("--id", required=True); s.add_argument("--reopen", action="store_true")
    s = common(sub.add_parser("modify")); s.add_argument("--id", required=True); s.add_argument("--title", dest="titulo"); s.add_argument("--status")
    s.add_argument("--priority"); s.add_argument("--due"); s.add_argument("--component"); s.add_argument("--notes"); s.add_argument("--restore", action="store_true")
    s = common(sub.add_parser("delete")); s.add_argument("--id", required=True)
    common(sub.add_parser("validate"), dry=False)
    common(sub.add_parser("install"))
    common(sub.add_parser("fix"))
    s = common(sub.add_parser("rename")); s.add_argument("--from", dest="frm", required=True); s.add_argument("--to", required=True)
    return p


def main(argv=None):
    try:
        a = make_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-todo", a.cmd)
    try:
        home = find_home(a.home)
        {"add": cmd_add, "list": cmd_list, "done": cmd_done, "modify": cmd_modify, "delete": cmd_delete,
         "validate": cmd_validate, "install": cmd_install, "fix": cmd_fix, "rename": cmd_rename}[a.cmd](a, home, rep)
    except TError as e:
        rep.add("FAIL", a.cmd, str(e))
        sys.stdout.write(rep.render(getattr(a, "json", False)))
        return e.cod
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(render(rep, a))
    return rep.exit_code()


def render(rep, a):
    """`list` en texto: tablas por estado; el resto de comandos y --json, el formato común."""
    if a.cmd == "list" and not a.json and getattr(rep, "tables", None) is not None:
        return "\n".join(rep.tables).rstrip("\n") + "\n"
    return rep.render(getattr(a, "json", False))


if __name__ == "__main__":
    sys.exit(main())
