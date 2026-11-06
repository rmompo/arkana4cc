---
name: status
description: Estado git local de ARKANA y de cada componente - rama, sin seguimiento (◌), preparados (✚), modificados (●), sin subir (⇡) y por bajar (⇣, o ⇣? si no se sabe). Todo local, sin red. Acepta --component y --json.
---

# arkana-workspace:status

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/status.py" [--component <alias>]... [--json]
```

Una línea por pieza: `ARKANA develop ◌13 ✚113 ●84 ⇡2 ⇣3` o `app develop ✓`. `◌ ✚ ● ⇡` salen siempre de git local. **Solo `⇣` depende del remoto**: es el número si el último `fetch` correcto fue hace menos de 30 minutos y `⇣?` en el mismo sitio si no se sabe; sin remoto o sin rama remota no se muestran flechas. No contacta con la red; para refrescar `⇣` se hace el `fetch` con `/arkana-workspace:sync`.

Presenta la tabla tal cual; resalta las piezas con cambios sin subir o por bajar.
