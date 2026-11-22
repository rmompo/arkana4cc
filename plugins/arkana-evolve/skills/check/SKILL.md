---
name: check
description: Diagnóstico de solo lectura de la evolución de Arkana - sello de layout del repo, migraciones aplicadas y pendientes, e integridad de lo ya aplicado. Avisa si el repo va por delante de esta instalación y lista los actualizadores de la máquina (p. ej. si la copia de la statusline de `~/.claude` es distinta de la del plugin). Acepta --json. Also invoked explicitly as /arkana-evolve:check
allowed-tools: []
version: 15
---

# arkana-evolve:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/evolve.py" check [--json]
```

Ids: `layout` (sello de `arkana-project.json` frente a la última migración conocida), una línea por migración (`0001`, …: `OK` aplicada, `WARN` pendiente o aplicada pero con algo roto) y una por actualizador de máquina (`u001`, …: `OK` al día, `WARN` pendiente). No admite `--dry-run` (nunca escribe).

- Todo `OK`: resúmelo en una línea.
- `WARN` de migración pendiente, de layout por debajo o de actualizador (`u001`) pendiente: propón `/arkana-evolve:apply` (los actualizadores solo tocan esta máquina).
- `WARN` de «el repo está en layout N y esta instalación solo conoce hasta M»: otra persona ha migrado; hay que **actualizar el plugin** `arkana-evolve` (no aplicar nada) y repetir.
