---
name: add
description: Añade una nota de conocimiento común (decisión, lección, pendiente, contrato o referencia) en arkana-knowledge/<topic>/ con frontmatter versionado, sección Changelog y entrada en el catálogo. Antes busca para no duplicar. Acepta --dry-run y --json.
---

# arkana-knowledge:add

Guarda conocimiento común en `arkana-knowledge/<topic>/<slug>.md` y lo registra en `arkana-knowledge/catalog.json`. Es **versionado en git** (el equipo lo comparte): tú no haces commit ni push.

## Pasos

1. **Reúne los datos** con `AskUserQuestion` si no los dio el usuario: **topic** (`decision` · `lesson` · `pending` · `contract` · `reference`), **título** y **resumen** (una frase), **componentes** a los que afecta (alias del manifiesto, `arkana` o `all`; por defecto `all`), **etiquetas** y **contenido** (Markdown; redáctalo tú a partir de lo hablado, sin inventar; **sin secretos**: ni credenciales, ni tokens, ni `.env`).
2. **¿Existe ya?** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --q "<título y palabras clave>" --limit 5`. Si hay una nota equivalente, **modifícala** (`/arkana-knowledge:modify`) y dilo.
3. **Crea:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" add --topic <topic> --title "<título>" --summary "<resumen>" --components app,api --tags a,b --body-file <fichero>` (`--dry-run` para ensayar).
4. **Valida:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate` debe terminar sin `FAIL`.
5. **Resume:** id, versión, ruta y componentes; recuerda que queda sin commitear.

## Reglas

- Una nota = un tema; el `id` sale de `topic-título`. No guardes copias de lo que es de otro componente: enlaza a su ruta. Idempotente: no dupliques.
