---
name: uninstall
description: Retira el despachador de la statusline de Arkana - devuelve la `statusLine` de usuario al proveedor de mayor prioridad (o la quita si no hay) y borra la copia de ~/.claude/arkana-statusline. Hazlo antes de desinstalar el plugin. Acepta --dry-run y --json. Also invoked explicitly as /arkana-statusline:uninstall
allowed-tools: [AskUserQuestion]
version: 1
---

# arkana-statusline:uninstall

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" uninstall [--dry-run] [--json]
```

Si desinstalas el plugin sin hacerlo antes, el despachador seguiría ocupando la `statusLine` de usuario.

1. `--dry-run` y enseña qué statusline recuperará la persona usuaria (la de mayor prioridad entre los proveedores) o que se quedará sin ninguna.
2. Con su confirmación (`AskUserQuestion`), aplica. Hace copia de `settings.json` en `bak/`; las copias y las elecciones (`~/.arkana/statusline.json`) se conservan.
3. Recuerda reiniciar Claude Code o recargar los plugins.
