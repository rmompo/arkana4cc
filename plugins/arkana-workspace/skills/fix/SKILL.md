---
name: fix
description: Corrige, de forma interactiva y paso a paso, lo que marcan los check de arkana-workspace en un componente - permisos (generador único), exclusiones locales de git, .gitignore, .gitattributes, .env.example e identidad git. Pide confirmación en cada cambio y deja copia .bak.
version: 5
---

# arkana-workspace:fix

Aplica, **uno a uno y con confirmación**, las correcciones de los `FAIL`/`WARN` que detecta `scripts/checks/component.py` en el componente actual (o en `--component <alias>`).

## Pasos

1. Comprueba el componente (solo lectura):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/checks/component.py" [--component <alias>] --no-network
   ```
   Si no hay `FAIL` ni `WARN`, dilo y termina. Con `--dry-run` en cada herramienta se ensaya sin escribir.

2. Para **cada** `FAIL`/`WARN` de la tabla, en este orden: explica en una frase qué es y qué vas a cambiar; pregunta con `AskUserQuestion` (aplicar / saltar / parar); si acepta, haz copia `<fichero>.bak` si existe, aplica el cambio y vuelve a comprobar ese ID.

3. Al final repite la comprobación y resume: corregido / saltado / pendiente.

## Arreglos por ID

| ID | Arreglo |
|---|---|
| `arkana-presente` | No se arregla aquí: hay que clonar el repo de Arkana en la carpeta del workspace |
| `permisos` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" apply --component <alias>` (`--dry-run` primero; deja copia en `.arkana/arkana-workspace/bak/` y el fichero en modo 0600). Solo añade lo que falta y limpia duplicados y reglas legacy; para **quitar** lo que concede de más, pregunta y usa `--prune`. **Una regla nueva se añade al modelo (`lib/permissions.py`), nunca a mano en `settings.local.json`** |
| `gitignore-env` | Añadir al `.gitignore` lo que falte: `.env`, `.env.*`, `!.env.example`, `node_modules/` |
| `registro` | Falta el registro o el id: `/arkana-evolve:apply`. Si el registro llama de otro modo a este componente (lo renombró otra persona): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/components.py" edit --alias <tuyo> --rename <el del registro>` (alinea manifiesto, `local.json` y datos locales) |
| `ignore-editor`, `ignore-editor-session`, `ignore-arkana-local` | `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/excludes.py" apply --component <alias>` (`--dry-run` primero): añade `.claude/`, `.claude-session/` y `ARKANA.local.md` a `.git/info/exclude` (local, no versionado). **Nunca** los pongas en el `.gitignore` del repo |
| `gitattributes-eol` | Crear o ampliar `.gitattributes` con `* text=auto eol=lf` |
| `env-example` | Crear `.env.example` con los **nombres** de las variables del `.env` real (nunca los valores), vacíos o `<pegar-aquí>` |
| `env-versionado` | Si el proyecto declara `versioned_env` no es fallo (INFO): no hacer nada. Si no, explicar `git rm --cached <fichero>` y que hay que **rotar las credenciales**; ejecutarlo solo si el usuario lo confirma. Sin commit |
| `env-historial` | Solo informar: rotar credenciales y limpiar el historial (manual y delicado) |
| `git-identidad`, `anidado-<alias>` | `git config user.email <correo>` **a nivel de repo** y con confirmación; no tocar `~/.gitconfig` |
| `jira-mcp`, `jira-mcp-deps` (extensión opcional: solo si el manifiesto tiene el bloque `jira`; los emite `check` como `tools:<ID>`, no `component.py`) | Plugin `ia4d-project-bridge` ausente: indica que se instale y se habilite. Con confirmación, `npm install --omit=dev` dentro del `mcp/jira-connector` que indica el check |
| `jira-mcp-duplicado` | Quita la clave `mcpServers.jira-connector` de `~/.claude/settings.json` (con copia `.bak` y parche mínimo): sobra, la definición buena es la del plugin; si tiene `${CLAUDE_PLUGIN_ROOT}` sin expandir o ruta rota, el servidor sale en rojo (`Connection closed`) |
| `jira-env-proyecto` | Mueve las variables `JIRA_*` del `.env` del proyecto a `~/.ia4d/.env` (el conector solo lee ese); sin mostrar valores |
| `husky-hooks` | `chmod +x` de los hooks listados |
| `rama`, `origin-accesible` | Solo informar (dependen del usuario o de la red/VPN) |
| `carpeta`, `git-repo`, `arkana-escribible` | Solo informar (la carpeta, el `git init`/remoto y los permisos del sistema de ficheros los decide el usuario) |

## Reglas

- **Interactivo siempre:** nunca apliques varios cambios con una sola confirmación.
- No leas ni muestres valores de `.env`, tokens o credenciales.
- No hagas commit ni push. Idempotente: si ya está bien, no toques nada.
