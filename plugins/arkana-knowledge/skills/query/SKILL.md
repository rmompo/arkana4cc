---
name: query
description: Consulta notas y documentos (por su versión en Markdown) filtrando por topic, componente y tipo, y responde citando UUID, versión y ruta. Oculta lo borrado. Úsalo antes de decidir algo que pueda estar ya decidido. Solo lectura; acepta --json.
version: 9
---

# arkana-knowledge:query

Responde con el conocimiento común **citando las fuentes**. Solo lectura.

1. **Busca:** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --q "<palabras clave>" [--topic <topic>] [--component <alias|arkana|all>] [--kind note|document|all] --limit 8 [--json]`. Salida: `puntuación|uuid|versión|topic|ruta|título`; los documentos salen como `doc`. `--component app` incluye lo de ese componente y lo de `all`. Sin resultados: sinónimos o un término más general; si sigue vacío, dilo.
2. **Lee solo las candidatas** (1–4): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --id <uuid|slug>` (de un documento devuelve su Markdown; el original está en `arkana-docs/`, en la ruta que indica su frontmatter).
3. **Responde** de forma concisa citando título · UUID · `vX.Y` · ruta. Si dos notas se contradicen, muéstralo y prioriza la más reciente. Si el Markdown de un documento lo hizo el modelo (`conversion: modelo`), avisa de su cobertura.
4. Si la respuesta no está, dilo; no inventes. No muestres valores de secretos aunque aparezcan: avisa de que el documento los contiene.
