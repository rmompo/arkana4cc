# arkana-workspace

Plugin base de Arkana para Claude Code. Gobierna el **workspace** (ARKANA, repositorio de conciliación y gobierno del proyecto y sus componentes, más el proyecto, que se compone de uno o más componentes, cada uno un repositorio): qué componentes lo forman, quién puede leer o escribir dónde, con qué credenciales, con qué herramientas, con qué convención de commits y en qué estado está cada repo. Es el único plugin del que dependen los demás para saber «dónde está todo».

Versión del plugin: 5.1.0 (`.claude-plugin/plugin.json`). Contrato `arkana-plugin.json` versión 1. Solo biblioteca estándar de Python 3 (`python3`, `git`; `jq` lo usan el núcleo bash y la statusline). Visión de conjunto de los seis plugins: [`../README.md`](../README.md).

## Índice

1. [Objetivo](#1-objetivo)
2. [Relación con los otros cuatro plugins](#2-relación-con-los-otros-cuatro-plugins)
3. [Modelo de datos y conceptos](#3-modelo-de-datos-y-conceptos)
4. [Referencia de skills](#4-referencia-de-skills) (`install`, `check`, `fix`, `component`, `config`, `status`, `sync`, `rew-grants`, `export`, `import`, `handover`)
5. [Herramientas auxiliares sin skill](#5-herramientas-auxiliares-sin-skill) (`credentials.py`, `arkana-exec.sh`, asistente de git)
6. [Hooks](#6-hooks)
7. [Variables de entorno y localización del workspace](#7-variables-de-entorno-y-localización-del-workspace)
8. [Contrato de salida y códigos de salida](#8-contrato-de-salida-y-códigos-de-salida)
9. [Instalación, pruebas y desarrollo](#9-instalación-pruebas-y-desarrollo)

---

## 1. Objetivo

El **workspace** es ARKANA más el **proyecto**. ARKANA tiene su propio repositorio (la carpeta de ARKANA) y sirve de repositorio de conciliación, gobierno y conocimiento del proyecto y de sus componentes (el conocimiento lo administran y consultan las personas usuarias); el proyecto se compone de uno o más **componentes**, cada uno un repositorio, hermano de ARKANA o anidado en otro. `arkana-workspace` resuelve, sin saber nada de ningún proyecto concreto (los componentes, herramientas, versiones, paquetes y registros se declaran en configuración; las comprobaciones de Jira, `jq`, `python3` y Node ≥ 20 de `check` sí están fijadas en el código):

| Necesidad | Cómo la cubre |
|---|---|
| Saber qué componentes hay, dónde están y de qué tipo son | Manifiesto `core/workspace.json` y skill `component` |
| Que cada componente pueda tocar solo lo que debe | Modelo único de permisos R/E/W generado desde el manifiesto (`permissions.py`), visible con `rew-grants` y aplicado con `fix` |
| Guardar secretos sin que lleguen a git, al manifiesto ni a un ZIP | `.credentials` (modo 600, solo nombres de clave en el manifiesto) y el asistente de credenciales de git |
| Declarar las herramientas del proyecto (Node, JDK, Maven…, paquetes globales, registros, URL, puertos) | `config tools` y la comprobación dirigida por datos de `check` |
| Una convención de commits por componente, también para ARKANA | `commit_format` y el bloque `arkana:commits` |
| Diagnosticar y reparar el estado del workspace | `check` (solo lectura, agregado) y `fix` (interactivo, con copia `.bak`) |
| Ver el estado git de todo y refrescar lo que baja del remoto | `status` (local) y `sync` (`git fetch` acotado) |
| Mover la configuración entre máquinas y traspasar el proyecto | `export` / `import` (ZIP verificable) y `handover` (informe sin secretos) |

Reglas transversales: ningún comando escribe fuera de `.arkana/` y de los ficheros que su skill declara; todos los que escriben admiten `--dry-run` y dejan copia de seguridad; ninguno hace commit ni push; ninguno imprime un secreto.

---

## 2. Relación con los otros cuatro plugins

### Qué les aporta

| Aporte | Detalle | Quién lo usa |
|---|---|---|
| **Manifiesto** `core/workspace.json` | Lista de piezas (ARKANA y componentes), rutas relativas a la raíz del workspace, tipos, ramas, remotos | Todos los plugins lo leen con el núcleo `arkana_core` |
| **`local.json`** | Ruta absoluta de cada pieza en esta máquina (manda sobre la del manifiesto), identidad git personal y rutas locales de herramientas | Todos, a través de `manifest.load` |
| **Permisos** | `permissions.py` es el generador único de `.claude/settings.local.json` de ARKANA y de cada componente, incluidas las reglas `Bash` del orquestador y el `deny` de `claude -p/--print/--bg` | `arkana-agentic` depende de estas reglas para que solo ARKANA lance workers y para proteger su estado |
| **Herramientas** `tools.json` | Versión, ruta, paquetes globales y registros por ámbito | `arkana-agentic` pone `path` en el `PATH` (y `JAVA_HOME` si la herramienta es `jdk`) y escribe el `.npmrc` de sus verificaciones |
| **Credenciales** `.credentials` | Resolvedor único de claves; `arkana-exec.sh` las pasa al entorno de un comando | Los demás plugins nunca leen `.credentials` directamente |
| **Convención de commits** | `commit_format` por componente y bloque `arkana:commits` en su `CLAUDE.md` | Los commits locales de `arkana-agentic` (rama `arkana-worker/<plan>`) siguen el formato del manifiesto |
| **Gestión de bloques** | `seedblock` (marcadores `<!-- arkana:NOMBRE:start/end -->`) | `arkana-messaging` (`arkana:messaging`), `arkana-agentic` (`arkana:agentic`) y este plugin (`arkana:commits`) |
| **`check` agregado** | `checks/all.py` ejecuta, además de lo suyo, el `check` que cada plugin declare en su `arkana-plugin.json` | Un único `/arkana-workspace:check` revisa el conjunto |
| **Exportar/importar** | Cada plugin declara en `arkana-plugin.json` la clase de sus datos (`config`, `data`, `local`, `secret`); `transfer.py` y `handover.py` solo leen esas declaraciones | Todos |
| **BRIEF de sesión** | Hook `SessionStart` que resume git, mensajes y plan activo | Usa datos de `arkana-messaging` (índice y marcas de lectura) y de `arkana-agentic` (plan activo) solo si existen |

### Qué usa de ellos

| Plugin | Qué lee este plugin | Cómo |
|---|---|---|
| `arkana-messaging` | `arkana-messaging/state/index.json` y `state/read/<actor>.json` | Solo el hook, para contar mensajes sin leer; si no existen, no aparece la sección |
| `arkana-agentic` | `arkana-agentic/state/actual` y `state/planes/<id>/plan.json` | El hook (plan activo y gasto) y `handover` (lista de planes); permisos (`agentic-state`, `agentic.sh`) |
| `arkana-statusline` | `statusLine` de `~/.claude/settings.json` | El BRIEF sugiere `/arkana-statusline:install` si no apunta a `arkana-statusline` |
| `arkana-knowledge` | nada directo | Solo participa como plugin con `check` y datos exportables |

Los contratos de los demás plugins declaran `check` (messaging: `scripts/messaging.sh check --all`; agentic: `scripts/agentic.sh check`; statusline: `scripts/lib/ops.py check`; knowledge: `scripts/lib/knowledge.py validate`) y `requires` (messaging y agentic requieren `arkana-workspace`). `arkana-workspace` no declara `check` propio en el contrato: sus comprobaciones son las que `all.py` ejecuta directamente.

Orden recomendado de puesta en marcha: `/arkana-workspace:install` → `component add` por cada repo → `config tools` → instalar el resto de plugins → `fix` → `check`.

---

## 3. Modelo de datos y conceptos

### 3.1 Piezas, alias y rutas

- **ARKANA** es la pieza `arkana` (el repo con `.arkana/`). Los **componentes** son el resto. Todas se llaman *piezas*.
- Un alias canónico va en minúsculas (`^[a-z0-9][a-z0-9-]*$`). `arkana` y `all` están reservados; `shared` es sinónimo de entrada de `arkana` (id histórico). ARKANA se muestra en mayúsculas.
- La raíz del workspace es el `root` de `.arkana/arkana.json` (relativa a la carpeta de Arkana; por defecto `..`, el directorio padre). Las rutas del manifiesto son relativas a esa raíz, no pueden salir de ella (`..`), ni ser absolutas, ni empezar por `~`, y no pueden repetirse entre piezas.
- Un componente es **anidado** en otro cuando su carpeta cuelga de la de este (p. ej. `app-web` y `app-ui` dentro de `app`). Se usa en los permisos (no se edita lo anidado) y en `check` (identidad git de los anidados).

Ejemplo de disposición: `<raíz>/arkana` (ARKANA), `<raíz>/api`, `<raíz>/app`, `<raíz>/app/app-web`, `<raíz>/app/app-ui`, `<raíz>/docs`, `<raíz>/specs`.

### 3.2 Carpeta `.arkana/` (`<carpeta de Arkana>/.arkana/`, ignorada por git)

```
.arkana/
  arkana.json                    identidad del workspace y raíz               (config)
  .credentials                   CLAVE=valor, modo 600                        (secret)
  core/workspace.json            manifiesto portable                          (config)
  arkana-workspace/
    local.json                   rutas absolutas, identidad git, rutas de herramientas   (local)
    tools.json                   herramientas, URL y puertos                  (config; la ruta no viaja)
    bak/                         copias de seguridad de cada cambio           (local)
    bin/git-credential-arkana    envoltorio del asistente de credenciales      (local)
  arkana-messaging/ arkana-agentic/ arkana-statusline/ ...                    (datos de cada plugin)
```

Además, el registro por usuario `~/.arkana-workspaces.json` (`{"workspaces":[{"name","arkana","root"}]}`) permite localizar el workspace desde la carpeta de un componente, que no cuelga de Arkana. Lo crea `install`.

Clases de datos (las declara cada plugin en `arkana-plugin.json`):

| Clase | Qué es | Exportación |
|---|---|---|
| `config` | Portable | Siempre |
| `data` | Datos del plugin (mensajes, planes…) | Solo con `--include-data` |
| `local` | Propio de esta instalación | Nunca |
| `secret` | Credenciales | Nunca; solo viaja el nombre de la clave dentro del manifiesto |

Datos que declara este plugin: `arkana.json` (config), `core/workspace.json` (config), `arkana-workspace/tools.json` (config; sin `path`), `arkana-workspace/local.json` (local), `arkana-workspace/bak/` (local), `arkana-workspace/bin/` (local), `.credentials` (secret). Detalle del resto en [`../docs/DATA-LAYOUT.md`](../docs/DATA-LAYOUT.md).

### 3.3 `arkana.json`

`{"schema_version": 1, "workspace": {"name": "...", "id": "..."}, "root": ".."}`. `install` lo crea con el nombre del directorio padre de la carpeta de Arkana.

### 3.4 Manifiesto `core/workspace.json`

Esquema `workspace.schema.json` (sin propiedades adicionales). Estructura de primer nivel:

| Campo | Tipo | Significado |
|---|---|---|
| `schema` | entero ≥ 1 | Versión del esquema (obligatorio) |
| `workspace.name` | texto | Nombre del workspace |
| `jira.url`, `jira.token_ref` | texto | Jira del proyecto; `token_ref` es el **nombre** de la clave en `.credentials` (lo fija `config jira`) |
| `arkana` | bloque | La pieza ARKANA (obligatorio) |
| `components` | lista de bloques | Los componentes (obligatorio, puede estar vacía) |

Campos de cada bloque (ARKANA y componentes comparten los marcados «ambos»):

| Campo | Ámbito | Tipo | Significado y quién lo fija |
|---|---|---|---|
| `alias` | ambos | texto | Identificador. En ARKANA vale `ARKANA`. `component add --alias` |
| `path` | ambos | texto | Carpeta relativa a la raíz. `--path` (se guarda relativa) |
| `type` | componente (obligatorio) | `node` \| `maven` \| `docs` \| `generic` | Tipo de repo; los adaptadores de `arkana-agentic` y `handover` lo leen. `--type`, por defecto `generic` |
| `remote` | ambos | texto | URL del remoto **sin usuario ni contraseña**. `--remote` |
| `remote_host` | ambos | texto | Host del remoto; se deriva de `--remote`. Lo usan `sync`, `check` y el asistente de git |
| `branches.main`, `branches.develop` | ambos | texto | Ramas principal y de integración (por defecto `main` y `develop`). `--main`, `--develop` |
| `commit_format` | ambos | texto | `ia4d` (por defecto) o `conventional`. `--commit-format` |
| `git.token_ref` | ambos | texto | Nombre de la clave del token en `.credentials`. `--token-ref` |
| `git.username` | ambos | texto | Usuario con el que el asistente de git entrega el token (por defecto `oauth2`). `--git-username` |
| `git.email_domains` | ambos | lista de texto (`^[A-Za-z0-9.-]+$`) | Dominios de correo que debe tener el autor de los commits; sin lista no hay regla. `--git-email-domain` (repetible) |
| `seed_file` | ambos | `CLAUDE.md` \| `CLAUDE.local.md` | Fichero donde van los bloques gestionados; `CLAUDE.local.md` para los repos que no versionan su `CLAUDE.md`. `--seed-file` |
| `vpn` | componente | booleano | Si requiere VPN. `--vpn` / `--no-vpn`; `handover` lo muestra |
| `tools[]` | componente | lista `{tool, version}` | Herramientas y versiones que pide el componente. `--tool-version tool=ver` |
| `statusline` | componente | booleano | Si `arkana-statusline` lo muestra (sin la marca se muestra salvo los de tipo `docs`). `--statusline` / `--no-statusline`; este plugin no lo lee |
| `owner`, `label` | componente | texto | Admitidos por el esquema; ningún script de este plugin los lee ni hay opción para fijarlos |

Ejemplo mínimo:

```json
{
  "schema": 1,
  "workspace": {"name": "proyecto"},
  "jira": {"url": "https://jira.example.org", "token_ref": "JIRA_TOKEN"},
  "arkana": {"alias": "ARKANA", "path": "arkana", "commit_format": "conventional",
             "branches": {"main": "main", "develop": "develop"}},
  "components": [
    {"alias": "app", "type": "node", "path": "app", "remote": "https://git.example.org/team/app.git",
     "remote_host": "git.example.org", "commit_format": "conventional", "seed_file": "CLAUDE.local.md",
     "git": {"token_ref": "GIT_TOKEN", "email_domains": ["example.org"]},
     "tools": [{"tool": "node", "version": "20"}]},
    {"alias": "app-web", "type": "node", "path": "app/app-web"},
    {"alias": "api", "type": "maven", "path": "api", "vpn": true},
    {"alias": "docs", "type": "docs", "path": "docs"}
  ]
}
```

Cada cambio por `component`/`config jira` valida el resultado antes de escribir (esquema + alias, ruta relativa y única) y guarda `bak/workspace.json.<fecha-hora UTC>`.

### 3.5 `arkana-workspace/local.json` (clase `local`, modo 0644)

```json
{
  "schema_version": 1,
  "paths":      {"arkana": "/ruta/abs/arkana", "app": "/ruta/abs/app"},
  "git":        {"app": {"name": "Nombre Apellido", "email": "persona@example.org"}},
  "tool_paths": {"app": {"node": "/opt/node-20"}}
}
```

- `paths[alias]` manda sobre el `path` del manifiesto (`manifest.Workspace.path`). `install` lo rellena con las rutas absolutas reales.
- `git[alias]` guarda la identidad personal (`--git-user`, `--git-email`); nunca va al manifiesto.
- `tool_paths[alias][tool]` guarda la ruta local de una herramienta pedida por un componente (`--tool-path`).

### 3.6 `arkana-workspace/tools.json` (clase `config`, modo 0644)

```json
{
  "schema_version": 1,
  "tools": [
    {"tool": "node", "version": "20", "path": "/opt/node-20",
     "packages": ["@angular/cli@17", "typescript"],
     "registries": {"@acme": "https://registry.example.org/npm/"}},
    {"tool": "jdk", "version": "21", "path": "/opt/jdk-21"},
    {"tool": "maven", "version": "3.9"}
  ],
  "urls": ["https://registry.example.org"],
  "ports": [4200, 8080]
}
```

| Campo | Significado |
|---|---|
| `tools[].tool` | Nombre (`node`, `npm`, `jdk`, `maven`, `angular-cli`…; cualquier otro nombre se prueba como ejecutable `<nombre> --version`) |
| `tools[].version` | Versión esperada; basta un prefijo (`21` encaja con `21.0.13`; `1.8` con `1.8.0`) |
| `tools[].path` | Carpeta de la herramienta en esta máquina (`<path>/bin/<cmd>` o `<path>/<cmd>`). **No se exporta**; se conserva al importar |
| `tools[].packages` | Paquetes globales exigidos, `nombre[@versión]` (ámbitos npm incluidos). Hoy se comprueban los de `node` |
| `tools[].registries` | `ámbito → URL` de registros npm |
| `urls` | URL cuya respuesta comprueba `check --network` |
| `ports` | Puertos locales cuya ocupación comprueba `check` |

La versión efectiva de una herramienta sale de `tools[]` de los componentes y de `tools.json`; si hay conflicto manda `tools.json`.

### 3.7 `.credentials`

`CLAVE=valor`, una por línea, modo 600, sin comillas obligatorias (se admiten pares `'…'`/`"…"`). Nombres `^[A-Z][A-Z0-9_]*$`. Nunca se versiona (hay que ignorar `/.arkana/`), nunca se exporta ni se importa (se rechaza por nombre y por clase), y los permisos generados deniegan su lectura y edición a todos los actores, workers incluidos. El manifiesto solo lleva el nombre de la clave (`git.token_ref`, `jira.token_ref`). Cualquier informe sustituye los valores por `***`.

### 3.8 Qué se exporta

`export` incluye: `arkana.json`, `core/workspace.json` y `arkana-workspace/tools.json` sin `path`, más los datos de clase `config` de los demás plugins (y los de clase `data` con `--include-data`). No viaja nada de clase `local` ni `secret`, ni `.credentials`, `__pycache__`, `*.bak`, `.tmp-*` ni enlaces simbólicos.

### 3.9 Convención de commits y bloque `arkana:commits`

| Formato | Plantilla | Ejemplo |
|---|---|---|
| `ia4d` (por defecto) | `verbo(scope) descripción`, sin dos puntos | `docs(app) link setup guides from the README` |
| `conventional` | `tipo(scope): descripción`, con dos puntos. Tipos: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test` (es lo que exige `commitlint`) | `chore(app): ignore local Claude files` |

Reglas comunes que lleva el bloque: inglés, ≤72 caracteres, sin punto final, un solo objetivo por commit; **nunca** `Co-Authored-By` ni otra línea de coautoría (no es configurable) y **nunca** `--no-verify`; solo se hace commit o push cuando el usuario lo pide; los commits locales de una orquestación siguen el mismo formato.

El bloque se escribe entre `<!-- arkana:commits:start -->` y `<!-- arkana:commits:end -->`, con el encabezado «Convención de commits (arkana-workspace)». Se reemplaza entero al aplicarlo; lo de fuera no se toca. Destino: `<carpeta de Arkana>/CLAUDE.md` para ARKANA; para un componente, su `seed_file` (por defecto `CLAUDE.md`). El `scope` del ejemplo es el alias de la pieza.

---

## 4. Referencia de skills

Los 11 skills están en `skills/<nombre>/SKILL.md` y delegan en scripts de `scripts/lib/` y `scripts/checks/` (`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/..."`). Convenciones:

- **`--home DIR`**: carpeta de Arkana; por defecto se localiza (sección 7). Si no se encuentra workspace, los scripts salen con 3 (los que lo detectan antes de actuar).
- **`--component ALIAS`** (repetible donde se indica): acepta el alias en cualquier capitalización y el sinónimo `shared`; un alias desconocido sale con 3 en los comandos que lo validan.
- **`--json`**: sustituye la salida de texto por `{"plugin","skill","status","items":[{"id","status","detail","component"}],"summary":{...}}`.
- **`--dry-run`**: ensaya sin escribir; las líneas de efecto salen como `DRY`.
- Salida de texto: `ESTADO|ID|detalle` y `RESUMEN|n FAIL|n WARN` (sección 8).

Resumen:

| Skill | Escribe | Red | Script principal |
|---|---|---|---|
| `install` | `.arkana/*`, `~/.arkana-workspaces.json`, permisos | no | `lib/layout.py init` |
| `check` | nada | opcional (`--network`) | `checks/all.py` |
| `fix` | `settings.local.json`, `CLAUDE.md`, `.gitignore`… del componente | no | `checks/component.py` + `permissions.py`/`commits.py apply` |
| `component` | manifiesto, `local.json` | no | `lib/components.py` |
| `config` | manifiesto (`jira`), `tools.json` | no | `lib/config.py` |
| `status` | nada | no | `lib/status.py` |
| `sync` | referencias git (`FETCH_HEAD`, remotas) | sí, acotada | `lib/sync.py` |
| `rew-grants` | nada | no | `lib/permissions.py` |
| `export` | un ZIP | no | `lib/transfer.py export` |
| `import` | `.arkana/*` (con copia) | no | `lib/transfer.py import` |
| `handover` | opcionalmente un informe | no | `lib/handover.py` |

---

### 4.1 `/arkana-workspace:install`

**Para qué sirve.** Primera puesta en marcha, repetible: deja `.arkana/` completo y registra el workspace. Lo que ya existe no se pisa.

**Cuándo.** Al clonar Arkana en una máquina nueva o cuando falte algún fichero base. No lleva `--component` y solo funciona con el repo de Arkana (carpeta con `plugins/`). Ya no existe ni el modo «sin manifiesto» ni la migración desde disposiciones antiguas: `layout.py` solo tiene `init`.

**Orden exacta** (el skill pide confirmación antes de cada cambio):

1. `python3 scripts/lib/layout.py init --dry-run` y después `init`. Precondiciones: la carpeta tiene `plugins/`; no hay plan activo de `arkana-agentic` (estados `aprobado`, `ejecutando`, `verificando`, `pausado`, `borrador`, `integrando`); no hay procesos `launch.py`/`watchdog.py` vivos. Si todo existe y el workspace está registrado, responde `OK|layout|ya está inicializado`. Si no: copia de seguridad `.arkana/arkana-workspace/bak/layout-<fecha-hora>.tar.gz` (solo si ya hay `core/` o `arkana-workspace/`; modo 600; excluye `bak/`); crea `arkana.json`, `core/workspace.json` (solo ARKANA, con su remoto sin credenciales y ramas `main`/`develop`), `arkana-workspace/local.json` (rutas absolutas e identidad git leída de cada repo), `arkana-workspace/tools.json` (`{"schema_version":1,"tools":[]}`); registra el workspace en `~/.arkana-workspaces.json`. Si ya había manifiesto, se valida y se conserva.
2. `components.py list`; si falta alguno, `/arkana-workspace:component add`.
3. `permissions.py apply --dry-run`, confirmar y `apply` (ARKANA y cada componente; solo añade lo que falta).
4. `credentials.py check`; si una clave referenciada no existe, `credentials.py set <CLAVE>` (valor por stdin) y `credentials.py wire-git <alias>`.
5. `/arkana-statusline:install`.
6. `/arkana-messaging:install` y `/arkana-workspace:fix` (semillas, `.gitignore`, permisos y commits de cada repo).
7. `/arkana-workspace:check`. Hay que reiniciar Claude Code para ver los cambios.

**Parámetros de `layout.py init`:**

| Opción | Valores | Por defecto | Efecto y restricciones |
|---|---|---|---|
| `--dry-run` | flag | no | No escribe; las acciones salen como `DRY` (incluida la ruta de la copia) |
| `--json` | flag | no | Salida estructurada |
| `--home DIR` | ruta | la que localiza el workspace; si no hay ninguna, la carpeta que contiene el plugin | Carpeta de Arkana. Debe contener `plugins/`, si no `FAIL|home` |
| `--base DIR` | ruta | directorio padre de la carpeta de Arkana | Raíz del workspace; se guarda como `root` relativo en `arkana.json` |

**Errores (`FAIL`, salida 1):** `home` (no parece el repo de Arkana), `plan-activo`, `procesos`, `manifiesto` (el existente no valida: se muestran hasta 3 errores).

**Lee:** manifiesto y `local.json` existentes, `git config user.name/email` y `remote get-url origin` de cada repo (git local, 15 s de tope), plan activo en `arkana-agentic/state/` (o la disposición antigua). **Escribe:** lo indicado arriba (JSON atómicos). **Red:** no.

**Ejemplos:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/layout.py" init --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/layout.py" init --base /work/proyecto
```

---

### 4.2 `/arkana-workspace:check`

**Para qué sirve.** Diagnóstico de **solo lectura** del workspace entero: cada pieza (permisos, `CLAUDE.md`, commits, git, `.gitignore`, identidad), herramientas y entorno, credenciales y el `check` que declare cada plugin de Arkana.

**Cuándo.** Al abrir una sesión, tras `install`/`fix`, antes de lanzar un plan, o cuando algo falle. Para corregir, `fix`; para el detalle de permisos, `rew-grants`.

**Orden exacta:**

1. `python3 scripts/checks/all.py [--component A]... [--network] [--json]`. Para cada pieza elegida (todas por defecto): si su carpeta existe ejecuta la comprobación de componente (tabla de IDs más abajo; ID de salida `<alias>:<id>`), si no `<alias>:carpeta` `WARN|no existe`. Después **siempre**: `tools:*` (herramientas y entorno), `credenciales:*` y los `check` de los plugins. Última línea `RESUMEN|n FAIL|n WARN`.
2. Solo si el usuario lo pide o hay `WARN` de red: `python3 scripts/checks/vpn.py [--component A] [--no-write]`.
3. `/arkana-statusline:check` y `/arkana-messaging:check`.
4. El skill presenta una tabla con los `FAIL` primero y luego los `WARN`; agrupa los `OK`.

**Parámetros de `all.py`:**

| Opción | Valores | Por defecto | Efecto y restricciones |
|---|---|---|---|
| `--component A` | alias, repetible | todas las piezas | Limita la comprobación de piezas; `tools`, `credenciales` y plugins se ejecutan siempre. Alias desconocido → salida 3 |
| `--network` | flag | no | Activa lo que contacta con la red: `origin-accesible` por componente (`git ls-remote`, 10 s), `tools:red-*` (HTTP a los hosts remotos y a `urls`) y el HTTP de los registros |
| `--json` | flag | no | Salida estructurada |
| `--home DIR` | ruta | localizada | Carpeta de Arkana |
| `--plugins-dir DIR` | ruta | `<carpeta de Arkana>/plugins` | Dónde buscar `arkana-plugin.json` de los demás plugins |

> El `SKILL.md` dice que `--dry-run` «se acepta y no hace nada»; `all.py` **no** lo define (`unrecognized arguments`, salida 2). Basta no pasarlo: el script ya es de solo lectura.

**Códigos de salida:** 0 sin `FAIL`; 1 con algún `FAIL`; 2 uso incorrecto; 3 sin workspace o alias desconocido.

**Check de plugins.** Para cada carpeta de `plugins/` con `arkana-plugin.json` (salvo `arkana-workspace`): contrato inválido → `<plugin>:contrato` `FAIL`; sin `check` declarado → `<plugin>:check` `INFO`; si lo declara se ejecuta con `bash -c` en la carpeta del plugin, sin stdin, 120 s de tope, con `ARKANA_HOME` y `CLAUDE_PLUGIN_ROOT` en el entorno. Se reproducen sus líneas `ESTADO|ID|detalle` como `<plugin>:<ID>`. Tiempo agotado → `FAIL|<plugin>:check|tiempo agotado`; sin salida en el formato común → `FAIL` si el código de retorno no es 0, `WARN` si lo es.

**IDs de la comprobación de componente** (`checks/component.py`; los muestra `<alias>:<id>`). `FAIL`/`WARN` es el nivel con el que se emiten; `fix` indica quién lo corrige:

| ID | Qué comprueba | Niveles |
|---|---|---|
| `componente` | Alias y ruta | INFO |
| `carpeta` | Existe la carpeta | FAIL |
| `arkana-presente`, `arkana-escribible` | Existe ARKANA y se puede escribir en ella | OK/FAIL |
| `permisos` | `settings.local.json` frente al modelo (`permissions.diff`); FAIL si hay `missing`, `weaker` o `bash-missing`; WARN con el resto | OK/WARN/FAIL |
| `claude-md` | Existe `CLAUDE.md` (o `CLAUDE.local.md` si el componente lo declara como `seed_file`) | OK/INFO/FAIL |
| `commits` | El bloque `arkana:commits` está al día con `commit_format` | OK/WARN/FAIL (formato desconocido) |
| `git-repo` | Es un repo git; si no, `WARN` y termina | WARN |
| `gitignore-env`, `gitignore-claude`, `gitignore-claude-session` | `.env`, `.claude/` y `.claude-session/` ignorados | OK/FAIL |
| `env-versionado`, `env-historial` | Ningún `.env*` (salvo `.env.example`) versionado ni en el historial | OK/FAIL |
| `env-example` | Existe `.env.example` | OK/WARN |
| `git-identidad` | `user.email` coherente con `git.email_domains` (sin regla: cualquiera; sin remoto: no se comprueba) | OK/WARN/FAIL |
| `gitattributes-eol` | `.gitattributes` con `eol=lf` | OK/WARN |
| `husky-hooks` | Los ficheros de `.husky/` son ejecutables | OK/FAIL |
| `rama` | Rama actual es la `develop` o la `main` esperadas | OK/WARN |
| `origin-accesible` | `git ls-remote` a `origin` (solo con red) | OK/WARN |
| `anidado-<alias>` | Remoto e identidad git de cada componente anidado | OK/WARN/FAIL |

**IDs de herramientas y entorno** (`checks/tools.py`, dirigido por datos: nada está fijado en el código). Se muestran como `tools:<id>`:

| ID | Qué comprueba | Niveles |
|---|---|---|
| `entorno` | Alias de ARKANA y su carpeta | INFO |
| `herramientas` | No hay ninguna declarada (indica cómo declararla) | INFO |
| `<tool>` | Ejecutable (en `<path>/bin/<cmd>`, `<path>/<cmd>` o `PATH`) y versión por **prefijo** (`21` ≙ `21.0.13`). Ejecutables por herramienta: `node`→`node -v`, `npm`→`npm -v`, `jdk`→`java -version`, `maven`→`mvn -v` (con `JAVA_HOME` del `jdk` declarado); el resto, `<nombre> --version`. La versión es la primera cadena numérica de la salida | OK/WARN (otra versión)/FAIL (no disponible) |
| `<tool>-paquete-<paquete>` | Paquetes globales declarados, con `npm ls -g --depth=0 --json` (20 s) y el `node` declarado. Falta → FAIL; versión distinta (igualdad exacta si se pidió `@versión`) → WARN; para herramientas que no son `node` → INFO «no se sabe comprobar» | OK/WARN/FAIL/INFO |
| `registro-<ámbito>` | `~/.npmrc` contiene `<ámbito>:registry=<url>`: ausente → FAIL; distinta URL (sin contar la `/` final) → WARN; igual → con `--network` además un GET a la URL (cualquier código HTTP vale; sin respuesta → WARN) | OK/WARN/FAIL |
| `node-claude` | `node` activo en el `PATH` es ≥ 20 (lo necesitan Claude Code y sus plugins) | OK/WARN/FAIL |
| `git`, `git-longpaths`, `git-credential-helper` | git instalado; `core.longpaths=true` y `credential.helper` globales | OK/WARN/FAIL |
| `cred-<host>` | Por cada `remote_host` de las piezas: hay entrada `@host` en `~/.git-credentials` o la clave `git.token_ref` existe en `.credentials` (solo existencia) | OK/FAIL |
| `red-<host\|url>` | Con `--network`: GET a `https://<host>` y a cada `urls` | OK/WARN |
| `puerto-<n>` | Cada `ports` está libre en `127.0.0.1` (ocupado → WARN). Siempre, también sin `--network` | OK/WARN |
| `jq`, `python3` | Instalados | OK/FAIL |
| `jira-env` | `~/.ia4d/.env` (o `~/.claude/.env`) con `JIRA_HOST` y `JIRA_API_TOKEN`, sin mostrar valores; falta → FAIL, vacío o `<…>` → WARN | OK/WARN/FAIL |
| `jira-env-proyecto` | Algún `.env` de componente define `JIRA_*` (el conector no lo lee) | WARN |
| `jira-mcp`, `jira-mcp-deps`, `jira-mcp-duplicado` | Conector Jira del plugin `ia4d-project-bridge` (localizado con `claude plugin list`): existe, dependencias instaladas y sin `mcpServers.jira-connector` duplicado en `~/.claude/settings.json` | OK/WARN/FAIL |

**IDs de credenciales** (`credenciales:<id>`): `credentials` (INFO, no hay fichero), `credentials-modo` (600), `credentials-ignorado` (git lo ignora), `credentials-valores` (sin claves vacías).

**`vpn.py` (opcional, paso 2):**

| Opción | Efecto |
|---|---|
| `--component A` | Repetible; limita las piezas |
| `--no-write` | No comprueba escritura (omite `git push --dry-run`) |
| `--no-network` | No resuelve ni contacta con hosts remotos; los repos con remoto salen como `INFO` «omitido» |
| `--json`, `--home` | Como arriba |

Por **host** distinto (IDs `red-<host>`): DNS (`getent hosts`, 8 s) y GET `https://host` (10 s); sin DNS → `FAIL` «¿VPN desconectada?». Por **repo** (ID `repo-<alias>`): lectura con `git ls-remote --heads origin` y, salvo `--no-write`, escritura con `git -c core.hooksPath=/dev/null push --dry-run origin HEAD:refs/heads/<rama>` (contacta con el servidor y no sube nada). Un fallo se clasifica en red/VPN, credenciales, permisos o repositorio inexistente. Las URL se muestran sin usuario ni contraseña. Hasta 6 repos en paralelo. **Si el DNS se queda colgado**, no insistas: es la red del contenedor o de la VPN.

`checks/component.py` también se puede lanzar solo: `component.py [--component A] [--home DIR] [--json] [--no-network]`. Sin `--component` deduce la pieza del directorio actual (la más específica que lo contiene); a diferencia de `all.py`, **por defecto sí** hace `ls-remote`.

**Lee:** manifiesto, `local.json`, `tools.json`, `.credentials` (solo claves), `settings.local.json`, ficheros de cada repo, git local, `~/.npmrc`, `~/.git-credentials` (solo para buscar `@host`), `~/.claude/settings.json`, `~/.ia4d/.env` (solo nombres). **Escribe:** nada. **Red:** solo con `--network` (y siempre en `vpn.py` salvo `--no-network`).

**Ejemplos:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/checks/all.py"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/checks/all.py" --component app --component api --network --json
```

---

### 4.3 `/arkana-workspace:fix`

**Para qué sirve.** Corrige, **una por una y con confirmación**, lo que marca el check de componente. No tiene un script propio: el skill orquesta las herramientas de este plugin.

**Cuándo.** Después de `check` cuando haya `FAIL`/`WARN` corregibles, en el componente actual o en el indicado con `--component <alias>`.

**Orden exacta:**

1. `python3 scripts/checks/component.py [--component <alias>] --no-network` (solo lectura). Sin `FAIL` ni `WARN`, termina.
2. Para cada `FAIL`/`WARN`, en el orden de la tabla: explica qué es y qué cambiará; pregunta (aplicar / saltar / parar); si se acepta, copia `<fichero>.bak` si existe, aplica y vuelve a comprobar ese ID.
3. Repite la comprobación y resume: corregido / saltado / sin resolver.

**Parámetros.** El skill solo admite `--component <alias>` (y `--dry-run` en las herramientas que lo soportan, para ensayar). Las herramientas que invoca:

| Herramienta | Opciones |
|---|---|
| `permissions.py apply` | `--component A` (repetible), `--home`, `--json`, `--dry-run`, `--prune` |
| `commits.py apply` | `--component A` (repetible), `--home`, `--json`, `--dry-run` |

**Arreglos por ID:**

| ID | Arreglo |
|---|---|
| `arkana-presente` | No se arregla aquí: hay que clonar el repo de Arkana en la carpeta del workspace |
| `permisos` | `permissions.py apply --component <alias>` (con `--dry-run` primero). Solo **añade** lo que falta y limpia duplicados, reglas `legacy` y `deny Write` redundantes; deja copia en `.arkana/arkana-workspace/bak/` y el fichero en modo 0600. Para **quitar** lo que concede de más, preguntar y usar `--prune`. Una regla nueva se añade al modelo (`lib/permissions.py`), nunca a mano en `settings.local.json` |
| `commits` | `commits.py apply --component <alias>` (`--dry-run` primero). Si falta el `CLAUDE.md` versionado, arreglar antes `claude-md` |
| `claude-md` | Copiar `<carpeta de Arkana>/plantillas/CLAUDE.modulo.md` como `CLAUDE.md` y rellenar nombre y descripción preguntando |
| `gitignore-env`, `gitignore-claude`, `gitignore-claude-session` | Añadir al `.gitignore` lo que falte: `.env`, `.env.*`, `!.env.example`, `.claude/`, `.claude-session/`, `node_modules/` |
| `gitattributes-eol` | Crear o ampliar `.gitattributes` con `* text=auto eol=lf` |
| `env-example` | Crear `.env.example` con los **nombres** de las variables del `.env` real (nunca los valores) |
| `env-versionado` | Explicar `git rm --cached <fichero>` y que hay que **rotar las credenciales**; ejecutarlo solo con confirmación. Sin commit |
| `env-historial` | Solo informar: rotar credenciales y limpiar el historial (manual y delicado) |
| `git-identidad`, `anidado-<alias>` | `git config user.email <correo>` a nivel de repo y con confirmación; no tocar `~/.gitconfig` |
| `jira-mcp`, `jira-mcp-deps` | Plugin `ia4d-project-bridge` ausente: indicar que se instale y habilite. Con confirmación, `npm install --omit=dev` en el `mcp/jira-connector` que indica el check |
| `jira-mcp-duplicado` | Quitar la clave `mcpServers.jira-connector` de `~/.claude/settings.json` (con copia `.bak` y parche mínimo) |
| `jira-env-proyecto` | Mover las variables `JIRA_*` del `.env` del proyecto a `~/.ia4d/.env`, sin mostrar valores |
| `husky-hooks` | `chmod +x` de los hooks listados |
| `rama`, `origin-accesible` | Solo informar (dependen del usuario o de la red/VPN) |

Sin arreglo en el skill: `arkana-escribible` (permisos del sistema de ficheros) y `git-repo` (`git init` y remoto los decide el usuario).

**Reglas.** Interactivo siempre (nunca varios cambios con una confirmación), no leer ni mostrar valores de `.env`/tokens, sin commit ni push, idempotente. **Escribe:** `settings.local.json` (0600), `CLAUDE.md`/`CLAUDE.local.md`, `.gitignore`, `.gitattributes`, `.env.example`, `.husky/*` (permisos), `git config` local, siempre con copia. **Red:** no (el check se lanza con `--no-network`).

**Ejemplo:**

```text
/arkana-workspace:fix --component app
  -> permisos: missing app:Edit esperado REW efectivo R··   ¿Aplicar? (aplicar / saltar / parar)
  -> commits: SIN-BLOQUE                                     ¿Aplicar? ...
```

---

### 4.4 `/arkana-workspace:component`

**Para qué sirve.** Altas, cambios y bajas de componentes en el manifiesto, y cambios en las directrices de ARKANA (commits, remoto, ramas, identidad).

**Cuándo.** Al incorporar o quitar un repo, cambiar su remoto, tipo, formato de commits o dominios de correo, o fijar su identidad git y rutas de herramientas locales.

**Orden exacta del skill:**

1. `components.py list` para ver el estado. Para `add`/`edit`/`remove`: recoger lo que falte, **ensayar con `--dry-run`** y confirmar.
2. Tras `add`/`edit`: ofrecer `permissions.py apply --component <alias> --dry-run` y luego sin `--dry-run`; y `credentials.py wire-git <alias>` si tiene `--token-ref`.
3. Si el token no existe: `credentials.py set <CLAVE>` (valor por stdin, nunca como argumento).

`python3 scripts/lib/components.py <list|add|edit|remove> [opciones]`

**Parámetros:**

| Opción | Valores | Por defecto | Efecto y restricciones |
|---|---|---|---|
| `cmd` (posicional) | `list`, `add`, `edit`, `remove` | obligatorio | Operación |
| `--alias` | `^[a-z0-9][a-z0-9-]*$` (se normaliza a minúsculas) | — | Obligatorio en `add`, `edit` y `remove`. `arkana`, `all` y `shared` están reservados para `add`; `--alias arkana` en `edit` edita ARKANA. Alias repetido → error |
| `--path` | ruta absoluta o relativa a la raíz | — | Obligatorio en `add`. Se guarda **relativa** a la raíz; debe estar dentro de ella y no repetirse. En `edit`, si `local.json` ya fija la ruta absoluta de la pieza, se actualiza también. No exige que exista la carpeta |
| `--type` | `node`, `maven`, `docs`, `generic` | `generic` en `add` | Tipo de repo. Rechazado para ARKANA |
| `--remote` | URL | — | Remoto **sin usuario ni contraseña** (`https://user@host/…` se rechaza). Deriva `remote_host` |
| `--main`, `--develop` | texto | `main` / `develop` | Si se da uno, se fijan ambos (el otro conserva su valor o el por defecto) |
| `--git-user`, `--git-email` | texto | — | Identidad personal; va a `local.json` (`git[alias]`), no al manifiesto |
| `--git-username` | texto | — | `git.username` del manifiesto (usuario con el que el asistente de git entrega el token; por defecto `oauth2`) |
| `--token-ref` | nombre de clave | — | `git.token_ref`: **solo el nombre** de la clave de `.credentials`, nunca el valor |
| `--git-email-domain` | dominio (`^[A-Za-z0-9.-]+$`; se elimina un `@` inicial) | sin regla | **Repetible**. Fija `git.email_domains`: **sustituye** la lista entera por los dominios dados. `check` exige que `user.email` termine en uno de ellos. Sin la opción, no cambia lo que haya |
| `--commit-format` | `ia4d`, `conventional` | `ia4d` (efectivo si falta) | El CLI acepta cualquier texto; un valor distinto de los dos hace fallar `commits.py` y `check` (`commits`) con «commit_format desconocido» |
| `--vpn` / `--no-vpn` | flags | sin definir | Guarda `vpn: true/false`. Rechazado para ARKANA |
| `--statusline` / `--no-statusline` | flags | sin definir | Guarda `statusline: true/false`: fuerza mostrar u ocultar el componente en la barra de `arkana-statusline`. Rechazado para ARKANA, que siempre se muestra |
| `--tool-version tool=ver` | repetible | — | Añade o cambia `tools[]` del componente. Formato `nombre=valor` (si no, error). Rechazado para ARKANA |
| `--tool-path tool=ruta` | repetible | — | Ruta local de la herramienta; va a `local.json` (`tool_paths[alias]`). Rechazado para ARKANA |
| `--seed-file` | `CLAUDE.md`, `CLAUDE.local.md` | `CLAUDE.md` efectivo | Fichero de Claude Code donde van los bloques gestionados |
| `--yes` | flag | no | Confirma `remove` (obligatorio salvo con `--dry-run`); solo quita del manifiesto, la carpeta y el repo no se tocan |
| `--home` | ruta | localizada | Carpeta de Arkana |
| `--dry-run` | flag | no | Valida y muestra sin escribir |
| `--json` | flag | no | Salida estructurada |

**Qué admite cada subcomando.** `list`: `--home`, `--json`. `add`: todo salvo `--yes`. `edit`: todo salvo `--yes` y, con `--alias arkana`, también `--type`, `--path`, `--vpn/--no-vpn`, `--statusline/--no-statusline`, `--tool-version`, `--tool-path` (error «no se aplica a ARKANA»); para ARKANA sí valen `--commit-format`, `--git-email-domain`, `--remote`, `--main`, `--develop`, `--token-ref`, `--git-username`, `--seed-file`, `--git-user`, `--git-email`. `remove`: `--alias`, `--yes`, `--dry-run`; ARKANA no se puede quitar.

**Salida.** `list`: una línea `INFO|<alias>|<tipo> <ruta> <host>` por pieza (ARKANA con tipo `arkana`). `add`/`edit`/`remove`: `OK|<alias>|...` o `DRY|...`. Errores → `FAIL|<operación>|motivo`, salida 1; sin workspace, salida 3.

**Escribe:** `core/workspace.json` (tras validar, con copia `bak/workspace.json.<hora UTC>`) y `local.json` si hay identidad, rutas de herramientas o ruta absoluta nueva. **Red:** no. **Idempotente.** Nunca se aceptan secretos como argumento.

**Ejemplos:**

```bash
# alta de un componente anidado con commitlint y dominio de correo exigido
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/components.py" add --alias app-ui --path app/app-ui --type node \
  --remote https://git.example.org/team/app-ui.git --commit-format conventional \
  --git-email-domain example.org --git-email-domain example.com --token-ref GIT_TOKEN --tool-version node=20 --dry-run

# directrices de ARKANA: formato de commits, dominios de correo y fichero de semilla
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/components.py" edit --alias arkana --commit-format ia4d --git-email-domain example.org
```

---

### 4.5 `/arkana-workspace:config`

**Para qué sirve.** Configuración general que no es de un componente: las herramientas del proyecto (`tools.json`) y, como **extensión opcional**, el bloque `jira` del manifiesto (si no existe, no se comprueba nada de Jira).

**Cuándo.** Al preparar un workspace nuevo o cuando cambien versiones, rutas locales, paquetes globales, registros, URL o puertos que `check` deba vigilar.

**Orden exacta:** 1) mostrar la configuración actual (`jira` y `tools` sin opciones); 2) si el usuario quiere cambiar algo, `--dry-run`, confirmar y aplicar; 3) para rutas de repos, altas o bajas, usar `component`.

`python3 scripts/lib/config.py <jira|tools> [opciones]`. Comunes: `--home DIR`, `--dry-run`, `--json`.

**`config jira`:**

| Opción | Efecto |
|---|---|
| `--url URL` | Guarda `jira.url` en el manifiesto (exportable) |
| `--token-ref CLAVE` | Guarda `jira.token_ref`: el **nombre** de la clave en `.credentials` (valor con `credentials.py set <CLAVE>`) |
| `--show` | Se acepta pero no cambia nada: sin `--url` ni `--token-ref` siempre se listan las claves `jira.*` |

Escribe en el manifiesto (con validación y copia `.bak`) solo si se da `--url` o `--token-ref`. Salida: `OK|jira|…` y una línea `INFO|jira.<clave>|<valor>` por clave.

**`config tools`:**

| Opción | Valores | Por defecto | Efecto y restricciones |
|---|---|---|---|
| `--tool` | texto (`node`, `jdk`, `maven`, `angular-cli`…) | — | Herramienta a registrar. Si ya existía, se parte de lo guardado |
| `--version` | texto | la ya guardada | Versión esperada. **Obligatoria** al registrar una herramienta nueva (`--tool necesita --version`) |
| `--path` | ruta | la ya guardada | Dónde está la herramienta en esta máquina. Se guarda tal cual; **no se exporta**. `arkana-agentic` la pone en el `PATH` de sus verificaciones y, si la herramienta es `jdk`, en `JAVA_HOME` |
| `--package` | `paquete[@versión]`, repetible | — | Paquetes globales exigidos. **Se suman** a los guardados (unión ordenada). Exige `--tool`; hoy `check` solo los comprueba para `node` |
| `--registry` | `ÁMBITO=URL`, repetible | — | Registros por ámbito (p. ej. `@acme=https://registry.example.org/npm/`). Se **fusionan** con los guardados (un ámbito repetido se sobrescribe). Exige `--tool`. `check` los compara con `~/.npmrc`; `arkana-agentic` escribe ese `.npmrc` en sus verificaciones |
| `--check-url` | URL, repetible | — | URL cuya respuesta comprueba `check --network`. Se añaden sin duplicar, conservando el orden. No exige `--tool` |
| `--port` | entero, repetible | — | Puerto local cuya ocupación comprueba `check`. Unión ordenada. No exige `--tool` |

Reglas: `--package` o `--registry` sin `--tool` → `FAIL` («necesitan --tool»). **Volver a registrar una herramienta conserva lo que no se repite** (versión, ruta, paquetes, registros). Para quitar un elemento hay que editar `tools.json` a mano. Sin ninguna opción lista las herramientas (`INFO|<tool>|<versión> ruta local · paquetes: … · registros: …`) y, si no hubo cambios, también `urls` y `ports`. Las versiones por componente se dan con `component edit --tool-version`.

**Escribe:** `.arkana/arkana-workspace/tools.json` (atómico, solo si hubo cambios y no es `--dry-run`). **Red:** no. Salida 1 con `FAIL`, 3 sin workspace.

**Ejemplos:**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/config.py" tools --tool node --version 20 --path /opt/node-20 \
  --package @angular/cli@17 --registry @acme=https://registry.example.org/npm/ --port 4200
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/config.py" tools --check-url https://registry.example.org --port 8080
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/config.py" jira --url https://jira.example.org --token-ref JIRA_TOKEN --dry-run
```

---

### 4.6 `/arkana-workspace:status`

**Para qué sirve.** Estado git **local** de ARKANA y de cada componente en una línea cada uno.

**Cuándo.** Antes de empezar a trabajar o de lanzar un plan, o para localizar repos con cambios.

**Orden exacta:** `python3 scripts/lib/status.py [--component A]... [--json]`; el skill presenta la tabla tal cual y resalta las piezas con cambios sin subir o por bajar.

| Opción | Efecto |
|---|---|
| `--component A` | Repetible; limita las piezas (alias desconocido → salida 3) |
| `--home DIR` | Carpeta de Arkana |
| `--json` | Estructurado; cada pieza lleva además `git: {branch, untracked, staged, modified, ahead, behind, has_remote}` |

**Salida.** `OK|<alias>|ARKANA develop ✓` si está limpia y `INFO|<alias>|ARKANA develop ◌13 ✚113 ●84 ⇡2 ⇣3` si no. Símbolos: `◌` sin seguimiento, `✚` preparados, `●` modificados, `⇡` commits sin subir, `⇣` commits por bajar (`⇣?` si no se sabe). `◌ ✚ ● ⇡` salen siempre de git local (`status --porcelain=v2 --branch -uall`, 10 s de tope, sin bloqueos opcionales). **Solo `⇣` depende del remoto**: es el número si el último `fetch` correcto (mtime de `.git/FETCH_HEAD`) fue hace menos de 30 minutos; si no, `⇣?`. Sin remoto o sin rama remota no se muestran flechas. `WARN` si la carpeta no existe o no es un repo. Salida 0 siempre (3 sin workspace). **Escribe:** nada. **Red:** no; para refrescar `⇣`, `sync`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/status.py" --component app --component api
```

---

### 4.7 `/arkana-workspace:sync`

**Para qué sirve.** Hace `git fetch` de los remotos de ARKANA y de los componentes para que `⇣` esté al día. **No integra**: nada de `pull`, `merge`, `rebase`, `push` ni commit, y no toca ficheros ni ramas locales.

**Cuándo.** Al empezar el día, antes de un plan o de decidir si hay que integrar algo.

**Orden exacta:** `python3 scripts/lib/sync.py [--component A]... [--no-fetch] [--json]`. Por pieza: carpeta inexistente → `WARN`; no es repo → `WARN`; si tiene algún remoto y hay `fetch`: comprueba el DNS de su `remote_host` (`getent hosts`, 3 s; una vez por host y ejecución) y, solo si resuelve, `git fetch --quiet --prune` con tope de 20 s; después muestra su estado. Hasta 4 piezas en paralelo.

| Opción | Efecto |
|---|---|
| `--component A` | Repetible; limita las piezas |
| `--no-fetch` | No toca la red; solo muestra el estado |
| `--home DIR`, `--json` | Como siempre |

**Contención de red.** (a) DNS previo con tope de 3 s: sin VPN no se intenta nada y se avisa (`WARN|<alias>|sin red: <host> no resuelve…`). (b) Cada `fetch` corre en su propio grupo de procesos y se mata el grupo entero al vencer los 20 s; además git se rinde si la conexión baja de 1 KB/s durante 15 s. (c) **Cortacircuitos** compartido entre procesos: tras un fallo (DNS o tiempo agotado) las operaciones de red siguientes fallan al instante durante 60 s (fichero `ARKANA_NET_BREAKER_FILE` o `<tmp>/arkana-net-breaker-<uid>.json`); un DNS correcto lo restablece. Un fallo de fetch se informa como `WARN|<alias>|fetch falló: <primera línea>`.

**Salida.** `OK|<alias>|<estado>` (como `status`) o `WARN`. Salida 0 (no emite `FAIL`), 2 uso incorrecto, 3 sin workspace. **Escribe:** solo referencias de git (`FETCH_HEAD`, ramas remotas, `--prune`). **Red:** sí, acotada.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/sync.py"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/sync.py" --component api --json
```

Si algo está por bajar, se informa al usuario y se le pregunta; integrar es decisión suya.

---

### 4.8 `/arkana-workspace:rew-grants`

**Para qué sirve.** Compara **lo que debería poder hacer cada actor** (modelo generado desde el manifiesto) con **lo que de verdad le concede** su `.claude/settings.local.json`, y lista las desviaciones. Solo lectura; corrige `fix`.

**Cuándo.** Tras cambiar el manifiesto, ante un permiso inesperado, o para regenerar la tabla de permisos de la documentación.

**Modelo esperado** (`permissions.expected`):

- ARKANA: R/E/W sobre sí misma y sobre todos los componentes.
- Cada componente: R/E/W sobre sí mismo y sobre ARKANA; solo R sobre los demás, con `deny Edit` explícito; sobre los anidados en su carpeta: R y `deny Edit`; sobre la carpeta que lo contiene: solo R, sin `deny` (taparía lo suyo).
- Para todos: `deny Read` y `deny Edit` de `.arkana/.credentials`; `deny Edit` de `.arkana/arkana-agentic/` (lo escribe `agentic.sh`); `allow Read` de `~/.claude/settings.json` (los check de herramientas lo leen).
- Solo ARKANA: `allow Bash(<ruta>/agentic.sh *)` en las dos ubicaciones del plugin (copia de trabajo y caché), `ask` para las decisiones humanas (`plan approve`, `approve`, `reject`, `policy set`, `integrate merge`, `integrate discard`) y `deny Bash(claude -p *)`, `claude --print *` y `claude --bg *`.
- Reglas de ruta: `//ruta/absoluta`, `/relativa-a-la-raíz-de-ajustes`, `~/bajo-el-home`; precedencia `deny` > `ask` > `allow`; `Edit` cubre `Write`.

**Orden exacta:**

1. `python3 scripts/lib/permissions.py matrix --expected` y `matrix --effective`. Filas = actores, columnas = piezas más `.credentials`, `agentic-state` y `core`. La celda muestra **solo las letras concedidas**: **R**ead, **E**dit, **W**rite; mayúscula = concedido, minúscula = pregunta (`ask`). `Rxx` se ve `R`; `xxx` se ve vacía: **celda vacía = sin ningún acceso** (denegado o sin regla). La diagonal es `REW` para todos, también ARKANA.
2. `permissions.py diff [--component A] [--json]` (o `status`, que es lo mismo).
3. El skill presenta primero la matriz efectiva, resalta lo que difiere de la esperada y lista las desviaciones (`FAIL` antes que `WARN`); las reglas `Bash` aparte. Si hay desviaciones, remite a `fix`.

**Subcomandos y opciones de `permissions.py`:**

| Subcomando | Qué hace |
|---|---|
| `expected` / `effective` | Imprime en JSON las reglas esperadas o las del `settings.local.json` de cada actor (`{"allow","ask","deny"}`). Salida 0 |
| `matrix` | Matriz (ver opciones). Salida 0 |
| `diff` / `status` | Desviaciones. Salida 1 si alguna es `FAIL` |
| `apply` | Genera o completa los permisos (lo usa `fix`; ver 4.3) |

| Opción | Valores | Por defecto | Efecto |
|---|---|---|---|
| `--component A` | repetible | todas las piezas | Limita a esas filas/actores (alias desconocido → salida 3) |
| `--expected` | flag | sí (en `matrix`) | Matriz del modelo |
| `--effective` | flag | no | Matriz de los ajustes reales (si se dan los dos, gana `--expected`) |
| `--format` | `text`, `md` | `text` | `md` genera la tabla Markdown de permisos para la documentación |
| `--json` | flag | no | En `matrix` imprime `{actor: {destino: "REW"\|"Rxx"\|"R··"…}}` y **conserva las tres posiciones**: `x` = denegado, `·` = sin regla; es lo que usa `diff`. En `diff` es el informe estructurado |
| `--home DIR` | ruta | localizada | Carpeta de Arkana |
| `--dry-run`, `--prune` | flags | no | Solo para `apply` |

**Tipos de desviación (`diff`):**

| Tipo | Nivel | Significado |
|---|---|---|
| `missing` | FAIL | Falta lo esperado (o falta el fichero `settings.local.json` entero) |
| `weaker` | FAIL | Concede menos de lo esperado (pregunta o deniega donde debía conceder) |
| `bash-missing` | FAIL | Faltan reglas `Bash` del orquestador |
| `stronger` | WARN | Concede más donde se esperaba `deny` o `ask` |
| `extra` | WARN | Concede donde no se esperaba nada |
| `legacy` | WARN | Regla `/ruta` con una barra, que Claude lee relativa a la raíz del repo: debe ser `//ruta` |
| `duplicate` | WARN | Regla repetida |
| `obsolete` | WARN | `deny Write` redundante (`Edit` ya lo cubre) |
| `mode` | WARN | Fichero con modo distinto de 0600 |

Las reglas ajenas al modelo (p. ej. `Bash(ls *)`) no cuentan como desviación. IDs de salida: `perm:<alias>` (`OK` si conforme, `WARN` si la carpeta no existe) y `perm:<alias>:<tipo>`.

**`apply`** (lo invoca `fix` y `install`): añade lo que falta sin quitar reglas ajenas; limpia duplicados, `legacy` y `deny Write`; no añade un `allow` que una regla más fuerte tape (se informa en `diff`); con `--prune` quita además los `allow` que dan más de lo esperado (nunca `~/.claude/settings.json`). Copia previa en `.arkana/arkana-workspace/bak/<alias>-settings.local.json.<hora>`, fichero resultante en modo 0600. Con `--dry-run` lista los cambios (`INFO|perm:<alias>:añadir|quitar`). Sin `--component` actúa sobre todas las piezas.

**Escribe:** nada (salvo `apply`). **Red:** no.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" matrix --effective --component app
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" matrix --expected --format md
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" diff --json
```

Ejemplo de matriz esperada con ARKANA y tres componentes:

```text
actor   arkana app api docs .credentials agentic-state core
ARKANA  REW    REW REW REW             R             REW
app     REW    REW R   R               R             REW
api     REW    R   REW R               R             REW
docs    REW    R   R   REW             R             REW
```

---

### 4.9 `/arkana-workspace:export`

**Para qué sirve.** Empaqueta la configuración del workspace (y, con `--include-data`, los datos de los plugins) en un ZIP verificable, para llevarla a otra máquina o guardarla.

**Cuándo.** Al cambiar de máquina, antes de reinstalar o para compartir la configuración (sin secretos).

**Orden exacta:** 1) si falta `--out`, proponer `arkana-export-<fecha>.zip` fuera del repo de Arkana (no sobrescribe un ZIP existente salvo `--force`; preguntar antes); 2) `--dry-run` primero si hay duda, y enseñar la lista; 3) ejecutar y resumir (nº de ficheros, si lleva datos y los `WARN`).

`python3 scripts/lib/transfer.py export --out FICHERO.zip [--include-data] [--force] [--home DIR] [--dry-run] [--json]`

| Opción | Valores | Por defecto | Efecto y restricciones |
|---|---|---|---|
| `--out` | ruta | **obligatoria** | ZIP de salida. Si existe y no hay `--force` ni `--dry-run` → `FAIL` |
| `--include-data` | flag | no | Incluye también los datos de clase `data` de los plugins |
| `--force` | flag | no | Permite sobrescribir el ZIP |
| `--home DIR` | ruta | localizada | Carpeta de Arkana |
| `--dry-run` | flag | no | Lista lo que entraría (`DRY|export:<ruta>|<clase> (<bytes>)`) sin crear el ZIP |
| `--json` | flag | no | Salida estructurada |

**Qué viaja.** Lo declara cada plugin en su `arkana-plugin.json`: `config` siempre; `data` solo con `--include-data`; `local` y `secret` nunca. `tools.json` viaja sin `path`. Se omiten `.credentials`, `__pycache__`, `*.bak`, `.tmp-*`, enlaces simbólicos (`WARN`), ficheros de más de 50 MB (`WARN`) y `tools.json` no válido (`WARN`). Límites del conjunto: 5000 ficheros y 200 MB. Los contratos se buscan en `$ARKANA_PLUGINS_DIR` (si está definida), `<carpeta de Arkana>/plugins` y la carpeta de plugins que contiene este plugin.

**Contenido del ZIP.** `arkana-export.json` (`schema_version` 1, fecha, `include_data`, `workspace`, versiones de los plugins y, por fichero: ruta, clase, plugin, tamaño y sha256) y los ficheros bajo `files/`. Marcas de tiempo fijas (1980) para que sea reproducible; el ZIP queda en modo 600.

Salida 0; 1 con `FAIL` (sin workspace, ZIP existente, límites); 2 uso. **Lee:** `.arkana/` según contratos. **Escribe:** el ZIP (por fichero temporal y `os.replace`). **Red:** no. Con `--include-data` el ZIP puede contener datos del proyecto: no compartirlo por canales abiertos.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/transfer.py" export --out ~/arkana-export-2026-01-15.zip --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/transfer.py" export --out ~/arkana-export.zip --include-data --force
```

---

### 4.10 `/arkana-workspace:import`

**Para qué sirve.** Restaura o fusiona un ZIP creado por `export`, validándolo **entero antes de escribir nada**.

**Cuándo.** En una máquina nueva, tras `install`, o para recibir la configuración de otra persona.

**Orden exacta:** 1) siempre primero `--dry-run` y mostrar qué se crearía, qué es idéntico y qué difiere; 2) si hay ficheros que difieren, preguntar: `keep`, `replace` o `ask`; 3) ejecutar con la decisión y resumir; si cambió `core/workspace.json`, recordar que la identidad git y las rutas de herramientas son locales y proponer `/arkana-workspace:check`.

`python3 scripts/lib/transfer.py import FICHERO.zip [--on-conflict keep|replace|ask] [--home DIR] [--dry-run] [--json]`

| Opción | Valores | Por defecto | Efecto |
|---|---|---|---|
| `file` (posicional) | ruta al ZIP | obligatorio | ZIP a importar |
| `--on-conflict` | `keep`, `replace`, `ask` | `keep` | Qué hacer con un fichero que difiere: `keep` conserva lo local; `replace` usa el del ZIP y deja copia en `.arkana/arkana-workspace/bak/import-<fecha-hora>/`; `ask` no escribe lo dudoso y lo lista (`WARN|import:<ruta>|conflicto`), para repetir luego con `keep` o `replace` |
| `--home DIR` | ruta | localizada | Carpeta de Arkana |
| `--dry-run` | flag | no | No escribe; `DRY` para lo que se crearía o reemplazaría |
| `--json` | flag | no | Estructurado |

**Validaciones previas (cualquier fallo → `FAIL`, «no se ha escrito nada», salida 1):** ZIP legible; rutas absolutas, con `..`, con `\`, con unidad o con NUL; entradas duplicadas; enlaces simbólicos; entradas fuera de `files/`; falta de `arkana-export.json`; `schema_version` distinto de 1; ficheros listados y ausentes (o al revés); sha256 o tamaño alterados; más de 5000 ficheros o más de 50 MB por entrada o 200 MB en total; `.credentials`; destino que ningún plugin instalado declara; clase `local` o `secret`; destino que salga de `.arkana/`; y `core/workspace.json` que no valide como manifiesto.

**Reglas de fusión por fichero.** Idéntico → se salta. Ausente → se crea. `tools.json`: con `replace` se toman las herramientas del ZIP **conservando las rutas locales**; con `ask` es conflicto; con `keep`, se conserva lo local. Registros de clase `data`: manda la marca de borrado (`state: deleted`, o `estado`) y luego el valor `updated` más reciente. El resto lo decide `--on-conflict`. Nunca se importan clases `local` ni `secret`.

**Escribe:** ficheros de `.arkana/` (atómicos), con copia de lo sustituido. **Red:** no. Salida 0; 1 con `FAIL`; 2 uso. Un conflicto sin resolver no es error: se informa con `INFO`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/transfer.py" import ~/arkana-export.zip --dry-run
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/transfer.py" import ~/arkana-export.zip --on-conflict replace
```

---

### 4.11 `/arkana-workspace:handover`

**Para qué sirve.** Informe de traspaso: qué hay en el workspace, en qué estado está y qué requiere atención. Sin secretos ni rutas absolutas.

**Cuándo.** Al pasar el proyecto a otra persona o equipo, o para un resumen del estado.

**Orden exacta:** `python3 scripts/lib/handover.py [--out FICHERO] [--format md|json]`; el skill presenta el resumen: componentes con cambios sin subir, credenciales sin valor y planes no completados. No se añade a mano nada que el script no dé (rutas absolutas, usuarios, URL completas).

| Opción | Valores | Por defecto | Efecto |
|---|---|---|---|
| `--out` | ruta | salida estándar | Escribe el informe en ese fichero (atómico) e imprime `OK|handover|informe escrito en <nombre> (<formato>)` |
| `--format` | `md`, `json` | `md` | Formato del informe |
| `--home` | ruta | localizada | Carpeta de Arkana |

**Contenido** (JSON: `generated`, `workspace`, `plugins`, `components`, `plans`, `data`, `credentials`; Markdown: secciones Plugins, Componentes, Herramientas requeridas, Planes de agentic, Credenciales, Datos por plugin):

- Plugins con su versión (los que declaran contrato).
- Componentes: alias, tipo, ruta **relativa a la raíz**, host del remoto, ramas, `vpn`, `tools[]`, `token_ref` y estado git (rama, `◌ ✚ ●`, `⇡`).
- Planes de `arkana-agentic` (`state/planes/*/plan.json`): id, asunto, estado y gasto en USD.
- Datos declarados por plugin: ruta, clase y número de ficheros.
- Credenciales: **solo nombres** de clave referenciados y cuáles no tienen valor.

**Depuración.** Las rutas absolutas se recortan a relativas, los remotos se reducen al host, se eliminan usuarios de las URL y se sustituye cualquier valor de `.credentials` por `***`. Salida 0; 1 si el manifiesto o un fichero no se puede leer; 3 sin workspace (estos errores salen por stderr como `FAIL|handover|…`). **Lee:** manifiesto, git local, planes, contratos. **Escribe:** solo `--out`. **Red:** no.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/handover.py"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/handover.py" --format json --out handover.json
```

---

## 5. Herramientas auxiliares sin skill

### 5.1 `scripts/lib/commits.py` (convención de commits)

`commits.py <status|apply> [--component A]... [--home DIR] [--dry-run] [--json]` (`--dry-run` solo afecta a `apply`). Sin `--component` actúa sobre todas las piezas.

- `status` (solo lectura): una línea `commits-<alias>` por pieza: `OK|…: al día (<formato>)` o `WARN|…: SIN-FICHERO | SIN-BLOQUE | DESACTUALIZADO`.
- `apply`: pone o reemplaza el bloque `arkana:commits` con el formato del manifiesto. Resultado por pieza: `igual`, `creado`, `añadido` o `reemplazado` (`DRY` con `--dry-run`). Si falta el `CLAUDE.md` versionado → `WARN` «falta … (arkana-workspace:fix, `claude-md`)»; un `CLAUDE.local.md` sí se crea. Carpeta inexistente → `WARN`. Formato desconocido → `FAIL`. Copia previa en `.arkana/arkana-workspace/bak/<alias>/<fichero>.<hora>`.
- Salida 0/1; 2 uso incorrecto; 3 sin workspace. No toca nada fuera de los marcadores. `check` lo refleja en el ID `commits`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/commits.py" status
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/commits.py" apply --component app --dry-run
```

### 5.2 `scripts/lib/credentials.py` (credenciales)

`credentials.py <cmd> [arg] [--home DIR] [--json] [--dry-run] [--server ID] [--prefix PREFIJO]`

| Subcomando | Efecto |
|---|---|
| `keys` | Lista los nombres de clave (sin valores) |
| `has <CLAVE>` | Sin salida; código 0 si existe y no está vacía, 1 si no |
| `set <CLAVE>` | Lee el valor de **stdin** (primera línea; nunca de argumentos). Nombre `^[A-Z][A-Z0-9_]*$`; el valor no puede ser vacío. Con `--dry-run` no lee nada |
| `unset <CLAVE>` | Elimina la clave (`INFO` si no estaba) |
| `check` | Modo 600, ignorada por git (`check-ignore`), sin valores vacíos |
| `import-maven <settings.xml>` | Copia usuario y contraseña de un `<server>` a `<PREFIJO>_USER` y `<PREFIJO>_PASSWORD`. `--server` (por defecto `registry`) elige el `<id>`; `--prefix` (por defecto `REGISTRY`) el prefijo |
| `wire-git <alias>` | Escribe `.arkana/arkana-workspace/bin/git-credential-arkana` (modo 700) y configura `credential.helper` **en el repo local** de la pieza. Exige `git.token_ref` en su bloque y que sea un repo git; avisa (`WARN`) si la clave no tiene valor. `--dry-run` ensaya |

```bash
printf '%s\n' "$TOKEN" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/credentials.py" set GIT_TOKEN
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/credentials.py" wire-git app
```

### 5.3 `scripts/arkana-exec.sh`

`arkana-exec.sh [--keys A,B] -- <comando> [args…]`. Ejecuta el comando con las credenciales de `.credentials` en su entorno (todas, o solo las de `--keys`), sin imprimirlas ni dejarlas en argumentos ni en disco; las variables ya definidas no se pisan. Sin comando → salida 2.

### 5.4 `scripts/git-credential-arkana` (asistente de git)

Asistente de `credential.helper`. Para `get` con `protocol` https/http busca la pieza cuyo `remote_host` coincide con el host y devuelve `username` (`git.username`, o `oauth2`) y `password` (el token de la clave `git.token_ref`). `store` y `erase` no hacen nada. Sin coincidencia no imprime nada y git sigue con los demás asistentes. Se activa por repo con `credentials.py wire-git`.

---

## 6. Hooks

`hooks/hooks.json` declara un único hook:

| Evento | Matcher | Orden | Tope |
|---|---|---|---|
| `SessionStart` | `startup\|resume\|clear\|compact` | `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/hooks.py" session-status` | 10 s |

**Qué hace.** Muestra al **usuario** (campo `systemMessage`; no se inyecta en el contexto del modelo) un BRIEF corto. Solo usa git local y ficheros de estado: sin red. No hace nada si `ARKANA_WORKER=1` (dentro de un worker), si no hay workspace, o si no hay nada que mostrar (todo limpio, sin plan activo y sin mensajes). Nunca falla (siempre sale con 0).

**Formato del BRIEF** (secciones en este orden; cada una solo si tiene contenido):

```text
****** [ARKANA] BRIEF ******

### GIT (pending):
1. app (develop)
2. ARKANA (develop)

### MESSAGING:
1. api (2 tasks, 1 repeat)

### ORCHESTRATION:
- plan P2601011200-abcd (ejecutando, 0.42 USD)

### QUICK START
- Use '/arkana-statusline:install' - show the Arkana status bar (git, plan, cost, usage)
- Use '/arkana-workspace:config' - set tool versions (and optional Jira)
- Use '/arkana-workspace:check' - diagnose the workspace and the environment
- Use '/arkana-workspace:fix' - repair what check reports, step by step
- Use '/arkana-messaging:query --unread' - list what is waiting for this component (read-only: it does not mark anything as read)
- Use '/arkana-workspace:sync' - fetch the remotes so the commits to pull (⇣) are up to date
- Use '/arkana-workspace:status' - git state of every component
- Use '/arkana-agentic:status' - progress and cost of the active plan
```

| Sección | Contenido y origen |
|---|---|
| `GIT` | Piezas con cambios o commits sin subir (`gitstate`, hasta 8 repos en paralelo), con su rama |
| `MESSAGING` | Por pieza, de `arkana-messaging/state/index.json` y `state/read/<actor>.json`: `N tasks` (task, review o question de una vez, abiertas y sin confirmar por ella), `N repeat` (directrices vigentes que le alcanzan; no las `propuesto`) y `N unread notices` (avisos sin leer, solo si los hay). Se excluyen borrados, reconciliados y propios |
| `ORCHESTRATION` | Plan activo (`arkana-agentic/state/actual` y su `plan.json`, salvo `completado`, `archivado` o `cancelado`) con su estado y gasto |
| `QUICK START` | Comandos en el orden **config → check → fix → uso diario**: primero la puesta a punto (`config`, `check`, `fix`), luego el trabajo del día. `/arkana-statusline:install` solo si `statusLine` de `~/.claude/settings.json` no apunta a `arkana-statusline`; `messaging query --unread` solo con mensajes; `sync` siempre; `status` solo con cambios git; `agentic:status` solo con plan |

Los demás plugins llevan sus propios hooks (ver [`../README.md`](../README.md)).

---

## 7. Variables de entorno y localización del workspace

Variables que **leen** el código y los hooks de este plugin (confirmadas en el código):

| Variable | Dónde se usa | Efecto |
|---|---|---|
| `ARKANA_HOME` | Localizador (`locate.find_home`, también en el núcleo bash) | Carpeta del repo de Arkana. Si apunta a un directorio existente, manda sobre todo lo demás. `all.py` la define para los `check` de los plugins |
| `ARKANA_PLUGINS_DIR` | `transfer.py` (exportar, importar, `handover`) | Carpeta adicional donde buscar los `arkana-plugin.json` de los plugins. En este plugin **no** relocaliza `.arkana`; `arkana-agentic` sí la usa para ubicar su estado |
| `ARKANA_WORKER` | `hooks.py` | Con `1` el hook no hace nada (lo fija el orquestador en los workers) |
| `ARKANA_NET_BREAKER_FILE` | `netguard` (`sync`, `credentials`) | Fichero del cortacircuitos de red; por defecto `<tmp>/arkana-net-breaker-<uid>.json` |
| `CLAUDE_PLUGIN_ROOT` | Skills, hook y `all.py` (lo fija Claude Code) | Carpeta del plugin; `all.py` la fija a la del plugin comprobado al ejecutar su `check` |

`ARKANA_SHARED` y `ARKANA_BASE` **no** existen en el código de este plugin (las citaba la documentación anterior). Internamente los scripts fijan `GIT_TERMINAL_PROMPT=0` y `LC_ALL=C` en cada llamada a git (más `GIT_HTTP_LOW_SPEED_*` en los de red), y `arkana-exec.sh` y las pruebas fijan `PYTHONDONTWRITEBYTECODE=1`.

**Cómo se localiza el workspace** (`locate.find_home`, mismo orden en bash y en Python):

1. `$ARKANA_HOME`, si es un directorio.
2. Un ancestro del directorio actual que tenga `.arkana/arkana.json`.
3. El registro `~/.arkana-workspaces.json`: el primer workspace cuya raíz contenga el directorio actual (así se localiza desde la carpeta de un componente).
4. Ninguno: los hooks no hacen nada y los scripts salen con 3. Todos aceptan `--home DIR` para forzarlo.

---

## 8. Contrato de salida y códigos de salida

Cada comprobación imprime `ESTADO|ID|detalle` con `ESTADO` ∈ `OK`, `WARN`, `FAIL`, `INFO`, `DRY`, y el informe termina con `RESUMEN|n FAIL|n WARN`. Con `--json` se imprime un objeto con `plugin`, `skill`, `status` (`ok`/`warn`/`fail`), `items[]` y `summary` (`fail`, `warn`, `ok`, `info`, `dry`). Formato completo: [`../docs/OUTPUT-CONTRACT.md`](../docs/OUTPUT-CONTRACT.md).

| Código | Significado |
|---|---|
| 0 | Sin fallos |
| 1 | Algún `FAIL` o error |
| 2 | Uso incorrecto (opción desconocida o falta un argumento) |
| 3 | Precondición no cumplida (no hay workspace, alias desconocido) |

Excepciones: `status` sale siempre con 0 (salvo 3); `sync` no emite `FAIL`; `credentials.py has` usa 0/1 sin salida; `permissions.py matrix|expected|effective` salen con 0; `layout.py` informa de sus precondiciones como `FAIL` con salida 1.

Un secreto nunca aparece en una salida: los informes sustituyen los valores de `.credentials` por `***`, las URL se muestran sin usuario ni contraseña y las rutas de `handover` son relativas.

---

## 9. Instalación, pruebas y desarrollo

### Instalación

Desde el marketplace local `arkana` (carpeta `plugins`):

```bash
claude plugin marketplace add <ruta>/plugins
claude plugin install arkana-workspace@arkana
```

Después, desde la carpeta de Arkana: `/arkana-workspace:install`, `component add` por cada repo, `config tools`, `fix` y `check` (sección 2). Reiniciar Claude Code o `/reload-plugins` para cargar el hook.

### Pruebas

Sin red, sin API real y sin tocar `~/.claude`:

```bash
bash tests/run-tests.sh [-v|-q] [-k <patrón>]      # desde plugins/arkana-workspace: unittest sobre tests/test_*.py
bash scripts/run-all-tests.sh [--quick] [--only <texto>]   # desde arkana: el núcleo y los seis plugins
claude plugin validate plugins/arkana-workspace    # validación del plugin
```

Los tests (`tests/`) cubren: `test_checks`, `test_commits`, `test_components`, `test_contracts`, `test_credentials`, `test_hooks`, `test_layout`, `test_permissions`, `test_sync` y `test_transfer`; `environment.py` monta workspaces temporales aislados.

### Desarrollo

- Estructura: `skills/<nombre>/SKILL.md` (11 skills), `scripts/lib/*.py` (herramientas), `scripts/checks/*.py` (comprobaciones), `scripts/hooks.py` y `hooks/hooks.json`, `arkana-plugin.json` (contrato) y `.claude-plugin/plugin.json`.
- **Núcleo vendorizado.** La fuente de `arkana_core` (localizador, manifiesto, esquemas, salida, red, bloques gestionados, contrato) es `lib/arkana_core/`. Un plugin instalado no puede leer a otro, así que cada uno lleva su copia en `scripts/_core/` (con `.vendor.json`: versión del núcleo y sha256 por fichero; incluye `arkana-core.sh` para bash, que necesita `jq`). Se regenera con:

  ```bash
  bash scripts/vendor-core.sh            # desde arkana: copia el núcleo en los seis plugins
  bash scripts/vendor-core.sh --check    # no escribe; sale con 1 si alguna copia difiere
  bash scripts/vendor-core.sh arkana-workspace
  ```

  No se edita nada dentro de `scripts/_core/`: se cambia `lib/arkana_core/` y se vuelve a vendorizar.
- Una regla de permisos nueva se añade a `expected()` en `scripts/lib/permissions.py`, nunca a mano en un `settings.local.json`. Un formato de commit nuevo, a `FORMATS` en `scripts/lib/commits.py`.
- Si cambia el esquema del manifiesto (`workspace.schema.json`), hay que revendorizar el núcleo en todos los plugins y revisar `manifest.validate`.

Documentación relacionada: [`../docs/PLUGIN-CONTRACT.md`](../docs/PLUGIN-CONTRACT.md), [`../docs/DATA-LAYOUT.md`](../docs/DATA-LAYOUT.md), [`../docs/OUTPUT-CONTRACT.md`](../docs/OUTPUT-CONTRACT.md).

## Extensiones opcionales

El núcleo no depende de ninguna herramienta ni formato concretos. Dos piezas son **opcionales y están apagadas por defecto**:

| Extensión | Cómo se activa | Qué añade |
|---|---|---|
| Formato de commit `ia4d` | `components.py edit --alias <alias> --commit-format ia4d` | `verbo(scope) descripción`, sin dos puntos. Sin esto, todos los componentes usan `conventional`. |
| Jira | `/arkana-workspace:config jira --url … --token-ref …` | Los checks `jira-env`, `jira-env-proyecto`, `jira-mcp`, `jira-mcp-deps` y `jira-mcp-duplicado` (conector del plugin externo `ia4d-project-bridge`). Sin el bloque `jira` en el manifiesto no se ejecuta ninguno. |
