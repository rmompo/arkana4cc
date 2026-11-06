---
name: query
description: Consulta el conocimiento común (catálogo + notas) filtrando por topic y componente y responde citando id, versión y ruta de cada fuente. Oculta las notas borradas. Úsalo antes de decidir algo que pueda estar ya decidido. Solo lectura; acepta --json.
---

# arkana-knowledge:query

Responde con el conocimiento común, **citando las fuentes**. Solo lectura.

## Pasos

1. **Busca** (pesa título, etiquetas, resumen y cuerpo): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --q "<palabras clave>" [--topic <topic>] [--component <alias|arkana|all>] --limit 8 [--json]`. Salida: `puntuación|id|versión|topic|ruta|título`. `--component app` incluye las notas de ese componente y las de `all`. Sin resultados: prueba sinónimos o un término más general; si sigue vacío, dilo y sugiere `/arkana-knowledge:add`.
2. **Lee solo las candidatas** (1–4): `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/knowledge.py" query --id <id>` o `Read` sobre la ruta. Cada nota termina con su `## Changelog`: úsalo para saber qué cambió y cuándo.
3. **Responde** de forma concisa citando `id` · `vX.Y` · ruta. Si dos notas se contradicen, muéstralo y prioriza la más reciente.
4. Si la respuesta no está en el conocimiento, dilo; no inventes. Las borradas solo se ven con `--include-deleted`.

No muestres secretos aunque aparecieran en una nota: avisa de que la nota los contiene.
