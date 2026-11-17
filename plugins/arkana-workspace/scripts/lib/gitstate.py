#!/usr/bin/env python3
"""Estado git local de un repo, el mismo para `status`, el hook de estado y la statusline.

Todo sale de git local (`--no-optional-locks`, sin red): `untracked` (◌), `staged` (✚), `modified` (●), `ahead` (⇡, commits sin subir).
Con `watch=False` (componente que no se vigila) no cuentan los cambios del árbol de trabajo (◌ ✚ ●) ni `behind` (⇣); `ahead` (⇡) sí.
Con `ref` (versión fijada de un componente de referencia) se comprueba además que `HEAD` resuelva a ese `ref` (`ref_ok`: True/False, None si el `ref` no existe en el repo):
`HEAD ≠ ref` cuenta como «no limpio» y se pinta `≠ref`, **aunque `watch` sea False**; con `HEAD` separado en el `ref` la rama que se muestra es el propio `ref`.
Lo único que depende del remoto es `behind` (⇣): se conoce solo si el último `fetch` es reciente (`fresh`); si no, es None (se pinta `⇣?`).
Sin remoto o sin rama remota no hay `ahead` ni `behind`.
"""
import os
import time

import proc

FRESH_SECONDS = 30 * 60


def _git(path, *args):
    return proc.run(["git", "--no-optional-locks", "-C", path, *args], 10, dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))


def fetch_age(path):
    """Segundos desde el último fetch correcto (mtime de .git/FETCH_HEAD), o None."""
    rc, gd = _git(path, "rev-parse", "--git-common-dir")
    if rc != 0:
        return None
    gd = gd if os.path.isabs(gd) else os.path.join(path, gd)
    try:
        return time.time() - os.stat(os.path.join(gd, "FETCH_HEAD")).st_mtime
    except OSError:
        return None


def ref_commit(path, ref):
    """Commit al que apunta `ref` (tag, rama o sha; también `origin/<ref>`), o None."""
    for cand in (ref, f"origin/{ref}"):
        rc, out = _git(path, "rev-parse", "--verify", "--quiet", f"{cand}^{{commit}}")
        if rc == 0 and out:
            return out
    return None


def state(path, watch=True, ref=None):
    """dict: branch, untracked, staged, modified, ahead, behind (None = desconocido), has_remote, clean. None si no es un repo."""
    rc, out = _git(path, "status", "--porcelain=v2", "--branch", "-uall")
    if rc != 0:
        return None
    s = {"branch": "", "untracked": 0, "staged": 0, "modified": 0, "ahead": 0, "behind": None, "has_remote": False}
    upstream = False
    for l in out.splitlines():
        if l.startswith("# branch.head "):
            s["branch"] = l.split(" ", 2)[2]
        elif l.startswith("# branch.upstream "):
            upstream = True
        elif l.startswith("# branch.ab "):
            a, b = l.split()[2:4]
            s["ahead"], behind = int(a[1:]), int(b[1:])
            age = fetch_age(path)
            s["behind"] = behind if age is not None and age < FRESH_SECONDS else None
        elif l.startswith("? "):
            s["untracked"] += 1
        elif l[:2] in ("1 ", "2 "):
            xy = l.split()[1]
            s["staged"] += xy[0] != "."
            s["modified"] += xy[1] != "."
        elif l.startswith("u "):
            s["modified"] += 1
    s["has_remote"] = upstream
    if not upstream:
        s["ahead"] = 0
    if not watch:                                     # no vigilado: ni cambios locales ni commits por bajar (se conserva lo sin subir)
        s["untracked"] = s["staged"] = s["modified"] = 0
        s["behind"] = 0
    s["ref"], s["ref_ok"] = ref or "", None
    if ref:
        want, head = ref_commit(path, ref), _git(path, "rev-parse", "HEAD")[1]
        s["ref_ok"] = None if want is None else want == head
        if s["ref_ok"] and s["branch"] == "(detached)":
            s["branch"] = ref                                  # HEAD separado en el ref fijado: el nombre útil es el ref
    s["clean"] = not (s["untracked"] or s["staged"] or s["modified"] or s["ahead"] or s["ref_ok"] is False)
    return s


def badge(s):
    """Texto del bloque de rama: ` develop ◌13 ✚113 ●84 ⇡2 ⇣3 ` / ` develop ✓ `; sin remoto no hay flechas; ⇣? si no se conoce."""
    if s is None:
        return ""
    parts = [s["branch"]]
    for sym, key in (("◌", "untracked"), ("✚", "staged"), ("●", "modified"), ("⇡", "ahead")):
        if s[key]:
            parts.append(f"{sym}{s[key]}")
    if s["has_remote"]:
        if s["behind"] is None:
            parts.append("⇣?")
        elif s["behind"]:
            parts.append(f"⇣{s['behind']}")
    if s.get("ref_ok") is False:
        parts.append("≠ref")
    if len(parts) == 1:
        parts.append("✓")
    return " " + " ".join(parts) + " "
