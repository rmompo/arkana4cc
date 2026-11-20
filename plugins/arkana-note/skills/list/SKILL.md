---
name: list
description: Consulta las notas en una tabla (identificador, componente, titulo, texto), las modificadas más recientemente primero; con --id muestra una nota entera; filtra por componente, texto o estado (active, removed, all). Solo lectura. Acepta --json. Also invoked explicitly as /arkana-note:list
allowed-tools: []
version: 3
---

# arkana-note:list

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/note.py" list [--status active|removed|all] [--component C] [--q TEXTO] [--id n-001] [--json]
```

Sin opciones salen las notas activas. La salida ya es una **tabla Markdown**: pégala tal cual, sin reformatear. Con `--id` muestra la nota completa (también si está borrada). `--component C` incluye las notas de `*` (todos). Con `--json` devuelve el formato común (una línea `INFO` por nota).
