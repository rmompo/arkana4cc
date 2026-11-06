---
name: costs
description: Consulta los costes del libro de planes y sesiones - gasto de los workers por plan y tarea y coste real de las sesiones de Claude (el que anota la statusline) - con filtros por plan, sesión, componente y fecha y agrupación por plan, sesión, componente o día. Solo lectura. Acepta --json.
---

# arkana-agentic:costs

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh costs [--plan <id>] [--session <id>] [--component <alias>] [--since AAAA-MM-DD] [--by plan|session|component|day] [--json]
```

Lee el libro (`.arkana/arkana-agentic/data/ledger/`, solo metadatos) y los planes en curso y archivados. Dos orígenes, que no se mezclan:

- **workers** (`plan-task`): lo que costaron los `claude -p` de cada tarea e intento (sale de los informes del worker).
- **sesiones**: el **coste real** de cada sesión de Claude, que escribe la statusline (única escritora); los hooks de `SessionStart`/`SessionEnd` lo leen y anotan duración, componente, plan y tokens (del transcript). **Sin ese dato el coste queda vacío: nunca se estima**, y se indica «N sesiones sin coste».

## Pasos

1. Ejecuta con los filtros pedidos y presenta el total (workers + sesiones) y, con `--by`, la tabla agrupada.
2. Si hay sesiones sin coste, explica por qué (la statusline no estaba activa o no anotó) en una línea.
3. `costs --purge [--dry-run]` aplica la **retención** (`ledger_retention_days`, 90 por defecto: se conservan los totales y se purga el detalle por tarea, intento y tipo de token). Pide confirmación antes de purgar de verdad.
