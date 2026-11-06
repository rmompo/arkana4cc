---
name: export
description: Exporta la configuración del workspace (y con --include-data los datos de los plugins) a un ZIP con manifiesto y hashes sha256. Nunca incluye .credentials, identidad git personal ni rutas absolutas. Acepta --dry-run y --json.
---

# arkana-workspace:export

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/transfer.py" export --out <fichero.zip> [--include-data] [--force] [--dry-run] [--json]
```

Lo que viaja lo declara cada plugin en su `arkana-plugin.json` (clase de cada dato): `config` siempre; `data` solo con `--include-data`; `local` y `secret` nunca. `tools.json` viaja sin las rutas de esta máquina. El ZIP lleva `arkana-export.json` (versión de esquema, versiones de plugins y ruta, clase, tamaño y sha256 de cada fichero) y los ficheros bajo `files/`.

## Pasos

1. Si el usuario no da `--out`, propón un nombre (`arkana-export-<fecha>.zip`) fuera del repo de Arkana. No sobrescribe un ZIP existente salvo `--force`: pregunta antes de usarlo.
2. Haz primero `--dry-run` si hay duda sobre qué entra, y enseña la lista.
3. Ejecuta y resume: nº de ficheros, si lleva datos, y los `WARN` (enlaces omitidos, ficheros grandes).

## Reglas

- Nunca copies ni muestres el contenido de `.credentials`; las credenciales no viajan, solo su nombre de referencia dentro del manifiesto del workspace.
- El ZIP puede contener datos del proyecto (con `--include-data`): avisa de no compartirlo por canales abiertos.
