---
name: delete
description: Borra un mensaje de forma lógica (queda la marca `deleted`, se ignora y viaja en sync y en export). Solo ARKANA o el componente que lo escribió. Pide confirmación. Acepta --dry-run y --json.
---

# arkana-messaging:delete

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" delete <id> [--dry-run] [--json]
```

El borrado es **lógico**: el fichero se conserva con `estado: deleted` (y `estado_previo`), de modo que el borrado se propaga al importar un ZIP (la marca de borrado gana siempre). Es idempotente.

## Pasos

1. Muestra el mensaje (`query --detail <id>`, que no lo marca como leído; `get --detail <id>` sí) y pide confirmación con `AskUserQuestion` («Borrar» / «Cancelar»).
2. Ejecuta `delete <id>`. Un componente solo borra lo que escribió él; ARKANA borra cualquiera.
3. No hay «deshacer»: si se borró por error, hay que crear otro mensaje.
