# Contrato de salida común

Los skills de Arkana comparten el formato de salida (`lib/arkana_core/output.py`).

**Texto.** Una línea por comprobación o acción, `ESTADO|ID|detalle`, y al final `RESUMEN|n FAIL|n WARN`.

| Estado | Significado |
|---|---|
| `OK` | Correcto o aplicado |
| `WARN` | Requiere atención; no bloquea |
| `FAIL` | Fallo; el comando termina con código 1 |
| `INFO` | Informativo |
| `DRY` | Lo que se haría con `--dry-run` |

**`--json`.**

```json
{"plugin": "arkana-workspace", "skill": "check",
 "status": "ok|warn|fail",
 "items": [{"id": "permisos", "status": "OK", "detail": "…", "component": "app"}],
 "summary": {"fail": 0, "warn": 1, "ok": 12, "info": 0, "dry": 0}}
```

Las consultas que devuelven datos (`messaging get --json`, `knowledge query --json`, `agentic status --json`) devuelven su propia estructura (un array de mensajes o de notas, o el estado), no este envoltorio.

**Códigos de salida.** `0` sin fallos · `1` fallos o error · `2` uso incorrecto · `3` precondición no cumplida (p. ej. sin workspace, o VPN caída). `arkana-agentic` añade `4` violación, `5` esperando al usuario, `6` límite y `7` detenido o en pausa.

**Seguridad.** Nunca se imprime un secreto, ni su longitud: `Report(secrets=[…])` sustituye los valores por `***`. Las rutas absolutas y los remotos con usuario no se muestran en los informes que se comparten (`handover`).
