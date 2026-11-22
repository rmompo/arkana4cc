---
name: apply
description: Aplica las migraciones pendientes de Arkana (registro del proyecto con UUID, carpetas fijas, modelo de estados de las tareas, `/.arkana/` en el `.gitignore`, `arkana-docs/` en `src/`, `md/` y `out/`, y el registro de workspaces de usuario…) en orden, de forma idempotente y con copia de seguridad. Siempre ensaya primero con --dry-run y pide confirmación; nunca hace commit ni push. Acepta --dry-run, --to N y --json. Also invoked explicitly as /arkana-evolve:apply
allowed-tools: [AskUserQuestion]
version: 13
---

# arkana-evolve:apply

Lleva esta instalación de Arkana al layout más reciente. Cada migración es idempotente: repetir `apply` no cambia nada.

## Pasos

1. Estado: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/evolve.py" check`. Si todo está `OK`, dilo en una línea y termina.
2. Ensayo: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/evolve.py" apply --dry-run` y enseña qué se crearía o cambiaría (líneas `DRY`).
3. Pide confirmación con `AskUserQuestion` («Aplicar» / «Cancelar»). Explica el ámbito: **compartido** = ficheros versionados del repo de ARKANA; **local** = `.arkana/` (deja copia `tar.gz` en `.arkana/arkana-workspace/bak/`).
4. Aplica: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/evolve.py" apply` (`--to N` para parar en una migración concreta).
5. Si el resultado trae `WARN|statusline`, la copia de la statusline de `~/.claude` es anterior (núcleo antiguo o instalada antes del despachador): es un dato de usuario fuera del repo que ninguna migración toca; ofrece `/arkana-statusline:fix`. Si trae `WARN|0007:versionado`, ficheros de `.arkana/` ya estaban en git: explica que hay que quitarlos con `git rm -r --cached .arkana` y rotar las credenciales (no lo hagas tú).
6. Resume y recuerda: **queda sin commitear**. Una sola persona migra, revisa `git status`, commitea y empuja; el resto hace pull y vuelve a ejecutar `/arkana-evolve:apply` (solo se aplica su parte local, sin regenerar UUID).

## Reglas

- Nunca hagas `commit`, `push` ni `git add` por tu cuenta.
- Con código de salida 3 (sin git, o cambios sin commitear en lo que va a escribir la migración) no fuerces nada: explica la causa y deja que el usuario la resuelva.
- Si una migración necesita una herramienta que no está instalada, **pídesela al usuario** (cuál, para qué y el comando exacto); no la instales.
