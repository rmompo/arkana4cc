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
| `add` | Añade una tarea (`--title`, `--priority`, `--due`, `--component`, `--notes`). `--component` admite **varios** componentes separados por comas (`--component m3wa,m3mf`); `*` = todos y no se combina con otros. |
| `list` | Una **tabla por estado** (`identificador \| prioridad \| componente \| descripcion \| estado`), ordenadas por prioridad; por defecto no muestra `done`, `rejected` ni `removed`. Filtra por `--status`, `--component`, `--priority`, `--overdue`. |
| `done` | Cierra una tarea (`done`); `--reopen` la deja en `pending`. |
| `modify` | Cambia campos y el estado (`--status`); `--due none` vacía el vencimiento y `--component m3wa,m3mf` cambia la lista de componentes y `--component *` la pone para todos; `--restore` recupera una borrada. |
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
| `componente` | **lista** de alias del manifiesto (`["m3wa", "m3mf"]`), `["arkana"]` o `["*"]` (todos; por defecto). `*` no se combina con otros. Se valida si hay manifiesto; al teclear cada elemento vale también la carpeta o el módulo (se guarda el alias) y en las tablas se muestra en MAYÚSCULAS (`M3WA, M3MF`). Una tarea sale en `list --component C` si su lista incluye C o es `*` |
| `creada` / `cerrada` | fechas ISO |
| `notas` | texto libre (sin secretos) |

**Varios componentes por tarea.** En disco `componente` es siempre una lista; la migración `0009` de `arkana-evolve` pasa los textos antiguos (`"api"`, `"*"`) a lista, y mientras tanto el plugin lee ambas formas. Una versión antigua de `arkana-todo` no sabe leer una lista: actualiza el plugin antes de dar varios componentes a una tarea (el sello `layout 9` lo avisa). `rename` cambia solo ese alias dentro de la lista.

**Valores antiguos.** Las listas creadas antes de este modelo (`open`, `deleted`, `normal`, `all`, componente vacío) se leen como `pending`, `removed`, `medium` y `*` sin tocar el fichero; `check` avisa (`valores-antiguos`) y `fix` los reescribe.

Clase de dato `data` en el contrato: viaja con `export --include-data` de `arkana-workspace` y no se versiona en git (`.arkana/` está en `.gitignore`).

## Pruebas

```bash
bash plugins/arkana-todo/tests/run-tests.sh      # hermético: workspace temporal, sin red ni ~/.claude
bash scripts/vendor-core.sh --check               # el núcleo copiado en scripts/_core está al día
```
