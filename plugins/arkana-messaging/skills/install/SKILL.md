---
name: install
description: Primera puesta en marcha (repetible) de la mensajería - crea el almacén y habilita el plugin en ~/.claude/settings.json. No escribe nada en los repos. Copia .bak de lo que modifica. Acepta --dry-run y --json.
---

# arkana-messaging:install

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" install [--dry-run] [--no-settings] [--json]
```

`--no-settings` no toca `~/.claude/settings.json`.

Hace: (1) crea `.arkana/arkana-messaging/state/messages/`; (2) habilita `arkana-messaging@arkana` en `~/.claude/settings.json` (copia previa en `.arkana/arkana-messaging/bak/`). Las instrucciones de uso las inyecta el hook de sesión: **no se escribe ningún fichero en los repos**.

## Pasos

1. Ejecuta primero `--dry-run` y enseña qué cambiaría. Pide confirmación (`AskUserQuestion`) antes de aplicar: modifica los ajustes de usuario.
2. Aplica. Recuerda al usuario que hay que **recargar los plugins** (`/reload-plugins`) o reiniciar la sesión para que los hooks arranquen.
3. No hagas commit ni push.
