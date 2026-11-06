---
name: stop
description: Para la orquestación - suave (la tarea en curso termina y el plan queda pausado), pausa y reanudación, o forzosa (mata al worker, cancela la tarea y detiene el plan). Obedece de inmediato.
---

# arkana-agentic:stop

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

Si el usuario pide parar, **hazlo al momento** sin discutir.

| Petición | Comando | Efecto |
|---|---|---|
| Parar sin perder la tarea en curso | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh stop` | La tarea actual termina; después el plan queda `pausado`. |
| Pausar | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh pause` | Igual que el anterior. |
| Reanudar | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh resume` | El plan vuelve a `en_ejecucion`. |
| Parar ya | `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh stop --force` | SIGTERM al grupo del worker y SIGKILL a los 10 s; tarea `cancelada`; plan `detenido`. |

1. Si no queda claro cuál quiere, pregunta (`AskUserQuestion`): *Suave* · *Forzosa* · *Solo pausar*. Si dice «para ya», «mátalo» o similar, es forzosa.
2. Ejecuta el comando y confirma con `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh status`.
3. Tras una parada forzosa, el repo puede tener cambios sin commitear de la tarea cancelada: indícaselo y ofrece `/arkana-agentic:fix` o `integrate keep` o `integrate discard`.
