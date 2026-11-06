---
name: install
description: Primera puesta en marcha (repetible) de la mensajería - crea el almacén, habilita el plugin en ~/.claude/settings.json y pone la semilla `arkana:messaging` en ARKANA y en cada componente. Copia .bak de lo que modifica. Acepta --dry-run y --json.
---

# arkana-messaging:install

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" install [--dry-run] [--no-settings] [--json]
```

`--no-settings` no toca `~/.claude/settings.json`. Si falta un `CLAUDE.md` versionado no lo crea (`WARN`): eso lo hace `/arkana-workspace:fix`.

Hace: (1) crea `.arkana/arkana-messaging/state/messages/`; (2) habilita `arkana-messaging@arkana` en `~/.claude/settings.json` (copia previa en `.arkana/arkana-messaging/bak/`); (3) pone el bloque `<!-- arkana:messaging:start -->…end -->` en el `CLAUDE.md` de ARKANA y en el de cada componente (`CLAUDE.local.md` en los que lo declaran como `seed_file`, que no se versiona); (4) quita de ARKANA la importación obsoleta `@.arkana/core/novedades.md`.

## Pasos

1. Ejecuta primero `--dry-run` y enseña qué cambiaría. Pide confirmación (`AskUserQuestion`) antes de aplicar: modifica ficheros de varios repos y los ajustes de usuario.
2. Aplica. Recuerda al usuario que **los cambios en los repos no están commiteados** (los `CLAUDE.md` versionados quedan modificados para que los revise) y que hay que **recargar los plugins** (`/reload-plugins`) o reiniciar la sesión para que los hooks arranquen.
3. No hagas commit ni push.
