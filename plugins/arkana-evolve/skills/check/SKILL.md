---
name: check
description: Diagnóstico de solo lectura de la evolución de Arkana - sello de layout del repo, migraciones aplicadas y pendientes, e integridad de lo ya aplicado. Avisa si el repo va por delante de esta instalación. Acepta --json.
---

# arkana-evolve:check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/evolve.py" check [--json]
```

Ids: `layout` (sello de `arkana-project.json` frente a la última migración conocida) y una línea por migración (`0001`, …): `OK` aplicada, `WARN` pendiente o aplicada pero con algo roto. No admite `--dry-run` (nunca escribe).

- Todo `OK`: resúmelo en una línea.
- `WARN` de migración pendiente o de layout por debajo: propón `/arkana-evolve:apply`.
- `WARN` de «el repo está en layout N y esta instalación solo conoce hasta M»: otra persona ha migrado; hay que **actualizar el plugin** `arkana-evolve` (no aplicar nada) y repetir.
