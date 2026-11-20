#!/usr/bin/env python3
"""Convención de commits de cada pieza, generada desde el manifiesto (`commit_format`). No escribe nada en los repos: la inyecta el hook de sesión.

  commits.py status [--component A]... [--home DIR] [--json]     valida el `commit_format` de cada pieza
  commits.py show   [--component A]... [--home DIR]              imprime la convención que se inyecta en la sesión de cada pieza

`commit_format` de la pieza: `conventional` (por defecto: `tipo(scope): descripción`, con dos puntos, p. ej. por commitlint) o `ia4d`
(formato opcional: `verbo(scope) descripción`, sin dos puntos). El scope es el alias de la pieza; con `conventional({module})` o `ia4d({module})` es su
nombre-módulo (`component edit --module`; sin módulo, el alias).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import manifest, output  # noqa: E402

FORMATS = {
    "ia4d": "**IA4D**: `verbo(scope) descripción`, **sin dos puntos**. Ejemplo: `docs({scope}) link workstation setup guides from the README`.",
    "conventional": "**Conventional Commits con dos puntos**: `tipo(scope): descripción`. Tipos: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, "
                    "`refactor`, `revert`, `style`, `test`. Ejemplo: `chore({scope}): ignore local editor files`. Es lo que exige `commitlint`.",
}
COMMON = """- Inglés, **≤72 caracteres**, sin punto final y un solo objetivo por commit.
- **Nunca** `Co-Authored-By` ni otras líneas de coautoría, y **nunca** `--no-verify`: si un hook rechaza el commit, corrige el mensaje.
- Solo haces commit o push **cuando el usuario lo pide**. Un commit afecta solo al repo de la carpeta donde se ejecuta (los repos anidados son aparte).
- Los commits locales de una orquestación (`arkana-agentic`, rama `arkana-worker/<plan>`) siguen esta misma convención."""


def fmt_of(ws, alias):
    """Formato del componente (`conventional` o `ia4d`), sin el origen del scope; ValueError si no se reconoce."""
    return manifest.parse_commit_format(ws.get(alias).get("commit_format"))[0]


def scope_of(ws, alias):
    return ws.commit_scope(alias)


def wants_module(ws, alias):
    """¿El formato pide el módulo como scope? (y, por tanto, debería tenerlo)."""
    try:
        return manifest.parse_commit_format(ws.get(alias).get("commit_format"))[1] == "module"
    except ValueError:
        return False


def body(alias, fmt, scope=None):
    if fmt not in FORMATS:
        raise ValueError(f"commit_format desconocido: {fmt!r} (usa {' o '.join(FORMATS)})")
    return f"## Convención de commits\n\nFormato de este repo ({manifest.display(alias)}): {FORMATS[fmt].format(scope=scope or alias)}\n\n{COMMON}"


def check(ws, alias):
    """None si el formato es válido; el motivo si no."""
    try:
        body(alias, fmt_of(ws, alias), scope_of(ws, alias))
        return None
    except ValueError as e:
        return str(e)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="commits.py")
    ap.add_argument("cmd", choices=("status", "show"))
    ap.add_argument("--component", action="append")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        al = [ws.key(c) for c in a.component] if a.component else ws.aliases()
        for c in al:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    if a.cmd == "show":
        for c in al:
            err = check(ws, c)
            print(f"### {manifest.display(c)}\n" + (body(c, fmt_of(ws, c), scope_of(ws, c)) if err is None else f"FAIL: {err}") + "\n")
        return 0
    rep = output.Report("arkana-workspace", "commits")
    for c in al:
        err = check(ws, c)
        rep.add("FAIL" if err else "OK", f"commits-{c}", err or f"formato {fmt_of(ws, c)}, scope {scope_of(ws, c)}", component=c)
        if not err and wants_module(ws, c) and not ws.module(c):
            rep.add("WARN", f"commits-{c}", f"el formato pide ({{module}}) pero {manifest.display(c)} no tiene módulo: se usa el alias (component edit --module)", component=c)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
