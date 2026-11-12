---
name: add
description: Añade una nota de conocimiento común (decisión, lección, pendiente, contrato, referencia o metodología) en arkana-knowledge/<topic>/ con id UUID, frontmatter versionado, procedencia (fuentes) y Changelog. Antes busca para no duplicar. Acepta --dry-run y --json.
---

# arkana-knowledge:add

Guarda conocimiento común en `arkana-knowledge/<topic>/<slug>.md`. Es **versionado en git** (el equipo lo comparte): tú no haces commit ni push. La identidad de la nota es su **UUID**; al usuario se le habla por el título y el slug.

## Pasos

1. **Reúne los datos** con `AskUserQuestion` si no los dio el usuario: **topic** (`decision` · `lesson` · `pending` · `contract` · `reference` · `methodology`), **título**, **resumen** (una frase), **componentes** (alias, `arkana` o `all`; por defecto `all`), **etiquetas**, **fuentes** (documentos ingeridos de los que sale la nota, si los hay) y **contenido** (Markdown redactado por ti a partir de lo hablado, sin inventar; no copies credenciales ni valores de `.env`).
2. **¿Existe ya?** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --q "<título y palabras clave>" --limit 5`. Si hay una equivalente, **modifícala** (`/arkana-knowledge:modify`).
3. **Crea:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" add --topic <topic> --title "<título>" --summary "<resumen>" --components app,api --tags a,b [--sources <uuid-doc>] --body-file <fichero>` (`--dry-run` para ensayar).
4. **Valida:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate` sin `FAIL`.
5. **Resume:** UUID, versión, ruta y componentes; recuerda que queda sin commitear.

## Reglas

- Una nota = un tema. `add` falla si ya existe `<topic>/<slug>` (aunque esté borrada): usa `modify` (con `--restore` si está borrada).
- `--components` y `--sources` se guardan por id: renombrar un componente no obliga a tocar la nota.
