---
name: install
description: Primera puesta en marcha - crea el almacén de notas (.arkana/arkana-note/notes.json) si falta. Repetible. Acepta --dry-run y --json. Also invoked explicitly as /arkana-note:install
allowed-tools: []
version: 1
---

# arkana-note:install

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" install [--dry-run] [--json]
```

Crea el almacén vacío. No toca nada más; si ya existe lo dice y termina.
