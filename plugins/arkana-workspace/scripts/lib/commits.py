#!/usr/bin/env python3
"""Convención de commits de cada componente, generada desde el manifiesto (`commit_format`) como bloque `arkana:commits` en su CLAUDE.md.

  commits.py status [--component A] [--home DIR] [--json]
  commits.py apply  [--component A] [--home DIR] [--dry-run] [--json]

`commit_format` del componente: `conventional` (por defecto: `tipo(scope): descripción`, con dos puntos, p. ej. por commitlint) o `ia4d`
(formato opcional: `verbo(scope) descripción`, sin dos puntos). El bloque va en el CLAUDE.md del componente (CLAUDE.local.md cuando el componente lo declara como `seed_file`) y en el de ARKANA; lo
de fuera no se toca y se deja copia en `.arkana/arkana-workspace/bak/`. No hay fichero intermedio ni importaciones.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import locate, manifest, output, seedblock  # noqa: E402

FORMATS = {
    "ia4d": "**IA4D**: `verbo(scope) descripción`, **sin dos puntos**. Ejemplo: `docs({scope}) link workstation setup guides from the README`.",
    "conventional": "**Conventional Commits con dos puntos**: `tipo(scope): descripción`. Tipos: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, "
                    "`refactor`, `revert`, `style`, `test`. Ejemplo: `chore({scope}): ignore local Claude files`. Es lo que exige `commitlint`.",
}
COMMON = """- Inglés, **≤72 caracteres**, sin punto final y un solo objetivo por commit.
- **Nunca** `Co-Authored-By` ni otras líneas de coautoría, y **nunca** `--no-verify`: si un hook rechaza el commit, corrige el mensaje.
- Solo haces commit o push **cuando el usuario lo pide**. Un commit afecta solo al repo de la carpeta donde se ejecuta (los repos anidados son aparte).
- Los commits locales de una orquestación (`arkana-agentic`, rama `arkana-worker/<plan>`) siguen esta misma convención."""


def body(alias, fmt):
    if fmt not in FORMATS:
        raise ValueError(f"commit_format desconocido: {fmt!r} (usa {' o '.join(FORMATS)})")
    return (f"## Convención de commits (arkana-workspace)\n\n<!-- generado por /arkana-workspace:fix desde el manifiesto; no se edita a mano -->\n\n"
            f"Formato de este repo ({manifest.display(alias)}): {FORMATS[fmt].format(scope=alias)}\n\n{COMMON}")


def fmt_of(ws, alias):
    return (ws.get(alias).get("commit_format") or "conventional").strip().lower()


def target(ws, alias):
    a = manifest.canon(alias)
    if a == "arkana":
        return os.path.join(ws.path("arkana"), "CLAUDE.md")
    return os.path.join(ws.path(a), ws.get(a).get("seed_file") or "CLAUDE.md")


def state(ws, alias):
    return seedblock.state(target(ws, alias), "commits", body(alias, fmt_of(ws, alias)))


def run(ws, aliases, apply, dry):
    rep = output.Report("arkana-workspace", "commits")
    bak = os.path.join(locate.state_dir(ws.home), "arkana-workspace", "bak")
    for al in aliases:
        p = target(ws, al)
        rel = os.path.relpath(p, ws.root)
        try:
            b = body(al, fmt_of(ws, al))
        except ValueError as e:
            rep.add("FAIL", f"commits-{al}", str(e), component=al)
            continue
        st = seedblock.state(p, "commits", b)
        if not apply:
            rep.add("OK" if st == "OK" else "WARN", f"commits-{al}", f"{rel}: {st}" if st != "OK" else f"{rel}: al día ({fmt_of(ws, al)})", component=al)
        elif not os.path.isdir(os.path.dirname(p)):
            rep.add("WARN", f"commits-{al}", "no existe la carpeta del componente", component=al)
        else:
            act = seedblock.apply(p, "commits", b, backup_dir=os.path.join(bak, al), dry=dry, create=os.path.basename(p) != "CLAUDE.md")
            if act == "falta-fichero":
                rep.add("WARN", f"commits-{al}", f"falta {rel}: créalo desde la plantilla (arkana-workspace:fix, `claude-md`) y repite", component=al)
            else:
                rep.add("DRY" if dry and act != "igual" else "OK", f"commits-{al}", f"{rel}: {act}", component=al)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="commits.py")
    ap.add_argument("cmd", choices=("status", "apply"))
    ap.add_argument("--component", action="append")
    ap.add_argument("--home")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        al = [manifest.canon(c) for c in a.component] if a.component else ws.aliases()
        for c in al:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = run(ws, al, a.cmd == "apply", a.dry_run)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
