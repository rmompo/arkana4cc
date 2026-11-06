---
name: fix
description: Corrige lo que check --all marca en la mensajería (almacén, plugin deshabilitado, semillas ausentes o desactualizadas). Interactivo, con copia .bak. Acepta --dry-run y --json.
---

# arkana-messaging:fix

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" fix [--dry-run] [--json]
```

Aplica solo lo que `check --all` marca con `WARN` (lo que ya está `OK` no se toca).

## Pasos

1. `check --all` y, si hay `WARN`, `fix --dry-run` para enseñar qué cambiaría.
2. Pide confirmación (`AskUserQuestion`) y aplica con `fix`.
3. Si falta un `CLAUDE.md` versionado, no lo crea: eso lo hace `/arkana-workspace:fix`. Vuelve a ejecutar `check --all` y muestra el resultado.
