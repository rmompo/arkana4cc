---
name: query
description: Consulta de SOLO LECTURA de los mensajes del componente actual (todos si eres ARKANA): muestra únicamente id, remitente, asunto y destinatarios. No los marca como leídos, ni como hechos, ni cambia ningún estado. Con --unread lista lo que el hook cuenta como sin leer; con --detail añade también el texto del mensaje (sin marcarlo). Local, sin red. Acepta --json.
---

# arkana-messaging:query

Herramienta: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" query [filtros]`. Lee del almacén local; **no escribe nada**: ni marca como leído, ni cierra (`done`), ni cambia estados, ni deja huella en el almacén. Solo muestra.

Es la forma de **ver qué hay** sin consumirlo. `get --detail <id>` es la que **marca como leído** (por eso el hook deja de avisar de ese mensaje); `query` nunca lo hace, ni siquiera con `--detail`.

El que ve es el componente que contiene el directorio actual (lo dirigido a él o escrito por él); ARKANA ve todo. Los mensajes `deleted` y `reconciled` no salen salvo `--state <estado>` o `--include-hidden`.

## Qué muestra

| Sin `--detail` | Con `--detail` |
|---|---|
| `ID`, `DE` (remitente), `PARA` (destinatarios, como se escribió: `all` se queda en `all`) y `ASUNTO` | lo mismo y, debajo de cada uno, **el mensaje**: cuerpo, instrucciones y criterios (sin metadatos ni historial) |

## Opciones

| Opción | Efecto |
|---|---|
| `--unread` | Solo lo **sin leer** para ti: los mismos que cuenta la línea `[ARKANA messaging] … sin leer` del hook (de otros, dirigidos a ti, no leídos, no propuestos) |
| `--pending` | Solo `task`/`review`/`question` de una vez, abiertas, dirigidas a ti y que no has confirmado |
| `--detail [id]` | Añade el texto del mensaje (sigue sin marcarlo como leído). Solo: a todo lo listado; con id (`--detail <id>`, como en `get`): ese mensaje con su texto |
| `--id`, `--type`, `--state` | Filtros exactos |
| `--to <alias>`, `--from <alias>`, `--user <u>`, `--since AAAA-MM-DD`, `--n <N>` | Filtros y límite (20 por defecto) |
| `--repeat` | Solo directrices permanentes (`repeat`) |
| `--json` | Array de `{id, de, asunto, para}` (con `--detail`, más `cuerpo`, `instrucciones` y `criterios` si los hay) |

## Pasos

1. Ejecuta con los filtros pedidos y presenta la tabla tal cual. **Al final de la salida en texto** (no en `--json`) la herramienta añade un aviso: es de solo lectura y, para consumir los mensajes, hay que usar `get --detail <id>`. Déjalo a la vista.
2. Para **leer** uno y que deje de contar como sin leer: `/arkana-messaging:get --detail <id>`. Para atenderlo: `/arkana-messaging:put --done <id> --result "..."`. **Ninguna de las dos acciones la hace `query`.**
