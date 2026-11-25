"""0010 · Layout 10: `arkana-docs/.arkanaignore`, la plantilla para declarar lo que NO son documentos.

`validate` de `arkana-knowledge` exige un Markdown para cada fichero de `arkana-docs/src/` y una dupla (`.md` + render) para cada documento de `out/`. Lo que no es un documento
(código fuente, dependencias, un proyecto de ejemplo, un script de apoyo) se declara en `arkana-docs/.arkanaignore`, con sintaxis de `.gitignore`. Las instalaciones nuevas lo reciben
de `knowledge install`; esta migración se lo da a las que ya existían: crea el fichero **solo con comentarios** (no ignora nada, así que no cambia ningún resultado) si falta. Nunca pisa
uno existente. Es un cambio compartido (un fichero versionado): una sola persona lo aplica y lo commitea. Fuera de un repo con `arkana-docs/` no hace nada.
"""
import os

ID = "0010"
TITLE = "arkana-docs/.arkanaignore: plantilla para declarar lo que no son documentos"
SCOPE = ("shared",)
LAYOUT = 10
FILE = os.path.join("arkana-docs", ".arkanaignore")
TEMPLATE = '# Ficheros de arkana-docs/ que NO son documentos y no necesitan su Markdown: código fuente, dependencias, builds...\n# Sintaxis como .gitignore, con las rutas relativas a arkana-docs/. Se aplica a src/ y a out/.\n#\n#   *.py                             un nombre o patrón en cualquier carpeta (file.name, file.*)\n#   node_modules/                    una carpeta y todo lo que contiene, en cualquier nivel\n#   src/proyecto-ejemplo/**          una ruta desde arkana-docs/ (** cruza carpetas)\n#   fuente/generar.py                un fichero concreto\n#   !src/proyecto-ejemplo/guia.pdf   vuelve a incluir lo ignorado antes\n#\n# Los documentos reales (PDF, DOCX, XLSX...) no se ignoran: deben tener su Markdown (/arkana-knowledge:ingest).\n'


def touches(ctx):
    return [FILE]


def detect(ctx):
    return os.path.isdir(ctx.path("arkana-docs")) and not os.path.isfile(ctx.path(FILE))


def apply(ctx, rep):
    if not ctx.dry:
        with open(ctx.path(FILE), "w", encoding="utf-8") as f:
            f.write(TEMPLATE)
    rep.add("DRY" if ctx.dry else "OK", f"{ID}:plantilla", f"{FILE} {'se crearía' if ctx.dry else 'creado'} (solo comentarios: no ignora nada hasta que lo edites)")


def verify(ctx):
    return [] if os.path.isfile(ctx.path(FILE)) else [f"falta {FILE}"]
