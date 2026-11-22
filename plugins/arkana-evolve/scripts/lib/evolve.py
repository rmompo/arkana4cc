#!/usr/bin/env python3
"""Evolución de una instalación de Arkana: migraciones numeradas, idempotentes y con --dry-run (solo biblioteca estándar).

  check  [--home DIR] [--json]                          solo lectura: migraciones aplicadas y pendientes, y el sello del layout
  apply  [--dry-run] [--to N] [--home DIR] [--json]     aplica las pendientes en orden (las `b*` de base, antes que las numéricas)

Una migración es un módulo de `migrations/` con: `ID`, `TITLE`, `SCOPE` (`shared`, `local` o ambos), `touches(ctx)` (rutas relativas a la carpeta
de ARKANA que escribe en el repo), `detect(ctx)` (¿está pendiente? idempotente), `apply(ctx, rep)` y `verify(ctx)` (lista de problemas).
`shared` = cambia ficheros versionados del repo de ARKANA: una persona migra, commitea y empuja, y el resto hace pull y vuelve a ejecutar `apply`
(solo se aplica su parte local). `local` = cambia `.arkana/`.

Reglas: nunca hace commit ni push; el ámbito `shared` exige repo git y que las rutas que va a escribir no tengan cambios sin commitear; antes de
tocar `.arkana/` deja una copia `tar.gz` en `.arkana/arkana-workspace/bak/`. El estado local está en `.arkana/arkana-evolve/state.json`; el sello
compartido (`layout`) está en `arkana-project.json`. Códigos de salida: 0 sin fallos, 1 fallo, 2 uso, 3 precondición no cumplida.
"""
import argparse
import datetime
import importlib.util
import os
import re
import subprocess
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import CORE_VERSION, datafiles, locate, output  # noqa: E402

MIGRATIONS_DIR = os.path.join(HERE, "migrations")
PROJECT_FILE = "arkana-project.json"
STATE_REL = os.path.join("arkana-evolve", "state.json")
REQUIRED = ("ID", "TITLE", "SCOPE", "touches", "detect", "apply", "verify")


class EError(Exception):
    def __init__(self, msg, cod=1):
        super().__init__(msg)
        self.cod = cod


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Ctx:
    """Lo que ven las migraciones: la carpeta de ARKANA, su estado local y `dry` (si es un ensayo)."""

    def __init__(self, home, dry=False):
        self.home = home
        self.state = locate.state_dir(home)
        self.dry = dry
        self.project_path = os.path.join(home, PROJECT_FILE)
        self.state_path = os.path.join(self.state, STATE_REL)

    def path(self, *parts):
        return os.path.join(self.home, *parts)

    def project(self):
        return datafiles.read_json(self.project_path)

    def git(self, *args):
        return subprocess.run(["git", "-C", self.home, *args], capture_output=True, text=True, timeout=20,
                              env=dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))

    def applied_local(self):
        st = datafiles.read_json(self.state_path, {}) or {}
        return {e.get("id") for e in st.get("applied", []) if isinstance(e, dict)}

    def mark_applied(self, mid):
        st = datafiles.read_json(self.state_path, {}) or {}
        applied = [e for e in st.get("applied", []) if isinstance(e, dict) and e.get("id") != mid]
        applied.append({"id": mid, "date": now_iso()})
        datafiles.atomic_write_json(self.state_path, {"schema_version": 1, "applied": applied}, mode=0o600)


def is_baseline(mod):
    return str(mod.ID).startswith("b")


def sort_key(mod):
    return (0, str(mod.ID)) if is_baseline(mod) else (1, "%08d" % int(mod.ID))


def load_migrations(directory=MIGRATIONS_DIR):
    if directory not in sys.path:
        sys.path.insert(0, directory)                  # las migraciones comparten el helper `_legacy`
    mods = []
    for f in sorted(os.listdir(directory)):
        if not re.match(r"^[bm]\d+_[a-z0-9_]+\.py$", f):
            continue
        spec = importlib.util.spec_from_file_location("arkana_evolve_" + f[:-3], os.path.join(directory, f))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        falta = [a for a in REQUIRED if not hasattr(mod, a)]
        if falta:
            raise EError(f"la migración {f} no define: {', '.join(falta)}")
        mods.append(mod)
    return sorted(mods, key=sort_key)


def latest_layout(mods):
    return max([int(m.ID) for m in mods if not is_baseline(m)] or [0])


def stamp(ctx, mod):
    """Tras aplicar una migración numérica, sube el sello `layout` del registro compartido y lo anota en su historial (la 0001 lo crea ya con layout 1)."""
    p = ctx.project()
    if is_baseline(mod) or not isinstance(p, dict):
        return
    n = int(mod.ID)
    if int(p.get("layout", 0) or 0) < n:
        p["layout"] = n
        p.setdefault("history", []).append({"id": mod.ID, "date": now_iso()})
        datafiles.atomic_write_json(ctx.project_path, p)


