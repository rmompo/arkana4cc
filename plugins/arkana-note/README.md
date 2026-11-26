# arkana-note

Notas de la persona usuaria en un workspace de Arkana. Son **locales y sin red**: un único fichero JSON en `.arkana/arkana-note/notes.json`, con título, texto opcional y componente (alias, o `*` para todos). Borrar es **lógico** (`removed`: la nota queda oculta, no se pierde). Las notas activas salen en el **BRIEF** al abrir la sesión y en el QUICK START (`/arkana-note:list`).

```bash
claude plugin install arkana-note@arkana
/arkana-note:install            # o /arkana:install, que lo incluye
/arkana-note:add                # título, texto y componente
/arkana-note:list               # tabla de las notas activas
```

## Skills

| Skill | Qué hace |
|---|---|
| `install` | Crea el almacén si falta (repetible). |
| `add` | Añade una nota (`--title`, `--text`, `--component`); antes busca si ya existe una equivalente. |
| `list` | Una **tabla** (`identificador \| componente \| titulo \| texto`) con las modificadas más recientemente primero; `--id` muestra una nota entera; filtra por `--status active\|removed\|all`, `--component` y `--q`. |
| `modify` | Cambia título, texto o componente; `--restore` recupera una borrada. |
| `delete` | Borrado lógico (pide confirmación). |
| `check` | Valida de solo lectura: campos, ids únicos, estados, fechas y contador. |
| `fix` | Añade los campos que faltan y recalcula el contador; no borra notas. |
| `rename` | No es un skill: cambia el alias de un componente en las notas (`--from A --to B`); lo invoca `component edit --rename` de `arkana-workspace` por el comando `rename` de su contrato. |

Todas aceptan `--json`; las que escriben aceptan `--dry-run`. Salida `ESTADO|ID|detalle` ([`OUTPUT-CONTRACT`](../docs/OUTPUT-CONTRACT.md)); `list` imprime la tabla en Markdown (con `--json`, el formato común). Uso directo: `python3 scripts/lib/note.py <comando> [--home DIR]`.

## En el BRIEF

El hook de sesión de `arkana-workspace` lee `notes.json` y añade, justo después de TODOS, **todas** las notas que no están eliminadas (también las ve `/arkana-workspace:brief`):

```
### NOTES
1. [N-004] (API) Rotar el token del CI
2. [N-002] (ARKANA) Hablar con el cliente de los permisos
3. [N-001] (*) Revisar la estructura de arkana-docs
```

Sin recortar, las modificadas más recientemente primero; `[ID]` en mayúsculas y el componente en MAYÚSCULAS (`*` = todos). Si hay notas, el QUICK START añade `/arkana-note:list`.

## Modelo de datos

`notes.json` = `{"version": 1, "next": N, "notas": [...]}`. Cada nota:

| Campo | Valores |
|---|---|
| `id` | `n-001`, `n-002`… (no se reutilizan ni tras borrar) |
| `titulo` | texto no vacío |
| `texto` | texto libre (sin secretos); puede ir vacío |
| `estado` | `active` (por defecto) · `removed` |
| `componente` | alias del manifiesto, `arkana` o `*` (todos; por defecto). Se valida si hay manifiesto; al teclearlo vale también la carpeta o el módulo (se guarda el alias) y se muestra en MAYÚSCULAS |
| `creada` / `modificada` | fechas ISO |

Clase de dato `data` en el contrato: viaja con `export --include-data` de `arkana-workspace` y no se versiona en git (`.arkana/` está en `.gitignore`). No confundir con las **notas de conocimiento** de `arkana-knowledge` (versionadas en git, con UUID y Changelog, para todo el equipo): estas son personales.

## Pruebas

```bash
bash plugins/arkana-note/tests/run-tests.sh      # hermético: workspace temporal, sin red ni ~/.claude
bash scripts/vendor-core.sh --check               # el núcleo copiado en scripts/_core está al día
```
