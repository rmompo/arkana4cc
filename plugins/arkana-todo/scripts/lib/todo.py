#!/usr/bin/env python3
"""Lista de tareas de la persona usuaria en un workspace de Arkana (local, sin red, solo biblioteca estándar).

  add      --title X [--priority high|normal|low] [--due AAAA-MM-DD] [--component C] [--notes TEXTO]
  list     [--state open|done|deleted|all] [--component C] [--priority P] [--overdue] [--json]       (por defecto: abiertas)
  done     --id ID [--reopen]                                   cierra la tarea; --reopen la vuelve a abrir
  modify   --id ID [--title X] [--priority P] [--due D|none] [--component C|none] [--notes T] [--restore]
  delete   --id ID                                              borrado lógico: queda con estado `deleted` (modify --restore la recupera)
  validate                                                      solo lectura (lo usa `check`)
  install                                                       crea .arkana/arkana-todo/todos.json si falta
  fix                                                           repara el contador y los campos que faltan
  Opciones comunes: --home DIR (carpeta del repo de Arkana; por defecto se localiza)  --dry-run (add, done, modify, delete, install, fix)  --json

Los datos viven en `.arkana/arkana-todo/todos.json` (local, no se versiona); `export --include-data` los lleva a otra máquina.
"""
import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402

STATES = ("open", "done", "deleted")
PRIORITIES = ("high", "normal", "low")
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


def load(home):
    d = datafiles.read_json(store(home), None)
    if d is None:
        return {"version": 1, "next": 1, "tareas": []}
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
    if v not in PRIORITIES:
        raise TError(f"prioridad inválida '{v}' (válidas: {', '.join(PRIORITIES)})", 2)
    return v


def check_component(home, v):
    if v in (None, "", "none"):
        return ""
    if v in ("all", "arkana"):
        return v
    try:
        al = manifest.load(home).aliases()
    except Exception:
        return v                                                  # sin manifiesto no se puede validar
    c = manifest.canon(v)
    if c not in al:
        raise TError(f"componente desconocido: {v} (válidos: {', '.join(al)}, arkana, all)", 2)
    return c


def find(d, id_):
    for t in d["tareas"]:
        if t["id"] == id_:
            return t
    raise TError(f"no existe la tarea {id_}", 2)


def overdue(t):
    return t["estado"] == "open" and bool(t.get("vence")) and t["vence"] < today()


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
    t = {"id": f"t-{d['next']:03d}", "titulo": a.titulo.strip(), "estado": "open", "prioridad": check_priority(a.priority),
         "vence": check_date(a.due) if a.due else "", "componente": check_component(home, a.component), "creada": today(),
         "cerrada": "", "notas": a.notes or ""}
    if a.dry_run:
        return rep.add("DRY", "add", f"{t['id']}: se añadiría «{t['titulo']}»")
    d["tareas"].append(t)
    d["next"] += 1
    save(home, d)
    rep.add("OK", t["id"], f"añadida «{t['titulo']}» (prioridad {t['prioridad']}" + (f", vence {t['vence']}" if t["vence"] else "") + ")")


def cmd_list(a, home, rep):
    tareas = load(home)["tareas"]
    if a.state != "all":
        tareas = [t for t in tareas if t["estado"] == a.state]
    if a.component:
        tareas = [t for t in tareas if t.get("componente") == manifest.canon(a.component)]
    if a.priority:
        tareas = [t for t in tareas if t.get("prioridad") == check_priority(a.priority)]
    if a.overdue:
        tareas = [t for t in tareas if overdue(t)]
    orden = {p: i for i, p in enumerate(PRIORITIES)}
    tareas.sort(key=lambda t: (t["estado"] != "open", t.get("vence") or "9999", orden.get(t.get("prioridad"), 1), t["id"]))
    for t in tareas:
        marca = "VENCIDA " if overdue(t) else ""
        rep.add("INFO", t["id"], f"[{t['estado']}] {marca}{t['titulo']} · {t['prioridad']}" + (f" · vence {t['vence']}" if t.get("vence") else "")
                + (f" · {t['componente']}" if t.get("componente") else ""))
    if not tareas:
        rep.add("INFO", "list", "sin tareas con ese filtro")


