#!/usr/bin/env python3
"""Valida un mensaje de commit segun la convencion de cada componente, que sale de su `commit_format` en el manifiesto del workspace.

ia4d (opcional)     : IA4D            verbo(scope) descripcion          (sin dos puntos)
conventional        : Conventional    tipo(scope): descripcion          (con dos puntos)
Comunes: ingles, <=72 caracteres, sin punto final, una sola linea de asunto, sin Co-Authored-By.
Si el componente declara `git.email_domains`, el autor del commit debe tener un correo de uno de esos dominios.

Uso:  commitmsg.py <repo-id> "<mensaje>"        (exit 0 valido, 1 no valido, 2 uso)
"""
import re
import sys

import repos

IA4D = re.compile(r"^(feat|fix|docs|chore|refactor|test|style|perf|build|ci|revert)\([a-z0-9._-]+\) \S.*$")
CONV = re.compile(r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)\([a-z0-9._-]+\): \S.*$")


def _block(repo):
    try:
        return repos._workspace().get(repo)
    except KeyError:
        return None


def format_of(repo):
    """'conv' o 'ia4d' segun el `commit_format` del componente (conv si no lo dice); None si el repo no existe."""
    b = _block(repo)
    if b is None:
        return None
    return "ia4d" if b.get("commit_format") == "ia4d" else "conv"


def check_message(repo, mensaje, autor_email=None):
    errs = []
    fmt = format_of(repo)
    if fmt is None:
        return [f"repo desconocido: {repo}"]
    asunto = mensaje.split("\n", 1)[0]
    if len(asunto) > 72:
        errs.append(f"el asunto tiene {len(asunto)} caracteres (maximo 72)")
    if asunto.endswith("."):
        errs.append("el asunto no debe terminar en punto")
    if re.search(r"co-authored-by", mensaje, re.I):
        errs.append("no se permite Co-Authored-By")
    rx = IA4D if fmt == "ia4d" else CONV
    if not rx.match(asunto):
        forma = "verbo(scope) descripcion, sin dos puntos" if fmt == "ia4d" else "tipo(scope): descripcion, con dos puntos"
        errs.append(f"formato invalido para {repo}: se espera {forma}")
    dominios = ((_block(repo) or {}).get("git") or {}).get("email_domains") or []
    if autor_email is not None and dominios and not any(autor_email.lower().endswith("@" + d.lower()) for d in dominios):
        errs.append("el autor debe tener un correo de " + " o ".join("@" + d for d in dominios) + f" en {repo}")
    return errs


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    errs = check_message(argv[1], argv[2])
    for e in errs:
        print(f"FAIL|commit|{e}")
    if not errs:
        print("OK|commit|mensaje valido")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
