# arkana-knowledge

Conocimiento común de un workspace de Arkana, guardado en el repositorio de ARKANA (que es también el repositorio de conocimiento del proyecto): **notas Markdown** (lo decidido y lo aprendido) y **documentos de origen** (especificaciones, manuales, actas) con su **versión en Markdown**, que es lo que Arkana consulta. Todo se versiona en git y lo comparte el equipo.

**Pseudo-RAG ligero.** Un índice local derivado (`.arkana/arkana-knowledge/index.json`, nunca versionado, sin conflictos de git) permite que `query` recupere por palabras clave —título, etiquetas, resumen, nombre y cuerpo— solo lo relevante, y el modelo trabaja con eso en lugar de cargar todo. Sin embeddings ni servicios externos: recuperación léxica, local y determinista. Solo biblioteca estándar de Python 3; sin red.

Es uno de los plugins del marketplace `arkana` (visión de conjunto en [`../README.md`](../README.md)).

## 1. Carpetas fijas

Las crea `install` (y vienen en cualquier clon, porque llevan su `.gitkeep`):

```text
<repo de Arkana>/
├── arkana-incoming/            cola de entrada. Solo se versionan .gitignore y .gitkeep: el resto es local
├── arkana-knowledge/<topic>/<slug>.md      notas
├── arkana-docs/
│   ├── src/                    los originales, tal cual los entregó el cliente; intactos y de solo lectura (0444)
│   ├── md/                     su versión en Markdown, con el MISMO árbol: arkana-docs/src/a/b.pdf → arkana-docs/md/a/b.pdf.md
│   └── out/                    documentos elaborados a petición de la persona usuaria, siempre en duplas (ver abajo)
└── arkana-project.json         registro de componentes (lo crea /arkana-evolve:apply)
```

Los documentos de `arkana-docs/src/` son la fuente y la prueba (no se editan: `validate` compara su sha256 con el que guarda su Markdown, y `ingest` los deja en solo lectura; git no versiona ese permiso y un sync desde Windows lo pierde, así que la garantía real es el hash). Los de `arkana-docs/md/` son la versión transformada para que la IA los lea, y es la que `query` consulta.

**`arkana-docs/out/`: documentos elaborados, siempre en duplas.** Cada documento que Arkana elabora a petición de la persona usuaria son dos ficheros en la misma carpeta y con el mismo nombre:

```text
arkana-docs/out/informe-x.md      fuente de la verdad: la información
arkana-docs/out/informe-x.docx    renderización de informe-x.md en el formato que pidió la persona usuaria
```

El `.md` manda: el render se regenera a partir de él (nunca al revés) y puede haber varios (`informe-x.docx`, `informe-x.pdf`). Un `.md` sin render es un entregable en Markdown y es válido; un render sin su `.md` no se puede regenerar ni auditar, y `validate` lo avisa (`WARN|out`). La estructura de subcarpetas de `out/` es libre. Hoy `out/` no se indexa en `query` ni hay un skill que escriba en ella: es la carpeta y su regla.

## 2. Identidad: UUID y alias

Cada nota y cada documento tiene un **UUID v4** (`id`) que no cambia nunca; el **slug** es solo el nombre del fichero, y el título es lo que se muestra. `components` guarda los componentes **por su id del registro** del proyecto (o `all`): renombrar un componente no obliga a tocar ningún documento, y `query` y los informes muestran siempre el alias. Se puede referir una nota por UUID o por slug.

## 3. Notas

Frontmatter: `id`, `slug`, `titulo`, `topic`, `version`, `fecha`, `autor`, `components`, `etiquetas`, `fuentes` (UUID de los documentos de los que sale: **procedencia**), `resumen`, `state` (`active|deleted`). El cuerpo termina en `## Changelog`, una línea por versión que `modify` añade y nunca pisa.

Topics: `decision`, `lesson`, `pending`, `contract`, `reference`, `methodology`. El borrado es lógico (`state: deleted`: se oculta de `query`, se conserva y `modify --restore` lo deshace).

## 4. Documentos e ingesta

`ingest` recoge lo que cae en `arkana-incoming/`:

1. **`ingest scan`** lista lo pendiente: tamaño, tipo, si ya es estable (que no se esté copiando), duplicados por **sha256** y conversión disponible.
2. **Clasificar** —nota de conocimiento o documento— es decisión con la persona usuaria: si hay duda, se le pregunta explicando cuál es.
3. **Conversión:** `md` sin más; `docx` y `pptx` con la biblioteca estándar (macros rechazadas, límites de zip); `pdf` con `pdftotext` si está instalado. Sin herramienta, o con un PDF sin texto, **lo lee el modelo** y escribe el Markdown (`--md-file F --conversion modelo --coverage completa|parcial`), y se pide a la persona usuaria que instale `poppler-utils`; `ingest reconvert` lo rehace cuando haya herramienta.
4. **`ingest add`** mueve el original a `arkana-docs/src/<dest-dir>/` (de solo lectura), guarda su Markdown en `arkana-docs/md/<dest-dir>/` y registra sha256, tipo, tamaño y conversión. Rechaza enlaces simbólicos, punteros git-lfs, macros y duplicados.

Sin tope de tamaño (git-lfs cuando el repo lo permita). Los secretos que lleven los documentos son naturaleza del cliente: no bloquean la ingesta y nunca se repiten sus valores.

**Arkana nunca instala herramientas** (`poppler-utils`, `git-lfs`…): las pide a la persona usuaria, porque su `sudo` necesita una contraseña que Arkana no tiene.

## 5. Hooks

| Evento | Qué hace |
|---|---|
| `SessionStart` | pide a Claude Code vigilar `arkana-incoming/` (`watchPaths`) y avisa si ya hay ficheros |
| `FileChanged` | apunta en `.arkana/arkana-knowledge/pending.json` el fichero que llegó |
| `UserPromptSubmit` | una línea con lo pendiente, solo cuando hay algo nuevo en esa sesión |

Los hooks no ingieren nada: solo avisan. Ingerir es `/arkana-knowledge:ingest`.

## 6. Herramienta `knowledge.py`

`python3 scripts/lib/knowledge.py <subcomando> [--home DIR] [--dry-run] [--json]`. Salida `ESTADO|ID|detalle` y `RESUMEN|n FAIL|n WARN`; códigos 0 sin fallos, 1 fallo, 2 uso, 3 precondición.

| Subcomando | Qué hace |
|---|---|
| `install` | crea las carpetas fijas y el índice |
| `add` / `modify` / `delete` | crea, versiona o borra (lógico) una nota |
| `query --q` / `query --id` | busca en notas y documentos (`--topic --component --kind --include-deleted`) o muestra una |
| `ingest scan\|convert\|add\|reconvert` | documentos |
| `validate` | solo lectura: frontmatter, UUID únicos, componentes contra el registro, Changelog, sha256 de los originales, huérfanos de `arkana-docs/src/`, originales sueltos del layout anterior (`WARN|suelto`), la regla de duplas de `arkana-docs/out/`, punteros git-lfs, catálogo antiguo y cola de `arkana-incoming/` |
| `reindex` | reconstruye el índice local |

## 7. Skills

`/arkana-knowledge:` `install` · `add` · `modify` · `delete` · `query` · `ingest` · `check` · `fix`. Detalle en cada `skills/*/SKILL.md`.

## 8. Pruebas

`bash tests/run-tests.sh` (sin red). Un fichero «estable» tarda 5 s en serlo; `ARKANA_STABLE_SECONDS=0` lo desactiva en pruebas. Para repos anteriores, `/arkana-evolve:apply` migra los ids antiguos y retira el catálogo versionado.
