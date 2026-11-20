---
name: delete
description: Borra una nota de forma lógica (queda con estado removed, se oculta de list y se conserva). Se recupera con modify --restore. Pide confirmación. Acepta --dry-run y --json. Also invoked explicitly as /arkana-note:delete
allowed-tools: [AskUserQuestion]
version: 5
---

# arkana-note:delete

1. Confirma con `AskUserQuestion` qué nota (id y título) se va a borrar.
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" delete --id n-001` (`--dry-run` para ensayar).
3. Recuerda que `/arkana-note:modify --id n-001 --restore` la recupera.
