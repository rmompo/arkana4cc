# Especificación del plugin: arkana-knowledge

> **Estado:** `beta` | **Versión:** `2.0.26`

---

## Descripción general

Conocimiento común de un workspace de Arkana: notas versionadas con id UUID y documentos de origen con su versión en Markdown, ingesta desde arkana-incoming y consulta (add, query, modify, delete, ingest)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `add` | 10 | Añade una nota de conocimiento común (decisión, lección, pendiente, contrato, referencia o metodología) en arkana-knowledge/<topic>/ con id UUID, frontmatter versionado, procedencia (fuentes) y Changelog. Antes busca para no duplicar. Acepta --dry-run y --json. |
| `check` | 11 | Valida de solo lectura notas y documentos - frontmatter, ids UUID únicos, componentes contra el registro, Changelog al día, sha256 de los originales, huérfanos, punteros git-lfs y cola de arkana-incoming. Nunca corrige. Acepta --json. |
| `delete` | 12 | Borra una nota de forma lógica - queda con state deleted, se oculta de query y se conserva; el borrado queda en su Changelog y se deshace con modify --restore. Pide confirmación. Acepta --dry-run y --json. |
| `fix` | 24 | Corrige el conocimiento - reconstruye el índice local derivado y crea las carpetas fijas que falten. Para el resto de avisos de check indica qué hacer, sin tocar notas ni documentos. Acepta --dry-run y --json. |
| `ingest` | 22 | Ingiere lo que hay en arkana-incoming/ (o una ruta indicada) - decide si es conocimiento (nota) o documento (original en arkana-docs/ con su Markdown en arkana-docs/md/), pregunta cuando hay duda explicando cuál, convierte con herramientas o con el propio modelo y registra procedencia. Nunca instala herramientas. Acepta --dry-run. |
| `install` | 25 | Primera puesta en marcha del conocimiento - crea las carpetas fijas arkana-incoming/, arkana-knowledge/, arkana-docs/ y arkana-docs/md/ (con .gitkeep) y el índice local. Repetible; nunca instala herramientas. Acepta --dry-run y --json. |
| `modify` | 16 | Modifica una nota existente (por UUID o slug) - sube la versión, añade una línea al Changelog de la propia nota (nunca lo pisa); también restaura una nota borrada con --restore. Acepta --dry-run y --json. |
| `query` | 17 | Consulta notas y documentos (por su versión en Markdown) filtrando por topic, componente y tipo, y responde citando UUID, versión y ruta. Oculta lo borrado. Úsalo antes de decidir algo que pueda estar ya decidido. Solo lectura; acepta --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 2.0.26 | Nucleo 1.11.1 vendorizado: el registro de workspaces conserva el nombre de una entrada existente |
| 2.0.25 | install: install: las carpetas finales (src, md, out, incoming y knowledge) llevan .gitkeep; arkana-docs/ ya no |
| 2.0.24 | fix: fix: indica que hacer con originales sueltos y renders sin fuente |
| 2.0.23 | install: install: crea tambien arkana-docs/src/ y arkana-docs/out/ |
| 2.0.22 | ingest: ingest: los originales van a arkana-docs/src/ (solo lectura) y se anuncia arkana-docs/out/ con duplas md y render |
| 2.0.21 | Nucleo vendorizado: registro de workspaces en ~/.arkana/workspaces.json |
| 2.0.20 | Nucleo 1.10.0 vendorizado: LAYOUT_KNOWN 7 |
| 2.0.19 | Nucleo 1.9.0 vendorizado: nombre-modulo compartido, resolucion por alias, carpeta o modulo y alias mostrados en mayusculas |
| 2.0.18 | Núcleo 1.8.0 vendorizado: campos mode, ref, watch y checks_skip del componente, esquema 2 del manifiesto y LAYOUT_KNOWN |
| 2.0.17 | query: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.16 | modify: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.15 | install: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.14 | ingest: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.13 | fix: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.12 | delete: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.11 | check: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.10 | add: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.0.9 | query: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.8 | modify: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.7 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.6 | ingest: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.5 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.4 | delete: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.3 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.2 | add: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.0.1 | Bootstrap: plugin registrado en catalog.json |
