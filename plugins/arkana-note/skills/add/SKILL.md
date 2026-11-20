---
name: add
description: Añade una nota para la persona usuaria con título, texto y componente opcionales (alias, carpeta o módulo; * = todos). Acepta --dry-run y --json. Also invoked explicitly as /arkana-note:add
allowed-tools: [AskUserQuestion]
version: 2
---

# arkana-note:add

## Pasos

1. Reúne con `AskUserQuestion` lo que no dio el usuario: **título** (obligatorio), **texto** (opcional) y **componente** (alias, carpeta o módulo del componente, `arkana` o `*` para todos; por defecto `*`). Sin secretos.
2. Comprueba duplicados: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" list --q "<palabra del título>" --status all`. Si hay una equivalente, usa `/arkana-note:modify` y dilo.
3. Crea: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" add --title "<título>" --text "..." --component api` (`--dry-run` para ensayar).
4. Resume: id, título y componente.
