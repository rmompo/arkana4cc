---
name: handover
description: Genera un informe de traspaso del workspace (plugins y versiones, componentes con su estado git, herramientas, planes de agentic, referencias de credenciales y datos por plugin) en Markdown o JSON, sin secretos ni rutas absolutas. Solo lectura, sin red.
---

# arkana-workspace:handover

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/handover.py" [--out <fichero>] [--format md|json]
```

Sin `--out` escribe en la salida estándar. Las rutas van relativas a la raíz del workspace, los remotos se reducen al host y se purga cualquier valor de `.credentials`. La sección de credenciales solo lista **nombres** de clave y cuáles no tienen valor.

## Pasos

1. Ejecútalo (con `--out` si el usuario quiere un fichero) y presenta el resumen: componentes con cambios sin subir, credenciales sin valor y planes no completados.
2. No añadas a mano información que el script no da (rutas absolutas, usuarios, URLs completas).
