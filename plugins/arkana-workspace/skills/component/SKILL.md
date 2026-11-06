---
name: component
description: Gestiona los componentes (repos) del workspace en el manifiesto core/workspace.json - list, add, edit y remove - con alias, ruta, tipo, remoto, ramas, referencia de token, VPN y herramientas. Valida, hace copia .bak y acepta --dry-run y --json. La identidad git personal y las rutas absolutas van a local.json.
---

# arkana-workspace:component

Altas, cambios y bajas de componentes (`edit --alias arkana` edita las directrices de ARKANA: commits, remoto, ramas, token, `--seed-file`; no admite `--type`, `--path`, `--vpn`, `--statusline` ni `--tool-*`). Herramienta: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/components.py" <list|add|edit|remove> [opciones]`.

| Opción | Significado |
|---|---|
| `--alias` | Identificador (`^[a-z0-9][a-z0-9-]*$`; `arkana`, `all` y `shared` están reservados) |
| `--path` | Carpeta del repo; absoluta o relativa a la raíz del workspace (se guarda relativa) |
| `--type` | `node`, `maven`, `docs` o `generic` |
| `--remote` | URL del remoto, **sin usuario ni contraseña** (se rechaza si los lleva) |
| `--main`, `--develop` | Ramas principal y de integración |
| `--git-user`, `--git-email` | Identidad personal (va a `local.json`, no se exporta) |
| `--git-username`, `--token-ref` | Usuario para git y **nombre** de la clave del token en `.credentials` (nunca el valor) |
| `--commit-format` | Convención de commits: `conventional` (por defecto) o `ia4d` (opcional) |
| `--git-email-domain` | Dominio de correo exigido al autor de los commits (repetible; sustituye la lista; sin él no hay regla) |
| `--vpn` / `--no-vpn` | Si requiere VPN |
| `--statusline` / `--no-statusline` | Si `arkana-statusline` lo muestra. Sin la marca se muestra salvo los de tipo `docs`; `--statusline` fuerza mostrarlo y `--no-statusline` lo oculta. No se aplica a ARKANA, que siempre se muestra |
| `--tool-version tool=ver`, `--tool-path tool=ruta` | Herramientas que pide (la ruta va a `local.json`) |
| `--seed-file` | `CLAUDE.md` o `CLAUDE.local.md` (el de Claude Code que el repo no versiona) |
| `--yes` | Confirma `remove` (solo quita del manifiesto; la carpeta no se toca) |

## Pasos

1. `list` para ver el estado actual. Para `add`/`edit`/`remove` recoge los datos con `AskUserQuestion` si faltan; **ensaya con `--dry-run`** y confirma antes de aplicar.
2. Tras `add` o `edit`: ofrece `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" apply --component <alias> --dry-run` (y luego sin `--dry-run`) para generar sus permisos, y `credentials.py wire-git <alias>` si tiene `--token-ref`.
3. Si el token no existe aún, indica `credentials.py set <CLAVE>` (el valor entra por stdin, nunca como argumento).

## Reglas

- Nunca pidas ni aceptes un token como argumento. No hagas commit ni push. Idempotente.