def cmd_done(a, home, rep):
    d = load(home)
    t = find(d, a.id)
    if t["estado"] == "deleted":
        raise TError(f"{a.id} está borrada: restáurala antes con modify --restore", 2)
    nuevo = "open" if a.reopen else "done"
    if t["estado"] == nuevo:
        return rep.add("OK", a.id, f"ya estaba {'abierta' if a.reopen else 'cerrada'}")
    if a.dry_run:
        return rep.add("DRY", a.id, f"pasaría de {t['estado']} a {nuevo}")
    t["estado"], t["cerrada"] = nuevo, ("" if a.reopen else today())
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
    if a.due is not None:
        cambios["vence"] = "" if a.due == "none" else check_date(a.due)
    if a.component is not None:
        cambios["componente"] = check_component(home, a.component)
    if a.notes is not None:
        cambios["notas"] = a.notes
    if a.restore:
        if t["estado"] != "deleted":
            raise TError(f"{a.id} no está borrada", 2)
        cambios["estado"] = "open"
    if not cambios:
        raise TError("nada que modificar (indica algún campo o --restore)", 2)
    if a.dry_run:
        return rep.add("DRY", a.id, "cambiaría: " + ", ".join(sorted(cambios)))
    t.update(cambios)
    save(home, d)
    rep.add("OK", a.id, "modificada: " + ", ".join(sorted(cambios)))


def cmd_delete(a, home, rep):
    d = load(home)
    t = find(d, a.id)
    if t["estado"] == "deleted":
        return rep.add("OK", a.id, "ya estaba borrada")
    if a.dry_run:
        return rep.add("DRY", a.id, "se marcaría como borrada")
    t["estado"] = "deleted"
    save(home, d)
    rep.add("OK", a.id, f"borrada (borrado lógico): «{t['titulo']}»; modify --restore la recupera")


def problems(d):
    """Lista de (id, problema) del almacén."""
    res, vistos = [], set()
    if not isinstance(d.get("tareas"), list):
        return [("almacen", "falta la lista 'tareas'")]
    for t in d["tareas"]:
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
    pro = problems(d)
    for i, m in pro:
        rep.add("FAIL", f"tarea:{i}", m)
    if not pro:
        abiertas = sum(1 for t in d["tareas"] if t["estado"] == "open")
        vencidas = sum(1 for t in d["tareas"] if overdue(t))
        rep.add("OK", "almacen", f"{len(d['tareas'])} tareas, {abiertas} abiertas")
        if vencidas:
            rep.add("WARN", "vencidas", f"{vencidas} tareas abiertas vencidas")


def cmd_fix(a, home, rep):
    p = store(home)
    if not os.path.isfile(p):
        return cmd_install(a, home, rep)
    d = datafiles.read_json(p, None)
    if not isinstance(d, dict) or not isinstance(d.get("tareas"), list):
        raise TError(f"{REL} no es reparable automáticamente: revísalo a mano", 1)
    cambios = []
    for t in d["tareas"]:
        for c in FIELDS:
            if c not in t:
                t[c] = {"estado": "open", "prioridad": "normal", "creada": today()}.get(c, "")
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


def make_parser():
    p = argparse.ArgumentParser(prog="todo.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, dry=True):
        s.add_argument("--json", action="store_true")
        if dry:
            s.add_argument("--dry-run", dest="dry_run", action="store_true")
        return s

    s = common(sub.add_parser("add")); s.add_argument("--title", dest="titulo", required=True); s.add_argument("--priority", default="normal")
    s.add_argument("--due"); s.add_argument("--component"); s.add_argument("--notes")
    s = common(sub.add_parser("list"), dry=False); s.add_argument("--state", choices=STATES + ("all",), default="open")
    s.add_argument("--component"); s.add_argument("--priority"); s.add_argument("--overdue", action="store_true")
    s = common(sub.add_parser("done")); s.add_argument("--id", required=True); s.add_argument("--reopen", action="store_true")
    s = common(sub.add_parser("modify")); s.add_argument("--id", required=True); s.add_argument("--title", dest="titulo")
    s.add_argument("--priority"); s.add_argument("--due"); s.add_argument("--component"); s.add_argument("--notes"); s.add_argument("--restore", action="store_true")
    s = common(sub.add_parser("delete")); s.add_argument("--id", required=True)
    common(sub.add_parser("validate"), dry=False)
    common(sub.add_parser("install"))
    common(sub.add_parser("fix"))
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
         "validate": cmd_validate, "install": cmd_install, "fix": cmd_fix}[a.cmd](a, home, rep)
    except TError as e:
        rep.add("FAIL", a.cmd, str(e))
        sys.stdout.write(rep.render(getattr(a, "json", False)))
        return e.cod
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(rep.render(getattr(a, "json", False)))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
