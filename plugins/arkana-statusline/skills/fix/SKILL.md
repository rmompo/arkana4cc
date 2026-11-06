---
name: fix
description: Reinstala la copia de la statusline si está desactualizada y activa `statusLine` si no hay ninguna. Nunca sustituye la de otro (eso es install --replace). Con copia .bak. Acepta --dry-run y --json.
---

# arkana-statusline:fix

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" fix [--dry-run] [--json]
```

1. `check`; si hay `WARN` de `copia` o `statusline` (sin ninguna activa), `fix --dry-run` y, con confirmación (`AskUserQuestion`), `fix`.
2. Si hay otra `statusLine` ajena, `fix` la deja como está y avisa; sustituirla es decisión del usuario (`install --replace`).
