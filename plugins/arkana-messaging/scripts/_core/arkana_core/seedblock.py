"""Bloques gestionados dentro de un fichero de texto (CLAUDE.md, CLAUDE.local.md): `<!-- arkana:NOMBRE:start -->` … `<!-- arkana:NOMBRE:end -->`.

El contenido entre marcadores es de Arkana (se reemplaza entero, nunca se edita a mano); lo de fuera no se toca. Es el mecanismo de la
semilla de `arkana-messaging` (`arkana:messaging`) y de la convención de commits de `arkana-workspace` (`arkana:commits`).
`legacy` admite pares de marcadores antiguos (una lista de pares `(inicio, fin)`) que se sustituyen al aplicar el bloque nuevo.
"""
import os
import shutil
import time

from . import datafiles


def markers(name):
    return f"<!-- arkana:{name}:start -->", f"<!-- arkana:{name}:end -->"


def render(name, body):
    s, e = markers(name)
    return f"{s}\n{body.strip()}\n{e}\n"


def _find(text, pairs):
    for s, e in pairs:
        if s in text:
            a = text.index(s)
            if e in text[a:]:
                b = text.index(e, a) + len(e)
                if text[b:b + 1] == "\n":
                    b += 1
                return a, b
    return None


def _pairs(name, legacy):
    return [markers(name), *legacy]


def state(path, name, body, legacy=()):
    """OK | DESACTUALIZADO (hay bloque distinto o con marcadores antiguos) | SIN-BLOQUE | SIN-FICHERO."""
    if not os.path.isfile(path):
        return "SIN-FICHERO"
    with open(path, encoding="utf-8") as f:
        text = f.read()
    r = _find(text, _pairs(name, legacy))
    if r is None:
        return "SIN-BLOQUE"
    return "OK" if text[r[0]:r[1]] == render(name, body) else "DESACTUALIZADO"


def apply(path, name, body, legacy=(), backup_dir=None, dry=False, create=True):
    """Pone el bloque. -> 'igual' | 'creado' | 'añadido' | 'reemplazado' | 'falta-fichero' (si create=False y no existe)."""
    exists = os.path.isfile(path)
    if not exists and not create:
        return "falta-fichero"
    text = ""
    if exists:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    new_block = render(name, body)
    r = _find(text, _pairs(name, legacy))
    if r is not None:
        if text[r[0]:r[1]] == new_block:
            return "igual"
        new, action = text[:r[0]] + new_block + text[r[1]:], "reemplazado"
    else:
        sep = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        new, action = text + (sep + "\n" if text else "") + new_block, "creado" if not exists else "añadido"
    if dry:
        return action
    if exists and backup_dir:
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(path, os.path.join(backup_dir, f"{os.path.basename(path)}.{time.strftime('%Y%m%dT%H%M%S')}"))
    datafiles.atomic_write(path, new)
    return action


def drop_lines(path, exact_lines, backup_dir=None, dry=False):
    """Quita del fichero las líneas que coinciden exactamente (p. ej. una importación `@…` obsoleta). -> nº de líneas quitadas."""
    if not os.path.isfile(path):
        return 0
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    keep = [l for l in lines if l.strip() not in exact_lines]
    n = len(lines) - len(keep)
    if n and not dry:
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copy2(path, os.path.join(backup_dir, f"{os.path.basename(path)}.{time.strftime('%Y%m%dT%H%M%S')}"))
        datafiles.atomic_write(path, "\n".join(keep))
    return n
