# arkana-todo

Lista de tareas pendientes de la persona usuaria en un workspace de Arkana. Es **local y sin red**: un único fichero JSON en `.arkana/arkana-todo/todos.json`, con estado, prioridad, vencimiento y componente. Cerrar es reversible y borrar es **lógico** (`removed`: la tarea queda oculta, no se pierde).

Es uno de los plugins del marketplace `arkana` (visión de conjunto en [`../README.md`](../README.md)). Solo usa la biblioteca estándar de Python 3.

## Instalación

```
/plugin marketplace add <ruta a este repo, o owner/repo de GitHub>
/plugin install arkana-todo@arkana
/arkana-todo:install
```

## Skills

| Skill | Qué hace |
|---|---|
| `install` | Crea el almacén si falta (repetible). |
| `check` | Valida de solo lectura: campos, ids únicos, estados, prioridades, fechas, contador; avisa de las vencidas. |
| `fix` | Añade los campos que faltan y recalcula el contador; no toca las tareas. |
| `rename` | No es un skill: cambia el alias de un componente en las tareas (`--from A --to B`); lo invoca `component edit --rename` de `arkana-workspace` por el comando `rename` de su contrato. |
| `add` | Añade una tarea (`--title`, `--priority`, `--due`, `--component`, `--notes`). |
| `list` | Una **tabla por estado** (`identificador \| prioridad \| componente \| descripcion \| estado`), ordenadas por prioridad; por defecto no muestra `done`, `rejected` ni `removed`. Filtra por `--status`, `--component`, `--priority`, `--overdue`. |
| `done` | Cierra una tarea (`done`); `--reopen` la deja en `pending`. |
| `modify` | Cambia campos y el estado (`--status`); `--due none` vacía el vencimiento y `--component *` la pone para todos; `--restore` recupera una borrada. |
| `delete` | Borrado lógico. |

Todas aceptan `--json`; las que escriben aceptan `--dry-run`. Salida `ESTADO|ID|detalle` ([`OUTPUT-CONTRACT`](../docs/OUTPUT-CONTRACT.md)). Uso directo: `python3 scripts/lib/todo.py <comando> [--home DIR]`.

## Modelo de datos

`todos.json` = `{"version": 1, "next": N, "tareas": [...]}`. Cada tarea:

| Campo | Valores |
|---|---|
| `id` | `t-001`, `t-002`… (no se reutilizan ni tras borrar) |
| `titulo` | texto no vacío |
| `estado` | `pending` (por defecto) · `in-progress` · `paused` · `blocked` · `done` · `rejected` · `removed` |
| `prioridad` | `critical` · `high` · `medium` (por defecto) · `low` |
| `vence` | `AAAA-MM-DD` o vacío |
| `componente` | alias del manifiesto, `arkana` o `*` (todos; por defecto). Se valida si hay manifiesto |
| `creada` / `cerrada` | fechas ISO |
| `notas` | texto libre (sin secretos) |

**Valores antiguos.** Las listas creadas antes de este modelo (`open`, `deleted`, `normal`, `all`, componente vacío) se leen como `pending`, `removed`, `medium` y `*` sin tocar el fichero; `check` avisa (`valores-antiguos`) y `fix` los reescribe.

Clase de dato `data` en el contrato: viaja con `export --include-data` de `arkana-workspace` y no se versiona en git (`.arkana/` está en `.gitignore`).

## Pruebas

```bash
bash plugins/arkana-todo/tests/run-tests.sh      # hermético: workspace temporal, sin red ni ~/.claude
bash scripts/vendor-core.sh --check               # el núcleo copiado en scripts/_core está al día
```
