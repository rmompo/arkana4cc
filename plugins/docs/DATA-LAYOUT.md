# Disposición de datos de Arkana (`.arkana/`)

Arkana es una herramienta general para gobernar proyectos de varias piezas en repos distintos. El **workspace** es Arkana más el proyecto; el proyecto son **componentes** (repos). Todo el estado de los plugins vive en `.arkana/` dentro del repo de Arkana (hoy la carpeta se sigue llamando `arkana`; solo el alias pasa a `ARKANA`). `.arkana/` es **local por instalación y no se versiona** (`/.arkana/` en el `.gitignore`).

## Mapa

```
<repo de Arkana>/
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
│   │   ├── state/                   planes/, run/ (worker, linea.json, marcas), sesiones/, actual
│   │   ├── data/                    ledger/{plans,sessions}/ (libro, solo metadatos) y archive/ (planes archivados)
│   │   └── bak/
│   ├── arkana-statusline/state/sessions/<sid>.json   coste real de cada sesión (la statusline es su única escritora)
│   └── arkana-todo/todos.json       lista de tareas de la persona usuaria (clase data)
├── arkana-knowledge/                notas versionadas en git (<topic>/<slug>.md) y catalog.json
└── plugins/                         los seis plugins y el marketplace `arkana`; los contratos comunes están en `plugins/docs/`
```

Fuera del repo, por usuario: `~/.arkana-workspaces.json` (localizador: raíces de workspace conocidas) y `~/.claude/arkana-statusline/` (copia instalada de la statusline).

## Clases de portabilidad

Cada plugin declara en su `arkana-plugin.json` qué guarda y de qué clase es cada dato (ver [`PLUGIN-CONTRACT.md`](PLUGIN-CONTRACT.md)):

| Clase | Significado | `export` | `import` |
|---|---|---|---|
| `config` | Configuración portable | siempre | sí |
| `data` | Datos del usuario (p. ej. mensajes) | solo con `--include-data` | sí, fusionando por id con precedencia de marcas de borrado |
| `local` | Propio de esta instalación (rutas, estado, copias, cerrojos) | nunca | nunca |
| `secret` | Credenciales | solo la **referencia** (el nombre de la clave) | nunca |

**Fuera de `.arkana/`.** El conocimiento de `arkana-knowledge` (`arkana-knowledge/<topic>/*.md` y `catalog.json`) está en la raíz del repositorio de ARKANA y **se versiona con git**: es la forma de compartirlo entre todas las personas usuarias, por lo que no forma parte de `export`/`import`.

## Manifiesto `core/workspace.json`

Bloque `arkana` (`alias ARKANA`, `path`, `remote`, `branches`, `git`, `commit_format`) y `components[]`: `alias`, `type` (`node`, `maven`, `docs`, `generic`), `path` relativa a la raíz del workspace, `remote` y `remote_host`, `branches {main, develop}`, `git {token_ref}`, `commit_format` (`ia4d` o `conventional`), `vpn`, `seed_file` (`CLAUDE.md` o `CLAUDE.local.md`), `statusline`, `tools[{tool, version}]`. El **orden** de `components[]` es el que usan la statusline, `list` y el BRIEF (ARKANA siempre primero); `statusline` (`component edit --statusline` / `--no-statusline`) fuerza mostrar u ocultar el componente, y sin la marca se muestra salvo los de tipo `docs`. La identidad git (usuario y correo) y las rutas absolutas **no** van aquí: están en `arkana-workspace/local.json`.

## Reglas

- Un único resolvedor de credenciales (`arkana-workspace`): el manifiesto y los ficheros exportables guardan solo nombres de clave.
- Los workers de `arkana-agentic` no pueden leer ni editar `.arkana/` (regla `deny` explícita, `.credentials` incluido).
- Exportar e importar (`arkana-workspace:export` / `import`) usa un ZIP con `arkana-export.json` (versión de esquema, versiones de plugins y sha256 de cada fichero); rechaza rutas absolutas, `..`, enlaces simbólicos y hashes alterados, y nunca incluye `.credentials`.
