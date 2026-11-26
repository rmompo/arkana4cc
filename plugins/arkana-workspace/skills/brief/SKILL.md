---
name: brief
description: Muestra el BRIEF de Arkana a demanda - QUICK START con los comandos útiles, mensajes sin leer, todas las tareas activas, todas las notas, componentes con cambios sin subir y el plan activo. Es el mismo que se ve al abrir, reanudar o compactar una sesión, pero siempre sale, aunque no haya nada pendiente. Solo lectura. Acepta --home. Also invoked explicitly as /arkana-workspace:brief
allowed-tools: []
version: 42
---

# arkana-workspace:brief

Enseña el BRIEF del workspace cuando la persona usuaria lo pide, sin esperar a abrir o reanudar una sesión.

```bash
python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/hooks.py" brief [--home DIR]
```

El workspace se localiza solo (`$ARKANA_HOME`, el directorio actual o el registro de usuario); `--home` lo fuerza. Sin workspace sale con código 3 y `FAIL|workspace|…`.

## Qué trae

Una cabecera en caja y estas secciones, cada una solo si tiene contenido (QUICK START siempre):

| Sección | Contenido |
|---|---|
| `QUICK START` | Los comandos útiles según lo pendiente, en dos columnas (`/comando  - para qué sirve`) |
| `MESSAGING` | Por componente: tareas, directrices `repeat` y avisos sin leer |
| `TODOS` | **Todas** las tareas activas (`pending`, `in-progress`, `paused`, `blocked`): `N. [T-014] (prioridad, componentes[, estado][, vencimiento]) título`, por prioridad |
| `NOTES` | **Todas** las notas que no están eliminadas: `N. [N-001] (componente) título`, las modificadas más recientemente primero |
| `GIT (pending)` | Componentes con cambios sin commitear o commits sin subir |
| `ORCHESTRATION` | Plan activo de `arkana-agentic`, con su coste |

Si la instalación va por detrás o por delante del repo, delante del BRIEF sale el aviso de layout (`/arkana-evolve:apply` o actualizar el plugin).

## Pasos

1. Ejecuta el comando y **pega la salida tal cual**, sin reformatear ni resumir: es texto ya preparado (empieza por una línea en blanco intencionada).
2. Si la persona usuaria pregunta por algo concreto del BRIEF, remítela al skill que lo gestiona: `/arkana-todo:list`, `/arkana-note:list`, `/arkana-messaging:query --unread`, `/arkana-workspace:status`.

## Reglas

- Solo lectura: no escribe nada ni modifica tareas, notas ni mensajes.
- No lo vuelvas a ejecutar para «refrescar» en la misma respuesta.
