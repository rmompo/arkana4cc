#!/usr/bin/env python3
"""Exportar e importar la configuración (y, opcionalmente, los datos) de un workspace de Arkana en un ZIP.

  transfer.py export --out FICHERO.zip [--include-data] [--force] [--home DIR] [--dry-run] [--json]
  transfer.py import FICHERO.zip [--on-conflict keep|replace|ask] [--home DIR] [--dry-run] [--json]

Qué viaja lo decide cada plugin en su `arkana-plugin.json` (`data[].class`): `config` siempre, `data` solo con --include-data,
`local` y `secret` nunca. `.credentials` no se exporta ni se importa jamás (por clase y por nombre). Las rutas absolutas de
`tools.json` (`path`) tampoco viajan.

El ZIP lleva `arkana-export.json` (versión de esquema, versiones de los plugins, y ruta/clase/tamaño/sha256 de cada fichero) y los
ficheros bajo `files/`. Al importar se valida TODO antes de escribir nada: rutas absolutas, `..`, `\\`, enlaces simbólicos, duplicados,
ficheros que no están en el manifiesto (o al revés), hashes alterados, tamaños desmedidos y destinos que ningún plugin declara.
Si algo falla no se escribe nada. Fusión por fichero: idéntico → se salta; ausente → se crea; distinto → en los registros de clase `data`
manda la marca de borrado (`state: deleted`) y luego `updated` más reciente; en el resto decide `--on-conflict` (`keep` por defecto;
`ask` no escribe lo dudoso y lo lista para que lo resuelvas). Lo que se sustituye deja copia en `.arkana/arkana-workspace/bak/import-<hora>/`.
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import time
import zipfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import contract, datafiles, locate, manifest, output  # noqa: E402

SCHEMA = 1
MANIFEST = "arkana-export.json"
PREFIX = "files/"
MAX_FILES, MAX_ENTRY, MAX_TOTAL = 5000, 50 * 1024 * 1024, 200 * 1024 * 1024
SKIP_NAMES = {".credentials", "__pycache__"}
TOOLS = "arkana-workspace/tools.json"
WORKSPACE = "core/workspace.json"


class TransferError(Exception):
    pass


# ---------- contratos de los plugins ----------
def plugin_roots(home):
    roots = []
    if os.environ.get("ARKANA_PLUGINS_DIR"):
        roots.append(os.environ["ARKANA_PLUGINS_DIR"])
    roots += [os.path.join(home, "plugins"), os.path.abspath(os.path.join(HERE, "..", "..", ".."))]
    return [r for r in roots if os.path.isdir(r)]


def contracts(home):
    """(contratos: {plugin: {"version", "data": [...]}}, avisos)."""
    res, warns = {}, []
    for root in plugin_roots(home):
        for d in sorted(os.listdir(root)):
            pd = os.path.join(root, d)
            if not os.path.isfile(os.path.join(pd, contract.CONTRACT_FILE)):
                continue
            try:
                c = contract.load(pd)
            except contract.ContractError as e:
                warns.append(f"{d}: contrato no válido ({e})")
                continue
            if c["plugin"] in res:
                continue
            ver = (datafiles.read_json(os.path.join(pd, ".claude-plugin", "plugin.json"), {}) or {}).get("version", "?")
            res[c["plugin"]] = {"version": ver, "data": c.get("data") or []}
    return res, warns


def classify(cons, rel):
    """(plugin, clase) del primer dato declarado que cubre `rel` (fichero exacto o carpeta con `/` final); None si ninguno."""
    for plug, c in cons.items():
        for d in c["data"]:
            p = d["path"]
            if rel == p or (p.endswith("/") and rel.startswith(p)):
                return plug, d["class"]
    return None


# ---------- validación de nombres ----------
def safe_rel(name):
    """Ruta relativa normalizada o TransferError. Rechaza absolutas, `..`, `\\`, unidades, NUL y `.credentials`."""
    if not name or "\x00" in name or "\\" in name or name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        raise TransferError(f"ruta no válida: {name!r}")
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise TransferError(f"ruta no válida: {name!r}")
    if any(p == ".credentials" for p in parts):
        raise TransferError(f"{name!r}: las credenciales nunca viajan")
    return name


def sha(b):
    return hashlib.sha256(b).hexdigest()


def tools_without_paths(raw):
    d = json.loads(raw.decode("utf-8"))
    if isinstance(d, dict):
        d["tools"] = [{k: v for k, v in t.items() if k != "path"} for t in d.get("tools", [])]
    return (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


# ---------- exportar ----------
def collect(home, include_data):
    """-> (entradas [(rel, clase, plugin, bytes)], plugins {nombre: versión}, avisos)."""
    cons, warns = contracts(home)
    st = locate.state_dir(home)
    out, seen = [], set()
    for plug, c in sorted(cons.items()):
        for d in c["data"]:
            if d["class"] not in (datafiles.CLASS_CONFIG, datafiles.CLASS_DATA) or (d["class"] == datafiles.CLASS_DATA and not include_data):
                continue
            base = os.path.join(st, d["path"])
            files = []
            if d["path"].endswith("/"):
                for dp, dns, fns in os.walk(base):
                    dns[:] = sorted(x for x in dns if x not in SKIP_NAMES and not os.path.islink(os.path.join(dp, x)))
                    for fn in sorted(fns):
                        if fn in SKIP_NAMES or fn.endswith(".bak") or fn.startswith(".tmp-"):
                            continue
                        files.append(os.path.join(dp, fn))
            elif os.path.isfile(base) or os.path.islink(base):
                files.append(base)
            for f in files:
                rel = os.path.relpath(f, st).replace(os.sep, "/")
                if rel in seen:
                    continue
                if os.path.islink(f):
                    warns.append(f"{rel}: enlace simbólico omitido")
                    continue
                if os.path.getsize(f) > MAX_ENTRY:
                    warns.append(f"{rel}: supera {MAX_ENTRY // 1048576} MB, omitido")
                    continue
                with open(f, "rb") as fh:
                    raw = fh.read()
                if rel == TOOLS:
                    try:
                        raw = tools_without_paths(raw)
                    except (ValueError, AttributeError):
                        warns.append(f"{rel}: JSON no válido, omitido")
                        continue
                safe_rel(rel)
                seen.add(rel)
                out.append((rel, d["class"], plug, raw))
    out.sort(key=lambda e: e[0])
    return out, {p: c["version"] for p, c in sorted(cons.items())}, warns


def do_export(a, rep):
    home = locate.find_home(a.home)
    if not home:
        raise TransferError("no hay workspace de Arkana (falta .arkana/arkana.json)")
    entries, plugins, warns = collect(home, a.include_data)
    for w in warns:
        rep.add("WARN", "export", w)
    if len(entries) > MAX_FILES or sum(len(e[3]) for e in entries) > MAX_TOTAL:
        raise TransferError("el conjunto supera los límites de tamaño")
    out = os.path.abspath(a.out)
    if os.path.exists(out) and not (a.force or a.dry_run):
        raise TransferError(f"{os.path.basename(out)} ya existe (usa --force para sobrescribirlo)")
    man = {"schema_version": SCHEMA, "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "include_data": bool(a.include_data),
           "workspace": (datafiles.read_json(os.path.join(locate.state_dir(home), "arkana.json"), {}) or {}).get("workspace", {}),
           "plugins": plugins,
           "files": [{"path": r, "class": c, "plugin": p, "size": len(b), "sha256": sha(b)} for r, c, p, b in entries]}
    for r, c, p, b in entries:
        rep.add("DRY" if a.dry_run else "OK", f"export:{r}", f"{c} ({len(b)} bytes)")
    if a.dry_run:
        return rep.add("DRY", "export", f"escribiría {len(entries)} ficheros en {os.path.basename(out)}")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name, data):
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type, zi.external_attr = zipfile.ZIP_DEFLATED, (0o100644 << 16)
            z.writestr(zi, data)
        put(MANIFEST, (json.dumps(man, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        for r, _c, _p, b in entries:
            put(PREFIX + r, b)
    os.chmod(tmp, 0o600)
    os.replace(tmp, out)
    rep.add("OK", "export", f"{len(entries)} ficheros en {os.path.basename(out)} (sin credenciales ni rutas absolutas)")


# ---------- importar: lectura y validación ----------
def read_bundle(path):
    """-> (manifiesto, {rel: bytes}). TransferError ante cualquier anomalía; no escribe nada."""
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise TransferError(f"no es un ZIP válido: {e}")
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES + 1:
            raise TransferError("demasiados ficheros en el ZIP")
        if sum(i.file_size for i in infos) > MAX_TOTAL or any(i.file_size > MAX_ENTRY for i in infos):
            raise TransferError("el ZIP descomprimiría más de lo permitido")
        names = set()
        for i in infos:
            n = i.filename
            safe_rel(n)
            if n in names:
                raise TransferError(f"entrada duplicada: {n}")
            names.add(n)
            if stat.S_ISLNK(i.external_attr >> 16):
                raise TransferError(f"{n}: enlace simbólico")
            if n != MANIFEST and not n.startswith(PREFIX):
                raise TransferError(f"{n}: fuera de files/")
        if MANIFEST not in names:
            raise TransferError(f"falta {MANIFEST}")
        try:
            man = json.loads(z.read(MANIFEST).decode("utf-8"))
        except ValueError as e:
            raise TransferError(f"{MANIFEST} no es JSON válido: {e}")
        if not isinstance(man, dict) or man.get("schema_version") != SCHEMA:
            raise TransferError(f"versión de esquema no soportada: {man.get('schema_version') if isinstance(man, dict) else '?'}")
        listed = man.get("files")
        if not isinstance(listed, list):
            raise TransferError("el manifiesto no lista ficheros")
        data, declared = {}, set()
        for f in listed:
            if not isinstance(f, dict) or not isinstance(f.get("path"), str):
                raise TransferError("entrada de manifiesto no válida")
            rel = safe_rel(f["path"])
            if rel in declared:
                raise TransferError(f"{rel}: repetido en el manifiesto")
            declared.add(rel)
            if PREFIX + rel not in names:
                raise TransferError(f"{rel}: listado pero ausente del ZIP")
            raw = z.read(PREFIX + rel)
            if len(raw) != f.get("size") or sha(raw) != f.get("sha256"):
                raise TransferError(f"{rel}: el hash o el tamaño no coinciden (fichero alterado)")
            data[rel] = raw
        extra = {n[len(PREFIX):] for n in names if n != MANIFEST} - declared
        if extra:
            raise TransferError(f"ficheros fuera del manifiesto: {', '.join(sorted(extra)[:3])}")
    return man, data


def stamp(raw):
    try:
        d = json.loads(raw.decode("utf-8"))
        return d if isinstance(d, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


def decide(rel, cls, cur, new, policy):
    """-> (acción, motivo, bytes a escribir). Acciones: create, same, keep, replace, conflict."""
    if cur is None:
        return "create", "no existía", new
    if cur == new:
        return "same", "idéntico", None
    if rel == TOOLS:
        a, b = stamp(cur), stamp(new)
        if a and b and policy != "keep":
            local = {t.get("tool"): t.get("path") for t in a.get("tools", []) if t.get("path")}
            for t in b.get("tools", []):
                if t.get("tool") in local:
                    t["path"] = local[t["tool"]]            # la ruta es de esta máquina: se conserva
            return ("conflict", "difiere", None) if policy == "ask" else ("replace", "herramientas del ZIP (rutas locales conservadas)",
                                                                           (json.dumps(b, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if cls == datafiles.CLASS_DATA:
        a, b = stamp(cur), stamp(new)
        if a is not None and b is not None:
            if (a.get("state") or a.get("estado")) == "deleted":
                return "keep", "borrado local (manda la marca de borrado)", None
            if (b.get("state") or b.get("estado")) == "deleted":
                return "replace", "borrado en el ZIP (manda la marca de borrado)", new
            ua, ub = str(a.get("updated", "")), str(b.get("updated", ""))
            if ua and ub and ua != ub:
                return ("replace", "más reciente en el ZIP", new) if ub > ua else ("keep", "más reciente en local", None)
    if policy == "replace":
        return "replace", "--on-conflict replace", new
    if policy == "ask":
        return "conflict", "difiere: hay que decidir", None
    return "keep", "se conserva lo local (--on-conflict keep)", None


def do_import(a, rep):
    home = locate.find_home(a.home)
    if not home:
        raise TransferError("no hay workspace de Arkana (falta .arkana/arkana.json)")
    man, data = read_bundle(a.file)
    cons, warns = contracts(home)
    for w in warns:
        rep.add("WARN", "import", w)
    st = os.path.realpath(locate.state_dir(home))
    plan = []
    for rel in sorted(data):                                         # 1) validar todo antes de escribir
        c = classify(cons, rel)
        if c is None:
            raise TransferError(f"{rel}: ningún plugin instalado declara ese destino")
        if c[1] not in (datafiles.CLASS_CONFIG, datafiles.CLASS_DATA):
            raise TransferError(f"{rel}: clase {c[1]!r}, no se importa")
        dest = os.path.join(st, rel)
        if not os.path.realpath(dest).startswith(st + os.sep):
            raise TransferError(f"{rel}: el destino sale de .arkana")
        if rel == WORKSPACE:
            try:
                errs = manifest.validate(json.loads(data[rel].decode("utf-8")))
            except ValueError as e:
                raise TransferError(f"{rel}: JSON no válido ({e})")
            if errs:
                raise TransferError(f"{rel}: manifiesto no válido ({'; '.join(errs[:3])})")
        cur = None
        if os.path.isfile(dest) and not os.path.islink(dest):
            with open(dest, "rb") as fh:
                cur = fh.read()
        plan.append((rel, c[1], dest, *decide(rel, c[1], cur, data[rel], a.on_conflict), cur is not None))
    backup = os.path.join(st, "arkana-workspace", "bak", "import-" + time.strftime("%y%m%d%H%M%S"))
    conflicts = 0
    for rel, cls, dest, act, why, new, existed in plan:               # 2) aplicar
        if act == "conflict":
            conflicts += 1
            rep.add("WARN", f"import:{rel}", f"conflicto: {why}")
            continue
        if act in ("create", "replace") and not a.dry_run:
            if existed:
                os.makedirs(os.path.dirname(os.path.join(backup, rel)), exist_ok=True)
                shutil.copy2(dest, os.path.join(backup, rel))
            datafiles.atomic_write(dest, new)
        label = {"create": "creado", "replace": "reemplazado", "same": "igual", "keep": "conservado"}[act]
        rep.add("DRY" if a.dry_run and act in ("create", "replace") else "OK" if act in ("create", "replace", "same") else "INFO",
                f"import:{rel}", f"{label}: {why}")
    if conflicts:
        rep.add("INFO", "import", f"{conflicts} conflicto(s) sin tocar: vuelve a ejecutar con --on-conflict keep|replace")
    if any(r == WORKSPACE and act in ("create", "replace") for r, _c, _d, act, *_ in plan):
        rep.add("INFO", "import", "el manifiesto cambió: la identidad git y las rutas de herramientas son locales; revisa con /arkana-workspace:check")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="transfer.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("export", "import"):
        p = sub.add_parser(n)
        p.add_argument("--home")
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--json", action="store_true")
        if n == "export":
            p.add_argument("--out", required=True)
            p.add_argument("--include-data", action="store_true")
            p.add_argument("--force", action="store_true")
        else:
            p.add_argument("file")
            p.add_argument("--on-conflict", choices=("keep", "replace", "ask"), default="keep")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    if a.home:
        a.home = os.path.realpath(a.home)
    rep = output.Report("arkana-workspace", a.cmd)
    try:
        (do_export if a.cmd == "export" else do_import)(a, rep)
    except TransferError as e:
        rep.add("FAIL", a.cmd, f"{e} (no se ha escrito nada)" if a.cmd == "import" else str(e))
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