def settle(ctx, mods, before=None):
    """Sube el sello a toda migración numérica que ya no está pendiente aunque no haya tenido nada que hacer en esta instalación (su `detect` es falso).
    Se detiene en la primera pendiente (el sello nunca salta una migración sin aplicar) y, con `before`, en la migración con ese número o mayor
    (así el historial recoge las intermedias antes de estampar la que se acaba de aplicar, y `--to N` no pasa de N)."""
    for m in mods:
        if is_baseline(m):
            continue
        if before is not None and int(m.ID) >= before:
            return
        if m.detect(ctx):
            return
        stamp(ctx, m)


def project_layout(ctx):
    p = ctx.project()
    return int(p.get("layout", 0)) if isinstance(p, dict) and isinstance(p.get("layout", 0), int) else 0


def find_home(arg):
    home = os.path.abspath(arg) if arg else locate.find_home()
    if not home or not locate.is_home(home):
        raise EError("no hay workspace de Arkana (falta .arkana/arkana.json): ejecuta /arkana-workspace:install", 3)
    return home


def statusline_copy_outdated():
    """Qué le pasa a la copia de la statusline (`~/.claude/arkana-statusline`), o None si está al día o no hay copia: `"anterior al despachador"` si le falta `dispatch.py`
    (instalada antes de que la statusline de usuario fuese un despachador), o la versión de su núcleo si es anterior a la de este plugin.
    Es un dato de usuario fuera del repo: ninguna migración lo toca, pero tras actualizar los plugins hay que refrescarlo con `/arkana-statusline:fix`."""
    d = os.path.join(os.path.expanduser("~"), ".claude", "arkana-statusline")
    if os.path.isfile(os.path.join(d, "statusline.sh")) and not os.path.isfile(os.path.join(d, "dispatch.py")):
        return "anterior al despachador"
    f = os.path.join(d, "arkana_core", "__init__.py")
    try:
        with open(f, encoding="utf-8") as fh:
            m = re.search(r'CORE_VERSION\s*=\s*"([\d.]+)"', fh.read())
    except OSError:
        return None
    if not m:
        return None
    ver = lambda v: tuple(int(x) for x in v.split("."))
    return m.group(1) if ver(m.group(1)) < ver(CORE_VERSION) else None


def migrar_registro(ctx, rep):
    """El registro de workspaces pasó de `~/.arkana-workspaces.json` a `~/.arkana/workspaces.json`: se mueve (conservando sus entradas) la primera vez que se aplica."""
    if os.path.isfile(locate.legacy_registry_path()) and not os.path.isfile(locate.registry_path()):
        if not ctx.dry:
            locate.register(ctx.home)
        rep.add("DRY" if ctx.dry else "OK", "registro-usuario", f"{locate.legacy_registry_path()} {'se movería a' if ctx.dry else 'movido a'} {locate.registry_path()}")


def aviso_statusline(rep):
    old = statusline_copy_outdated()
    if old:
        que = "es anterior al despachador de statusline (falta dispatch.py)" if old == "anterior al despachador" else f"lleva el núcleo {old}, anterior al de esta instalación"
        rep.add("WARN", "statusline", f"la copia de la statusline (~/.claude/arkana-statusline) {que}: ejecuta /arkana-statusline:fix")


# ---------- check ----------
def cmd_check(a, ctx, rep):
    mods = load_migrations()
    latest = latest_layout(mods)
    layout = project_layout(ctx)
    if layout > latest:
        rep.add("WARN", "layout", f"el repo está en layout {layout} y esta instalación solo conoce hasta {latest}: actualiza arkana-evolve")
    elif layout < latest:
        rep.add("WARN", "layout", f"el repo está en layout {layout}; la última migración es {latest}: ejecuta /arkana-evolve:apply")
    else:
        rep.add("OK", "layout", f"layout {layout} (al día)")
    aviso_statusline(rep)
    for m in mods:
        if m.detect(ctx):
            rep.add("WARN", m.ID, f"pendiente: {m.TITLE} → /arkana-evolve:apply")
        else:
            problems = m.verify(ctx)
            if problems:
                for p in problems:
                    rep.add("WARN", m.ID, f"aplicada, pero {p}")
            else:
                rep.add("OK", m.ID, f"aplicada: {m.TITLE}")


# ---------- apply ----------
def parse_to(value):
    if value is None:
        return None
    if not re.match(r"^\d+$", str(value)):
        raise EError(f"--to espera un número de migración (p. ej. 1 o 0001), no {value!r}", 2)
    return int(value)


