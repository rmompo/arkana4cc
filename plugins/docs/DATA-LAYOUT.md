# Disposición de datos de Arkana (`.arkana/`)

Arkana es una herramienta general para gobernar proyectos de varias piezas en repos distintos. El **workspace** es Arkana más el proyecto; el proyecto son **componentes** (repos). Todo el estado de los plugins vive en `.arkana/` dentro del repo de Arkana (hoy la carpeta se sigue llamando `arkana`; solo el alias pasa a `ARKANA`). `.arkana/` es **local por instalación y no se versiona** (`/.arkana/` en el `.gitignore`).

## Mapa

```
<repo de Arkana>/                    (repo git propio; los plugins NO viven aquí: se instalan desde el marketplace)
├── .arkana/
│   ├── arkana.json                  versión de esquema, nombre del workspace y `root` (relativa; por defecto `..`)
│   ├── .credentials                 CLAVE=valor, modo 600; nunca se exporta ni se versiona; denegado a todos, workers incluidos
│   ├── core/
│   │   └── workspace.json           manifiesto portable: bloque `arkana` y `components[]`
│   ├── arkana-workspace/
│   │   ├── tools.json               herramientas (versión, ruta, paquetes, registros), urls y puertos que comprueba `check` (la ruta no se exporta)
│   │   ├── local.json               identidad git personal y rutas absolutas de esta instalación
│   │   ├── bak/                     copias de seguridad (`.bak`) de lo que modifican check/fix/install
│   │   └── bin/                     asistente de credenciales de git
│   ├── arkana-messaging/state/      messages/<id>.json (clase data), index.json, read/, sessions/, .lock
│   │                                (cada mensaje: para y destinatarios, repeticion once|repeat, confirmaciones/entregas/ejecuciones por destinatario)
│   ├── arkana-agentic/
│   │   ├── config/                  politica.json y comandos-permitidos.json locales (aditivos)
│   │   ├── state/                   planes/, run/ (worker, linea.json, marcas), actual
│   │   ├── data/                    ledger/{plans,sessions}/ (libro, solo metadatos) y archive/ (planes archivados)
│   │   └── bak/
│   ├── arkana-evolve/state.json     migraciones aplicadas en esta instalación (clase local)
│   ├── arkana-statusline/state/sessions/<sid>.json   coste real de cada sesión (la statusline es su única escritora)
│   ├── arkana-todo/todos.json       lista de tareas de la persona usuaria (clase data)
│   └── arkana-note/notes.json       notas de la persona usuaria (clase data)
├── arkana-project.json              registro del proyecto (versionado): UUID, alias y nombre-módulo (`module`, opcional) de cada pieza y sello `layout`
├── arkana-incoming/                 entrada de documentos; solo `.gitkeep` y su `.gitignore` interno se versionan
├── arkana-knowledge/                notas versionadas en git (<topic>/<slug>.md); su índice es local y derivado (.arkana/arkana-knowledge/index.json)
├── arkana-docs/                     versionado; tres subcarpetas con el mismo árbol de nombres:
│   ├── src/                         los originales, intactos y de solo lectura
│   ├── md/                          su versión en Markdown (`src/a/b.pdf` → `md/a/b.pdf.md`)
│   └── out/                         documentos elaborados a petición, siempre en duplas: `x.md` (fuente) + `x.docx`… (render)
└── .gitignore                       ignora `/.arkana/` (lo deja `layout init`, o la migración 0007 en instalaciones antiguas)
```

Fuera del repo, por usuario: `~/.arkana/workspaces.json` (localizador: raíces de todos los workspaces de esta máquina; antes `~/.arkana-workspaces.json`, que se lee y se mueve al registrar), `~/.claude/arkana-statusline/` (copia instalada del despachador de la statusline) y `~/.arkana/statusline.json` (proveedores de statusline y elección por componente).

## Clases de portabilidad

Cada plugin declara en su `arkana-plugin.json` qué guarda y de qué clase es cada dato (ver [`PLUGIN-CONTRACT.md`](PLUGIN-CONTRACT.md)):

| Clase | Significado | `export` | `import` |
|---|---|---|---|
| `config` | Configuración portable | siempre | sí |
| `data` | Datos del usuario (p. ej. mensajes) | solo con `--include-data` | sí, fusionando por id con precedencia de marcas de borrado |
| `local` | Propio de esta instalación (rutas, estado, copias, cerrojos) | nunca | nunca |
| `secret` | Credenciales | solo la **referencia** (el nombre de la clave) | nunca |

**Fuera de `.arkana/`.** El conocimiento de `arkana-knowledge` (notas en `arkana-knowledge/<topic>/*.md`, documentos de origen en `arkana-docs/src/`, su versión en Markdown en `arkana-docs/md/` y los elaborados en `arkana-docs/out/`) está en la raíz del repositorio de ARKANA y **se versiona con git**: es la forma de compartirlo entre todas las personas usuarias, por lo que no forma parte de `export`/`import`.

## Manifiesto `core/workspace.json`

Bloque `arkana` (`alias ARKANA`, `path`, `remote`, `branches`, `git`, `commit_format`) y `components[]`: `alias`, `type` (`node`, `maven`, `docs`, `generic`), `path` relativa a la raíz del workspace, `remote` y `remote_host`, `branches {main, develop}`, `git {token_ref}`, `commit_format` (`ia4d` o `conventional`, con `({module})` opcional para que el scope del commit sea el módulo), `vpn`, `statusline`, `watch`, `mode`, `ref`, `checks_skip`, `tools[{tool, version}]`. `watch`, `mode` (`work` \| `reference`), `ref` y `checks_skip` son de **esquema 2**: el manifiesto declara `schema: 2` solo cuando alguien guarda uno, y una instalación que solo conoce el esquema 1 lo rechaza con «actualiza el plugin»; el sello compartido `layout` (5 en este caso, lo estampa `arkana-evolve` con `0005`) avisa a las instalaciones nuevas de que otra persona ya migró. El **orden** de `components[]` es el que usan la statusline, `list` y el BRIEF (ARKANA siempre primero); `statusline` (`component edit --statusline` / `--no-statusline`, en cualquier momento) fuerza mostrar u ocultar el componente, y sin la marca se muestra salvo los de tipo `docs`; `watch` (`--watch` / `--no-watch`) decide si cuentan sus cambios, con independencia de si se ve. La identidad git (usuario y correo) y las rutas absolutas **no** van aquí: están en `arkana-workspace/local.json`.

## Reglas

- Un único resolvedor de credenciales (`arkana-workspace`): el manifiesto y los ficheros exportables guardan solo nombres de clave.
- Los workers de `arkana-agentic` no pueden leer ni editar `.arkana/` (regla `deny` explícita, `.credentials` incluido).
- Exportar e importar (`arkana-workspace:export` / `import`) usa un ZIP con `arkana-export.json` (versión de esquema, versiones de plugins y sha256 de cada fichero); rechaza rutas absolutas, `..`, enlaces simbólicos y hashes alterados, y nunca incluye `.credentials`.
