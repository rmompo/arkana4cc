---
name: import
description: Importa un ZIP creado por arkana-workspace:export. Valida todo antes de escribir (zip-slip, rutas absolutas, enlaces simbólicos, hashes, tamaños, destinos no declarados) y fusiona por fichero con --on-conflict keep|replace|ask. Acepta --dry-run y --json.
---

# arkana-workspace:import

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/transfer.py" import <fichero.zip> [--on-conflict keep|replace|ask] [--dry-run] [--json]
```

Si el ZIP tiene cualquier anomalía (ruta absoluta o con `..`, enlace simbólico, hash o tamaño alterado, fichero fuera del manifiesto, esquema desconocido, destino que ningún plugin declara, `.credentials`) **no se escribe nada** y sale con `FAIL`.

## Pasos

1. Ejecuta siempre primero con `--dry-run` y enseña qué se crearía, qué es idéntico y qué difiere.
2. Si hay ficheros que difieren, pregunta al usuario: `keep` (por defecto, conserva lo local), `replace` (usa el ZIP; deja copia en `.arkana/arkana-workspace/bak/import-<hora>/`) o `ask` (no toca lo dudoso y lo lista; tras la respuesta se vuelve a ejecutar con `keep` o `replace`).
3. Ejecuta de verdad con la decisión y resume. Si cambió `core/workspace.json`, recuerda que la identidad git y las rutas de herramientas son locales y propón `/arkana-workspace:check`.

## Reglas de fusión

- Idéntico → se salta. Ausente → se crea.
- Registros de clase `data` (p. ej. mensajes): manda la marca de borrado (`state: deleted`) y luego el `updated` más reciente.
- `tools.json`: se toman las herramientas del ZIP conservando las rutas locales.
- Nunca se importan clases `local` ni `secret`.
