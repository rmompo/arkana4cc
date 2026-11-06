---
name: install
description: Instala la statusline de Arkana en ~/.claude/arkana-statusline/ (statusline.sh, statusline.py y arkana_core) y activa `statusLine` en ~/.claude/settings.json. Una statusLine ajena solo se sustituye con --replace (copia de los ajustes en bak/). Acepta --dry-run y --json.
---

# arkana-statusline:install

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" install [--replace] [--dry-run] [--json]
```

La statusline la ejecuta Claude Code como un comando de usuario, sin raíz de plugin: por eso se **copia** a `~/.claude/arkana-statusline/` (el script y el núcleo `arkana_core`, que viajan juntos). Funciona también fuera de un workspace.

## Pasos

1. `--dry-run` primero y enseña qué cambiaría. Si ya hay otra `statusLine` (un script propio, el antiguo `statusline-command.sh` u otro plugin), **no la pises**: explica la diferencia y pregunta (`AskUserQuestion`) si sustituirla; solo entonces `--replace`.
2. Aplica. Hace copia de `~/.claude/settings.json` en `~/.claude/arkana-statusline/bak/` y una prueba de humo (la statusline instalada debe imprimir al menos una línea).
3. Recuerda reiniciar Claude Code o recargar los plugins para verla. No uses a la vez otro plugin de statusline con autoinstalación: `check` los detecta.
