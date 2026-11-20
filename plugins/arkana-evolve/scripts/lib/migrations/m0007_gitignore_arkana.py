"""0007 · Layout 7: el repo de ARKANA ignora su carpeta local `.arkana/`.

`.arkana/` guarda el manifiesto, los datos de los plugins y `.credentials`: es local y nunca debe versionarse. Antes lo dejaba cada persona a mano; ahora `layout init` lo hace en las
instalaciones nuevas y esta migración en las que ya existían: añade `/.arkana/` al `.gitignore` de ARKANA si git no lo ignora ya (lo crea si falta). Es un cambio **compartido**
(un fichero versionado del repo): una sola persona lo aplica y lo commitea; si ya está ignorado por otra vía (`.gitignore`, `.git/info/exclude`, el ignore global), no hace nada.
Fuera de un repo git no hace nada.
"""
import os

import _legacy  # noqa: F401  (las migraciones comparten el helper; aquí no se usa)

ID = "0007"
TITLE = "el repo de ARKANA ignora .arkana/ (datos locales y credenciales) en su .gitignore"
SCOPE = ("shared",)
LAYOUT = 7
PROBE = os.path.join(".arkana", "arkana.json")


def _is_repo(ctx):
    r = ctx.git("rev-parse", "--is-inside-work-tree")
    return r.returncode == 0 and r.stdout.strip() == "true"


def _ignored(ctx):
    return ctx.git("check-ignore", "--no-index", "-q", PROBE).returncode == 0       # --no-index: también cuenta si algún fichero ya está versionado


def touches(ctx):
    return [".gitignore"]


def detect(ctx):
    return _is_repo(ctx) and not _ignored(ctx)


def apply(ctx, rep):
    gi = ctx.path(".gitignore")
    if not ctx.dry:
        try:
            with open(gi, encoding="utf-8") as f:
                cur = f.read()
        except OSError:
            cur = ""
        with open(gi, "w", encoding="utf-8") as f:
            f.write(cur + ("" if not cur or cur.endswith("\n") else "\n") + "/.arkana/\n")
    tracked = ctx.git("ls-files", "--", ".arkana").stdout.split()
    if tracked:
        rep.add("WARN", f"{ID}:versionado", f"{len(tracked)} ficheros de .arkana/ ya están versionados (¿y `.credentials`?): ignorarlos no los saca de git; "
                "quítalos con `git rm -r --cached .arkana`, rota las credenciales si estaban y commitea")
    rep.add("DRY" if ctx.dry else "OK", f"{ID}:gitignore", "/.arkana/ " + ("se añadiría al" if ctx.dry else "añadido al") + " .gitignore de ARKANA (queda sin commitear)")


def verify(ctx):
    return [] if _ignored(ctx) else ["git sigue sin ignorar .arkana/ (¿una regla `!` lo reincluye?)"]
