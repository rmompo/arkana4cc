# Especificación del plugin: arkana-workspace

> **Estado:** `beta` | **Versión:** `6.2.42`

---

## Descripción general

Gobierno del workspace de Arkana: componentes, permisos R/E/W, credenciales, herramientas, red/VPN, comprobaciones (check/fix), export/import, handover y convención de commits. La statusline es de arkana-statusline y los mensajes, de arkana-messaging.

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `brief` | 42 | Muestra el BRIEF de Arkana a demanda - QUICK START con los comandos útiles, mensajes sin leer, todas las tareas activas, todas las notas, componentes con cambios sin subir y el plan activo. Es el mismo que se ve al abrir, reanudar o compactar una sesión, pero siempre sale, aunque no haya nada pendiente. Solo lectura. Acepta --home. Also invoked explicitly as /arkana-workspace:brief |
| `check` | 27 | Diagnóstico de solo lectura de todo el workspace - cada componente (permisos, commits, git, .gitignore, identidad), herramientas y entorno (las declaradas con config tools, git, y Jira solo si está configurado), credenciales y los check que declara cada plugin de Arkana (statusline, mensajería, agentic…). Acepta --component, --network y --json. |
| `component` | 36 | Gestiona los componentes (repos) del workspace en el manifiesto core/workspace.json - list, add, edit y remove - con alias, ruta, tipo, remoto, ramas, referencia de token, VPN y herramientas. Valida, hace copia .bak y acepta --dry-run y --json. La identidad git personal y las rutas absolutas van a local.json. |
| `config` | 14 | Configura el workspace - jira (extensión opcional: URL y nombre de la clave del token), tools (herramientas, versiones y rutas locales) y policy (políticas compartidas del proyecto). Los componentes se gestionan con component. Valida, hace copia .bak y acepta --dry-run y --json. |
| `export` | 15 | Exporta la configuración del workspace (y con --include-data los datos de los plugins) a un ZIP con manifiesto y hashes sha256. Nunca incluye .credentials, identidad git personal ni rutas absolutas. Acepta --dry-run y --json. |
| `fix` | 28 | Corrige, de forma interactiva y paso a paso, lo que marcan los check de arkana-workspace en un componente - permisos (generador único), exclusiones locales de git, .gitignore, .gitattributes, .env.example e identidad git. Pide confirmación en cada cambio y deja copia .bak. |
| `handover` | 17 | Genera un informe de traspaso del workspace (plugins y versiones, componentes con su estado git, herramientas, planes de agentic, referencias de credenciales y datos por plugin) en Markdown o JSON, sin secretos ni rutas absolutas. Solo lectura, sin red. |
| `import` | 18 | Importa un ZIP creado por arkana-workspace:export. Valida todo antes de escribir (zip-slip, rutas absolutas, enlaces simbólicos, hashes, tamaños, destinos no declarados) y fusiona por fichero con --on-conflict keep\|replace\|ask. Acepta --dry-run y --json. |
| `install` | 19 | Primera puesta en marcha (repetible) de arkana-workspace - crea la disposición de .arkana (solo lo que falta) (manifiesto, local.json, tools.json, registro del workspace), genera los permisos de cada componente, comprueba las credenciales e instala la statusline. Interactiva, idempotente, con copia .bak y --dry-run. No lleva --component. |
| `rew-grants` | 30 | Muestra la matriz de permisos R/E/W entre ARKANA y los componentes - la esperada (del manifiesto) y la efectiva (de cada .claude/settings.local.json) - y sus desviaciones (missing, extra, weaker, stronger, legacy, duplicate, mode). Solo lectura; sirve también para regenerar la tabla de organizacion-proyecto.md. |
| `status` | 29 | Estado git local de ARKANA y de cada componente - rama, sin seguimiento (◌), preparados (✚), modificados (●), sin subir (⇡) y por bajar (⇣, o ⇣? si no se sabe). Todo local, sin red. Acepta --component y --json. |
| `sync` | 22 | Hace `git fetch` de los remotos de ARKANA y de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 6.2.42 | brief: Se crea la skill brief (el BRIEF a demanda) y el BRIEF cambia de formato: cabecera en caja, columnas, TODOS y NOTES con todas las filas e ids en mayusculas |
| 6.2.41 | Nucleo 1.13.0 vendorizado: LAYOUT_KNOWN 10 |
| 6.2.40 | BRIEF: tras compact o resume se da siempre y llega tambien al contexto del modelo; las tareas de varios componentes salen con todos ellos |
| 6.2.39 | Nucleo 1.11.1 vendorizado: el registro de workspaces conserva el nombre de una entrada existente |
| 6.2.38 | Nucleo 1.11.0 vendorizado: LAYOUT_KNOWN 8 |
| 6.2.37 | El registro de workspaces vive en ~/.arkana/workspaces.json (el antiguo se lee y se migra) |
| 6.2.36 | component: component: pide usuario y correo git al anadir un componente y, si tiene remoto, usuario y clave del token; la identidad se aplica al repo; credentials set pide el valor sin mostrarlo |
| 6.2.35 | layout init deja /.arkana/ ignorado en el .gitignore de ARKANA y el BRIEF muestra el componente de las tareas en mayusculas (hallazgos del laboratorio de install) |
| 6.2.34 | BRIEF: seccion NOTES con las notas activas de arkana-note y linea en el QUICK START |
| 6.2.33 | component: Tres nombres por componente (alias, carpeta y modulo compartido), referencia por cualquiera con prefijos dir:, mod: y alias:, scope de commit con ({module}), check nombres y alias siempre en mayusculas |
| 6.2.32 | BRIEF: las tareas activas de arkana-todo salen por prioridad con su estado (nuevo modelo de estados y prioridades) |
| 6.2.31 | stop requiring a plugins folder to recognise the Arkana repo |
| 6.2.30 | rew-grants: rew-grants: solo lectura para todos sobre un componente de referencia |
| 6.2.29 | status: status: sección de referencias aparte y sin vigilar |
| 6.2.28 | fix: fix: ref solo informa y lo omitido no se arregla |
| 6.2.27 | check: check: el componente de referencia no recibe los checks de un repo de trabajo, se verifica contra su ref y lista lo omitido |
| 6.2.26 | component: Componentes: --mode reference, --ref y --checks-skip (repos que solo se descargan y se ejecutan) |
| 6.2.25 | component: Componentes: --watch/--no-watch (esquema 2), watch en status y BRIEF, aviso de layout superior y de copia antigua de la statusline |
| 6.2.24 | El BRIEF de sesión cambia el orden de las secciones: QUICK START, MESSAGING, TODO, GIT y ORCHESTRATION |
| 6.2.23 | El BRIEF de sesión añade la sección TODO (tareas abiertas de arkana-todo) y las líneas de arkana-knowledge:ingest y arkana-evolve:check en el QUICK START |
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
