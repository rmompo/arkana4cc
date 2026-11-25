"""u002 · El registro de workspaces de usuario vive en `~/.arkana/workspaces.json` (antes `~/.arkana-workspaces.json`).

Es un dato de **máquina** (no del repo ni de `.arkana/`): lo usan los hooks para localizar el workspace desde la carpeta de un componente. Si todavía existe el fichero antiguo y no
el nuevo, `apply` lo mueve conservando las entradas de TODOS los workspaces de la máquina (y el nombre de este); mientras tanto el antiguo se sigue leyendo. Sin fichero antiguo, o con el
nuevo ya creado, no hace nada. Idempotente y sin sello: `detect` decide cada vez.
"""
from arkana_core import locate
import os

ID = "u002"
TITLE = "registro de workspaces de usuario: ~/.arkana-workspaces.json pasa a ~/.arkana/workspaces.json"


def detect(ctx):
    return os.path.isfile(locate.legacy_registry_path()) and not os.path.isfile(locate.registry_path())


def apply(ctx, rep):
    viejo, nuevo = locate.legacy_registry_path(), locate.registry_path()
    if ctx.dry:
        rep.add("DRY", "registro-usuario", f"{viejo} se movería a {nuevo} (con las entradas de todos los workspaces)")
        return
    locate.register(ctx.home)                                   # copia las entradas antiguas al nuevo, añade este workspace si faltaba y borra el antiguo
    rep.add("OK", "registro-usuario", f"{viejo} movido a {nuevo}")


def verify(ctx):
    return []
