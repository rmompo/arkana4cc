"""0002 · Arkana deja de escribir en los ficheros de instrucciones de los repos de trabajo.

Antes, los plugins ponían bloques gestionados (`arkana:messaging`, `arkana:commits`, `arkana:agentic`) en el `CLAUDE.md` de ARKANA y de cada componente
(o en `CLAUDE.local.md`, según `seed_file`). Ahora esas directrices las inyectan los hooks de sesión y las notas locales de cada repo van en
`ARKANA.local.md` (local, excluido con `.git/info/exclude`). Esta migración, por cada pieza (ARKANA y los componentes):

  - quita los bloques gestionados de `CLAUDE.md` y `CLAUDE.local.md` y deja lo demás tal cual (un `CLAUDE.md` versionado queda modificado: se commitea en su repo);
  - renombra `CLAUDE.local.md` a `ARKANA.local.md` si este no existe (si se queda sin contenido tras quitar los bloques, lo borra);
  - añade `.claude/`, `.claude-session/` y `ARKANA.local.md` a `.git/info/exclude` si no estaban ya ignorados por otra vía.
Y retira `seed_file` del manifiesto local. No toca un fichero versionado con cambios sin commitear (lo avisa y lo salta).
"""
import json
import os
import re
import subprocess

from arkana_core import datafiles
import _legacy

ID = "0002"
TITLE = "sin ficheros de instrucciones en los repos (directrices por hook, ARKANA.local.md)"
SCOPE = ("local", "shared")

BLOCK = re.compile(r"[ \t]*<!-- arkana:(messaging|commits|agentic):start -->.*?<!-- arkana:\1:end -->[ \t]*\n?", re.S)
EXCLUDES = [(".claude/", ".claude/x"), (".claude-session/", ".claude-session/x"), ("ARKANA.local.md", "ARKANA.local.md")]


def _git(path, *args):
    try:
        r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, timeout=15,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"))
        return r.returncode, r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _is_repo(path):
    return os.path.isdir(path) and _git(path, "rev-parse", "--git-dir")[0] == 0


def _read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _stripped(text):
    return BLOCK.sub("", text)


def _tracked_dirty(path, name):
    """¿`name` está versionado y con cambios sin commitear en su repo?"""
    if not _is_repo(path):
        return False
    if _git(path, "ls-files", "--error-unmatch", "--", name)[0] != 0:
        return False
    return bool(_git(path, "status", "--porcelain", "--", name)[1])


def _missing_excludes(path):
    return [pat for pat, probe in EXCLUDES if _git(path, "check-ignore", "-q", probe)[0] != 0] if _is_repo(path) else []


def _manifest(ctx):
    return os.path.join(ctx.state, "core", "workspace.json")


def _has_seed_file(ctx):
    mf = datafiles.read_json(_manifest(ctx), {}) or {}
    return any("seed_file" in c for c in [mf.get("arkana") or {}] + list(mf.get("components", [])) if isinstance(c, dict))


def _pending(ctx, verifying=False):
    """[(alias, carpeta, motivos)] de las piezas con algo que migrar. Al verificar se omite lo que se salta a propósito y ya se avisó con WARN
    (un CLAUDE.md versionado con cambios sin commitear, o un CLAUDE.local.md junto a un ARKANA.local.md que ya existe)."""
    res = []
    for alias, path in _legacy.raw_pieces(ctx):
        if not os.path.isdir(path):
            continue
        why = []
        for name in ("CLAUDE.md", "CLAUDE.local.md"):
            t = _read(os.path.join(path, name))
            if t is not None and BLOCK.search(t) and not (verifying and name == "CLAUDE.md" and _tracked_dirty(path, "CLAUDE.md")):
                why.append(f"bloques en {name}")
        cl = _read(os.path.join(path, "CLAUDE.local.md"))
        if cl is not None and (not os.path.exists(os.path.join(path, "ARKANA.local.md")) or BLOCK.search(cl)):
            why.append("CLAUDE.local.md → ARKANA.local.md")
        if _missing_excludes(path):
            why.append("exclusiones locales de git")
        if why:
            res.append((alias, path, why))
    return res


def touches(ctx):
    return ["CLAUDE.md", "CLAUDE.local.md"]


def detect(ctx):
    return _has_seed_file(ctx) or bool(_pending(ctx))


def _write(path, text):
    datafiles.atomic_write(path, text)


def _migrate_piece(ctx, rep, alias, path):
    st = "DRY" if ctx.dry else "OK"
    # 1. bloques gestionados en CLAUDE.md
    cm = os.path.join(path, "CLAUDE.md")
    t = _read(cm)
    if t is not None and BLOCK.search(t):
        if _tracked_dirty(path, "CLAUDE.md"):
            rep.add("WARN", f"{ID}:{alias}", "CLAUDE.md tiene cambios sin commitear: no se toca (commitéalos y repite)")
        else:
            if not ctx.dry:
                _write(cm, _stripped(t))
            rep.add(st, f"{ID}:{alias}", "bloques de Arkana quitados de CLAUDE.md (queda sin commitear en su repo)")
    # 2. CLAUDE.local.md → ARKANA.local.md
    cl = os.path.join(path, "CLAUDE.local.md")
    al = os.path.join(path, "ARKANA.local.md")
    t = _read(cl)
    if t is not None:
        limpio = _stripped(t).strip()
        if os.path.exists(al):
            rep.add("WARN", f"{ID}:{alias}", "existen CLAUDE.local.md y ARKANA.local.md: no se pisa; pasa a mano lo que quieras conservar")
            if not ctx.dry and BLOCK.search(t):
                _write(cl, _stripped(t))
        elif not limpio:
            if not ctx.dry:
                os.remove(cl)
            rep.add(st, f"{ID}:{alias}", "CLAUDE.local.md solo tenía bloques de Arkana: borrado")
        else:
            if not ctx.dry:
                _write(al, limpio + "\n")
                os.remove(cl)
            rep.add(st, f"{ID}:{alias}", "CLAUDE.local.md → ARKANA.local.md (sin los bloques de Arkana)")
    # 3. exclusiones locales de git
    faltan = _missing_excludes(path)
    if faltan:
        rc, out = _git(path, "rev-parse", "--git-path", "info/exclude")
        f = out if os.path.isabs(out) else os.path.join(path, out)
        if rc == 0 and f:
            if not ctx.dry:
                cur = _read(f) or ""
                _write(f, cur + ("" if not cur or cur.endswith("\n") else "\n") + "".join(p + "\n" for p in faltan))
            rep.add(st, f"{ID}:{alias}", f"{', '.join(faltan)} añadido a .git/info/exclude")


def apply(ctx, rep):
    st = "DRY" if ctx.dry else "OK"
    for alias, path, _why in _pending(ctx):
        _migrate_piece(ctx, rep, alias, path)
    if _has_seed_file(ctx):
        if not ctx.dry:
            mf = datafiles.read_json(_manifest(ctx), {}) or {}
            for c in [mf.get("arkana") or {}] + list(mf.get("components", [])):
                if isinstance(c, dict):
                    c.pop("seed_file", None)
            datafiles.atomic_write_json(_manifest(ctx), mf)
        rep.add(st, f"{ID}:manifiesto", "`seed_file` retirado del manifiesto local")
    rep.add("INFO", ID, "las directrices de cada sesión las inyectan los hooks de los plugins; las notas locales de un repo van en ARKANA.local.md")


def verify(ctx):
    p = [f"{a}: {', '.join(w)}" for a, _, w in _pending(ctx, verifying=True)]
    return p[:5] + (["el manifiesto conserva seed_file"] if _has_seed_file(ctx) else [])
