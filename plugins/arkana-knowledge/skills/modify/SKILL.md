---
name: modify
description: Modifica una nota existente - sube la versión, añade una línea al Changelog de la propia nota (nunca lo pisa) y actualiza el catálogo; también restaura una nota borrada con --restore. Acepta --dry-run y --json.
---

# arkana-knowledge:modify

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" modify --id <id> [--body-file f | --body "texto"] [--title ..] [--summary ..] [--components ..] [--tags ..] [--author ..] [--major] [--change "qué cambia"] [--restore] [--dry-run]
```

Sube la versión (`1.0` → `1.1`; `--major` → `2.0`), reescribe el cuerpo si se da y **añade al `## Changelog`** de la nota una línea `- vX.Y · fecha · autor — <--change>`. El historial ya no se guarda en ficheros aparte: vive en la nota (y en git).

## Pasos

1. Localiza la nota (`query`), léela y redacta el cambio sin inventar ni incluir secretos. Pasa **el cuerpo completo** nuevo (sin el Changelog: la herramienta lo conserva).
2. Ensaya con `--dry-run` si hay duda; ejecuta con un `--change` claro (una frase).
3. `validate` debe seguir sin `FAIL`. Queda sin commitear.
4. Una nota **borrada** no se modifica: se recupera antes con `--restore` (pregunta al usuario).
