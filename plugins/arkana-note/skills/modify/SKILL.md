---
name: modify
description: Cambia el título, el texto o el componente de una nota (* = todos), o restaura una borrada con --restore. Acepta --dry-run y --json. Also invoked explicitly as /arkana-note:modify
allowed-tools: []
version: 4
---

# arkana-note:modify

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" modify --id n-001 [--title X] [--text T] [--component C|*] [--restore] [--dry-run]
```

Solo cambia los campos indicados y anota la fecha de modificación. Si no sabes el id, búscalo antes con `/arkana-note:list --status all`. Una nota borrada solo se toca con `--restore`.
