"""u001 · La copia de la statusline de usuario (`~/.claude/arkana-statusline`) al día con el plugin `arkana-statusline` instalado en esta máquina.

Un actualizador es de **máquina** (no del repo): converge lo que Arkana deja fuera de `.arkana/` y del repo, en cada terminal que actualiza los plugins. No lleva sello:
`detect` decide cada vez. Aquí, si hay una copia instalada del despachador y su contenido difiere del que trae el plugin `arkana-statusline` (por una versión nueva del
renderizador, del despachador o del núcleo), `apply` ejecuta el propio `arkana-statusline fix`, que la reinstala (con copia de los ajustes) y, si otra herramienta pisó la
`statusLine` de usuario, la recupera dejando a la otra como proveedor. Sin copia instalada, o sin el plugin, no hace nada: evolve no depende de ningún otro plugin, solo lo
invoca si está. El plugin se busca en `ARKANA_STATUSLINE_PLUGIN`, junto a este (árbol del repo) o, en la caché de Claude Code, como `.../arkana/arkana-statusline/<versión>`.
"""
import glob
import json
import os
import re
import subprocess
import sys

ID = "u001"
TITLE = "statusline de usuario: la copia de ~/.claude/arkana-statusline coincide con la del plugin arkana-statusline instalado"
TIMEOUT = 60


def installed_dir():
    return os.path.join(os.path.expanduser("~"), ".claude", "arkana-statusline")


def _version(path):
    return tuple(int(x) for x in re.findall(r"\d+", os.path.basename(path))) or (0,)


def plugin_dir():
    """Carpeta del plugin `arkana-statusline` (con scripts/lib/ops.py) o None."""
    env = os.environ.get("ARKANA_STATUSLINE_PLUGIN")
    cands = [env] if env else []
    if not env:
        mine = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))        # plugins/arkana-evolve o .../arkana-evolve/<versión>
        cands.append(os.path.join(os.path.dirname(mine), "arkana-statusline"))
        cands += sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(mine)), "arkana-statusline", "*")), key=_version, reverse=True)
    for c in cands:
        if os.path.isfile(os.path.join(c, "scripts", "lib", "ops.py")):
            return c
    return None


def _run(plugin, *args):
    p = subprocess.run([sys.executable, "-I", os.path.join(plugin, "scripts", "lib", "ops.py"), *args, "--json"], capture_output=True, text=True, timeout=TIMEOUT, stdin=subprocess.DEVNULL)
    try:
        return p.returncode, (json.loads(p.stdout) or {}).get("items", [])
    except ValueError:
        return p.returncode, None


def detect(ctx):
    """¿Hay una copia instalada y distinta de la del plugin? (cualquier fallo al consultar = no pendiente: nunca bloquea)."""
    if not os.path.isfile(os.path.join(installed_dir(), "statusline.sh")):
        return False
    plugin = plugin_dir()
    if not plugin:
        return False
    try:
        _, items = _run(plugin, "check")
    except (OSError, subprocess.SubprocessError):
        return False
    return any(i.get("id") == "copia" and i.get("status") == "WARN" for i in (items or []))


def apply(ctx, rep):
    plugin = plugin_dir()
    if ctx.dry:
        rep.add("DRY", ID, "se ejecutaría arkana-statusline fix: se reinstalaría la copia del despachador en ~/.claude/arkana-statusline")
        return
    try:
        rc, items = _run(plugin, "fix")
    except (OSError, subprocess.SubprocessError) as e:
        rep.add("FAIL", ID, f"no se pudo ejecutar arkana-statusline fix: {e}")
        return
    if items is None:
        rep.add("FAIL", ID, f"arkana-statusline fix no dio una salida legible (código {rc})")
        return
    for i in items:
        rep.add(i.get("status") if i.get("status") in ("OK", "WARN", "FAIL", "INFO", "DRY") else "INFO", f"{ID}:{i.get('id')}", i.get("detail", ""))
    if rc != 0 and not any(i.get("status") == "FAIL" for i in items):
        rep.add("FAIL", ID, f"arkana-statusline fix terminó con código {rc}")


def verify(ctx):
    return []
