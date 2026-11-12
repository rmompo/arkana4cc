---
name: check
description: Diagnóstico de solo lectura de la mensajería - almacén, plugin habilitado y latido de los hooks en ESTA sesión. Nunca corrige; propone install o fix. Acepta --json.
version: 0
---

# arkana-messaging:check

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" check [--json]
```

Salida `ESTADO|ID|detalle` y `RESUMEN`. Comprueba: `almacen`, `plugin` (habilitado en `~/.claude/settings.json`) y `latido` (los hooks han corrido en esta sesión, por `CLAUDE_CODE_SESSION_ID`; respaldo: latido del componente en los últimos 15 min). `--all` y `--component` se aceptan por compatibilidad y no cambian nada.

## Pasos

1. Ejecútalo y resume en una línea si todo está `OK`.
2. Si el `latido` es `WARN` (los hooks no corren), propón al usuario `/arkana-messaging:install` y recargar los plugins. **Una sola vez por sesión**: no lo repitas en bucle.
3. Si hay otras advertencias, propón `/arkana-messaging:fix`.
