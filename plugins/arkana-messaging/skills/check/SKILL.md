---
name: check
description: Diagnóstico de solo lectura de la mensajería - almacén, plugin habilitado, latido de los hooks en ESTA sesión y semilla del componente actual (--all para todos). Nunca corrige; propone install o fix. Acepta --json.
---

# arkana-messaging:check

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" check [--component <alias>|--all] [--json]
```

Salida `ESTADO|ID|detalle` y `RESUMEN`. Comprueba: `almacen`, `plugin` (habilitado en `~/.claude/settings.json`), `latido` (los hooks han corrido en esta sesión, por `CLAUDE_CODE_SESSION_ID`; respaldo: latido del componente en los últimos 15 min) y `semilla-<alias>`.

## Pasos

1. Ejecútalo (es lo que pide la semilla en el **primer turno** de cada sesión) y resume en una línea si todo está `OK`.
2. Si el `latido` es `WARN` (los hooks no corren), propón al usuario `/arkana-messaging:install` y recargar los plugins. **Una sola vez por sesión**: no lo repitas en bucle.
3. Si hay otras advertencias, propón `/arkana-messaging:fix`.
