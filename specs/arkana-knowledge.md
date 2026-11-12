# Especificación del plugin: arkana-knowledge

> **Estado:** `beta` | **Versión:** `2.0.9`

---

## Descripción general

Conocimiento común de un workspace de Arkana: notas versionadas con id UUID y documentos de origen con su versión en Markdown, ingesta desde arkana-incoming y consulta (add, query, modify, delete, ingest)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `add` | 2 | Añade una nota de conocimiento común (decisión, lección, pendiente, contrato, referencia o metodología) en arkana-knowledge/<topic>/ con id UUID, frontmatter versionado, procedencia (fuentes) y Changelog. Antes busca para no duplicar. Acepta --dry-run y --json. |
| `check` | 3 | Valida de solo lectura notas y documentos - frontmatter, ids UUID únicos, componentes contra el registro, Changelog al día, sha256 de los originales, huérfanos, punteros git-lfs y cola de arkana-incoming. Nunca corrige. Acepta --json. |
| `delete` | 4 | Borra una nota de forma lógica - queda con state deleted, se oculta de query y se conserva; el borrado queda en su Changelog y se deshace con modify --restore. Pide confirmación. Acepta --dry-run y --json. |
| `fix` | 5 | Corrige el conocimiento - reconstruye el índice local derivado y crea las carpetas fijas que falten. Para el resto de avisos de check indica qué hacer, sin tocar notas ni documentos. Acepta --dry-run y --json. |
| `ingest` | 6 | Ingiere lo que hay en arkana-incoming/ (o una ruta indicada) - decide si es conocimiento (nota) o documento (original en arkana-docs/ con su Markdown en arkana-docs/md/), pregunta cuando hay duda explicando cuál, convierte con herramientas o con el propio modelo y registra procedencia. Nunca instala herramientas. Acepta --dry-run. |
| `install` | 7 | Primera puesta en marcha del conocimiento - crea las carpetas fijas arkana-incoming/, arkana-knowledge/, arkana-docs/ y arkana-docs/md/ (con .gitkeep) y el índice local. Repetible; nunca instala herramientas. Acepta --dry-run y --json. |
| `modify` | 8 | Modifica una nota existente (por UUID o slug) - sube la versión, añade una línea al Changelog de la propia nota (nunca lo pisa); también restaura una nota borrada con --restore. Acepta --dry-run y --json. |
| `query` | 9 | Consulta notas y documentos (por su versión en Markdown) filtrando por topic, componente y tipo, y responde citando UUID, versión y ruta. Oculta lo borrado. Úsalo antes de decidir algo que pueda estar ya decidido. Solo lectura; acepta --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 2.0.9 | query: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.8 | modify: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.7 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.6 | ingest: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.5 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.4 | delete: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.3 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.2 | add: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.1 | Bootstrap: plugin registrado en catalog.json |
