# Arkana

Arkana gobierna, con Claude Code, un **workspace multi-repo**. Su estructura es:

```
workspace
+-- ARKANA            repositorio de conciliación, gobierno y conocimiento del proyecto y sus componentes (carpeta de ARKANA): manifiesto, mensajes, planes, conocimiento
+-- proyecto
    +-- componentes   los repos del proyecto (hermanos o anidados unos dentro de otros)
```

Un **proyecto** se compone de uno o más **componentes**, que son repositorios. El **workspace** es ARKANA más el proyecto, y ARKANA tiene su propio repositorio, distinto de los de los componentes. ARKANA es el repositorio de **conciliación y gobierno** del proyecto y de sus componentes: desde él se declaran, se comunican, se orquestan y se comprueban. Es también el repositorio de **conocimiento** del proyecto, y son las **personas usuarias** quienes lo gestionan (administran y consultan) con `arkana-knowledge`. Esta carpeta es el **marketplace local `arkana`** y contiene los plugins del conjunto. Cada plugin se documenta en su propio `README.md` (y los que tienen más profundidad, en su carpeta `docs/`); aquí está el mapa del conjunto.

Arkana no sabe nada de ningún proyecto concreto: los componentes, sus rutas, tipos, formatos de commit, herramientas y registros se **declaran en la configuración** (el manifiesto y `config tools`), no en el código.

## Los plugins

| Plugin | Responsabilidad | Depende de | Hooks |
|---|---|---|---|
| [`arkana-workspace`](arkana-workspace/README.md) | El workspace: componentes (manifiesto), permisos R/E/W, credenciales, herramientas, red/VPN, convención de commits, `export`/`import`/`handover` | — | `SessionStart` (resumen `BRIEF`) |
| [`arkana-messaging`](arkana-messaging/README.md) | Mensajes entre componentes (avisos, tareas, revisiones, preguntas y directrices permanentes), con almacén local | `arkana-workspace` | `SessionStart`, `UserPromptSubmit`, `Stop` |
| [`arkana-agentic`](arkana-agentic/README.md) | Orquestación: plan aprobado por ti, un worker sin shell por tarea, verificación por script, ramas `arkana-worker/<plan>` | `arkana-workspace` | `SessionStart`, `SessionEnd` (libro de sesiones) |
| [`arkana-statusline`](arkana-statusline/README.md) | Barra de estado de dos líneas: componentes y su estado git, plan, coste, modelo y uso | — | — |
| [`arkana-knowledge`](arkana-knowledge/README.md) | Conocimiento del proyecto, versionado en git y gestionado por las personas usuarias (`add`, `modify`, `delete`, `query`); funciona como un pseudo-RAG: catálogo y documentos indexados para consultarlos con eficiencia, con changelog por nota | — | — |
| [`arkana-todo`](arkana-todo/README.md) | Lista de tareas pendientes de la persona usuaria: local, con prioridad, vencimiento y componente; cierre reversible y borrado lógico (`add`, `list`, `done`, `modify`, `delete`) | — | — |
| [`arkana-evolve`](arkana-evolve/README.md) | Evolución de una instalación: migraciones numeradas, idempotentes y con `--dry-run` (`apply`, `check`); crea el registro del proyecto con UUID y las carpetas fijas | — | — |

Todos ofrecen los verbos `install`, `check` y `fix`, salvo `arkana-evolve`, que ofrece `check` y `apply`.

## Puesta en marcha

```bash
claude plugin marketplace add <ruta>
claude plugin install arkana-workspace@arkana     # y el resto que quieras: arkana-messaging, arkana-agentic, arkana-statusline, arkana-knowledge, arkana-todo, arkana-evolve
```

Después, desde la carpeta de Arkana y en este orden:

1. `/arkana-workspace:install` crea `.arkana/` y el manifiesto (solo con ARKANA).
2. `/arkana-workspace:component add` da de alta cada componente (alias, ruta, tipo, remoto, formato de commit…).
3. `/arkana-workspace:config tools` declara las herramientas del proyecto (ver «Dónde vive cada cosa»).
4. `/arkana-messaging:install`, `/arkana-agentic:install`, `/arkana-statusline:install`, `/arkana-knowledge:install` y `/arkana-todo:install`, los que uses.
5. `/arkana-evolve:apply` lleva el layout al más reciente (registro del proyecto con UUID y carpetas fijas con `.gitkeep`); una sola persona lo aplica y empuja, el resto hace pull y lo ejecuta.
6. `/arkana-workspace:fix` y `/arkana-workspace:check`: permisos, `CLAUDE.md`, identidad git y convención de commits; el `check` revisa también los demás plugins.

## Dónde vive cada cosa

Los metadatos no ensucian los repos del proyecto: están en `.arkana/` (ignorada por git). Detalle en [`docs/DATA-LAYOUT.md`](docs/DATA-LAYOUT.md).

