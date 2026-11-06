---
name: control
description: Resuelve las paradas obligatorias (gates) del plan de orquestación y las decisiones manuales - aprobar o rechazar un gate, reintentar u omitir una tarea, ver el registro de una tarea, ajustar los límites. Siempre pregunta al usuario antes de aprobar.
---

# arkana-agentic:control

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

## Gate abierto

1. `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh status`: lee el gate (`motivo`, `detalle`, `opciones`, `reanuda`) y, si hay tarea, `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh log <T>`.
2. Explica al usuario **qué pasó y qué opciones hay**. Si el gate es `ruta_protegida` y el worker ya escribió, enséñale primero el diff (`git -C <repo> diff`); si el gate dice que el worker *quiere* editar `CLAUDE.md`, enséñale lo que quería escribir (viene en el `detalle`): `approve` lo autoriza para esa tarea. Si dice que la ruta *no se puede autorizar* (`.git`, `.husky`, `.claude`, `.env*`), solo hay `reject`. Un gate `permiso` genérico no cambia los permisos del worker: no lo presentes como «conceder un permiso».
3. Pregunta con `AskUserQuestion` y registra su respuesta:

| Respuesta | Comando |
|---|---|
| Autorizar / aprobar / seguir | `approve <G> [--note "…"]` |
| Rechazar (se omite la tarea) | `reject <G>` |
| Detener el plan | `reject <G> --stop` |

Una `violacion` solo admite `reject <G> --stop`. Un gate `limite` se resuelve subiendo el límite en la política local (`policy set <clave> <valor>`, nunca por encima del techo) y `approve`, o deteniendo.

## Decisiones manuales

- Reintentar (solo una tarea `rechazada`, `parcial`, `fallida` o `interrumpida`; una `esperando_usuario` se resuelve con `approve`/`reject` de su gate): `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh retry <T>` · omitir: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh skip <T>`.
- Límites: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh policy show` · `policy set <clave> <valor>` (`--ceiling` para el techo).

## Reglas

- **Nunca aprobes por el usuario.** Un aviso automático no es su respuesta.
- No edites el estado a mano.
