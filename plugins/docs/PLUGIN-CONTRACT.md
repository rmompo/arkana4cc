# Contrato de plugin (`arkana-plugin.json`)

Cada plugin de Arkana trae en su raíz un `arkana-plugin.json` (esquema en `lib/arkana_core/schemas/arkana-plugin.schema.json`, en la raíz del repositorio). Con él, `export`, `import`, `handover` y el `check` agregado no necesitan conocer los detalles internos de ningún plugin.

```json
{
  "plugin": "arkana-messaging",
  "contract": 1,
  "provides": ["install", "check", "fix", "put", "get", "query", "delete", "sync"],
  "requires": [{"plugin": "arkana-workspace"}],
  "check": "bash scripts/messaging.sh check --all",
  "hooks": ["SessionStart", "UserPromptSubmit", "Stop"],
  "data": [
    {"path": "arkana-messaging/state/messages/", "class": "data", "description": "un JSON por mensaje"},
    {"path": "arkana-messaging/state/index.json", "class": "local", "description": "índice derivado"}
  ]
}
```

| Campo | Significado |
|---|---|
| `plugin` | Nombre (`arkana-<nombre>`) |
| `contract` | Versión del contrato (hoy 1) |
| `provides` | Skills que ofrece |
| `requires` | Plugins de los que depende (`plugin`, y opcionalmente `min`); si `dependencies` de `plugin.json` no lo aplica, `check` lo informa |
| `check` | Orden de solo lectura que el `check` agregado de `arkana-workspace` ejecuta para este plugin |
| `hooks` | Eventos de Claude Code que usa (`SessionStart`, `UserPromptSubmit`, `Stop`, `SessionEnd`) |
| `data[]` | Rutas relativas a `.arkana/` (nunca absolutas ni con `..`) con su clase (`config`, `data`, `local`, `secret`). Lo que un plugin guarda **fuera** de `.arkana/` y ya viaja con git no se declara: es el caso de `arkana-knowledge`, cuyas notas viven en `arkana-knowledge/` en el repositorio de ARKANA y se comparten entre las personas usuarias por git (por eso su `data` es `[]`) |

## Los seis plugins

Estructura: el **workspace** es ARKANA más el proyecto, y el proyecto se compone de uno o más **componentes** (repositorios). ARKANA tiene su propio repositorio y es el de **conciliación, gobierno y conocimiento** del proyecto y de sus componentes; los plugins actúan desde él.

| Plugin | Responsabilidad | Verbos comunes |
|---|---|---|
| `arkana-workspace` | Componentes (`component`, con `--statusline` para mostrarlos u ocultarlos en la barra), permisos R/E/W (`rew-grants`), credenciales, herramientas (`config tools`), red/VPN, convención de commits, `export`/`import`/`handover` | `install`, `check`, `fix` |
| `arkana-messaging` | Mensajes entre ARKANA y los componentes (avisos, tareas, revisiones, preguntas y directrices permanentes `repeat`): `put`, `get`, `query` (solo lectura, no marca como leído), `delete` (lógico), `sync` (`--reconcile`); hooks y semilla `arkana:messaging` | `install`, `check`, `fix` |
| `arkana-statusline` | Statusline de dos líneas (ARKANA y los componentes en el orden del manifiesto); única escritora del coste real de sesión; `refresh` | `install`, `check`, `fix` |
| `arkana-agentic` | Orquestación: `plan`, `run`, `status`, `control`, `stop`, `archive`, `costs`; adaptadores por tipo de componente; libro de sesiones | `install`, `check`, `fix` |
| `arkana-knowledge` | Conocimiento del proyecto que las personas usuarias administran (`add`, `modify`, `delete` lógico) y consultan (`query`); funciona como un pseudo-RAG: catálogo y documentos indexados y organizados para consultarlos con eficiencia | `install`, `check`, `fix` |
| `arkana-todo` | Lista de tareas pendientes de la persona usuaria (`add`, `list`, `done`, `modify`, `delete` lógico), en `.arkana/arkana-todo/todos.json` (clase `data`) | `install`, `check`, `fix` |

## Convenciones

- **Verbos comunes.** `install` (primera puesta en marcha, repetible), `check` (solo lectura, nunca corrige) y `fix` (corrige lo que `check` marca, interactivo, con copia `.bak`). **Todos los skills aceptan `--dry-run` y `--json`** (en los de solo lectura `--dry-run` no hace nada).
- **Código común.** La fuente canónica es `lib/arkana_core/` (localizador, manifiesto, contratos, salida, `netguard`, `seedblock`); cada plugin lleva su **copia** en `scripts/_core/` con `.vendor.json` (versión y sha256), generada por `scripts/vendor-core.sh` y vigilada por los tests. Los plugins instalados se leen de una copia en la caché de Claude Code, así que no se referencian entre sí.
- **Contención de red.** Ningún comando que pueda tocar la red se ejecuta sin tope de tiempo y en su propio grupo de procesos (`arkana_core.netguard`): `git` de red 20 s, DNS comprobado antes (3 s) y cortacircuitos; sin VPN se avisa en lugar de esperar.
- **Hooks.** No hacen nada dentro de un worker (`ARKANA_WORKER=1`, además de `disableAllHooks` en sus ajustes) ni fuera de un workspace; un hook nunca rompe la sesión.
- **Bloques gestionados.** `seedblock` escribe bloques `<!-- arkana:NOMBRE:start -->…<!-- arkana:NOMBRE:end -->` (`messaging`, `commits`, `agentic`) en los `CLAUDE.md`; lo de fuera no se toca y se deja copia `.bak`.
