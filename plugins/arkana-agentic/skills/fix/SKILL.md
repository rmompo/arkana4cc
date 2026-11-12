---
name: fix
description: Corrige la orquestación - limpia un worker.json obsoleto y recupera tras una caída las tareas interrumpidas preguntando al usuario si reintentar (descartando lo hecho a medias) o descartar. Nunca reintenta por su cuenta. Acepta --dry-run. Also invoked explicitly as /arkana-agentic:fix
allowed-tools: [AskUserQuestion]
version: 15
---

# arkana-agentic:fix

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

1. `agentic.sh check` y `agentic.sh status`.
2. `agentic.sh fix` detecta las tareas `en_curso` sin worker vivo y las marca `interrumpida`, e indica el estado del repo (rama y si tiene cambios sin commitear).
3. Explica al usuario lo ocurrido y qué hay a medias. Pregunta (`AskUserQuestion`): *Reintentar la tarea* (descarta lo hecho a medias) · *Descartar la tarea* · *Detener el plan*.
4. Ejecuta: `agentic.sh fix --task <T> --action retry|discard`, o `agentic.sh act stop`.
5. Para seguir: `/arkana-agentic:run`.

## Reglas

- Nunca reintentes por tu cuenta tras una caída.
- Si hay un worker vivo que no reconoces, **no lo mates** sin que el usuario lo pida (`stop --force`).
