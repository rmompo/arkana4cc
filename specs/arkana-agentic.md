# Especificación del plugin: arkana-agentic

> **Estado:** `beta` | **Versión:** `0.10.10`

---

## Descripción general

Orquestación multi-repo desde ARKANA: plan, un worker a la vez sin shell, verificación por scripts, límites y control (estado, parada, recuperación).

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `archive` | 1 | Archiva un plan de orquestación terminado en .arkana/arkana-agentic/data/archive/ (plan, tareas, informes, verificaciones y registro, sin logs ni instantáneas) y, con confirmación, integra, deja o descarta la rama del plan en cada repo. |
| `check` | 2 | Comprueba la salud de la orquestación de arkana-agentic - versión y flags de claude, utilidades, directorio de ejecución (700), política válida, workers huérfanos, reglas de permisos de arkana y reglas del orquestador (hook). Solo lectura y sin coste (con --deep ejecuta además la batería de contención con claude real, ~0,3-0,6 USD). |
| `control` | 3 | Resuelve las paradas obligatorias (gates) del plan de orquestación y las decisiones manuales - aprobar o rechazar un gate, reintentar u omitir una tarea, ver el registro de una tarea, ajustar los límites. Siempre pregunta al usuario antes de aprobar. |
| `costs` | 4 | Consulta los costes del libro de planes y sesiones - gasto de los workers por plan y tarea y coste real de las sesiones de Claude (el que anota la statusline) - con filtros por plan, sesión, componente y fecha y agrupación por plan, sesión, componente o día. Solo lectura. Acepta --json. |
| `fix` | 5 | Corrige la orquestación - limpia un worker.json obsoleto y recupera tras una caída las tareas interrumpidas preguntando al usuario si reintentar (descartando lo hecho a medias) o descartar. Nunca reintenta por su cuenta. Acepta --dry-run. |
| `install` | 6 | Primera puesta en marcha (repetible) de la orquestación - carpetas config/state/data y plugin habilitado en ~/.claude/settings.json. No escribe nada en los repos (las reglas del orquestador las inyecta un hook). Copia .bak de lo que modifica. Acepta --dry-run. |
| `plan` | 7 | Redacta un plan de orquestación multi-repo a partir de lo que pide el usuario (tareas pequeñas, un repo cada una, con criterios verificables), lo valida y lo somete a su aprobación. Solo desde arkana. No ejecuta nada hasta que el usuario aprueba. |
| `run` | 8 | Ejecuta el plan de orquestación actual, una tarea cada vez - lanza el worker en segundo plano, verifica su resultado con scripts, decide la acción siguiente y se detiene en las paradas obligatorias (gates). Solo desde arkana. |
| `status` | 9 | Muestra el estado del plan de orquestación actual - tareas, intentos, gasto y tiempo frente a los límites, worker en marcha y gate abierto - en formato legible. Solo lectura. |
| `stop` | 10 | Para la orquestación - suave (la tarea en curso termina y el plan queda pausado), pausa y reanudación, o forzosa (mata al worker, cancela la tarea y detiene el plan). Obedece de inmediato. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 0.10.10 | stop: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.9 | status: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.8 | run: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.7 | plan: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.6 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.5 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.4 | costs: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.3 | control: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.2 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.1 | archive: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.10.0 | Bootstrap: plugin registrado en catalog.json |
