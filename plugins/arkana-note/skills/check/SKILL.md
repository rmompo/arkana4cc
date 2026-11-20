---
name: check
description: Valida las notas de solo lectura - campos obligatorios, ids únicos, estados, fechas y contador. Nunca corrige. Acepta --json. Also invoked explicitly as /arkana-note:check
allowed-tools: []
version: 6
---

# arkana-note:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" validate [--json]
```

Un `FAIL` por problema de nota y `WARN` si falta el almacén. Si todo está `OK`, resume en una línea; si no, propón `/arkana-note:fix` (contador y campos que faltan) o `/arkana-note:modify`.
