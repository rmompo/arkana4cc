#!/usr/bin/env python3
"""Comprueba un componente del proyecto (permisos, CLAUDE.md, git, .gitignore, identidad…). Solo lectura.

  component.py [--component <alias>] [--home <dir>] [--json] [--no-network]

Sin --component se deduce del directorio actual (el componente más específico que lo contiene). Salida común: `ESTADO|ID|detalle`
y `RESUMEN|n FAIL|n WARN` (o --json). Las correcciones las hace `arkana-workspace:fix`.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from arkana_core import manifest, output  # noqa: E402
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
    # 3. CLAUDE.md
    cm = os.path.join(path, "CLAUDE.md")
    seed_local = c.get("seed_file") == "CLAUDE.local.md"
    if os.path.isfile(cm):
        add("OK", "claude-md", "presente")
    elif seed_local and os.path.isfile(os.path.join(path, "CLAUDE.local.md")):
        add("INFO", "claude-md", "sin CLAUDE.md propio (el componente usa CLAUDE.local.md)")
    else:
        add("FAIL", "claude-md", "falta CLAUDE.md")
    # 3b. Convención de commits (bloque arkana:commits generado desde el manifiesto)
    try:
        cs = commits.state(ws, alias)
        add("OK" if cs == "OK" else "WARN", "commits", "bloque de convención de commits al día" if cs == "OK" else f"convención de commits: {cs} (arkana-workspace:fix)")
    except ValueError as e:
        add("FAIL", "commits", str(e))
    # 4. Git
    if git(path, "rev-parse", "--git-dir")[0] != 0:
        add("WARN", "git-repo", "no es un repositorio git (git init y remoto pendientes)")
        return rep
    for pat, id_, label in ((".env", "gitignore-env", ".env"), (".claude/x", "gitignore-claude", ".claude/"), (".claude-session/x", "gitignore-claude-session", ".claude-session/")):
        ok = git(path, "check-ignore", "-q", pat)[0] == 0
        add("OK" if ok else "FAIL", id_, f"{label} ignorado" if ok else f".gitignore no cubre {label}")
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
    eol = os.path.isfile(ga) and "eol=lf" in open(ga, encoding="utf-8", errors="replace").read()
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
