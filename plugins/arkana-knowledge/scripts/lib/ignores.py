"""Fichero de ignores de `arkana-docs/`: lo que NO son documentos (código fuente, dependencias, builds…) y por tanto no necesita su Markdown.

`arkana-docs/.arkanaignore` (versionado, lo decide el equipo). Sintaxis como `.gitignore`, con las rutas relativas a `arkana-docs/`:

  # comentario                    línea en blanco o que empieza por # : se ignora
  *.py                            sin `/`: el nombre en cualquier carpeta (file.*, file.name, *.json…)
  node_modules/                   `/` final: una carpeta (y todo lo que contiene), en cualquier nivel
  src/proyecto-ejemplo/**         con `/` en medio o al principio: ruta desde arkana-docs/; `**` cruza carpetas, `*` y `?` no
  **/target/                      una carpeta `target` a cualquier profundidad
  fuente/generar.py               un fichero concreto
  !src/proyecto-ejemplo/guia.pdf  `!` : vuelve a incluir lo que una regla anterior ignoró (gana la última regla que case)

Se aplica a `src/` (un original ignorado no exige su Markdown) y a `out/` (un fichero ignorado no se toma por un render sin su `.md` fuente). Lo que cuelga de una carpeta ignorada
queda ignorado. Un puntero de git-lfs sigue avisando aunque esté ignorado (falta `git lfs pull`). Sin fichero o sin reglas no se ignora nada.
"""
import os
import re

FILE = ".arkanaignore"
TEMPLATE = """# Ficheros de arkana-docs/ que NO son documentos y no necesitan su Markdown: código fuente, dependencias, builds...
# Sintaxis como .gitignore, con las rutas relativas a arkana-docs/. Se aplica a src/ y a out/.
#
#   *.py                             un nombre o patrón en cualquier carpeta (file.name, file.*)
#   node_modules/                    una carpeta y todo lo que contiene, en cualquier nivel
#   src/proyecto-ejemplo/**          una ruta desde arkana-docs/ (** cruza carpetas)
#   fuente/generar.py                un fichero concreto
#   !src/proyecto-ejemplo/guia.pdf   vuelve a incluir lo ignorado antes
#
# Los documentos reales (PDF, DOCX, XLSX...) no se ignoran: deben tener su Markdown (/arkana-knowledge:ingest).
"""


def _regex(pat):
    """Glob estilo gitignore → regex (sin anclas): `**/` cualquier prefijo de carpetas, `**` cualquier cosa, `*` y `?` sin cruzar `/`, `[...]` clases."""
    out, i, n = "", 0, len(pat)
    while i < n:
        c = pat[i]
        if c == "*":
            if pat[i:i + 2] == "**":
                if pat[i + 2:i + 3] == "/":
                    out += "(?:.*/)?"
                    i += 3
                    continue
                out += ".*"
                i += 2
                continue
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        elif c == "[":
            j = pat.find("]", i + 2)
            if j == -1:
                out += re.escape(c)
            else:
                cuerpo = pat[i + 1:j]
                out += "[" + ("^" + cuerpo[1:] if cuerpo.startswith("!") else cuerpo) + "]"
                i = j + 1
                continue
        else:
            out += re.escape(c)
        i += 1
    return out


class Rule:
    def __init__(self, line):
        self.neg = line.startswith("!")
        pat = line[1:] if self.neg else line
        self.dir_only = pat.endswith("/")
        pat = pat.rstrip("/")
        anclada = "/" in pat
        pat = pat.lstrip("/")
        self.rx = re.compile(("^" if anclada else "^(?:.*/)?") + _regex(pat) + "$")


class Matcher:
    def __init__(self, lines=()):
        self.rules = []
        for l in lines:
            l = l.rstrip("\n").rstrip()
            if l and not l.lstrip().startswith("#"):
                try:
                    self.rules.append(Rule(l.strip()))
                except re.error:
                    pass                                            # una regla mal formada no rompe la validación: se salta

    def __bool__(self):
        return bool(self.rules)

    def ignored(self, rel, is_dir=False):
        """¿`rel` (ruta con `/` relativa a arkana-docs/) queda ignorada por sí misma? Gana la última regla que case; `!` la reincluye."""
        res = None
        for r in self.rules:
            if r.dir_only and not is_dir:
                continue
            if r.rx.match(rel):
                res = not r.neg
        return bool(res)


def load(home, docs="arkana-docs"):
    try:
        with open(os.path.join(home, docs, FILE), encoding="utf-8") as f:
            return Matcher(f.read().splitlines())
    except (OSError, UnicodeDecodeError):
        return Matcher()


def walk(home, base, docs="arkana-docs", matcher=None):
    """Recorre `base` (src/ u out/) y rinde (ruta absoluta, ruta relativa a `docs`, ignorado). No entra en carpetas que empiezan por punto; lo que cuelga de una carpeta ignorada es ignorado."""
    m = matcher if matcher is not None else load(home, docs)
    raiz_docs = os.path.join(home, docs)
    estado = {base: False}
    for root, dirs, files in os.walk(base):
        ign_root = estado.get(root, False)
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for d in dirs:
            p = os.path.join(root, d)
            estado[p] = ign_root or m.ignored(os.path.relpath(p, raiz_docs).replace(os.sep, "/"), True)
        for f in sorted(files):
            p = os.path.join(root, f)
            yield p, os.path.relpath(p, raiz_docs).replace(os.sep, "/"), ign_root or m.ignored(os.path.relpath(p, raiz_docs).replace(os.sep, "/"))