def check_preconditions(ctx, pending):
    if not any("shared" in m.SCOPE for m in pending):
        return
    r = ctx.git("rev-parse", "--is-inside-work-tree")
    if r.returncode != 0 or r.stdout.strip() != "true":
        raise EError("la carpeta de ARKANA no es un repositorio git: las migraciones compartidas necesitan git para poder revisarse y revertirse", 3)
    sucios = []
    for m in pending:
        if "shared" not in m.SCOPE:
            continue
        rutas = list(m.touches(ctx)) + ([PROJECT_FILE] if not is_baseline(m) and int(m.ID) > 1 else [])
        if rutas:
            # solo bloquean los ficheros VERSIONADOS con cambios (los sin seguimiento `??` ya existen y la migración no los pisa)
            sucios += [l[3:] for l in ctx.git("status", "--porcelain", "--", *rutas).stdout.splitlines() if l.strip() and not l.startswith("??")]
    if sucios:
        raise EError("hay cambios sin commitear en lo que va a escribir la migración: " + ", ".join(sorted(set(sucios))[:5]) + " (commitéalos o descártalos y repite)", 3)


def backup(ctx):
    bak = os.path.join(ctx.state, "arkana-workspace", "bak")
    os.makedirs(bak, exist_ok=True)
    dest = os.path.join(bak, "evolve-" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S") + ".tar.gz")

    def skip(ti):
        return None if ti.name.startswith(os.path.join(".arkana", "arkana-workspace", "bak")) else ti

    with tarfile.open(dest, "w:gz") as tf:
        tf.add(ctx.state, arcname=".arkana", filter=skip)
    os.chmod(dest, 0o600)
    return dest


def cmd_apply(a, ctx, rep):
    mods = load_migrations()
    hasta = parse_to(a.to)

    def pendientes(done):
        return [m for m in mods if m not in done and m.detect(ctx) and (is_baseline(m) or hasta is None or int(m.ID) <= hasta)]

    pending = pendientes([])
    if not pending:
        if not ctx.dry:
            settle(ctx, mods, before=None if hasta is None else hasta + 1)
        migrar_registro(ctx, rep)
        rep.add("OK", "apply", f"nada que hacer: layout {project_layout(ctx)}, sin migraciones pendientes")
        return
    done, backed = [], False
    while pending:
        if not done:                                      # solo lo que ya estaba sucio ANTES de empezar: lo que escribe esta misma ejecución no cuenta
            check_preconditions(ctx, pending)
        if not ctx.dry and not backed and any("local" in m.SCOPE for m in pending):
            rep.add("OK", "copia", f"copia de .arkana en {os.path.relpath(backup(ctx), ctx.home)}")
            backed = True
        cola = list(pending)
        while cola:
            m = cola.pop(0)
            if not ctx.dry and not is_baseline(m):
                settle(ctx, mods, before=int(m.ID))                 # las intermedias sin nada que hacer quedan en el historial antes que ésta
            rep.add("INFO", m.ID, f"{m.TITLE} (ámbito {'+'.join(m.SCOPE)})")
            antes = rep.count("FAIL")
            m.apply(ctx, rep)
            done.append(m)
            if rep.count("FAIL") > antes:
                rep.add("FAIL", "apply", f"se detiene en {m.ID}: las siguientes no se han aplicado")
                return
            if not ctx.dry:
                problems = m.verify(ctx)
                if problems:
                    for p in problems:
                        rep.add("FAIL", m.ID, f"verificación: {p}")
                    return
                stamp(ctx, m)
                # una migración deja listo el terreno de otra (la 0001 crea el registro que hace pendientes a las de solo sello; la de base mueve ficheros que luego
                # migra una numérica): se vuelve a mirar después de CADA una, así ninguna se salta ni se queda fuera del historial
                cola = pendientes(done)
        pending = []
    if not ctx.dry:
        settle(ctx, mods, before=None if hasta is None else hasta + 1)
    aviso_statusline(rep)
    migrar_registro(ctx, rep)
    if ctx.dry:
        rep.add("DRY", "apply", f"{len(done)} migraciones se aplicarían; no se ha escrito nada")
    else:
        rep.add("OK", "apply", f"{len(done)} migraciones aplicadas. Nada commiteado: revisa `git status` y commitea (una sola persona; el resto hace pull y ejecuta apply)")


def make_parser():
    p = argparse.ArgumentParser(prog="evolve.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)

    def common(x, dry):
        x.add_argument("--home")
        x.add_argument("--json", action="store_true")
        if dry:
            x.add_argument("--dry-run", dest="dry_run", action="store_true")
        return x

    common(s.add_parser("check"), False)
    ap = common(s.add_parser("apply"), True)
    ap.add_argument("--to")
    return p


def main(argv=None):
    try:
        a = make_parser().parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-evolve", a.cmd)
    try:
        ctx = Ctx(find_home(a.home), dry=getattr(a, "dry_run", False))
        {"check": cmd_check, "apply": cmd_apply}[a.cmd](a, ctx, rep)
    except EError as e:
        rep.add("FAIL", a.cmd, str(e))
        sys.stdout.write(rep.render(getattr(a, "json", False)))
        return e.cod
    except OSError as e:
        rep.add("FAIL", a.cmd, f"error de ficheros: {e}")
    sys.stdout.write(rep.render(getattr(a, "json", False)))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
