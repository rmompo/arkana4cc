# arkana-knowledge

Conocimiento común de un workspace de Arkana (ARKANA más el proyecto y sus componentes), guardado en el repositorio de ARKANA, que es también el repositorio de conocimiento del proyecto. Son las personas usuarias quienes lo gestionan (lo administran con `add`, `modify` y `delete`, y lo consultan con `query`): **notas Markdown versionadas en git**, que el equipo comparte, con un **catálogo** que se lee primero y un **changelog dentro de cada nota**. Sustituye al antiguo plugin `arkana-shared`.

**Funciona como un pseudo-RAG.** El plugin mantiene un **catálogo** (`catalog.json`) y los documentos que indexa, y los organiza para que las personas usuarias los consulten y exploten su contenido de la forma más eficiente: el catálogo se lee primero, `query` recupera las notas más relevantes por palabras clave (puntúa título, etiquetas, resumen, id y cuerpo, y filtra por `topic` y componente) y el modelo trabaja solo con lo recuperado en lugar de cargar todo el conocimiento. No usa embeddings ni servicios externos: la recuperación es léxica, local y determinista.

Es uno de los seis plugins del marketplace `arkana` (visión de conjunto en [`../README.md`](../README.md)). Solo usa la biblioteca estándar de Python 3; no necesita red.

## Contenido

