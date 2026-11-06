---
name: install
description: Primera puesta en marcha (repetible) de arkana-workspace - crea o migra la disposición de .arkana (manifiesto, local.json, tools.json, registro del workspace), genera los permisos de cada componente, comprueba las credenciales e instala la statusline. Interactiva, idempotente, con copia .bak y --dry-run. No lleva --component.
---

# arkana-workspace:install

Deja el workspace listo. **Todo es repetible**: lo que ya está bien no se toca. Pide confirmación antes de cada cambio y acepta `--dry-run` (ensayo) y `--json`.

## Pasos

1. **Disposición de `.arkana/`** (manifiesto, `local.json`, `tools.json`, registro en `~/.arkana-workspaces.json`; copia de seguridad previa; se niega si hay un plan activo):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/layout.py" init --dry-run
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/layout.py" init
   ```
2. **Componentes**: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/components.py" list`. Si falta alguno, `/arkana-workspace:component add`.
3. **Permisos** de ARKANA y de cada componente (modelo en `/arkana-workspace:rew-grants`): `permissions.py apply --dry-run`, confirmar y aplicar. Solo añade lo que falta; deja copia en `.arkana/arkana-workspace/bak/`.
4. **Credenciales**: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/credentials.py" check`; si falta una clave que un componente referencia, indica `credentials.py set <CLAVE>` (valor por stdin) y `credentials.py wire-git <alias>`.
5. **Statusline:** `/arkana-statusline:install` (plugin propio).
6. **Semillas, `.gitignore`, permisos y convención de commits** de cada repo: `/arkana-messaging:install` y `/arkana-workspace:fix` (no hacen commit).
7. **Verificación**: `/arkana-workspace:check`. Avisa de que hay que **reiniciar Claude Code** para ver los cambios.

## Reglas

- Una confirmación por cambio. No toques otros ajustes de `settings.json`. No hagas commit ni push. Idempotente.
