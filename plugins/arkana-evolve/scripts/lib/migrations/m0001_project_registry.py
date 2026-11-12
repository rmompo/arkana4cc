"""0001 · Registro del proyecto y carpetas fijas.

Crea `arkana-project.json` (versionado: el registro compartido de componentes con su UUID inmutable y el sello `layout`) y las carpetas fijas del repo
de ARKANA, cada una con su `.gitkeep` para que existan en cualquier clon sin instalar nada:

  arkana-incoming/   cola local de entrada de documentos (solo se versiona `.gitkeep` y el `.gitignore` interno, que ignora el resto)
  arkana-knowledge/  decisiones, lecciones y metodología
  arkana-docs/       documentos de origen; `arkana-docs/md/` guarda sus versiones en Markdown

No pisa nada de lo que existe. Si `arkana-project.json` ya existe (otra persona migró y empujó), no regenera ningún UUID: solo comprueba que los alias del
manifiesto local estén en el registro y anota la migración como aplicada en esta instalación.
"""
import datetime
import os
import re
import uuid

from arkana_core import datafiles
import _legacy

ID = "0001"
TITLE = "registro del proyecto (arkana-project.json) y carpetas fijas"
SCOPE = ("shared", "local")

PROJECT = "arkana-project.json"
UUID_RX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
INCOMING_GITIGNORE = "*\n!.gitignore\n!.gitkeep\n"
FILES = [  # (carpeta, fichero, contenido)
    ("arkana-incoming", ".gitkeep", ""),
    ("arkana-incoming", ".gitignore", INCOMING_GITIGNORE),
    ("arkana-knowledge", ".gitkeep", ""),
    ("arkana-docs", ".gitkeep", ""),
    (os.path.join("arkana-docs", "md"), ".gitkeep", ""),
]


def _rel(folder, name):
    return os.path.join(folder, name)


def touches(ctx):
    return [PROJECT] + [_rel(d, f) for d, f, _ in FILES]


def detect(ctx):
    if not os.path.isfile(ctx.project_path):
        return True
    if any(not os.path.isfile(ctx.path(d, f)) for d, f, _ in FILES):
        return True
    return ID not in ctx.applied_local()


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manifest_aliases(ctx, rep):
    """Alias de las piezas del manifiesto local (leído en crudo, sea cual sea su versión), con `arkana` primero. Sin manifiesto: solo `arkana` (con aviso)."""
    aliases = [a for a, _ in _legacy.raw_pieces(ctx)]
    if len(aliases) == 1:
        rep.add("WARN", ID, "el manifiesto local no tiene componentes: el registro solo lleva `arkana`; da de alta los componentes y vuelve a ejecutar apply")
    return ["arkana"] + [a for a in aliases if a != "arkana"]


def _workspace_block(ctx):
    base = datafiles.read_json(os.path.join(ctx.state, "arkana.json"), {}) or {}
    ws = base.get("workspace") or {}
    name = ws.get("name") or os.path.basename(os.path.dirname(ctx.home)) or "workspace"
    return {"id": ws.get("id") or str(uuid.uuid4()), "name": name}


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    aliases = _manifest_aliases(ctx, rep)
    proj = ctx.project()
    if proj is None:
        doc = {"schema_version": 1, "layout": 1, "workspace": _workspace_block(ctx),
               "components": [{"id": str(uuid.uuid4()), "alias": a} for a in aliases],
               "history": [{"id": ID, "date": _now()}]}
        rep.add(st, "registro", f"{PROJECT} {'se crearía' if ctx.dry else 'creado'} con {len(aliases)} piezas, cada una con su UUID")
        if not ctx.dry:
            datafiles.atomic_write_json(ctx.project_path, doc)
    else:
        known = {c.get("alias") for c in proj.get("components", []) if isinstance(c, dict)}
        sin = [a for a in aliases if a not in known]
        rep.add("OK", "registro", f"{PROJECT} ya existe: no se regeneran UUID")
        if sin:
            rep.add("WARN", "registro", "alias del manifiesto local que no están en el registro: " + ", ".join(sin) + " (se darán de alta con component add)")
        if int(proj.get("layout", 0) or 0) < 1 and not ctx.dry:
            proj["layout"] = 1
            proj.setdefault("history", []).append({"id": ID, "date": _now()})
            datafiles.atomic_write_json(ctx.project_path, proj)
            rep.add("OK", "registro", "sello de layout puesto a 1")
    for d, f, content in FILES:
        ruta = ctx.path(d, f)
        rel = _rel(d, f)
        if os.path.isfile(ruta):
            if f == ".gitignore" and open(ruta, encoding="utf-8").read() != content:
                rep.add("WARN", "carpetas", f"{rel} existe con otro contenido: no se toca (debe ignorar todo salvo .gitignore y .gitkeep)")
            continue
        rep.add(st, "carpetas", f"{rel} {'se crearía' if ctx.dry else 'creado'}")
        if not ctx.dry:
            datafiles.atomic_write(ruta, content)
    if not ctx.dry:
        ctx.mark_applied(ID)


def verify(ctx):
    problems = []
    p = ctx.project()
    if not isinstance(p, dict):
        return [f"falta o no es válido {PROJECT}"]
    if int(p.get("layout", 0) or 0) < 1:
        problems.append("el sello layout es menor que 1")
    if not UUID_RX.match(str((p.get("workspace") or {}).get("id", ""))):
        problems.append("workspace.id no es un UUID v4")
    comps = p.get("components")
    if not isinstance(comps, list) or not comps:
        problems.append("components está vacío")
    else:
        al = [c.get("alias") for c in comps if isinstance(c, dict)]
        if len(set(al)) != len(al) or "arkana" not in al:
            problems.append("los alias del registro están repetidos o falta `arkana`")
        if any(not UUID_RX.match(str(c.get("id", ""))) for c in comps if isinstance(c, dict)):
            problems.append("algún componente no tiene UUID v4")
        ids = [c.get("id") for c in comps if isinstance(c, dict)]
        if len(set(ids)) != len(ids):
            problems.append("hay UUID repetidos en el registro")
    for d, f, _ in FILES:
        if not os.path.isfile(ctx.path(d, f)):
            problems.append(f"falta {_rel(d, f)}")
    return problems
