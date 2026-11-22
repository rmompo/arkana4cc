---
name: choose
description: Elige qué statusline se ve al abrir Claude Code en un componente gobernado por ARKANA - la de Arkana, la que ya tenga configurada (proveedores) o volver a preguntar. En la carpeta de ARKANA siempre se ve la de Arkana. Acepta --dry-run, --home y --json. Also invoked explicitly as /arkana-statusline:choose
allowed-tools: [AskUserQuestion]
version: 1
---

# arkana-statusline:choose

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" choose --component <alias> --use arkana|other|ask [--home DIR] [--dry-run] [--json]
```

El hook `SessionStart` te pide esta pregunta la primera vez que se abre Claude Code en un componente sin elección. Si no te dieron ya la respuesta:

1. Pregunta (`AskUserQuestion`): **Arkana** (ver la statusline de Arkana en ese componente) u **otra** (la que ya tenga configurada, p. ej. plugin4cc).
2. Guarda: `--use arkana` o `--use other`. La elección es **por persona y por componente** (`~/.arkana/statusline.json`), no se versiona.
3. Para cambiarla más adelante, `--use arkana` o `--use other`; `--use ask` borra la elección y se volverá a preguntar.

Se aplica en el siguiente render, sin reiniciar. No vale para la carpeta de ARKANA (siempre la de Arkana).
