---
name: check
description: Diagnóstico de solo lectura de todo el workspace - cada componente (permisos, CLAUDE.md, git, .gitignore, identidad), herramientas y entorno (Node, Angular, Java, Maven, git, y Jira solo si está configurado), credenciales, los check que declara cada plugin de Arkana y la statusline. Acepta --component, --network, --json y --dry-run (sin efecto).
---

# arkana-workspace:check

Comprueba el workspace entero. **No modifica nada** (`--dry-run` se acepta y no hace nada). Para corregir: `/arkana-workspace:fix`.

## Pasos

1. Diagnóstico agregado (sin red por defecto; `--network` añade los hosts remotos; `--json` para salida estructurada):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/checks/all.py" [--component <alias>]... [--network] [--json]
   ```
   Cada línea es `ESTADO|ID|detalle` con `ID = <origen>:<comprobación>` (origen = alias del componente, `tools`, `credenciales` o el plugin que declara su `check` en `arkana-plugin.json`). La última es `RESUMEN|n FAIL|n WARN`. Códigos de salida: 0 sin fallos, 1 con fallos, 3 si no hay workspace.

2. Red y acceso a los remotos (solo si el usuario lo pide o hay `WARN` de red): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/checks/vpn.py" [--component <alias>] [--no-write]`. Comprueba DNS/HTTPS por host y lectura/escritura por repo (`git push --dry-run`, no sube nada). **Si el DNS se queda colgado** (el proceso queda en estado D), no insistas: es la red del contenedor/VPN.

3. Statusline y mensajería: `/arkana-statusline:check` y `/arkana-messaging:check` (cada plugin comprueba lo suyo).

4. Presenta una tabla con los `FAIL` primero y luego los `WARN`; agrupa las `OK` en una línea. Si hay problemas corregibles, termina con «`/arkana-workspace:fix` los corrige paso a paso; `/arkana-workspace:rew-grants` detalla los permisos».

## Reglas

- Solo lectura. No muestres valores de `.env`, tokens ni credenciales (los informes ya los redactan).
- Cada `check` de plugin se ejecuta con tiempo límite y sin stdin.
