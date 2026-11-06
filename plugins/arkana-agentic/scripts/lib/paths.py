#!/usr/bin/env python3
"""Ubicacion de los metadatos de los plugins arkana-*: la carpeta `.arkana/` del repositorio de ARKANA.

Una subcarpeta por plugin, con el nombre del plugin, y `core/` para lo que usan varios plugins (los metadatos no ensucian los repos):
  arkana-agentic/            estado de arkana-agentic: planes/, run/linea.json, sesiones/, actual, politica.json
  arkana-workspace/bak/      copias de seguridad de arkana-workspace
  core/workspace.json      manifiesto del workspace (componentes, rutas, tipos, formatos de commit): lo leen todos los plugins arkana-*
  core/novedades.md        semilla de novedades compartidas (se importa desde los CLAUDE.md)
  core/commits.md          convencion de commits del plugin (la importa novedades.md)

Resolucion de la carpeta de ARKANA (la misma en los scripts de bash de arkana-workspace):
  0. $ARKANA_HOME (carpeta del repo de Arkana; el localizador del nucleo, arkana_core.locate, la encuentra tambien por cwd y por registro)
  1. $ARKANA_SHARED (nombre heredado, equivale a ARKANA_HOME)
  2. un ancestro de este fichero que sea la carpeta de ARKANA (contiene plugins/ y `.arkana/arkana.json`; antes, catalogo.json), sea cual sea su nombre
  3. la raiz git del directorio actual: la carpeta hermana ../arkana (o ../shared, nombre heredado), o ella misma si es la de ARKANA
  Si ninguna lo encuentra: error `NoWorkspace` (no hay ruta por defecto: el workspace se crea con /arkana-workspace:install).
Resolucion de `.arkana`: $ARKANA_PLUGINS_DIR o <arkana>/.arkana.
"""
import os
import subprocess



class NoWorkspace(RuntimeError):
    """No se encuentra la carpeta de Arkana (ni ARKANA_HOME, ni ARKANA_SHARED, ni la raíz git del directorio actual)."""


def _is_arkana(d):
    return os.path.isdir(os.path.join(d, "plugins")) and (os.path.isfile(os.path.join(d, ".arkana", "arkana.json")) or os.path.isfile(os.path.join(d, "catalogo.json")))


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
    env = os.environ.get("ARKANA_SHARED")
    if env and os.path.isdir(env):
        return os.path.realpath(env)
    d = os.path.dirname(os.path.realpath(__file__))
    while d != os.path.dirname(d):
        if _is_arkana(d):
            return d
        d = os.path.dirname(d)
    root = _git_root(cwd or os.getcwd())
    if root:
        for nombre in ("arkana", "shared"):                       # `shared` es el nombre heredado de la carpeta de ARKANA
            sib = os.path.join(os.path.dirname(root), nombre)
            if _is_arkana(sib):
                return sib
        if _is_arkana(root):
            return root
    raise NoWorkspace("no se encuentra el workspace de Arkana: define ARKANA_HOME o ejecuta desde el repo de Arkana")


shared_dir = arkana_dir                                      # nombre heredado, se mantiene por compatibilidad


def plugins_dir(cwd=None):
    return os.environ.get("ARKANA_PLUGINS_DIR") or os.path.join(arkana_dir(cwd), ".arkana")


def item(name):
    """Ruta de un elemento de metadatos, relativa a .arkana (p. ej. 'arkana-agentic' o 'core/workspace.json')."""
    return os.path.join(plugins_dir(), name)


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plugins-dir"
    if cmd in ("arkana", "shared"):                           # `shared`: nombre heredado
        print(arkana_dir())
    elif cmd == "item" and len(sys.argv) > 2:
        print(item(sys.argv[2]))
    else:
        print(plugins_dir())
