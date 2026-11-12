---
name: fix
description: Corrige lo que check marca en la mensajería (almacén ausente, plugin deshabilitado). Interactivo, con copia .bak. Acepta --dry-run y --json.
version: 0
---

# arkana-messaging:fix

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" fix [--dry-run] [--no-settings] [--json]
```

Aplica solo lo que `check` marca con `WARN` (lo que ya está `OK` no se toca). No escribe nada en los repos.

## Pasos

1. `check` y, si hay `WARN`, `fix --dry-run` para enseñar qué cambiaría.
2. Pide confirmación (`AskUserQuestion`) y aplica con `fix`.
3. Vuelve a ejecutar `check` y muestra el resultado.
