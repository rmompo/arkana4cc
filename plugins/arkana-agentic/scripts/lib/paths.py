#!/usr/bin/env python3
"""Ubicacion de los metadatos de los plugins arkana-*: la carpeta `.arkana/` del repositorio de ARKANA.

Una subcarpeta por plugin, con el nombre del plugin, y `core/` para lo que usan varios plugins (los metadatos no ensucian los repos):
  arkana-agentic/            estado de arkana-agentic: planes/, run/linea.json, actual, politica.json
  arkana-workspace/bak/      copias de seguridad de arkana-workspace
  core/workspace.json      manifiesto del workspace (componentes, rutas, tipos, formatos de commit): lo leen todos los plugins arkana-*

Resolucion de la carpeta de ARKANA (la misma en los scripts de bash de arkana-workspace):
  0. $ARKANA_HOME (carpeta del repo de Arkana; el localizador del nucleo, arkana_core.locate, la encuentra tambien por cwd y por registro)
  1. un ancestro de este fichero que sea la carpeta de ARKANA (contiene `.arkana/arkana.json`), sea cual sea su nombre
  2. la raiz git del directorio actual: la carpeta hermana ../arkana, o ella misma si es la de ARKANA
  Si ninguna lo encuentra: error `NoWorkspace` (no hay ruta por defecto: el workspace se crea con /arkana-workspace:install).
Resolucion de `.arkana`: $ARKANA_PLUGINS_DIR o <arkana>/.arkana.
"""
import os
import subprocess



class NoWorkspace(RuntimeError):
    """No se encuentra la carpeta de Arkana (ni ARKANA_HOME, ni la raíz git del directorio actual)."""


def _is_arkana(d):
    return os.path.isfile(os.path.join(d, ".arkana", "arkana.json"))


def _git_root(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def arkana_dir(cwd=None):
    home = os.environ.get("ARKANA_HOME")
    if home and os.path.isdir(home):
        return os.path.realpath(home)
    d = os.path.dirname(os.path.realpath(__file__))
    while d != os.path.dirname(d):
        if _is_arkana(d):
            return d
        d = os.path.dirname(d)
    root = _git_root(cwd or os.getcwd())
    if root:
        sib = os.path.join(os.path.dirname(root), "arkana")
        if _is_arkana(sib):
            return sib
        if _is_arkana(root):
            return root
    raise NoWorkspace("no se encuentra el workspace de Arkana: define ARKANA_HOME o ejecuta desde el repo de Arkana")


def plugins_dir(cwd=None):
    return os.environ.get("ARKANA_PLUGINS_DIR") or os.path.join(arkana_dir(cwd), ".arkana")


def item(name):
    """Ruta de un elemento de metadatos, relativa a .arkana (p. ej. 'arkana-agentic' o 'core/workspace.json')."""
    return os.path.join(plugins_dir(), name)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plugins-dir"
    if cmd == "arkana":
        print(arkana_dir())
    elif cmd == "item" and len(sys.argv) > 2:
        print(item(sys.argv[2]))
    else:
        print(plugins_dir())
