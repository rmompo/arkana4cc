---
name: status
description: Muestra el estado del plan de orquestación actual - tareas, intentos, gasto y tiempo frente a los límites, worker en marcha y gate abierto - en formato legible. Solo lectura.
---

# arkana-agentic:status

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

1. `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh status` (y `status --plan <id>` para otro plan). Muestra la salida tal cual, es legible.
2. Añade una línea de interpretación: qué falta, si algo espera al usuario (gate) y qué comando o skill corresponde (`/arkana-agentic:control` para un gate, `/arkana-agentic:fix` para una tarea interrumpida, `/arkana-agentic:run` para continuar).
3. Si el usuario pregunta por el gasto total (de todos los planes y todas las sesiones): `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh totals` (solo consulta; la statusline anota el coste de cada sesión).
4. Si el usuario pregunta por una tarea concreta: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh log <T> [--attempt N]`.

Solo lectura: no cambies nada.
