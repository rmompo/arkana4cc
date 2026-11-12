#!/usr/bin/env python3
"""Comprueba un componente del proyecto (permisos, CLAUDE.md, git, .gitignore, identidad…). Solo lectura.

  component.py [--component <alias>] [--home <dir>] [--json] [--no-network]

Sin --component se deduce del directorio actual (el componente más específico que lo contiene). Salida común: `ESTADO|ID|detalle`
y `RESUMEN|n FAIL|n WARN` (o --json). Las correcciones las hace `arkana-workspace:fix`.
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from arkana_core import manifest, output, project  # noqa: E402
import commits  # noqa: E402
import permissions  # noqa: E402
import proc  # noqa: E402


def git(path, *args, timeout=15):
    rc, out = proc.run(["git", "-C", path, *args], timeout, dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))
    return rc, out


def want_domains(block):
    """Dominios de correo que exige el componente (`git.email_domains` del manifiesto); vacío = sin regla."""
    return [d.lstrip("@") for d in ((block or {}).get("git") or {}).get("email_domains") or []]


def email_ok(email, doms):
    return not doms or any(email.lower().endswith("@" + d.lower()) for d in doms)


def check(ws, alias, network=True):
    rep = output.Report("arkana-workspace", "check-component")
    path = ws.path(alias)
    c = ws.get(alias)
    ark = ws.path("arkana")
    add = lambda st, i, d: rep.add(st, i, d, component=alias)
    add("INFO", "componente", f"{manifest.display(alias)} {path}")
    if not os.path.isdir(path):
        add("FAIL", "carpeta", f"no existe {path}")
        return rep
    # 1. Arkana presente y escribible
    if os.path.isdir(ark):
        add("OK", "arkana-presente", ark)
        add("OK" if os.access(ark, os.W_OK) else "FAIL", "arkana-escribible", "se puede escribir en ARKANA" if os.access(ark, os.W_OK) else f"sin escritura en {ark}")
    else:
        add("FAIL", "arkana-presente", f"no existe {ark}: clona el repo de Arkana como carpeta del workspace")
    # 2. Permisos (comparación semántica con el modelo)
    its = permissions.diff(ws, alias)
    if not its:
        add("OK", "permisos", "settings.local.json conforme al modelo")
    else:
        graves = [k for k, _ in its if permissions.STATUS_OF[k] == "FAIL"]
        add("FAIL" if graves else "WARN", "permisos", f"{len(its)} desviaciones ({', '.join(sorted({k for k, _ in its}))}); ver arkana-workspace:rew-grants")
    # 2b. Registro del proyecto (id inmutable + alias renombrable, compartidos por git)
    reg = project.Registry.load(ws.home)
    bid = c.get("id")
    if not reg.present:
        add("WARN", "registro", f"no hay {project.FILE}: ejecuta /arkana-evolve:apply")
    elif reg.id_of(alias) is None and reg.alias_of(bid) is None:
        add("WARN", "registro", f"{manifest.display(alias)} no está en el registro compartido: se da de alta con /arkana-evolve:apply")
    elif bid and reg.alias_of(bid) and reg.alias_of(bid) != manifest.canon(alias):
        add("WARN", "registro", f"el registro compartido llama {reg.alias_of(bid)} a este componente: alinea tu copia con `component edit --alias {alias} --rename {reg.alias_of(bid)}`")
    elif not bid:
        add("WARN", "registro", "el manifiesto local no lleva el id del componente: ejecuta /arkana-evolve:apply")
    else:
        add("OK", "registro", f"id {bid[:8]}… en el registro compartido")
    # 3. Convención de commits (la inyecta el hook de sesión desde el manifiesto: aquí solo se valida el formato)
    err = commits.check(ws, alias)
    add("FAIL" if err else "OK", "commits", err or f"convención de commits: {commits.fmt_of(ws, alias)}")
    # 4. Git
    if git(path, "rev-parse", "--git-dir")[0] != 0:
        add("WARN", "git-repo", "no es un repositorio git (git init y remoto pendientes)")
        return rep
    ok = git(path, "check-ignore", "-q", ".env")[0] == 0
    add("OK" if ok else "FAIL", "gitignore-env", ".env ignorado" if ok else ".gitignore no cubre .env")
    for pat, id_, label in ((".claude/x", "ignore-editor", ".claude/"), (".claude-session/x", "ignore-editor-session", ".claude-session/"),
                            ("ARKANA.local.md", "ignore-arkana-local", "ARKANA.local.md")):
        ok = git(path, "check-ignore", "-q", pat)[0] == 0
        add("OK" if ok else "FAIL", id_, f"{label} ignorado" if ok else f"{label} sin ignorar: se añade a .git/info/exclude con fix (no se toca el .gitignore)")
    rc, tracked = git(path, "ls-files")
    envs = [f for f in tracked.splitlines() if (os.path.basename(f) == ".env" or os.path.basename(f).startswith(".env.")) and not f.endswith(".env.example")][:3]
    add("FAIL" if envs else "OK", "env-versionado", ("versionado: " + " ".join(envs)) if envs else "ningún .env versionado")
    hist = git(path, "log", "--all", "--oneline", "--", ".env")[1]
    add("FAIL" if hist else "OK", "env-historial", ".env aparece en el historial de git: rotar las credenciales y limpiar el historial" if hist else ".env no está en el historial")
    add("OK" if os.path.isfile(os.path.join(path, ".env.example")) else "WARN", "env-example", ".env.example presente" if os.path.isfile(os.path.join(path, ".env.example")) else "falta .env.example (plantilla con placeholders)")
    url = git(path, "remote", "get-url", "origin")[1]
    email = git(path, "config", "user.email")[1]
    want = want_domains(c)
    if not url:
        add("WARN", "git-identidad", "sin remoto origin: no se puede comprobar la identidad")
    elif not email:
        add("FAIL", "git-identidad", "user.email sin configurar")
    elif email_ok(email, want):
        add("OK", "git-identidad", f"{email}" + (f" (dominios del componente: {', '.join('@' + d for d in want)})" if want else " (sin regla de dominio)"))
    else:
        add("FAIL", "git-identidad", f"{email} no encaja con los dominios del componente ({', '.join('@' + d for d in want)})")
    ga = os.path.join(path, ".gitattributes")
    eol = os.path.isfile(ga) and "eol=lf" in Path(ga).read_text(encoding="utf-8", errors="replace")
    add("OK" if eol else "WARN", "gitattributes-eol", "eol=lf" if eol else "falta .gitattributes con eol=lf")
    hk = os.path.join(path, ".husky")
    if os.path.isdir(hk):
        bad = [f for f in sorted(os.listdir(hk)) if os.path.isfile(os.path.join(hk, f)) and not os.access(os.path.join(hk, f), os.X_OK)]
        add("FAIL" if bad else "OK", "husky-hooks", ("sin permiso de ejecución: " + " ".join(bad)) if bad else "hooks ejecutables")
    br = git(path, "branch", "--show-current")[1]
    exp = c.get("branches", {}) if alias != "arkana" else ws.get("arkana").get("branches", {})
    if br in (exp.get("develop", "develop"), exp.get("main", "main")):
        add("OK", "rama", br)
    else:
        add("WARN", "rama", f"{br or 'HEAD desacoplado'} (se esperaba {exp.get('develop', 'develop')} o {exp.get('main', 'main')})")
    if url and network:
        ok = git(path, "ls-remote", "--exit-code", "-q", "origin", "HEAD", timeout=10)[0] == 0
        add("OK" if ok else "WARN", "origin-accesible", "origin responde" if ok else "origin no responde (VPN, credenciales o rama aún no publicada)")
    # 5. Repos anidados (componentes cuya carpeta cuelga de la de este)
    for n in ws.nested_in(alias):
        np = ws.path(n)
        if not os.path.isdir(np):
            continue
        u = git(np, "remote", "get-url", "origin")[1]
        e = git(np, "config", "user.email")[1]
        w = want_domains(ws.get(n))
        if not u:
            add("WARN", f"anidado-{n}", "sin remoto origin")
        elif email_ok(e, w):
            add("OK", f"anidado-{n}", f"identidad {e}")
        else:
            add("FAIL", f"anidado-{n}", f"identidad '{e}' no encaja con los dominios del componente ({', '.join('@' + d for d in w)})")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="component.py")
    ap.add_argument("--component")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-network", action="store_true")
    a = ap.parse_args(argv)
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        alias = manifest.canon(a.component) if a.component else ws.owner_of(os.getcwd())
        if not alias:
            raise manifest.ManifestError("el directorio actual no pertenece a ningún componente: usa --component")
        ws.get(alias)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = check(ws, alias, not a.no_network)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
