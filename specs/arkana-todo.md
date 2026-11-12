# Especificación del plugin: arkana-todo

> **Estado:** `beta` | **Versión:** `1.1.0`

---

## Descripción general

Lista de tareas pendientes de la persona usuaria en un workspace de Arkana: local, sin red, con prioridad, vencimiento y componente, cierre reversible y borrado lógico (add, list, done, modify, delete)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `add` | 0 | Añade una tarea a la lista de pendientes con prioridad, vencimiento y componente opcionales. Antes busca si ya existe una equivalente. Acepta --dry-run y --json. |
| `check` | 0 | Valida la lista de tareas de solo lectura - campos obligatorios, ids únicos, estados, prioridades, fechas y contador; avisa de las tareas vencidas. Nunca corrige. Acepta --json. |
| `delete` | 0 | Borra una tarea de forma lógica (queda con estado deleted, se oculta de list y se conserva). Se recupera con modify --restore. Pide confirmación. Acepta --dry-run y --json. |
| `done` | 0 | Cierra una tarea de la lista (o la reabre con --reopen). Acepta --dry-run y --json. |
| `fix` | 0 | Repara la lista de tareas - añade los campos que faltan y recalcula el contador de ids. No borra ni reescribe tareas. Acepta --dry-run y --json. |
| `install` | 0 | Primera puesta en marcha - crea la lista de tareas (.arkana/arkana-todo/todos.json) si falta. Repetible. Acepta --dry-run y --json. |
| `list` | 0 | Lista las tareas pendientes (por defecto las abiertas), ordenadas por vencimiento y prioridad; filtra por estado, componente, prioridad o vencidas. Solo lectura. Acepta --json. |
| `modify` | 0 | Cambia el título, la prioridad, el vencimiento (o none), el componente (o none) o las notas de una tarea, o restaura una borrada con --restore. Acepta --dry-run y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
