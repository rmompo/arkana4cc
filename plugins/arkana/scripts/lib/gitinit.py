#!/usr/bin/env python3
"""Inicia el repositorio git de la carpeta de ARKANA y fija la identidad (usuario y correo) del repo. Idempotente; nunca toca `~/.gitconfig`.

  gitinit.py --home <dir> [--name N] [--email E] [--branch main] [--dry-run] [--json]

Sin repo, hace `git init` (rama `--branch`, por defecto `main`). Si faltan usuario o correo del repo, **no los inventa**: sale con código 2 y pide `--name` y `--email`
(el skill los pregunta a la persona usuaria). Si se dan `--name`/`--email`, se fijan a nivel de repo (`git config --local`). No hace commit, no añade remoto y no maneja
tokens: el remoto y su token se dan de alta con `/arkana-workspace:component edit --alias arkana` y `credentials.py set` (en la terminal de la persona usuaria).
Una carpeta que ya pertenece a otro repo (subcarpeta de otro proyecto) se rechaza: ARKANA es su propio repo.
Códigos de salida: 0 correcto, 1 fallo, 2 faltan --name/--email.
"""
import argparse
import json
import os
import re
import subprocess
import sys

EMAIL_RX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def git(path, *args):
    r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=20,
                       env=dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def toplevel(path):
    rc, out, _ = git(path, "rev-parse", "--show-toplevel")
    return os.path.realpath(out) if rc == 0 and out else None


def run(home, name=None, email=None, branch="main", dry=False):
    """Lista de (estado, id, detalle) y código de salida."""
    res = []
    add = lambda s, i, d: res.append((s, i, d))
    home = os.path.realpath(home)
    if not os.path.isdir(home):
        add("FAIL", "git", f"{home} no existe")
        return res, 1
    if name is not None and not name.strip():
        add("FAIL", "identidad", "--name vacío")
        return res, 1
    if email is not None and not EMAIL_RX.match(email.strip()):
        add("FAIL", "identidad", f"--email no parece un correo: {email!r}")
        return res, 1
    top = toplevel(home)
    if top and top != home:
        add("FAIL", "git", f"{home} pertenece al repo {top}: ARKANA es su propio repo; elige otra carpeta o inicia git en la raíz de ARKANA")
        return res, 1
    if top:
        add("OK", "git", f"repo existente en {home}")
    elif dry:
        add("DRY", "git", f"git init (rama {branch}) en {home}")
    else:
        rc, _, err = git(home, "init", "-q")
        if rc != 0:
            add("FAIL", "git", f"git init falló: {err[:120]}")
            return res, 1
        git(home, "symbolic-ref", "HEAD", f"refs/heads/{branch}")           # rama inicial sin depender de `init.defaultBranch` ni de la versión de git
        add("OK", "git", f"repo iniciado en {home} (rama {branch}; sin commits)")
    for key, value in (("user.name", name), ("user.email", email)):
        if value is not None:
            if dry:
                add("DRY", "identidad", f"{key} del repo = {value.strip()}")
            else:
                git(home, "config", "--local", key, value.strip())
                add("OK", "identidad", f"{key} del repo = {value.strip()}")
    if dry and not top:
        faltan = [k for k, v in (("user.name", name), ("user.email", email)) if v is None]
    else:
        faltan = [k for k, v in (("user.name", name), ("user.email", email)) if v is None and not git(home, "config", k)[1]]
    if faltan:
        add("WARN", "identidad", f"faltan {' y '.join(faltan)} del repo: pídeselos a la persona usuaria y repite con --name y --email")
        return res, 2
    if dry and not top:
        nm, em = (name or "").strip(), (email or "").strip()
    else:
        nm, em = git(home, "config", "user.name")[1], git(home, "config", "user.email")[1]
    add("DRY" if dry and not top else "OK", "identidad", f"{nm} <{em}>")
    return res, 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gitinit.py")
    ap.add_argument("--home", required=True)
    ap.add_argument("--name")
    ap.add_argument("--email")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    res, code = run(a.home, a.name, a.email, a.branch, a.dry_run)
    if a.json:
        print(json.dumps({"plugin": "arkana", "skill": "install", "items": [{"status": s, "id": i, "detail": d} for s, i, d in res], "code": code}, ensure_ascii=False, indent=2))
    else:
        for s, i, d in res:
            print(f"{s}|{i}|{d}")
        print(f"RESUMEN|{sum(1 for s, _, _ in res if s == 'FAIL')} FAIL|{sum(1 for s, _, _ in res if s == 'WARN')} WARN")
    return code


if __name__ == "__main__":
    sys.exit(main())
