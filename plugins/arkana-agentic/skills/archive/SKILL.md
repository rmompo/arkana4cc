---
name: archive
description: Archiva un plan de orquestación terminado en .arkana/arkana-agentic/data/archive/ (plan, tareas, informes, verificaciones y registro, sin logs ni instantáneas) y, con confirmación, integra, deja o descarta la rama del plan en cada repo.
---

# arkana-agentic:archive

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

1. `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh status`: el plan debe estar `completado`, `detenido` o `fallido`.
2. **Ramas** (si el plan las creó): `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh integrate review` (por repo: commits por tarea, `diff --stat` y avisos). Pregunta **por repo** (`AskUserQuestion`): *Integrar en la rama original (merge local, sin push)* · *Dejar la rama para revisar* · *Descartar la rama*. Con un plan `detenido` o `fallido`, no ofrezcas integrar. Ejecuta `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh integrate merge --repo <r>` (o `keep` / `discard`; `--up-to <Tnnn>` solo con `merge`); no hace push.
3. Pregunta si archivar el plan (queda en local, en `.arkana/arkana-agentic/data/archive/`); si sí, `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh archive`.
4. El archivo es **local** (`data/archive/<plan>/`, no se versiona ni se commitea; viaja solo con `arkana-workspace:export --include-data`).