1. [Objetivo](#1-objetivo)
2. [Relación con los otros plugins](#2-relación-con-los-otros-plugins)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Herramienta `knowledge.py`](#4-herramienta-knowledgepy)
5. [Referencia de skills](#5-referencia-de-skills)
6. [Migración del formato antiguo](#6-migración-del-formato-antiguo)
7. [Pruebas, desarrollo e instalación](#7-pruebas-desarrollo-e-instalación)

---

## 1. Objetivo

Guardar **lo que el equipo ha decidido o aprendido** de forma que sobreviva a las sesiones y a las personas: una decisión de arquitectura, una lección aprendida, un pendiente global, un contrato entre componentes o una nota de referencia. Cada nota es un fichero `.md` revisable en un PR, con su historial en git y, además, con su propio `## Changelog` de una línea por versión.

Cómo se usa: **antes de decidir algo**, se consulta (`query`); **al decidir o aprender algo**, se añade (`add`) o se actualiza (`modify`); lo obsoleto se borra de forma lógica (`delete`). El catálogo (`arkana-knowledge/catalog.json`) es el índice que se lee primero para no abrir todas las notas.

| | `arkana-knowledge` | `arkana-messaging` | `arkana-agentic` |
|---|---|---|---|
| Para qué | **Recordar** (conocimiento duradero) | **Avisar o pedir** (algo que hay que atender) | **Ejecutar** trabajo de edición con workers |
| Vida | Permanente, se versiona y se corrige | Efímera: se lee, se atiende y se cierra | Un plan: se aprueba, se ejecuta y se archiva |
| Dónde vive | En el repo de Arkana, **versionado en git** | Local a la máquina (`.arkana/`), no se versiona | Local (`.arkana/`) y ramas `arkana-worker/<plan>` |
| Quién la ve | Todo el equipo, vía git | El componente destinatario | La persona que gobierna el plan |

Regla práctica: si es algo **a hacer** o **a contestar**, es un mensaje; si es algo que **conviene recordar dentro de seis meses**, es una nota.

## 2. Relación con los otros plugins

| Plugin | Relación |
|---|---|
| `arkana-workspace` | Aporta el **manifiesto**: los alias válidos de `components` salen de él. Además de los alias de los componentes valen `arkana` (el propio repo de Arkana) y `all` (todos). El alias histórico `shared` se normaliza a `arkana`. Si el manifiesto no se puede cargar, no se validan los componentes (no se bloquea el trabajo). Localiza el repo de Arkana con la misma lógica de siempre (`ARKANA_HOME`, subida de carpetas con `.arkana/arkana.json`, registro de workspaces). |
| `arkana-messaging` | **Complementarios.** Un mensaje avisa («hay una nota nueva sobre X», «revisa la decisión Y») y la nota es la que queda; un mensaje no sustituye a la nota ni al revés. |
| `arkana-agentic` | **Los workers no leen el conocimiento** (no ven otros ficheros que los de su tarea ni este plugin). Por eso las notas **no son el sitio de las directrices** que un worker deba cumplir: para eso están los mensajes `repeat`, que `launch` copia en el prompt del worker. Lo que un worker necesite de una nota lo lee el orquestador y lo pasa como contexto del plan. |
| `arkana-statusline` | **Sin relación**: la barra de estado no lee ni muestra notas, y `arkana-knowledge` no depende de ella ni al revés. |

`arkana-knowledge` no declara dependencias (`arkana-plugin.json`: `provides` = `install`, `check`, `fix`, `add`, `query`, `modify`, `delete`; `check` = `python3 scripts/lib/knowledge.py validate`; sin hooks ni datos propios en `.arkana/`).

## 3. Modelo de datos

### 3.1 Estructura

```text
<repo de Arkana>/
├── arkana-knowledge/
│   ├── catalog.json                 # índice (se genera; no se edita a mano)
│   ├── decision/<slug>.md
│   ├── lesson/<slug>.md
│   ├── pending/<slug>.md
│   ├── contract/<slug>.md
│   └── reference/<slug>.md
└── <cualquier-otra-ruta>/nota.md    # también cuentan las notas con frontmatter fuera de arkana-knowledge/
```

Las notas nuevas se crean siempre en `arkana-knowledge/<topic>/<slug>.md`. Pero **cualquier `.md` con frontmatter e `id`** bajo el repo se considera nota (por ejemplo, las notas de referencia que viven en la raíz de ARKANA); `reindex` las recoge en el catálogo con su ruta real. Se ignoran estas carpetas: `.git`, `node_modules`, `archivo`, `plantillas`, `plugins`, `scripts`, `.claude`, `.claude-session`, `.arkana`, `lib`, `.historial` y `conocimiento` (esta última es el formato antiguo; ver [sección 6](#6-migración-del-formato-antiguo)).

### 3.2 Frontmatter

```markdown
---
id: decision-usar-cache-en-api
titulo: "Usar caché en la API de consulta"
topic: decision
version: 1.2
fecha: 2026-11-04
autor: Nombre Apellido
components: [api, app]
etiquetas: [cache, rendimiento]
resumen: "La API de consulta cachea respuestas 60 s; la app no reintenta."
state: active
---

# Usar caché en la API de consulta
(cuerpo en Markdown)

## Changelog

- v1.0 · 2026-10-02 · Nombre Apellido — creada
- v1.1 · 2026-10-20 · Nombre Apellido — amplía el motivo
- v1.2 · 2026-11-04 · Nombre Apellido — reduce el TTL a 60 s
```

| Campo | Contenido | Quién lo pone |
|---|---|---|
| `id` | Identificador **estable**: `<topic>-<slug>`, solo `a-z`, `0-9` y `-` (debe empezar por letra o dígito). No cambia nunca: ni al modificar ni al migrar. | `add` |
| `titulo` | Título legible (entre comillas en el fichero) | `add`, `modify --title` |
| `topic` | Uno de los cinco topics (tabla siguiente) | `add` (no se cambia después) |
| `version` | Formato `N.N` (`1.0`, `1.1`, `2.0`…) | La herramienta (versionado automático) |
| `fecha` | Fecha ISO (`AAAA-MM-DD`) de la **última** versión | La herramienta |
| `autor` | Autor de la última versión | `--author`; si falta, `git config user.name` del repo de Arkana, luego `$USER`, luego `desconocido` |
| `components` | Lista de alias del manifiesto, `arkana` y/o `all`. Por defecto `[all]` | `add`, `modify --components` |
| `etiquetas` | Lista libre de palabras clave (pesan en la búsqueda) | `add`, `modify --tags` |
| `resumen` | Una frase (entre comillas en el fichero) | `add`, `modify --summary` |
| `state` | `active` o `deleted` | La herramienta |

La herramienta escribe el frontmatter siempre en este orden y en este formato; si editas a mano, respétalo (una clave por línea, listas entre corchetes separadas por comas, sin saltos de línea en `titulo` ni `resumen`).

### 3.3 Topics

| `topic` | Qué guarda |
|---|---|
| `decision` | Una decisión tomada y su porqué |
| `lesson` | Una lección aprendida (qué pasó y qué hacer la próxima vez) |
| `pending` | Un pendiente global que no pertenece a un solo componente |
| `contract` | Un acuerdo entre componentes (API, formato, convención) |
| `reference` | Información de consulta (cómo está organizado algo, guías) |

### 3.4 Estado y borrado lógico

`state: active` es lo normal. `state: deleted` es un **borrado lógico**: el fichero **no se elimina**, sigue en el catálogo (con `state: deleted`) y en git, pero `query` lo oculta salvo con `--include-deleted`. Borrar sube la versión y deja la línea en el Changelog; `modify --restore` lo deshace. No hay ningún borrado físico en la herramienta.

### 3.5 Changelog

Al final de cada nota, bajo `## Changelog`, **una línea por versión** con el formato `- vN.N · AAAA-MM-DD · autor — texto`. Lo mantiene la herramienta: `add` escribe `v1.0 … creada`, `modify` añade una línea con el `--change`, `delete` añade «borrada (borrado lógico)» y el motivo. **`modify` nunca lo pisa**: lee las líneas existentes (las que empiezan por `- `), reescribe solo el cuerpo y las vuelve a escribir con la nueva al final. `validate` exige que exista y que su **última entrada sea la versión actual**. Ya no hay ficheros `.historial` aparte: el historial completo vive en la nota y en git.

### 3.6 Catálogo

`arkana-knowledge/catalog.json` es un índice que se **genera** (no se edita a mano) y se reescribe tras cada `add`, `modify`, `delete`, `reindex` y `migrate`:

```json
{ "version": 2, "actualizado": "2026-11-04",
  "notas": [ { "id": "...", "titulo": "...", "topic": "...", "version": "...", "fecha": "...", "autor": "...",
               "components": ["..."], "etiquetas": ["..."], "resumen": "...", "state": "active",
               "ruta": "arkana-knowledge/decision/<slug>.md" } ] }
```

Las entradas van ordenadas por `id`. Incluye las notas borradas (con `state: deleted`) y solo las que tienen `topic` (las del formato antiguo no entran hasta migrar). `validate` avisa si está desincronizado (nota que falta, sobra o con otra ruta); `reindex` lo reconstruye.

### 3.7 Reglas de seguridad y qué se versiona

- **Sin secretos**: ni credenciales, ni tokens, ni contenido de `.env`, ni datos personales. Las notas se comparten por git y quedan en su historial. Si una nota los contiene, `query` no debe mostrarlos y hay que avisar de que los contiene.
- **Qué se versiona**: todo `arkana-knowledge/` (notas y `catalog.json`) es parte del repo de Arkana y **se commitea**. El plugin **nunca hace `commit`, `push` ni `git add`**: tras cada cambio la nota queda sin commitear, y lo gestiona la persona con la convención de commits del repo. Lo que no se versiona es `.arkana/` (ignorada por git), donde este plugin no escribe nada.
- Una nota no duplica lo que es de otro componente: enlaza a su ruta.

---

## 4. Herramienta `knowledge.py`

Todo lo hacen los skills llamando a `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" <subcomando> [opciones]`. Ejecutada a mano, desde `scripts/lib/knowledge.py` del plugin.

```text
knowledge.py [--home DIR] {add|modify|delete|query|validate|reindex|install|migrate} [opciones]
```

### 4.1 Opciones comunes

| Opción | Dónde va | Efecto |
|---|---|---|
| `--home DIR` | **Antes** del subcomando | Carpeta del repo de Arkana. Por defecto se localiza (variable `ARKANA_HOME`, o subiendo desde el directorio actual hasta una carpeta con `.arkana/arkana.json`, o el registro de workspaces). Sin workspace ni `--home`: error y salida 3. |
| `--json` | Después del subcomando; todos | Salida JSON en vez de líneas de texto. En `query` imprime una lista de resultados (ver `query`); con `query --id` se ignora y se imprime la nota. |
| `--dry-run` | Después del subcomando; solo `add`, `modify`, `delete`, `reindex`, `install`, `migrate` | No escribe nada ni mueve ni borra; informa con estado `DRY` de lo que haría. **No existe** en `query` ni en `validate` (que ya son de solo lectura): usarlo ahí es un error de uso (salida 2). |

### 4.2 Formato de salida y códigos de salida

Salvo `query` (que tiene salida propia), cada comando imprime una línea por comprobación `ESTADO|ID|detalle` (`OK`, `WARN`, `FAIL`, `INFO`, `DRY`) y al final `RESUMEN|n FAIL|n WARN`. Con `--json`: `{"plugin": "arkana-knowledge", "skill": <subcomando>, "status": "ok|warn|fail", "items": [{"id", "status", "detail", "component"}], "summary": {"fail", "warn", "ok", "info", "dry"}}`.

| Código | Cuándo |
|---|---|
| `0` | Sin `FAIL` (los `WARN` no cuentan) |
| `1` | Hay algún `FAIL`: nota inexistente, nota ya existente, nota borrada sin `--restore`, error de ficheros (p. ej. `--body-file` ilegible)… |
| `2` | Uso incorrecto: opción desconocida o faltante, `topic` inválido, `id` resultante inválido, componentes desconocidos, consulta vacía |
| `3` | Precondición: no se localiza un workspace de Arkana |

### 4.3 Resumen de subcomandos

| Subcomando | Lee | Escribe | Skill |
|---|---|---|---|
| `add` | catálogo, git (`user.name`), manifiesto | la nota nueva y `catalog.json` | `add` |
| `modify` | la nota, catálogo, git (`user.name`), manifiesto | la nota y `catalog.json` | `modify` |
| `delete` | la nota, catálogo, git (`user.name`) | la nota y `catalog.json` | `delete` |
| `query` | notas (o la nota concreta con `--id`) | nada | `query` |
| `validate` | notas, catálogo, manifiesto | nada | `check` |
| `reindex` | notas | `catalog.json` | `fix` (parcial) |
| `install` | carpeta y catálogo | `arkana-knowledge/` y `catalog.json` si faltan | `install` |
| `migrate` | formato antiguo | notas, borra restos antiguos, `catalog.json`; usa `git mv` / `git rm` | `fix` |

Escrituras atómicas (fichero temporal y renombrado). **Git**: la herramienta solo ejecuta `git config user.name` (autor por defecto) y, en `migrate`, `git ls-files`, `git mv` y `git rm`; nunca `add`, `commit` ni `push`.

---

## 5. Referencia de skills

Los 7 skills están en `skills/<nombre>/SKILL.md`. Cada uno invoca la herramienta con `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" …`.

| Skill | Subcomando(s) | Escribe |
|---|---|---|
| [`add`](#51-arkana-knowledgeadd) | `query` (antes) + `add` + `validate` | sí |
| [`query`](#52-arkana-knowledgequery) | `query` | no |
| [`modify`](#53-arkana-knowledgemodify) | `modify` + `validate` | sí |
| [`delete`](#54-arkana-knowledgedelete) | `delete` | sí |
| [`install`](#55-arkana-knowledgeinstall) | `install` | sí |
| [`check`](#56-arkana-knowledgecheck) | `validate` | no |
| [`fix`](#57-arkana-knowledgefix) | `validate` + `migrate` / `reindex` + `validate` | sí |

### 5.1 `/arkana-knowledge:add`

**Para qué**: guardar un conocimiento nuevo como nota versionada y registrarla en el catálogo. **Cuándo**: tras tomar una decisión, aprender una lección, fijar un contrato o querer dejar una referencia, y **solo si no existe ya** una nota equivalente.

**Orden exacta**

1. Reunir los datos (con `AskUserQuestion` si no los dio el usuario): topic, título, resumen (una frase), componentes (por defecto `all`), etiquetas y contenido en Markdown, redactado a partir de lo hablado **sin inventar y sin secretos**.
2. Buscar duplicados: `query --q "<título y palabras clave>" --limit 5`. Si hay una nota equivalente, **se modifica** (`/arkana-knowledge:modify`) y se dice.
3. Crear: `add --topic <topic> --title "<título>" --summary "<resumen>" --components app,api --tags a,b --body-file <fichero>` (`--dry-run` para ensayar).
4. Validar: `validate` debe terminar sin `FAIL`.
5. Resumir: id, versión, ruta y componentes, recordando que **queda sin commitear**.

**Parámetros de `add`**

| Parámetro | Obligatorio | Valores / por defecto | Efecto y errores |
|---|---|---|---|
| `--topic` | sí | `decision`, `lesson`, `pending`, `contract`, `reference` | Carpeta y prefijo del id. Otro valor: error, salida 2. |
| `--title` | sí | texto | Va en `titulo`. Si no hay `--slug`, de él sale el slug. |
| `--summary` | sí | una frase | Va en `resumen`. |
| `--slug` | no | por defecto, el título pasado a minúsculas, sin tildes ni `ñ`, con guiones y recortado a 60 caracteres (`nota` si queda vacío) | El `id` será `<topic>-<slug>` y el fichero `arkana-knowledge/<topic>/<slug>.md`. Si el id resultante no cumple `a-z0-9-` (empezando por letra o dígito): error, salida 2. |
| `--components` | no | lista separada por comas de alias, `arkana` o `all`; por defecto `all` | Los alias se pasan a minúsculas (`shared` → `arkana`). Un alias que no esté en el manifiesto: error con la lista de válidos, salida 2. Vacío equivale a `all`. |
| `--tags` | no | lista separada por comas; por defecto vacía | Va en `etiquetas`. |
| `--author` | no | por defecto `git config user.name`, luego `$USER`, luego `desconocido` | Va en `autor` y en el Changelog. |
| `--body-file` | no | ruta de un fichero Markdown | Cuerpo de la nota. Si no se puede leer: `FAIL` «error de ficheros», salida 1. |
| `--body` | no | texto | Cuerpo en línea. Si se dan ambos, gana `--body-file`. Sin cuerpo, se escribe `# <título>`. |
| `--dry-run` | no | | Informa `DRY add: se crearía <id> v1.0 → <ruta>` sin escribir. |
| `--json` | no | | Salida JSON. |

**Efecto**: crea `arkana-knowledge/<topic>/<slug>.md` con `version: 1.0`, `fecha` de hoy, `state: active` y un Changelog con `v1.0 … creada`, y reescribe `catalog.json`. Si el id ya existe (aunque esté borrado): `FAIL «ya existe la nota '<id>': usa modify para versionarla»`, salida 1. No hace `git add` ni commit.

**Salida**: `OK|add|creada <id> v1.0 → <ruta>` (`DRY|add|…` con `--dry-run`).

**Ejemplo**

```bash
python3 scripts/lib/knowledge.py query --q "cache respuestas api" --limit 5
python3 scripts/lib/knowledge.py add --topic decision --title "Usar caché en la API de consulta" \
  --summary "La API cachea respuestas 60 s; la app no reintenta." --components api,app --tags cache,rendimiento --body-file /tmp/nota.md
python3 scripts/lib/knowledge.py validate
```

### 5.2 `/arkana-knowledge:query`

**Para qué**: responder con el conocimiento común **citando las fuentes** (id, versión, ruta). **Cuándo**: **antes de decidir** algo que pueda estar ya decidido, o cuando alguien pregunta «¿qué acordamos sobre…?». **Solo lectura.**

**Orden exacta**

1. Buscar: `query --q "<palabras clave>" [--topic <topic>] [--component <alias|arkana|all>] --limit 8 [--json]`. Sin resultados: probar sinónimos o un término más general; si sigue vacío, decirlo y sugerir `/arkana-knowledge:add`.
2. Leer **solo las candidatas** (1–4): `query --id <id>` o `Read` sobre la ruta. Cada nota termina en su `## Changelog` (qué cambió y cuándo).
3. Responder de forma concisa citando `id` · `vX.Y` · ruta. Si dos notas se contradicen, mostrarlo y priorizar la más reciente.
4. Si la respuesta no está en el conocimiento, decirlo; no inventar. No mostrar secretos aunque aparecieran (avisar de que la nota los contiene).

**Parámetros de `query`**

| Parámetro | Valores / por defecto | Efecto y errores |
|---|---|---|
| `--q` | palabras | Se parte en palabras (`\w+`, minúsculas) y se descartan las de un solo carácter. Cada palabra puntúa: título ×5, etiquetas ×4, resumen ×3, id ×2, cuerpo (incluido el Changelog) ×1, contando como máximo 5 apariciones por campo. Solo salen notas con puntuación > 0. Sin palabras útiles (y sin `--id`): `FAIL «consulta vacía (usa --q o --id)»`, salida 2. |
| `--id` | id de nota | Imprime la nota completa (frontmatter, cuerpo y Changelog), **sin importar su `state`**, y sale con 0. Ignora `--q`, filtros y `--json`. Id inexistente: `FAIL`, salida 1. La ruta se resuelve con el catálogo (si falta, se calcula al vuelo sin escribirlo). |
| `--topic` | uno de los cinco topics | Deja solo las notas de ese topic. No se valida el valor: uno desconocido simplemente no devuelve nada. |
| `--component` | alias, `arkana` o `all` | Con un alias (o `arkana`) salen las notas que lo incluyen **y las de `all`**. Con `all` no filtra. El alias se pasa a minúsculas (`shared` → `arkana`) y no se valida contra el manifiesto. |
| `--limit` | entero, por defecto `8` | Máximo de resultados tras ordenar por puntuación descendente y, a igualdad, por id. |
| `--include-deleted` | marca | Incluye las notas con `state: deleted` (por defecto se ocultan). |
| `--json` | marca | Lista JSON de objetos `{score, id, version, topic, state, components, titulo, ruta, resumen}`. Sin resultados, `[]`. |

`query` no admite `--dry-run`. Busca recorriendo las notas (no depende del catálogo) e ignora las del formato antiguo hasta migrarlas.

**Salida de texto**: una línea por resultado `puntuación|id|vX.Y|topic|ruta|título`, o `sin resultados`. Salida 0 salvo los errores indicados.

**Ejemplos**

```bash
python3 scripts/lib/knowledge.py query --q "cache api" --topic decision --component api --limit 5
python3 scripts/lib/knowledge.py query --q "contrato" --component app-web --json
python3 scripts/lib/knowledge.py query --id decision-usar-cache-en-api
python3 scripts/lib/knowledge.py query --q "cache" --include-deleted
```

### 5.3 `/arkana-knowledge:modify`

**Para qué**: actualizar una nota existente (cuerpo y/o metadatos) subiendo su versión y dejando constancia en su Changelog; también **restaurar** una borrada. **Cuándo**: cambia la decisión o el contexto, se amplía una lección, o `add` detecta que la nota ya existía.

**Orden exacta**

1. Localizar la nota (`query`), leerla y redactar el cambio sin inventar ni incluir secretos. Pasar **el cuerpo completo** nuevo, sin el Changelog (la herramienta lo conserva).
2. Ensayar con `--dry-run` si hay duda y ejecutar con un `--change` claro (una frase).
3. `validate` debe seguir sin `FAIL`. Queda sin commitear.
4. Una nota **borrada** solo se toca con `--restore` en la misma orden (restaura y aplica los cambios; preguntando antes al usuario).

**Parámetros de `modify`**

| Parámetro | Obligatorio | Valores / por defecto | Efecto y errores |
|---|---|---|---|
| `--id` | sí | id existente | Id inexistente: `FAIL`, salida 1. Si la nota está borrada y no se da `--restore`: `FAIL «está borrada (borrado lógico): usa --restore para recuperarla»`, salida 1. |
| `--body-file` | no | fichero | **Sustituye** el cuerpo (sin Changelog). Sin `--body-file` ni `--body`, el cuerpo no cambia. Ilegible: salida 1. |
| `--body` | no | texto | Igual, en línea (gana `--body-file` si se dan ambos). |
| `--title` | no | texto | Cambia `titulo`. |
| `--summary` | no | texto | Cambia `resumen`. |
| `--components` | no | lista de alias, `arkana` o `all` | **Sustituye** la lista (no la fusiona), con la misma validación que `add`. Vacío equivale a `all`. |
| `--tags` | no | lista separada por comas | **Sustituye** las etiquetas. Vacío las borra. |
| `--author` | no | texto | Autor de esta versión. Si falta: `git config user.name`, `$USER`, `desconocido` (es decir, **no se conserva el autor anterior**). |
| `--major` | no | marca | Versión mayor: `1.4` → `2.0`. Sin ella, versión menor: `1.0` → `1.1`. |
| `--change` | no | texto | Texto de la línea del Changelog; por defecto `actualizada`. |
| `--restore` | no | marca | Pone `state: active`, y la línea del Changelog empieza por `restaurada.`. Es la única forma de modificar una nota borrada. Sobre una nota activa no falla: solo sube la versión. |
| `--dry-run` | no | | Informa `DRY modify: <id>: v<ant> → v<nueva>` sin escribir. |
| `--json` | no | | Salida JSON. |

**Versionado automático**: cada `modify` sube **siempre** la versión (aunque no cambie ningún campo), pone `fecha` de hoy, actualiza `autor` y añade una línea `- v<nueva> · fecha · autor — <--change>` **al final** del Changelog, conservando las anteriores. El `topic` y el `id` no cambian. Después reescribe `catalog.json`.

**Salida**: `OK|modify|<id>: v1.0 → v1.1 (el Changelog de la nota lo recoge)`.

**Ejemplos**

```bash
python3 scripts/lib/knowledge.py modify --id decision-usar-cache-en-api --body-file /tmp/nuevo.md --change "reduce el TTL a 60 s"
python3 scripts/lib/knowledge.py modify --id contract-formato-fechas --components api,app-web --major --change "el contrato pasa a v2"
python3 scripts/lib/knowledge.py modify --id lesson-orden-de-arranque --restore --change "vuelve a aplicar"
```

### 5.4 `/arkana-knowledge:delete`

**Para qué**: retirar una nota que ya no aplica sin perderla (**borrado lógico**). **Cuándo**: la decisión quedó obsoleta o la nota era errónea. **Pide confirmación.**

**Orden exacta**

1. Mostrar la nota (`query --id`) y pedir confirmación con `AskUserQuestion` («Borrar» / «Cancelar»), con el motivo.
2. Ejecutar `delete --id <id> [--reason "por qué"] [--dry-run]`.
3. Recordar que queda sin commitear y que `modify --restore` la recupera.

**Parámetros de `delete`**

| Parámetro | Obligatorio | Valores / por defecto | Efecto y errores |
|---|---|---|---|
| `--id` | sí | id existente | Inexistente: `FAIL`, salida 1. Ya borrada: `OK|delete|<id> ya estaba borrada` sin cambios (**idempotente**). |
| `--reason` | no | texto | Se añade al Changelog: `borrada (borrado lógico): <motivo>`. |
| `--dry-run` | no | | `DRY delete: <id>: se marcaría como borrada (v<ant> → v<nueva>)`. |
| `--json` | no | | Salida JSON. |

**Efecto**: pone `state: deleted`, sube la versión (menor), actualiza `fecha` y `autor` (el de git o `$USER`) y añade la línea al Changelog; **el fichero se conserva**, el catálogo lo mantiene con `state: deleted` y `query` lo oculta salvo con `--include-deleted`.

**Salida**: `OK|delete|<id> borrada (borrado lógico: se oculta de query y se conserva; modify --restore la recupera)`.

**Ejemplo**

```bash
python3 scripts/lib/knowledge.py delete --id pending-migrar-registro --reason "resuelto en la rama de la API"
```

### 5.5 `/arkana-knowledge:install`

**Para qué**: primera puesta en marcha. **Cuándo**: al activar el plugin en un workspace; es **repetible** (no toca lo que ya existe).

**Orden exacta**: `install [--dry-run] [--json]`. Si avisa de formato antiguo, `/arkana-knowledge:fix`.

**Parámetros de `install`**

| Parámetro | Efecto |
|---|---|
| `--dry-run` | No crea nada; informa `DRY` de lo que haría. |
| `--json` | Salida JSON. |

**Efecto**: crea `arkana-knowledge/` si falta y `arkana-knowledge/catalog.json` si falta (se genera a partir de las notas que ya haya, también fuera de la carpeta). Si hay **formato antiguo** (carpeta `conocimiento/`, `catalogo.json` o notas con `tipo`/`modulos`), añade `WARN|formato-antiguo|…: ejecuta /arkana-knowledge:fix`. No migra nada por sí mismo.

**Salida**: `OK|carpeta|arkana-knowledge/ creada` (o `presente`), `OK|catalogo|catálogo generado` (o `presente`), y el posible `WARN`. Salida 0; 3 si no hay workspace.

### 5.6 `/arkana-knowledge:check`

**Para qué**: validar el conocimiento **sin corregir nada**. **Cuándo**: tras añadir o modificar notas, en cada revisión del workspace, o antes de un PR. Es el `check` que declara `arkana-plugin.json`.

**Orden exacta**: `validate [--json]`. Si todo está `OK`, resumirlo en una línea; si no, proponer `/arkana-knowledge:fix` (catálogo y formato) o corregir la nota con `/arkana-knowledge:modify`.

**Parámetros de `validate`**: solo `--json` (y `--home` antes del subcomando). No admite `--dry-run` porque nunca escribe.

**Qué comprueba**

| Resultado | Condición |
|---|---|
| `FAIL\|nota:<id>` (una línea por nota, con todos sus problemas) | Falta alguno de `id`, `titulo`, `topic`, `version`, `fecha`, `autor`, `resumen`, `state`; `id` inválido; `topic` fuera de los cinco; `state` distinto de `active`/`deleted`; `version` que no sea `N.N`; componentes que no sean alias del manifiesto, `arkana` ni `all` (solo si el manifiesto carga); id duplicado; sin `## Changelog` (sin líneas `- `); última entrada del Changelog distinta de la versión actual |
| `WARN\|nota:<id>` | Nota con frontmatter del formato antiguo (`tipo`/`modulos`, sin `topic`): se salta |
| `WARN\|catalogo` | Falta `catalog.json`, o está desincronizado (nota ausente, sobrante o con otra ruta) |
| `OK\|catalogo` | `catálogo al día (N notas)` |
| `WARN\|formato-antiguo` | Quedan `conocimiento/`, `catalogo.json` o notas `tipo`/`modulos` |
| `OK\|notas` | `N notas válidas` (solo si no hay ningún `FAIL`) |

**Salida y códigos**: `0` sin `FAIL` (los `WARN` no fallan); `1` con algún `FAIL`.

### 5.7 `/arkana-knowledge:fix`

**Para qué**: dejar el conocimiento en el formato actual: migrar el formato antiguo y reconstruir el catálogo. **Cuándo**: cuando `check` o `install` avisan de `formato-antiguo` o de catálogo desincronizado. **Pide confirmación antes de migrar** (porque se borran restos antiguos).

**Orden exacta**

1. `validate` y, si hay `WARN` de `formato-antiguo`, `migrate --dry-run`: enseñar qué se movería, qué Changelog se genera y qué se borra (`conocimiento/.historial/` y `catalogo.json`; los ficheros antiguos siguen en el historial de git).
2. Pedir confirmación (`AskUserQuestion`) y aplicar `migrate`.
3. Si solo está desincronizado el catálogo: `reindex`.
4. `validate` otra vez; recordar que **queda sin commitear**.

**Parámetros de `migrate`**: `--dry-run`, `--json` (y `--home` antes). **Parámetros de `reindex`**: `--dry-run` (calcula el catálogo sin escribirlo e informa `DRY|reindex|catálogo (no escrito) reconstruido: N notas`), `--json`. Detalle de la migración en la [sección 6](#6-migración-del-formato-antiguo).

**Salida**: líneas `OK|migrar:<id>|<origen> → <destino> (N entradas de Changelog; componentes …)`, `OK|borrar:<ruta>|…` y `OK|migrate|N notas migradas` (o `no hay notas del formato antiguo`); `OK|reindex|catálogo reconstruido: N notas`.

---

## 6. Migración del formato antiguo

El formato antiguo es: carpeta `conocimiento/<tipo>/`, `catalogo.json` en la raíz, historial en `conocimiento/.historial/<id>/v*.md` y frontmatter con `tipo` y `modulos` (sin `topic` ni `components`). `migrate` (lo que ejecuta `fix`) lo convierte **sin cambiar ningún id**:

| Antes | Después |
|---|---|
| `conocimiento/<tipo>/x.md` | `arkana-knowledge/<tipo>/x.md`, movida con **`git mv`** si estaba versionada (si no, con un movimiento normal). Las notas que viven **fuera** de `conocimiento/` (p. ej. las de referencia de la raíz) **se quedan donde están** y solo se reescriben en su sitio. |
| `tipo` | `topic`; un tipo fuera de los cinco se convierte en `reference` |
| `modulos` | `components`, **copiados tal cual**; vacío → `[all]` |
| Historial `.historial/<id>/v*.md` | Líneas de `## Changelog`: una por versión archivada (con el `resumen` de esa versión) más la de la versión actual. Si la nota ya tenía Changelog, se respeta |
| Campos ausentes | `version` `1.0`, `fecha` hoy, `autor` `desconocido`, `etiquetas` vacías, `state: active` |
| `conocimiento/.historial/` y `catalogo.json` | Se borran (con `git rm` si estaban versionados). Sus ficheros siguen en el historial de git. Si `conocimiento/` queda sin ficheros, se elimina |
| (nada) | `arkana-knowledge/catalog.json` reconstruido |

Es **idempotente**: sin notas antiguas informa `no hay notas del formato antiguo`. `--dry-run` muestra cada nota con origen, destino y nº de entradas de Changelog sin tocar nada. Tras migrar, la herramienta no hace commit: revisa `git status` y commitea.

---

## 7. Pruebas, desarrollo e instalación

**Pruebas** (sin red ni API real; unittest de la biblioteca estándar, 8 casos que cubren add/modify/query/validate con Changelog intacto, `all` y `--dry-run`, banderas y topics inválidos, componentes contra el manifiesto, borrado lógico y restauración, detección de problemas, migración con `git mv` e idempotencia, e `install`):

```bash
bash tests/run-tests.sh            # añade argumentos de unittest si hace falta (por defecto -v)
```

Todo el conjunto de plugins: `bash scripts/run-all-tests.sh` desde la carpeta de Arkana (`--only knowledge` para filtrar). Validación del plugin: `claude plugin validate plugins/arkana-knowledge`.

**Desarrollo**

- Código: `scripts/lib/knowledge.py` (un único fichero; `argparse` en `make_parser`). Es la fuente de verdad junto con `skills/*/SKILL.md`.
- **Núcleo vendorizado**: `scripts/_core/` es una copia de `lib/arkana_core/` (localizador, manifiesto, esquemas, salida y escrituras atómicas). No se edita aquí: se cambia en `lib/arkana_core/` y se regenera con `bash scripts/vendor-core.sh` (`--check` comprueba que todas las copias están al día), porque un plugin instalado no puede leer a otro.
- Contrato del plugin: `arkana-plugin.json` (ver [`../docs/PLUGIN-CONTRACT.md`](../docs/PLUGIN-CONTRACT.md)); formato de salida y códigos en [`../docs/OUTPUT-CONTRACT.md`](../docs/OUTPUT-CONTRACT.md).

**Instalación**

```bash
claude plugin marketplace add <ruta>/plugins
claude plugin install arkana-knowledge@arkana
```

Después, desde el repo de Arkana: `/arkana-knowledge:install` (crea `arkana-knowledge/` y el catálogo) y `/arkana-knowledge:check`. Si el conocimiento venía del formato antiguo o de `arkana-shared`, `/arkana-knowledge:fix`. Requiere Python 3 y, para la migración con `git mv`, `git`; el manifiesto de `arkana-workspace` solo hace falta para validar los alias de `components`.
