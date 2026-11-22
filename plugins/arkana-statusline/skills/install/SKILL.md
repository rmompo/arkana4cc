---
name: install
description: Instala el despachador de la statusline de Arkana en ~/.claude/arkana-statusline/ (statusline.sh, dispatch.py, statusline.py y arkana_core) y lo activa como `statusLine` de usuario; en ARKANA se ve la de Arkana y en otros sitios la que hubiera. Con Arkana instalada, Arkana gobierna las statuslines: ocupa el hueco y la statusLine ajena que hubiera pasa a ser un proveedor (copia de los ajustes en bak/). Acepta --dry-run y --json. Also invoked explicitly as /arkana-statusline:install
allowed-tools: [AskUserQuestion]
version: 9
---

# arkana-statusline:install

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" install [--dry-run] [--json]
```

La statusline la ejecuta Claude Code como un comando de usuario, sin raíz de plugin: por eso se **copia** a `~/.claude/arkana-statusline/` (el despachador, el renderizador y el núcleo `arkana_core`, que viajan juntos). Claude Code admite una sola `statusLine` por ámbito, así que se instala un **despachador**: en cada render decide qué statusline se ve según la carpeta.

| Dónde estás | Qué se ve |
|---|---|
| carpeta de ARKANA | la de Arkana |
| componente gobernado por ARKANA | la de Arkana si la persona usuaria lo eligió; si no, la que ya tenga |
| cualquier otro sitio | la que ya tenga (nada, si no hay) |

«La que ya tenga» son los **proveedores** (`~/.arkana/statusline.json`): `plugin4cc` antes que cualquier otra. Si `~/.claude/statusline-command.sh` (el script de plugin4cc) existe, se registra como proveedor aunque otra herramienta ocupe la `statusLine`.

**Control de la jerarquía.** Una statusline de un tercero que no conozca esta jerarquía puede volver a escribir la `statusLine` de usuario. Los hooks `SessionStart` y `UserPromptSubmit` lo detectan y recuperan el hueco: la que la pisó queda como proveedor y se recoloca el despachador (`/arkana-statusline:provider auto off` lo desactiva).

## Pasos

1. `--dry-run` primero y enseña qué cambiaría. Si ya hay otra `statusLine` de usuario (un script propio, el antiguo `statusline-command.sh` de plugin4cc u otro plugin), díselo: con Arkana instalada **Arkana gobierna** y la actual **no se pierde**, pasa a ser un proveedor (se sigue viendo fuera de ARKANA y en los componentes que no elijan la de Arkana). No hace falta pedir permiso para ello; si la persona usuaria prefiere no cambiarla, que no instale este plugin. (`--replace` se acepta por compatibilidad y no hace nada distinto.)
2. Aplica. Hace copia de `~/.claude/settings.json` en `~/.claude/arkana-statusline/bak/` y una prueba de humo.
3. Recuerda reiniciar Claude Code o recargar los plugins para verla. En un componente, la primera vez se preguntará qué statusline ver (`/arkana-statusline:choose`).
