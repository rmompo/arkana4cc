---
name: check
description: Diagnóstico de solo lectura de la statusline - python3 y git, copia instalada al día, `statusLine` activa y nuestra, otros plugins de statusline que podrían pisarla y prueba de humo. Nunca corrige. Acepta --json.
---

# arkana-statusline:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" check [--json]
```

Ids: `python3`, `git`, `instalada`, `copia`, `statusline`, `otros-plugins`, `humo`. Presenta el resultado en una línea si todo está `OK`; si hay `WARN`, propón `/arkana-statusline:fix` (copia desactualizada) o `/arkana-statusline:install` (no instalada) y, si hay otra `statusLine`, `install --replace` con confirmación.
