# Fase 0 · Resultados de los experimentos de hooks y plugins

> Registro histórico de los experimentos de hooks y plugins que fundamentaron el diseño; sigue siendo referencia sobre el comportamiento de Claude Code.

Experimentos del refactor de Arkana (plan `refactor/arkana`, Fase 0), hechos con `claude` 2.1.317 y un plugin desechable cargado con `--plugin-dir` (ya borrado), aislado de los plugins de usuario con `--setting-sources project,local`, modelo `haiku` y `--max-budget-usd 0.05`. Cada ejecución costó entre 0,001 y 0,003 USD. Los hooks de prueba solo registraban su entrada y devolvían marcas reconocibles (`NONCE-…`).

## Resultados

| # | Pregunta | Resultado | Confirmado |
|---|---|---|---|
| E1 | Valores de `source` de `SessionStart` | `startup`; `resume` con `-c`; `clear` con `/clear`; `compact` con `/compact`. Los comandos `/clear` y `/compact` funcionan con `-p`. `/clear` dispara además `SessionEnd` con `reason: clear` | Sí |
| E1 | ¿`additionalContext` llega al modelo? | Sí, en `SessionStart` y en `UserPromptSubmit`: el modelo repitió las dos marcas | Sí |
| E2 | Campo del prompt en `UserPromptSubmit` | `prompt` (más `prompt_id`, `permission_mode`, `session_id`, `transcript_path`, `cwd`) | Sí |
| E3 | `Stop` con bloqueo | `{"decision":"block","reason":"…"}`: el motivo llega al modelo como un mensaje de usuario y este responde. El segundo `Stop` trae `stop_hook_active: true`. **Efecto secundario: el usuario ve una notificación «Stop hook error occurred»** al bloquear. La entrada de `Stop` incluye además `last_assistant_message`, `effort`, `background_tasks`, `session_crons` | Sí |
| E4 | Hooks bajo `-p` | Se ejecutan. `--settings '{"disableAllHooks":true}'` los silencia por completo (no se ejecuta ninguno). Las variables de entorno llegan a los hooks | Sí |
| E5 | `--include-hook-events` | Con `--output-format stream-json --verbose` el flujo trae `system/hook_started` y `system/hook_response` (con `hook_event`, `outcome`, `exit_code`, `stdout`) | Sí |
| E6 | Datos para tokens y coste | Los hooks **no reciben coste**. `SessionEnd` solo trae `reason` (`other`, `clear`). El transcript (`transcript_path`) tiene `message.usage` por mensaje del asistente (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`). El mensaje final de `-p` trae `total_cost_usd`. La existencia del fichero de coste de la statusline al cierre no se puede probar con `-p` (no hay statusline) | Parcial |
| E7 | `dependencies` en `plugin.json` | `claude plugin validate` lo acepta como lista de nombres y como lista de objetos `{name, version}`. **Que Claude Code lo aplique al instalar no está verificado** | Solo sintaxis |
| E8 | Variables de entorno | Los hooks ven `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_CODE_SESSION_ID` y, solo en `SessionStart`, `CLAUDE_ENV_FILE`. El Bash del modelo ve `CLAUDE_CODE_SESSION_ID` y el entorno heredado, pero **no** `CLAUDE_PROJECT_DIR`. El id de sesión del Bash del modelo **es el mismo** que el `session_id` que reciben los hooks | Sí |
| E9 | Alias `haiku` | Válido (`claude-haiku-5-5`) | Sí |
| E10 | Salida y tiempo límite de un hook | Texto plano en `UserPromptSubmit` se inyecta como contexto. Un hook que supera su `timeout` queda con `outcome: cancelled` y `exit_code: 1` y **la sesión continúa** | Sí |

## Lo que no se ha podido verificar
- Que el `systemMessage` de un hook de `SessionStart` se **vea en pantalla** en una sesión interactiva: en `-p` solo aparece dentro de la respuesta del hook en el flujo.
- Que `dependencies` instale o exija plugins.
- El coste de una sesión interactiva leído por la statusline (solo existe en la statusline interactiva).

## Qué cambia en el diseño por estos resultados
1. **El latido se liga al id de sesión, no a una ventana de tiempo.** El modelo puede leer `CLAUDE_CODE_SESSION_ID` por Bash y es igual al `session_id` del hook, así que `arkana-messaging:check` puede comprobar el latido de **su** sesión de forma exacta. La ventana de 15 minutos queda solo como respaldo.
2. **El bloqueo de `Stop` se usa con mucho cuidado:** cada bloqueo se muestra al usuario como un error. Se reserva para mensajes urgentes sin leer; lo demás espera al siguiente `UserPromptSubmit`.
3. **Aislamiento de los workers:** `launch.py` pasará `--settings '{"disableAllHooks":true}'` (E4 lo confirma) además de `ARKANA_WORKER=1`.
4. **Coste de sesión:** los hooks no lo tienen; lo escribirá la statusline y los hooks del libro de `arkana-agentic` lo leerán. Los tokens salen del transcript.
5. **Los cuatro orígenes de `SessionStart`** (`startup`, `resume`, `clear`, `compact`) existen y se pueden probar de forma no interactiva con `-p`, `-c`, `/clear` y `/compact`: el e2e de la Fase 8 puede cubrirlos.
6. **Tiempo límite de los hooks:** un hook lento se cancela sin romper la sesión, así que basta con un `timeout` corto (5 s) y con que el hook no escriba nada si no llega a tiempo.
7. **Texto plano o JSON:** ambos se inyectan en `UserPromptSubmit`; en `SessionStart` y `Stop` se usa JSON (`additionalContext`, `systemMessage`, `decision`).
