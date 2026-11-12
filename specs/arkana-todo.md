# Especificación del plugin: arkana-todo

> **Estado:** `beta` | **Versión:** `1.1.8`

---

## Descripción general

Lista de tareas pendientes de la persona usuaria en un workspace de Arkana: local, sin red, con prioridad, vencimiento y componente, cierre reversible y borrado lógico (add, list, done, modify, delete)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `add` | 1 | Añade una tarea a la lista de pendientes con prioridad, vencimiento y componente opcionales. Antes busca si ya existe una equivalente. Acepta --dry-run y --json. |
| `check` | 2 | Valida la lista de tareas de solo lectura - campos obligatorios, ids únicos, estados, prioridades, fechas y contador; avisa de las tareas vencidas. Nunca corrige. Acepta --json. |
| `delete` | 3 | Borra una tarea de forma lógica (queda con estado deleted, se oculta de list y se conserva). Se recupera con modify --restore. Pide confirmación. Acepta --dry-run y --json. |
| `done` | 4 | Cierra una tarea de la lista (o la reabre con --reopen). Acepta --dry-run y --json. |
| `fix` | 5 | Repara la lista de tareas - añade los campos que faltan y recalcula el contador de ids. No borra ni reescribe tareas. Acepta --dry-run y --json. |
| `install` | 6 | Primera puesta en marcha - crea la lista de tareas (.arkana/arkana-todo/todos.json) si falta. Repetible. Acepta --dry-run y --json. |
| `list` | 7 | Lista las tareas pendientes (por defecto las abiertas), ordenadas por vencimiento y prioridad; filtra por estado, componente, prioridad o vencidas. Solo lectura. Acepta --json. |
| `modify` | 8 | Cambia el título, la prioridad, el vencimiento (o none), el componente (o none) o las notas de una tarea, o restaura una borrada con --restore. Acepta --dry-run y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.8 | modify: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.7 | list: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.6 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.5 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.4 | done: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.3 | delete: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.2 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.1 | add: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
