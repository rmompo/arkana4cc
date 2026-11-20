---
name: component
description: Gestiona los componentes (repos) del workspace en el manifiesto core/workspace.json - list, add, edit y remove - con alias, ruta, tipo, remoto, ramas, referencia de token, VPN y herramientas. Valida, hace copia .bak y acepta --dry-run y --json. La identidad git personal y las rutas absolutas van a local.json. Also invoked explicitly as /arkana-workspace:component
allowed-tools: [AskUserQuestion]
version: 33
---

# arkana-workspace:component

Altas, cambios y bajas de componentes (`edit --alias arkana` edita las directrices de ARKANA: commits, remoto, ramas, token; no admite `--type`, `--path`, `--vpn`, `--statusline`, `--watch` ni `--tool-*`; en un componente, `edit` sí cambia `--statusline` y `--watch` en cualquier momento). Herramienta: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/components.py" <list|add|edit|remove> [opciones]`.

| Opción | Significado |
|---|---|
| `--alias` | Identificador (`^[a-z0-9][a-z0-9-]*$`; `arkana` y `all` están reservados). Se acepta en cualquier caso y **se muestra siempre en MAYÚSCULAS** (`WEBAPP`). En `edit` y `remove` vale también la carpeta real o el nombre-módulo del componente (`dir:<carpeta>`, `mod:<módulo>`, `alias:<alias>` fuerzan el tipo) |
| `--module NOMBRE` | Nombre-módulo (la aplicación; minúsculas, `.`, `_`, `-`). **Compartido**: va en `arkana-project.json` (registro del proyecto, versionado), no en el manifiesto local; exige `/arkana-evolve:apply`. `--module ""` lo quita. Alias, carpeta y módulo **no pueden repetirse entre componentes** (se rechaza el cambio que lo provoque) |
| `--path` | Carpeta del repo; absoluta o relativa a la raíz del workspace (se guarda relativa) |
| `--type` | `node`, `maven`, `docs` o `generic` |
| `--remote` | URL del remoto, **sin usuario ni contraseña** (se rechaza si los lleva) |
| `--main`, `--develop` | Ramas principal y de integración |
| `--git-user`, `--git-email` | Identidad personal (va a `local.json`, no se exporta) |
| `--git-username`, `--token-ref` | Usuario para git y **nombre** de la clave del token en `.credentials` (nunca el valor) |
| `--commit-format` | Convención de commits: `conventional` (por defecto) o `ia4d` (opcional). Con `conventional({module})` o `ia4d({module})` el scope del commit es el módulo del componente (sin módulo, el alias) |
| `--git-email-domain` | Dominio de correo exigido al autor de los commits (repetible; sustituye la lista; sin él no hay regla) |
| `--vpn` / `--no-vpn` | Si requiere VPN |
| `--statusline` / `--no-statusline` | Si `arkana-statusline` lo muestra. Sin la marca se muestra salvo los de tipo `docs`; `--statusline` fuerza mostrarlo y `--no-statusline` lo oculta (también con `edit`, en cualquier momento; un componente oculto se ve mientras estás dentro). No se aplica a ARKANA, que siempre se muestra |
| `--mode work\|reference` | `reference` = repo que solo se descarga y se ejecuta: oculto en la barra, sin vigilar, `check` no le exige identidad git, `.gitignore`, `.env`…, permisos solo de lectura para todos. `--mode work` lo devuelve a repo de trabajo (y quita su `ref`). No se aplica a ARKANA |
| `--ref REF` | Versión (tag, rama o sha) en la que debe estar `HEAD`; solo con `mode: reference`. `check` avisa si se mueve |
| `--checks-skip ID` / `--reset-checks-skip` | Checks que no se exigen a este componente (repetible); `--reset-checks-skip` vuelve al defecto del modo; una lista vacía explícita ejecuta todos. Lo explícito (`--statusline`, `--watch`, `--checks-skip`) siempre gana al defecto del modo |
| `--watch` / `--no-watch` | Si cuentan sus cambios (◌ ✚ ● y ⇣) en la barra, `status` y el BRIEF; independiente de `--statusline`. Con `--no-watch` siguen contando los commits sin subir (⇡). Escribe `schema: 2` del manifiesto. No se aplica a ARKANA |
| `--tool-version tool=ver`, `--tool-path tool=ruta` | Herramientas que pide (la ruta va a `local.json`) |
| `--rename NUEVO` | Solo `edit`: cambia el alias (el id no cambia) en el manifiesto, `local.json`, el registro y los datos locales de los plugins; ensaya antes y no cambia nada si algún plugin no puede (plan activo). Los documentos compartidos referencian por id y no se tocan |
| `--yes` | Confirma `remove` (solo quita del manifiesto; la carpeta no se toca) |

## Pasos

1. `list` para ver el estado actual. Para `add`/`edit`/`remove` recoge los datos con `AskUserQuestion` si faltan; **ensaya con `--dry-run`** y confirma antes de aplicar.
2. Tras `add` o `edit`: ofrece `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" apply --component <alias> --dry-run` (y luego sin `--dry-run`) para generar sus permisos, y `credentials.py wire-git <alias>` si tiene `--token-ref`.
3. Si el token no existe aún, indica `credentials.py set <CLAVE>` (el valor entra por stdin, nunca como argumento).

## Reglas

- Nunca pidas ni aceptes un token como argumento. No hagas commit ni push. Idempotente.
