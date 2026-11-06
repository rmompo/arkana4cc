#!/usr/bin/env python3
"""Comparadores deterministas: rutas protegidas, alcance, comandos permitidos, package.json sensible."""
import re


def _expand_braces(patron):
    m = re.search(r"\{([^{}]+)\}", patron)
    if not m:
        return [patron]
    res = []
    for opc in m.group(1).split(","):
        res += _expand_braces(patron[:m.start()] + opc + patron[m.end():])
    return res


def _to_regex(patron):
    out, i = "", 0
    while i < len(patron):
        c = patron[i]
        if patron.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
            continue
        if patron.startswith("**", i):
            out += ".*"
            i += 2
            continue
        if c == "*":
            out += "[^/]*"
        elif c == "?":
            out += "[^/]"
        else:
            out += re.escape(c)
        i += 1
    return re.compile("^" + out + "$")


def matches(ruta, patron):
    """Una ruta relativa coincide con un glob. Un patron sin '/' se aplica a cualquier profundidad."""
    ruta = ruta.lstrip("./") if ruta.startswith("./") else ruta
    for p in _expand_braces(patron):
        if "/" not in p:
            if _to_regex(p).match(ruta.rsplit("/", 1)[-1]):
                return True
        else:
            r = _to_regex(p)
            if r.match(ruta):
                return True
            # '.git/**' tambien cubre '.git' a secas
            if p.endswith("/**") and ruta == p[:-3]:
                return True
    return False


def is_protected_path(ruta, patrones):
    return any(matches(ruta, p) for p in patrones)


def outside_scope(rutas, permitidas):
    """Rutas que no encajan en ningun glob permitido. Sin 'permitidas' se acepta todo el repo."""
    if not permitidas:
        return []
    return [r for r in rutas if not any(matches(r, p) for p in permitidas)]


def is_allowed_command(argv, permitidos):
    """Igualdad exacta del argv contra la lista cerrada (sin shell, sin comodines)."""
    return list(argv) in [list(x) for x in permitidos]


def package_json_sensible(antes, despues, campos):
    """Campos sensibles de package.json que han cambiado (comparando objetos ya cargados)."""
    return [c for c in campos if (antes or {}).get(c) != (despues or {}).get(c)]


# Comandos de la lista cerrada que se ejecutan pero NO prueban nada de un criterio (siempre terminan con exito): su resultado es informativo.
INFORMATIVE_CHECKS = [["git", "diff", "--stat"]]


def is_informative_check(comando):
    return list(comando) in INFORMATIVE_CHECKS
