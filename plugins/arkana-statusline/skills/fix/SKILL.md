---
name: fix
description: Reinstala la copia del despachador de la statusline si está desactualizada, activa `statusLine` si no hay ninguna y, si otra herramienta la pisó tras instalar Arkana, la recupera dejando a la otra como proveedor. Sin instalación previa no sustituye la de otro (eso es install). Con copia .bak. Acepta --dry-run y --json. Also invoked explicitly as /arkana-statusline:fix
allowed-tools: [AskUserQuestion]
version: 8
---

# arkana-statusline:fix

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" fix [--dry-run] [--json]
```

1. `check`; si hay `WARN` de `copia` o `statusline` (sin ninguna activa), `fix --dry-run` y, con confirmación (`AskUserQuestion`), `fix`.
2. Si hay otra `statusLine` ajena y **ya había una instalación de Arkana**, `fix` recupera el hueco como los hooks: la ajena pasa a ser un proveedor y se recoloca el despachador (con copia en `bak/`). Si no había instalación previa, la deja como está y avisa; sustituirla es decisión del usuario (`install --replace`). Con `provider auto off`, `fix` tampoco la sustituye.
