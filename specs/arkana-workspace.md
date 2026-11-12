# Especificación del plugin: arkana-workspace

> **Estado:** `beta` | **Versión:** `6.2.22`

---

## Descripción general

Gobierno del workspace de Arkana: componentes, permisos R/E/W, credenciales, herramientas, red/VPN, comprobaciones (check/fix), export/import, handover y convención de commits. La statusline es de arkana-statusline y los mensajes, de arkana-messaging.

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 12 | Diagnóstico de solo lectura de todo el workspace - cada componente (permisos, commits, git, .gitignore, identidad), herramientas y entorno (las declaradas con config tools, git, y Jira solo si está configurado), credenciales y los check que declara cada plugin de Arkana (statusline, mensajería, agentic…). Acepta --component, --network y --json. |
| `component` | 13 | Gestiona los componentes (repos) del workspace en el manifiesto core/workspace.json - list, add, edit y remove - con alias, ruta, tipo, remoto, ramas, referencia de token, VPN y herramientas. Valida, hace copia .bak y acepta --dry-run y --json. La identidad git personal y las rutas absolutas van a local.json. |
| `config` | 14 | Configura el workspace - jira (extensión opcional: URL y nombre de la clave del token), tools (herramientas, versiones y rutas locales) y policy (políticas compartidas del proyecto). Los componentes se gestionan con component. Valida, hace copia .bak y acepta --dry-run y --json. |
| `export` | 15 | Exporta la configuración del workspace (y con --include-data los datos de los plugins) a un ZIP con manifiesto y hashes sha256. Nunca incluye .credentials, identidad git personal ni rutas absolutas. Acepta --dry-run y --json. |
| `fix` | 16 | Corrige, de forma interactiva y paso a paso, lo que marcan los check de arkana-workspace en un componente - permisos (generador único), exclusiones locales de git, .gitignore, .gitattributes, .env.example e identidad git. Pide confirmación en cada cambio y deja copia .bak. |
| `handover` | 17 | Genera un informe de traspaso del workspace (plugins y versiones, componentes con su estado git, herramientas, planes de agentic, referencias de credenciales y datos por plugin) en Markdown o JSON, sin secretos ni rutas absolutas. Solo lectura, sin red. |
| `import` | 18 | Importa un ZIP creado por arkana-workspace:export. Valida todo antes de escribir (zip-slip, rutas absolutas, enlaces simbólicos, hashes, tamaños, destinos no declarados) y fusiona por fichero con --on-conflict keep\|replace\|ask. Acepta --dry-run y --json. |
| `install` | 19 | Primera puesta en marcha (repetible) de arkana-workspace - crea la disposición de .arkana (solo lo que falta) (manifiesto, local.json, tools.json, registro del workspace), genera los permisos de cada componente, comprueba las credenciales e instala la statusline. Interactiva, idempotente, con copia .bak y --dry-run. No lleva --component. |
| `rew-grants` | 20 | Muestra la matriz de permisos R/E/W entre ARKANA y los componentes - la esperada (del manifiesto) y la efectiva (de cada .claude/settings.local.json) - y sus desviaciones (missing, extra, weaker, stronger, legacy, duplicate, mode). Solo lectura; sirve también para regenerar la tabla de organizacion-proyecto.md. |
| `status` | 21 | Estado git local de ARKANA y de cada componente - rama, sin seguimiento (◌), preparados (✚), modificados (●), sin subir (⇡) y por bajar (⇣, o ⇣? si no se sabe). Todo local, sin red. Acepta --component y --json. |
| `sync` | 22 | Hace `git fetch` de los remotos de ARKANA y de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 6.2.22 | sync: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.21 | status: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.20 | rew-grants: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.19 | install: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.18 | import: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.17 | handover: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.16 | fix: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.15 | export: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.14 | config: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.13 | component: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.12 | check: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 6.2.11 | sync: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.10 | status: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.9 | rew-grants: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.8 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.7 | import: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.6 | handover: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.5 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.4 | export: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.3 | config: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.2 | component: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.1 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 6.2.0 | Bootstrap: plugin registrado en catalog.json |
