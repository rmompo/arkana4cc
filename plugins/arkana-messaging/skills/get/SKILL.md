---
name: get
description: Lista o muestra los mensajes dirigidos al componente actual (o todos, si eres ARKANA), con filtros por tipo, estado, destinatario, remitente, usuario y fecha; --pending para lo que hay que atender. Solo lectura, local, sin red. Acepta --json.
---

# arkana-messaging:get

Herramienta: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" get [filtros]`. Lee del almacén local; no usa git ni red y no modifica nada.

El que ve es el componente que contiene el directorio actual: ve lo dirigido a él o escrito por él; ARKANA ve todo. Los mensajes `deleted` y `reconciled` no se muestran salvo `--state <estado>` o `--include-hidden`.

| Opción | Efecto |
|---|---|
| `--pending` | Solo `task`/`review`/`question` de una vez, abiertas, **dirigidas a ti** y que no has confirmado (las directrices `repeat` no son pendientes) |
| `--repeat` | Solo las directrices permanentes (`repeat`; `propuesto` o `vigente`) |
| `--id`, `--type`, `--state` | Filtros exactos (`open`, `done`, `discarded`, `deleted`, `reconciled`) |
| `--to <alias>`, `--from <alias>`, `--user <u>`, `--since AAAA-MM-DD`, `--n <N>` | Filtros y límite (20 por defecto) |
| `--detail <id>` | Detalle completo (cuerpo, instrucciones, criterios, historial) |
| `--json` | Array de mensajes (para scripts y hooks) |

## Pasos

1. Ejecuta con los filtros pedidos y presenta la tabla tal cual. Resalta lo de prioridad `ALTA` y lo abierto.
2. **Al abrir una sesión en un componente**: `get --pending`; si hay algo, **propón** al usuario atenderlo (nunca lo des por hecho). Para ver el detalle: `get --detail <id>`.
3. Al terminar una tarea o pregunta, propón cerrarla con `/arkana-messaging:put --done <id> --result "..."`.
