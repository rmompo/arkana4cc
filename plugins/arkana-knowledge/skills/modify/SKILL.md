---
name: modify
description: Modifica una nota existente (por UUID o slug) - sube la versión, añade una línea al Changelog de la propia nota (nunca lo pisa); también restaura una nota borrada con --restore. Acepta --dry-run y --json. Also invoked explicitly as /arkana-knowledge:modify
allowed-tools: []
version: 16
---

# arkana-knowledge:modify

1. **Localiza** la nota con `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --q "<palabras>"` y lee la candidata (`query --id <uuid|slug>`).
2. **Aplica el cambio:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" modify --id <uuid|slug> [--body-file F] [--title X] [--summary R] [--components ..] [--tags ..] [--sources ..] [--major] --change "<qué cambió>"` (`--dry-run` para ensayar). `--major` sube la versión mayor (N+1.0); si no, la menor (N.M+1). `--restore` recupera una nota borrada.
3. **Valida:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate`. Resume la versión nueva y recuerda que queda sin commitear.

El Changelog de la nota recibe una línea por versión; nunca se reescribe el historial.
