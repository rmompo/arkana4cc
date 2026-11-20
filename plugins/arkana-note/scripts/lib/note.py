#!/usr/bin/env python3
"""Notas de la persona usuaria en un workspace de Arkana (locales, sin red, solo biblioteca estándar).

  add      --title X [--text TEXTO] [--component C|*]
  list     [--status active|removed|all] [--component C] [--q TEXTO] [--id ID] [--json]       (por defecto: activas; --id muestra la nota entera)
           salida: una tabla (identificador|componente|titulo|texto), las modificadas más recientemente primero
  modify   --id ID [--title X] [--text T] [--component C|*] [--restore]
  delete   --id ID                                      borrado lógico: queda en `removed` (modify --restore la recupera)
  validate                                              solo lectura (lo usa `check`)
  install                                               crea .arkana/arkana-note/notes.json si falta
  fix                                                   repara el contador y los campos que faltan
  rename   --from A --to B                              cambia el alias de un componente en las notas (lo invoca `component edit --rename`)
  Opciones comunes: --home DIR (carpeta del repo de Arkana; por defecto se localiza)  --dry-run (add, modify, delete, install, fix)  --json

Una nota es: id (`n-001`…), título, texto (opcional), componente (alias o `*` = todos) y fechas. Estados: active, removed.
Los datos viven en `.arkana/arkana-note/notes.json` (local, no se versiona); `export --include-data` los lleva a otra máquina.
"""
import argparse
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402