| Qué | Dónde | Se exporta |
|---|---|---|
| Componentes: alias, ruta relativa, tipo (`node`, `maven`, `docs`, `generic`), remoto, ramas, `commit_format`, `git.email_domains`, versiones de herramientas (`tools[]`) | `core/workspace.json` (el **manifiesto**) | sí |
| Rutas absolutas de esta máquina, identidad git personal, rutas locales de herramientas | `arkana-workspace/local.json` | no |
| Herramientas del proyecto: versión, ruta, paquetes globales, registros por ámbito, URL y puertos a comprobar | `arkana-workspace/tools.json` (`/arkana-workspace:config tools`) | la ruta no |
| Credenciales (solo nombres de clave en el manifiesto) | `.credentials` (modo 600; denegado a todos, workers incluidos) | nunca |
| Registro del proyecto: UUID y alias de cada pieza y sello de layout | `arkana-project.json` (raíz de ARKANA, **versionado**) | por git |
| Carpetas fijas del repo de ARKANA: entrada de documentos, conocimiento y documentos de origen | `arkana-incoming/` (solo `.gitkeep`), `arkana-knowledge/`, `arkana-docs/` (con `md/`) | por git |
| Mensajes, planes y libro de sesiones | `arkana-messaging/`, `arkana-agentic/` | datos locales |

**Directrices de commit.** Cada componente, **incluida ARKANA**, elige su formato (`conventional` por defecto: `tipo(scope): descripción`; `ia4d`, opcional: `verbo(scope) descripción`) y puede fijar los dominios de correo del autor (`--git-email-domain`). Un bloque `arkana:commits` lo deja en su `CLAUDE.md` o `CLAUDE.local.md`. Siempre en inglés, ≤72 caracteres, sin punto final y **sin `Co-Authored-By`, que nunca se permite y no es configurable**.

**Herramientas.** Lo específico del stack (Node, JDK, Maven, paquetes de Angular, un registro privado de npm…) se declara una vez con `config tools`. `arkana-workspace:check` lo comprueba y `arkana-agentic` lo usa para el `PATH`, `JAVA_HOME` y `.npmrc` de sus verificaciones. Los plugins no llevan ninguna herramienta, versión ni registro fijados.

## Convenciones comunes

- **Contrato de plugin.** Cada plugin trae `arkana-plugin.json` (skills que ofrece, dependencias, hooks, datos); ver [`docs/PLUGIN-CONTRACT.md`](docs/PLUGIN-CONTRACT.md).
- **Salida.** Una línea `ESTADO|ID|detalle` por comprobación y `RESUMEN|n FAIL|n WARN`, o `--json`; todos los skills aceptan `--dry-run`. Ver [`docs/OUTPUT-CONTRACT.md`](docs/OUTPUT-CONTRACT.md).
- **Red.** Ningún comando de red se ejecuta sin tope de tiempo, con el DNS comprobado antes; `sync` y el asistente de credenciales usan además un cortacircuitos. Sin VPN, `arkana-agentic` avisa (`WARN`) pero sigue: su trabajo es local.
- **Herramientas del sistema.** Los plugins usan lo que el entorno ya tiene (`shutil.which`) y nunca instalan nada por su cuenta: ni paquetes del sistema, ni con `sudo` (el usuario lo protege con contraseña y Arkana no la tiene). Si falta algo, `check` lo señala y el skill **pide a la persona usuaria que lo instale**, explicando qué herramienta, para qué sirve y el comando exacto. Lo opcional degrada la función (se avisa), lo imprescindible bloquea con un `FAIL` claro.
- **Hooks.** No hacen nada dentro de un worker (`ARKANA_WORKER=1`) ni fuera de un workspace, y nunca rompen la sesión.
- **Bloques gestionados.** Los plugins escriben bloques `<!-- arkana:NOMBRE:start -->…<!-- arkana:NOMBRE:end -->` (`messaging`, `commits`, `agentic`) en los `CLAUDE.md`; lo de fuera no se toca y se deja copia `.bak`.
- **Código común.** La fuente es `lib/arkana_core/` (localizador, manifiesto, esquemas, salida, red, bloques). Cada plugin lleva su copia en `scripts/_core/`, porque un plugin instalado no puede leer a otro: se regenera con `bash scripts/vendor-core.sh` y `--check` comprueba que está al día.

## Pruebas

Todas sin red y sin API real, y sin tocar `~/.claude`:

```bash
bash scripts/run-all-tests.sh            # el núcleo y todos los plugins; --quick omite las e2e (~3 min); --only <texto> filtra
bash plugins/arkana-agentic/tests/containment/run-containment.sh   # con claude real: cuesta dinero (~0,1 USD); solo con --containment desde run-all-tests
claude plugin validate plugins/arkana-workspace        # validación del plugin (repetir con cada uno)
```

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/PLUGIN-CONTRACT.md`](docs/PLUGIN-CONTRACT.md) | `arkana-plugin.json` y las convenciones comunes |
| [`docs/DATA-LAYOUT.md`](docs/DATA-LAYOUT.md) | Qué hay en `.arkana/`, qué se exporta y qué es secreto |
| [`docs/OUTPUT-CONTRACT.md`](docs/OUTPUT-CONTRACT.md) | Formato de salida y códigos de salida comunes |
| [`arkana-agentic/docs/GUIA.md`](arkana-agentic/docs/GUIA.md) | Guía para personas de la orquestación multi-repo |
| [`arkana-agentic/docs/ESPECIFICACION.md`](arkana-agentic/docs/ESPECIFICACION.md) | Especificación de la orquestación  |
