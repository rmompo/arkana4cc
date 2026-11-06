---
name: install
description: Primera puesta en marcha (repetible) de la orquestación - carpetas config/state/data, bloque `arkana:agentic` (reglas del orquestador) en el CLAUDE.md de ARKANA y plugin habilitado en ~/.claude/settings.json. Copia .bak de lo que modifica. Acepta --dry-run.
---

# arkana-agentic:install

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh install [--dry-run] [--no-settings]
```

Hace: (1) crea `.arkana/arkana-agentic/{config,state,data}` (700); (2) pone en el `CLAUDE.md` de ARKANA el bloque `<!-- arkana:agentic:start -->…end -->` con las reglas del orquestador (plantilla del plugin, `templates/orquestador.md`) y sustituye la referencia antigua `@orquestacion/ORQUESTADOR.md`; (3) habilita `arkana-agentic@arkana` en `~/.claude/settings.json` (copia previa en `.arkana/arkana-agentic/bak/`).

## Pasos

1. `--dry-run` primero y enseña qué cambiaría; pide confirmación (`AskUserQuestion`) antes de aplicar: modifica `CLAUDE.md` y los ajustes de usuario.
2. Aplica y recuerda que el `CLAUDE.md` de ARKANA queda modificado **sin commit** y que hay que recargar los plugins.
3. Si hay un layout antiguo (`planes/`, `run/`…), el siguiente paso es `/arkana-agentic:fix`.
