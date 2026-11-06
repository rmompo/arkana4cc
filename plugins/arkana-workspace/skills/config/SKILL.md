---
name: config
description: Configura el workspace - jira (extensión opcional: URL y nombre de la clave del token) y tools (herramientas, versiones y rutas locales). Los componentes se gestionan con component. Valida, hace copia .bak y acepta --dry-run y --json.
---

# arkana-workspace:config

Herramienta: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/config.py" <jira|tools> [opciones]`.

- **`jira`** `--url <URL> --token-ref <CLAVE>`: guarda el bloque `jira` del manifiesto (exportable). El token vive en `.credentials` bajo esa clave: `credentials.py set <CLAVE>` (valor por stdin). Sin opciones muestra lo configurado.
- **`tools`** `--tool <nombre> --version <v> [--path <ruta>] [--package <paquete[@versión]>]... [--registry <ámbito>=<url>]... [--check-url <url>]... [--port <n>]...`: declara las herramientas del proyecto en `.arkana/arkana-workspace/tools.json`. **Aquí vive todo lo específico del stack; los plugins no llevan ninguna herramienta, versión ni registro fijados.**
  - `--tool`/`--version`/`--path`: la herramienta (`node`, `jdk`, `maven`, `angular-cli`…), su versión esperada y dónde está (la ruta es local y no se exporta; `arkana-agentic` la pone en el `PATH` de las verificaciones, y `JAVA_HOME` si es `jdk`).
  - `--package`: paquetes globales que exige la herramienta (hoy se comprueban los de `node`, con `npm ls -g`).
  - `--registry`: registros por ámbito (`@acme=https://…`): `check` comprueba el `~/.npmrc` y `arkana-agentic` escribe ese `.npmrc` en sus verificaciones.
  - `--check-url` y `--port`: URL cuya respuesta y puertos cuya ocupación comprueba `check` (sin ellos no se comprueba nada).
  - Volver a registrar una herramienta conserva lo que no se repite; sin `--tool` lista. Las versiones por componente se dan con `component edit --tool-version tool=ver` (y `--tool-path` para la ruta local).

## Pasos

1. Muestra la configuración actual (`jira` y `tools` sin opciones).
2. Si el usuario quiere cambiar algo, ensaya con `--dry-run`, confirma y aplica.
3. Para rutas de repos, altas o bajas: `/arkana-workspace:component`.

## Reglas

- Nunca aceptes un token como argumento: solo el nombre de la clave. No hagas commit.
