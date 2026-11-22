---
name: provider
description: Gestiona los proveedores de la statusline (las otras statuslines que se ven fuera de ARKANA o cuando no se elige la de Arkana) y la recuperación automática del hueco - list, add, remove y auto on|off. Un proveedor es un comando con prioridad (plugin4cc 20, otra 30; gana el menor). Acepta --dry-run y --json. Also invoked explicitly as /arkana-statusline:provider
allowed-tools: [AskUserQuestion]
version: 1
---

# arkana-statusline:provider

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" provider list [--json]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" provider add --id <id> --command "<comando>" [--priority N] [--dry-run]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" provider remove --id <id> [--dry-run]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" provider auto on|off [--dry-run]
```

La jerarquía de Arkana es **Arkana → plugin4cc → otra**. Los proveedores son las «otras»: se ven en un componente cuando no se elige la de Arkana y fuera de ARKANA. Se capturan solos con `install` y cuando otra herramienta pisa la `statusLine` de usuario; con `add` se registra a mano una que no se capturó (p. ej. la que otra herramienta pisó antes de instalar Arkana).

1. `list` primero y enseña los proveedores y si la recuperación automática está activa.
2. `add`: confirma con la persona usuaria el comando (el mismo que tendría en `statusLine`, p. ej. `bash ~/mi-barra.sh`); la prioridad por defecto es 20 si el comando contiene `statusline-command.sh` (plugin4cc) y 30 en otro caso.
3. `auto off` desactiva la recuperación automática: si otra herramienta pisa el hueco, solo se avisa con `check`. Por defecto está activa.
