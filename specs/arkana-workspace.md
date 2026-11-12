# Especificación del plugin: arkana-workspace

> **Estado:** `beta` | **Versión:** `6.2.11`

---

## Descripción general

Gobierno del workspace de Arkana: componentes, permisos R/E/W, credenciales, herramientas, red/VPN, comprobaciones (check/fix), export/import, handover y convención de commits. La statusline es de arkana-statusline y los mensajes, de arkana-messaging.

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 1 | Diagnóstico de solo lectura de todo el workspace - cada componente (permisos, commits, git, .gitignore, identidad), herramientas y entorno (las declaradas con config tools, git, y Jira solo si está configurado), credenciales y los check que declara cada plugin de Arkana (statusline, mensajería, agentic…). Acepta --component, --network y --json. |
| `component` | 2 | Gestiona los componentes (repos) del workspace en el manifiesto core/workspace.json - list, add, edit y remove - con alias, ruta, tipo, remoto, ramas, referencia de token, VPN y herramientas. Valida, hace copia .bak y acepta --dry-run y --json. La identidad git personal y las rutas absolutas van a local.json. |
| `config` | 3 | Configura el workspace - jira (extensión opcional: URL y nombre de la clave del token), tools (herramientas, versiones y rutas locales) y policy (políticas compartidas del proyecto). Los componentes se gestionan con component. Valida, hace copia .bak y acepta --dry-run y --json. |
| `export` | 4 | Exporta la configuración del workspace (y con --include-data los datos de los plugins) a un ZIP con manifiesto y hashes sha256. Nunca incluye .credentials, identidad git personal ni rutas absolutas. Acepta --dry-run y --json. |
| `fix` | 5 | Corrige, de forma interactiva y paso a paso, lo que marcan los check de arkana-workspace en un componente - permisos (generador único), exclusiones locales de git, .gitignore, .gitattributes, .env.example e identidad git. Pide confirmación en cada cambio y deja copia .bak. |
| `handover` | 6 | Genera un informe de traspaso del workspace (plugins y versiones, componentes con su estado git, herramientas, planes de agentic, referencias de credenciales y datos por plugin) en Markdown o JSON, sin secretos ni rutas absolutas. Solo lectura, sin red. |
| `import` | 7 | Importa un ZIP creado por arkana-workspace:export. Valida todo antes de escribir (zip-slip, rutas absolutas, enlaces simbólicos, hashes, tamaños, destinos no declarados) y fusiona por fichero con --on-conflict keep\|replace\|ask. Acepta --dry-run y --json. |
| `install` | 8 | Primera puesta en marcha (repetible) de arkana-workspace - crea la disposición de .arkana (solo lo que falta) (manifiesto, local.json, tools.json, registro del workspace), genera los permisos de cada componente, comprueba las credenciales e instala la statusline. Interactiva, idempotente, con copia .bak y --dry-run. No lleva --component. |
| `rew-grants` | 9 | Muestra la matriz de permisos R/E/W entre ARKANA y los componentes - la esperada (del manifiesto) y la efectiva (de cada .claude/settings.local.json) - y sus desviaciones (missing, extra, weaker, stronger, legacy, duplicate, mode). Solo lectura; sirve también para regenerar la tabla de organizacion-proyecto.md. |
| `status` | 10 | Estado git local de ARKANA y de cada componente - rama, sin seguimiento (◌), preparados (✚), modificados (●), sin subir (⇡) y por bajar (⇣, o ⇣? si no se sabe). Todo local, sin red. Acepta --component y --json. |
| `sync` | 11 | Hace `git fetch` de los remotos de ARKANA y de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
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
