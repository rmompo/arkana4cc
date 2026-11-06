# arkana-todo

Lista de tareas pendientes de la persona usuaria en un workspace de Arkana. Es **local y sin red**: un único fichero JSON en `.arkana/arkana-todo/todos.json`, con prioridad, vencimiento y componente opcionales. Cerrar es reversible y borrar es **lógico** (la tarea queda oculta, no se pierde).

Es uno de los seis plugins del marketplace `arkana` (visión de conjunto en [`../README.md`](../README.md)). Solo usa la biblioteca estándar de Python 3.

## Instalación

```
/plugin marketplace add <ruta o repo de este marketplace>
/plugin install arkana-todo@arkana
/arkana-todo:install
```

## Skills

| Skill | Qué hace |
|---|---|
| `install` | Crea el almacén si falta (repetible). |
| `check` | Valida de solo lectura: campos, ids únicos, estados, prioridades, fechas, contador; avisa de las vencidas. |
| `fix` | Añade los campos que faltan y recalcula el contador; no toca las tareas. |
| `add` | Añade una tarea (`--title`, `--priority`, `--due`, `--component`, `--notes`). |
| `list` | Lista (por defecto las abiertas) por vencimiento y prioridad; filtra por `--state`, `--component`, `--priority`, `--overdue`. |
| `done` | Cierra una tarea; `--reopen` la reabre. |
| `modify` | Cambia campos (`--due none` y `--component none` los vacían); `--restore` recupera una borrada. |
| `delete` | Borrado lógico. |

Todas aceptan `--json`; las que escriben aceptan `--dry-run`. Salida `ESTADO|ID|detalle` ([`OUTPUT-CONTRACT`](../docs/OUTPUT-CONTRACT.md)). Uso directo: `python3 scripts/lib/todo.py <comando> [--home DIR]`.

## Modelo de datos

`todos.json` = `{"version": 1, "next": N, "tareas": [...]}`. Cada tarea:

| Campo | Valores |
|---|---|
| `id` | `t-001`, `t-002`… (no se reutilizan ni tras borrar) |
| `titulo` | texto no vacío |
| `estado` | `open` · `done` · `deleted` |
| `prioridad` | `high` · `normal` (por defecto) · `low` |
| `vence` | `AAAA-MM-DD` o vacío |
| `componente` | alias del manifiesto, `arkana`, `all` o vacío (se valida si hay manifiesto) |
| `creada` / `cerrada` | fechas ISO |
| `notas` | texto libre (sin secretos) |

Clase de dato `data` en el contrato: viaja con `export --include-data` de `arkana-workspace` y no se versiona en git (`.arkana/` está en `.gitignore`).

## Pruebas

```bash
bash plugins/arkana-todo/tests/run-tests.sh      # hermético: workspace temporal, sin red ni ~/.claude
bash scripts/vendor-core.sh --check               # el núcleo copiado en scripts/_core está al día
```
