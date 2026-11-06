---
name: check
description: Comprueba la salud de la orquestación de arkana-agentic - versión y flags de claude, utilidades, directorio de ejecución (700), política válida, workers huérfanos, reglas de permisos de arkana y ORQUESTADOR.md. Solo lectura y sin coste (con --deep ejecuta además la batería de contención con claude real, ~0,1 USD).
---

# arkana-agentic:check

> En los ejemplos, `agentic.sh <sub>` significa `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>`. Usa siempre este mismo comando: **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permiso solo reconocen esa forma).

Valida que el entorno puede orquestar con garantías. **No modifica nada.**

## Pasos

1. Ejecuta:

   ```bash
   bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh check
   ```

   Con `--deep` ejecuta también la batería de contención con `claude` real. **Cuesta dinero (unos 0,1 USD con haiku, con un tope de seguridad de 2 USD) y tarda unos 4 minutos**: pide confirmación al usuario antes de usarlo.

   **`red-vpn` es un `WARN`, no un `FAIL`**: agentic solo edita y hace commits locales en la rama del plan (no hace `fetch`, `pull` ni `push`), así que sin VPN el trabajo sigue; `launch` también avisa y lanza. Con `--need-network` pasa a `FAIL` (úsalo antes de algo que sí necesite los remotos).

   Formato: `ESTADO|ID|detalle` (`OK`, `WARN`, `FAIL`) y al final `RESUMEN|n FAIL|n WARN`.

2. Presenta una tabla (comprobación · estado · detalle) con los `FAIL` primero y luego los `WARN`; agrupa las `OK` en una línea.

3. Para cada problema, indica la salida:

| ID | Si no está OK |
|---|---|
| `claude-version`, `claude-flags` | Actualiza Claude Code; sin los flags `--restricted`, `--tools`, `--json-schema` y `--permission-prompts` no se puede garantizar la contención. **No se orquesta.** |
| `utilidades` | Instala lo que falte (`timeout`, `setsid`, `flock`, `python3`, `jq`, `git`, `sha256sum`). |
| `runtime-700` | `chmod 700` sobre el directorio de ejecución indicado. |
| `politica-valida` | Revisa `<arkana>/.arkana/arkana-agentic/politica.json` (`agentic.sh policy show`). |
| `layout` | Layout antiguo (planes/, run/…): `/arkana-agentic:fix` migra a `config/`, `state/` y `data/`. |
| `worker-huerfano` | Ejecuta `agentic.sh fix`. |
| `permisos-arkana` | `/arkana-workspace:fix` en `arkana` (añade las reglas del orquestador). |
| `instrucciones` | Falta o está desactualizado el bloque `arkana:agentic` del `CLAUDE.md` de ARKANA: `/arkana-agentic:install`. |
| `contencion` | Una aserción de contención ha fallado: **no orquestes** hasta resolverlo. |

## Reglas

- No ejecutes `claude` directamente ni toques los JSON de estado a mano.
- Si hay algún `FAIL`, no inicies ni reanudes ningún plan.