STATES = ("active", "removed")
FIELDS = ("id", "titulo", "texto", "estado", "componente", "creada", "modificada")
ID_RE = re.compile(r"^n-\d{3,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ALL = "*"
REL = os.path.join("arkana-note", "notes.json")
TEXT_MAX = 60                                                       # ancho del texto en la tabla de `list`


class NError(Exception):
    def __init__(self, msg, cod=1):
        super().__init__(msg)
        self.cod = cod


def today():
    return datetime.date.today().isoformat()


def find_home(arg):
    home = os.path.abspath(arg) if arg else locate.find_home()
    if not home or not os.path.isdir(home):
        raise NError("no hay workspace de Arkana (usa --home o ejecuta dentro de uno)", 3)
    return home


def store(home):
    return os.path.join(locate.state_dir(home), REL)


def load(home):
    d = datafiles.read_json(store(home), None)
    return d if d is not None else {"version": 1, "next": 1, "notas": []}


def save(home, d):
    datafiles.atomic_write_json(store(home), d)


def check_state(v):
    if v not in STATES + ("all",):
        raise NError(f"estado inválido '{v}' (válidos: {', '.join(STATES)}, all)", 2)
    return v


def check_component(home, v):
    if v in (None, "", "none", "all", ALL):
        return ALL
    if v == "arkana":
        return v
    try:
        ws = manifest.load(home)
    except Exception:
        return manifest.canon(v)                                    # sin manifiesto no se puede validar
    c = ws.key(v)                                                   # alias, carpeta o módulo (o con alias:/dir:/mod:)
    if not ws.has(c):
        raise NError(f"componente desconocido: {v} (válidos: {', '.join(manifest.display(a) for a in ws.aliases())}, *)", 2)
    return c


def find(d, id_):
    for n in d["notas"]:
        if n["id"] == id_:
            return n
    raise NError(f"no existe la nota {id_}", 2)


def esc(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def short(text, n=TEXT_MAX):
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[:n - 1] + "…"


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
        raise NError("el título no puede estar vacío", 2)
    d = load(home)
    n = {"id": f"n-{d['next']:03d}", "titulo": a.titulo.strip(), "texto": (a.text or "").strip(), "estado": "active",
         "componente": check_component(home, a.component), "creada": today(), "modificada": today()}
    if a.dry_run:
        return rep.add("DRY", "add", f"{n['id']}: se añadiría «{n['titulo']}»")
    d["notas"].append(n)
    d["next"] += 1
    save(home, d)
    rep.add("OK", n["id"], f"añadida «{n['titulo']}»" + ("" if n["componente"] == ALL else f" ({manifest.display(n['componente'])})"))


def cmd_list(a, home, rep):
    estado = check_state(a.status)
    notas = load(home)["notas"]
    if a.id:
        notas = [find({"notas": notas}, a.id)]                      # una nota concreta, aunque esté borrada
    else:
        notas = [n for n in notas if estado == "all" or n["estado"] == estado]
    if a.component:
        c = check_component(home, a.component)
        notas = [n for n in notas if n.get("componente") in (c, ALL)]   # una nota para `*` afecta a todos
    if a.q:
        q = a.q.lower()
        notas = [n for n in notas if q in (n["titulo"] + " " + n.get("texto", "")).lower()]
    notas.sort(key=lambda n: (n.get("modificada", ""), n["id"]), reverse=True)
    rep.tables = []
    if a.id and notas:
        n = notas[0]
        rep.tables = [f"### {n['id']} · {n['titulo']}", "",
                      f"- componente: {ALL if n.get('componente') in (None, '', ALL) else manifest.display(n['componente'])}",
                      f"- estado: {n['estado']} · creada {n['creada']} · modificada {n['modificada']}", "", n.get("texto") or "(sin texto)"]
    elif notas:
        rep.tables = [f"### notas ({len(notas)})", "", "| identificador | componente | titulo | texto |", "|---|---|---|---|"]
        for n in notas:
            comp = ALL if n.get("componente") in (None, "", ALL) else manifest.display(n["componente"])
            rep.tables.append(f"| {n['id']} | {comp} | {esc(n['titulo'])} | {esc(short(n.get('texto')))} |")
    else:
        rep.tables = ["Sin notas con ese filtro."]
    for n in notas:
        rep.add("INFO", n["id"], f"[{n['estado']}] {n['titulo']} · {n.get('componente') or ALL}")
    if not notas:
        rep.add("INFO", "list", "sin notas con ese filtro")


def cmd_modify(a, home, rep):
    d = load(home)
    n = find(d, a.id)
    cambios = {}
    if a.titulo is not None:
        if not a.titulo.strip():
            raise NError("el título no puede estar vacío", 2)
        cambios["titulo"] = a.titulo.strip()
    if a.text is not None:
        cambios["texto"] = a.text.strip()
    if a.component is not None:
        cambios["componente"] = check_component(home, a.component)
    if a.restore:
        if n["estado"] != "removed":
            raise NError(f"{a.id} no está borrada", 2)
        cambios["estado"] = "active"
    if not cambios:
        raise NError("nada que modificar (indica algún campo o --restore)", 2)
    if n["estado"] == "removed" and not a.restore:
        raise NError(f"{a.id} está borrada: restáurala antes con --restore", 2)
    if a.dry_run:
        return rep.add("DRY", a.id, "cambiaría: " + ", ".join(sorted(cambios)))
    n.update(cambios)
    n["modificada"] = today()
    save(home, d)
    rep.add("OK", a.id, "modificada: " + ", ".join(sorted(cambios)))


def cmd_delete(a, home, rep):
    d = load(home)
    n = find(d, a.id)
    if n["estado"] == "removed":
        return rep.add("OK", a.id, "ya estaba borrada")
    if a.dry_run:
        return rep.add("DRY", a.id, "se marcaría como borrada (removed)")
    n["estado"], n["modificada"] = "removed", today()
    save(home, d)
    rep.add("OK", a.id, f"borrada (borrado lógico): «{n['titulo']}»; modify --restore la recupera")


def problems(d):
    res, vistos = [], set()
    if not isinstance(d.get("notas"), list):
        return [("almacen", "falta la lista 'notas'")]
    for n in d["notas"]:
        i = n.get("id", "?")
        pro = [f"falta '{c}'" for c in ("id", "titulo", "estado", "creada") if not n.get(c)]
        if n.get("id") and not ID_RE.match(n["id"]):
            pro.append(f"id inválido '{n['id']}'")
        if n.get("id") in vistos:
            pro.append("id duplicado")
        vistos.add(n.get("id"))
        if n.get("estado") and n["estado"] not in STATES:
            pro.append(f"estado inválido '{n['estado']}'")
        for c in ("creada", "modificada"):
            if n.get(c) and not DATE_RE.match(n[c]):
                pro.append(f"fecha inválida en '{c}'")
        res += [(i, p) for p in pro]
    nums = [int(n["id"][2:]) for n in d["notas"] if isinstance(n.get("id"), str) and ID_RE.match(n["id"])]
    if nums and d.get("next", 0) <= max(nums):
        res.append(("almacen", f"el contador 'next' ({d.get('next')}) no supera el mayor id: /arkana-note:fix"))
    return res


def cmd_validate(a, home, rep):
    p = store(home)
    if not os.path.isfile(p):
        return rep.add("WARN", "almacen", f"falta {REL}: /arkana-note:install")
    d = datafiles.read_json(p, None)
    if not isinstance(d, dict):
        return rep.add("FAIL", "almacen", f"{REL} no es un JSON válido")
    pro = problems(d)
    for i, m in pro:
        rep.add("FAIL", f"nota:{i}", m)
    if not pro:
        rep.add("OK", "almacen", f"{len(d['notas'])} notas, {sum(1 for n in d['notas'] if n['estado'] == 'active')} activas")


def cmd_fix(a, home, rep):
    p = store(home)
    if not os.path.isfile(p):
        return cmd_install(a, home, rep)
    d = datafiles.read_json(p, None)
    if not isinstance(d, dict) or not isinstance(d.get("notas"), list):
        raise NError(f"{REL} no es reparable automáticamente: revísalo a mano", 1)
    cambios = []
    for n in d["notas"]:
        for c in FIELDS:
            if c not in n:
                n[c] = {"estado": "active", "componente": ALL, "creada": today(), "modificada": today()}.get(c, "")
                cambios.append(f"{n.get('id', '?')}: añadido '{c}'")
    nums = [int(n["id"][2:]) for n in d["notas"] if isinstance(n.get("id"), str) and ID_RE.match(n["id"])]
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
    k = 0
    for n in d.get("notas", []):
        if isinstance(n, dict) and manifest.canon(n.get("componente")) == old:
            n["componente"] = new
            k += 1
    if k and not a.dry_run:
        save(home, d)
    rep.add("DRY" if a.dry_run else "OK", "rename", f"{k} notas pasan de {old} a {new}")


def make_parser():
    p = argparse.ArgumentParser(prog="note.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--home")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(s, dry=True):
        s.add_argument("--json", action="store_true")
        if dry:
            s.add_argument("--dry-run", dest="dry_run", action="store_true")
        return s

    s = common(sub.add_parser("add")); s.add_argument("--title", dest="titulo", required=True); s.add_argument("--text"); s.add_argument("--component")
    s = common(sub.add_parser("list"), dry=False); s.add_argument("--status", default="active"); s.add_argument("--component"); s.add_argument("--q"); s.add_argument("--id")
    s = common(sub.add_parser("modify")); s.add_argument("--id", required=True); s.add_argument("--title", dest="titulo"); s.add_argument("--text")
    s.add_argument("--component"); s.add_argument("--restore", action="store_true")
    s = common(sub.add_parser("delete")); s.add_argument("--id", required=True)
    common(sub.add_parser("validate"), dry=False)
    common(sub.add_parser("install"))
    common(sub.add_parser("fix"))
    s = common(sub.add_parser("rename")); s.add_argument("--from", dest="frm", required=True); s.add_argument("--to", required=True)
    return p


def render(rep, a):
    """`list` en texto: la tabla (o la nota entera); el resto de comandos y --json, el formato común."""
    if a.cmd == "list" and not a.json and getattr(rep, "tables", None) is not None:
        return "\n".join(rep.tables).rstrip("\n") + "\n"
    return rep.render(getattr(a, "json", False))


def main(argv=None):
    try:
        a = make_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-note", a.cmd)
    try:
        home = find_home(a.home)
        {"add": cmd_add, "list": cmd_list, "modify": cmd_modify, "delete": cmd_delete, "validate": cmd_validate,
         "install": cmd_install, "fix": cmd_fix, "rename": cmd_rename}[a.cmd](a, home, rep)
    except NError as e:
        rep.add("FAIL", a.cmd, str(e))
        sys.stdout.write(rep.render(getattr(a, "json", False)))
        return e.cod
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(render(rep, a))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
