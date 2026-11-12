---
name: ingest
description: Ingiere lo que hay en arkana-incoming/ (o una ruta indicada) - decide si es conocimiento (nota) o documento (original en arkana-docs/ con su Markdown en arkana-docs/md/), pregunta cuando hay duda explicando cuál, convierte con herramientas o con el propio modelo y registra procedencia. Nunca instala herramientas. Acepta --dry-run.
version: 6
---

# arkana-knowledge:ingest

Convierte lo que cae en `arkana-incoming/` en conocimiento consultable. **Siempre con la persona usuaria**: clasificar exige criterio.

## Pasos

1. **Ve qué hay:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" ingest scan [--from <ruta>] [--json]` → ruta, tamaño, tipo, si ya es estable (no se está copiando), `DUPLICADO` (mismo sha256 ya ingerido) y qué conversión hay disponible. Los inestables se dejan para después.
2. **Clasifica cada uno** — *nota de conocimiento* (lo decidido o aprendido, que el equipo debe recordar) o *documento* (material de origen del cliente o del proyecto: especificaciones, manuales, actas). Si hay duda real, **pregunta con `AskUserQuestion` explicando por qué dudas** (p. ej. «es un acta: contiene una decisión pero también el hilo completo»). Un documento puede dar lugar además a notas (`--sources <uuid>`).
3. **Convierte (documentos):** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" ingest convert --file <ruta> [--out F]` usa herramientas (docx, pptx y md sin instalar nada; PDF con `pdftotext`). Sin herramienta o PDF sin texto (escaneado): **lee el documento tú**, escribe su Markdown (resumen fiel del contenido, sin inventar) y pásalo con `--md-file F --conversion modelo --coverage completa|parcial`; **pide a la persona usuaria** que instale `poppler-utils` para mejorarlo (**tú no lo instalas jamás**: su sudo pide contraseña que Arkana no tiene).
4. **Ingiere:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" ingest add --file <ruta> --title "<título>" --summary "<resumen>" [--tags a,b] [--components app,all] [--dest-dir sub/carpeta] [--md-file F --conversion modelo --coverage ..] [--keep-source] [--dry-run]`. Mueve el original a `arkana-docs/<dest-dir>/` y guarda su Markdown en `arkana-docs/md/` con el mismo árbol; registra sha256, tipo y tamaño. Rechaza enlaces simbólicos, punteros git-lfs, macros y duplicados.
5. **Notas:** para lo que es conocimiento, usa `/arkana-knowledge:add` (con `--sources` si procede).
6. **Valida:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" validate` sin `FAIL`. Resume qué se ingirió (UUID, ruta) y que **queda sin commitear**.

## Reglas

- Los secretos que contengan los documentos son naturaleza del cliente: **no bloquees** la ingesta ni repitas sus valores en tus respuestas.
- Sin tope de tamaño: si el repo usa git-lfs y no está instalado, pídeselo a la persona usuaria.
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" ingest reconvert --id <uuid>` rehace el Markdown con una herramienta nueva si antes lo hizo el modelo.
