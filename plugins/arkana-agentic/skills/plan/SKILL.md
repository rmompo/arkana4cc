---
name: plan
description: Redacta un plan de orquestación multi-repo a partir de lo que pide el usuario (tareas pequeñas, un repo cada una, con criterios verificables), lo valida y lo somete a su aprobación. Solo desde arkana. No ejecuta nada hasta que el usuario aprueba.
---

# arkana-agentic:plan

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

Reglas completas: el bloque `arkana:agentic` del `CLAUDE.md` de ARKANA (sección «Cómo se redacta un plan»; plantilla en `templates/orquestador.md`). Este skill solo se usa en `arkana`.

## Pasos

1. `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh check`. Si hay un `FAIL`, díselo al usuario y no sigas.
2. Entiende la petición. Si es ambigua, pregunta (`AskUserQuestion`) antes de planificar. **Lee tú** el código de los repos que haga falta (solo lectura) para repartir bien el trabajo y para copiar extractos de otros repos en las tareas.
3. Escribe el borrador en el directorio **scratchpad** de la sesión (`<scratchpad>/<tema>.json`) con el formato del orquestador; `plan new` lo copia al estado, así que no hace falta conservarlo.
4. `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh plan new <borrador>`. Corrige hasta que no haya `FAIL`; cuéntale al usuario los `WARN`.
5. `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh plan show` y preséntale un resumen claro: tareas, repo, orden, criterios, verificaciones, límites y qué autoriza el plan (commits locales en la rama `arkana-worker/<plan>` de cada repo). Si `plan show` lista **mensajes que recibirá el worker** (directrices `repeat` y peticiones `once` de otros componentes), enséñaselos en el resumen: aprobar el plan es también confirmar que se les entregan. Lo que llegue después de `plan start` no se entrega a este plan. Para un mensaje concreto (p. ej. un aviso), `plan new <fichero> --from-message <id>` lo asigna a las tareas de sus destinatarios y `plan new --from-message <id> --paths '<glob>'` (sin fichero; `--paths` es obligatorio y, si el mensaje va a varios componentes, `--repo` una vez por componente) genera el plan a partir del mensaje; léelo antes con `/arkana-messaging:query --detail` y enséñaselo al usuario.
6. Pregunta con `AskUserQuestion`: *Aprobar y ejecutar* · *Aprobar sin ejecutar* · *Cambiar algo* · *Descartar*.
   - *Aprobar y ejecutar*: `plan approve`, `plan start` y **sin parar** invoca la herramienta `Skill` con `arkana-agentic:run` para ejecutarlo (el usuario ya ha dicho que quiere ejecutarlo; no le hagas lanzar otro comando).
   - *Aprobar sin ejecutar*: `plan approve` y dile que `/arkana-agentic:run` lo ejecutará cuando quiera.
   - Cambiar: vuelve al paso 3 con un plan nuevo.
   - Descartar: `act stop` si ya se creó.

## Reglas

- No apruebes por el usuario ni ejecutes sin su respuesta.
- Pon `autoriza.commits_locales: true` (commit local en la rama del plan `arkana-worker/<plan>`; «sin push» no es «sin commit»), no pidas al worker que ejecute comandos y no enlaces un criterio a `git diff --stat`: detalle en `ORQUESTADOR.md`.
- No crees planes de más de 12 tareas: divídelo en fases.
- Si la tarea exige tocar rutas protegidas (`package.json`, lockfiles, configuración de build, `.husky`…), avísalo antes de crear el plan.
