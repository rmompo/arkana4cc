"""0008 · Layout 8: `arkana-docs/` se reparte en tres subcarpetas: `src/` (originales), `md/` (su Markdown) y `out/` (documentos elaborados).

Antes los originales colgaban directamente de `arkana-docs/` y `md/` era una subcarpeta suya. Ahora `src/` y `md/` son hermanas con el MISMO árbol
(`arkana-docs/src/a/b.pdf` ↔ `arkana-docs/md/a/b.pdf.md`) y `out/` guarda lo que Arkana elabora a petición de la persona usuaria (estructura libre). La migración:
  - mueve a `arkana-docs/src/` todo lo que cuelga de `arkana-docs/` fuera de `md/`, `src/` y `out/` (con `git mv` si está versionado, así se conserva el historial y los punteros
    de git-lfs) y deja los originales de solo lectura (0444); un destino ya ocupado se avisa y se salta;
  - crea `src/.gitkeep` y `out/.gitkeep`.
El campo `original` del frontmatter de cada Markdown es relativo a la carpeta de originales, así que no hay que reescribir ningún documento. Si `.gitattributes` fija git-lfs con una ruta
`arkana-docs/…`, lo AVISA (no lo reescribe): hay que apuntarlo a `arkana-docs/src/…`. Un cambio compartido: una sola persona lo aplica y lo commitea.
"""
import os
import shutil
import stat
import subprocess

import _legacy  # noqa: F401  (las migraciones comparten el helper; aquí no se usa)

ID = "0008"
TITLE = "arkana-docs/ en src/ (originales, solo lectura), md/ y out/ (elaborados)"
SCOPE = ("shared",)
LAYOUT = 8
DOCS = "arkana-docs"
KEEP = ("src", "md", "out")


def _docs(ctx):
    return ctx.path(DOCS)


def _sueltos(ctx):
    """Entradas de `arkana-docs/` que no son src/, md/, out/ ni ocultas: los originales del layout anterior."""
    d = _docs(ctx)
    if not os.path.isdir(d):
        return []
    return [n for n in sorted(os.listdir(d)) if n not in KEEP and not n.startswith(".")]


def touches(ctx):
    return [os.path.join(DOCS, n) for n in _sueltos(ctx)]


def detect(ctx):
    d = _docs(ctx)
    if not os.path.isdir(d):
        return False
    return bool(_sueltos(ctx)) or not os.path.isdir(os.path.join(d, "src")) or not os.path.isdir(os.path.join(d, "out"))


def _tracked(ctx, rel):
    return ctx.git("ls-files", "--error-unmatch", "--", rel).returncode == 0


def _read_only(path):
    try:
        os.chmod(path, stat.S_IMODE(os.stat(path).st_mode) & ~0o222)
    except OSError:
        pass


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    src = os.path.join(_docs(ctx), "src")
    movidos = 0
    for n in _sueltos(ctx):
        origen, destino = os.path.join(_docs(ctx), n), os.path.join(src, n)
        rel_o, rel_d = os.path.relpath(origen, ctx.home), os.path.relpath(destino, ctx.home)
        if os.path.exists(destino):
            rep.add("WARN", f"{ID}:{n}", f"{rel_d} ya existe: no se mueve {rel_o} (resuélvelo a mano)")
            continue
        if not ctx.dry:
            os.makedirs(src, exist_ok=True)
            if not (_tracked(ctx, rel_o) and ctx.git("mv", "--", rel_o, rel_d).returncode == 0):
                shutil.move(origen, destino)
        movidos += 1
        rep.add(st, f"{ID}:mover", f"{rel_o} → {rel_d}")
    if not ctx.dry:
        for raiz, _dirs, ficheros in os.walk(src):
            for f in ficheros:
                if not f.startswith("."):
                    _read_only(os.path.join(raiz, f))                 # el original es la prueba: solo lectura (git no versiona ese bit; el sha256 es la garantía)
    for d in ("src", "out"):
        carpeta, gk = os.path.join(_docs(ctx), d), os.path.join(_docs(ctx), d, ".gitkeep")
        if not os.path.isfile(gk) and not (d == "src" and os.path.isdir(carpeta) and os.listdir(carpeta)):
            if not ctx.dry:
                os.makedirs(carpeta, exist_ok=True)
                open(gk, "w").close()
            rep.add(st, f"{ID}:carpeta", f"{DOCS}/{d}/.gitkeep {'se crearía' if ctx.dry else 'creado'}")
    ga = ctx.path(".gitattributes")
    try:
        lineas = [l.strip() for l in open(ga, encoding="utf-8").read().splitlines()] if os.path.isfile(ga) else []
    except OSError:
        lineas = []
    for l in lineas:
        if "filter=lfs" in l and l.startswith(DOCS + "/") and not l.startswith(DOCS + "/src/"):
            rep.add("WARN", f"{ID}:gitattributes", f"`{l.split()[0]}` fija git-lfs en la ruta antigua: cámbiala a `{DOCS}/src/{l.split()[0][len(DOCS) + 1:]}`")
    rep.add(st, f"{ID}:resumen", f"{movidos} originales pasan a {DOCS}/src/")


def verify(ctx):
    malos = []
    if _sueltos(ctx):
        malos.append("quedan entradas fuera de src/, md/ y out/ en arkana-docs/: " + ", ".join(_sueltos(ctx)[:3]))
    for d in ("src", "out"):
        if not os.path.isdir(os.path.join(_docs(ctx), d)):
            malos.append(f"falta {DOCS}/{d}/")
    return malos
