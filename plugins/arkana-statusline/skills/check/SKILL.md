---
name: check
description: Diagnóstico de solo lectura de la statusline - python3 y git, copia instalada al día, `statusLine` de usuario del despachador, proveedores, elección por componente, otros plugins de statusline y prueba de humo. Nunca corrige. Acepta --home y --json. Also invoked explicitly as /arkana-statusline:check
allowed-tools: []
version: 7
---

# arkana-statusline:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" check [--home DIR] [--json]
```

Ids: `python3`, `git`, `instalada`, `copia`, `statusline`, `proveedores`, `elecciones`, `otros-plugins`, `humo`. `proveedores` lista las otras statuslines registradas y `elecciones` lo elegido para cada componente del workspace. Presenta el resultado en una línea si todo está `OK`; si hay `WARN`, propón `/arkana-statusline:fix` (copia desactualizada) o `/arkana-statusline:install` (no instalada) y, si la `statusLine` de usuario es de otro (p. ej. plugin4cc la volvió a escribir), `/arkana-statusline:fix` o `install`.
