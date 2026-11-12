---
name: install
description: Primera puesta en marcha (repetible) de la orquestación - carpetas config/state/data y plugin habilitado en ~/.claude/settings.json. No escribe nada en los repos (las reglas del orquestador las inyecta un hook). Copia .bak de lo que modifica. Acepta --dry-run.
---

# arkana-agentic:install

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh install [--dry-run] [--no-settings]
```

Hace: (1) crea `.arkana/arkana-agentic/{config,state,data}` (700); (2) habilita `arkana-agentic@arkana` en `~/.claude/settings.json` (copia previa en `.arkana/arkana-agentic/bak/`).

## Pasos

1. `--dry-run` primero y enseña qué cambiaría; pide confirmación (`AskUserQuestion`) antes de aplicar: modifica los ajustes de usuario.
2. Aplica y recuerda que hay que recargar los plugins: el hook que inyecta las reglas del orquestador arranca con ellos.
