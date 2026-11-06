# Especificación e implementación: plugin `arkana-agentic` (orquestación multi-repo) y actualización de `arkana-workspace`

> **Estado: implementada en la versión 0.1.0** (fases 0 a 7 del §15). Este documento es el plan aprobado, ajustado a lo construido; las diferencias con el plan inicial están en el §22. Falta el piloto real supervisado (fase 8) para la 1.0.0. Todo vive en la carpeta `plugins/` del repo de Arkana (marketplace local `arkana`).

> **Cambios posteriores a este documento** (vigentes; ver [`../README.md`](../README.md) y [`GUIA.md`](GUIA.md)). Donde el texto de abajo los contradiga, mandan estos:
>
> - **Terminología.** El workspace es ARKANA (con su propio repositorio, la carpeta `arkana`) más el proyecto; el proyecto se compone de uno o más componentes, cada uno un repositorio.
> - **Rama de plan:** `arkana-worker/<plan>` (antes `m3a/<plan>`; las ramas y planes antiguos se reconocen).
> - **Repos y rutas** salen del manifiesto del workspace (`.arkana/core/workspace.json`); no hay listas de repos en el código ni modo sin manifiesto.
> - **Formato de commit** por componente (`commit_format`, `git.email_domains`); nunca coautor.
> - **Herramientas** (`PATH`, `JAVA_HOME`, `.npmrc` de las verificaciones) desde `arkana-workspace/tools.json` (`config tools`).
> - **`check`:** `red-vpn` es `WARN` (el trabajo y el commit son locales); `--need-network` lo convierte en `FAIL`.
> - **`recover` ya no existe:** lo cubre `fix` (layout antiguo y recuperación de tareas interrumpidas).
> - **Reglas del orquestador** en el bloque `arkana:agentic` del `CLAUDE.md` de ARKANA (plantilla `templates/orquestador.md`), no en `orquestacion/`; la guía para personas es `docs/GUIA.md`.
> - **`--from-message <id>`** en `plan new`, `launch`, `act retry` y `act investigate` entrega a un worker el mensaje indicado; `--message` sigue siendo el texto del commit.

## 1. Contexto y objetivos

**Problema.** El proyecto tiene varios repos (`arkana`, `app`, `api`, `app-web`, `app-ui`) con sesiones de Claude independientes. Sin coordinación es un caos: cada repo avanza por su lado y no hay forma de repartir trabajo, verificarlo ni pararlo.

**Objetivo.** Que `arkana` **gobierne** a los demás: tú pides algo en `arkana`, el orquestador (la sesión de Claude de `arkana`) redacta un plan, tú lo apruebas, y va lanzando **un worker cada vez** en el repo que toque, recoge su informe, lo verifica por su cuenta y decide el siguiente paso, con límites, controles de parada y paradas obligatorias para ti.

**Entregables.**
1. Plugin nuevo **`arkana-agentic`**: cola **orquestada** (la gestiona `arkana`).
2. Actualización de **`arkana-workspace`**: la cola **manual** (`put`/`get`) pasa a JSON con `id` y `asunto`, tipos y estados.
3. Cambios mínimos en `arkana-module` (modelo de permisos), `arkana` (docs, `CLAUDE.md`, catálogo) y el marketplace.

**Requisitos (los de la conversación).**
- R1. Dos colas distintas: manual (`put`/`get`) y orquestada. Ambas con `id` y `asunto` para referirse a un mensaje.
- R2. En la orquestada, **un solo worker a la vez**; decide `arkana`.
- R3. El usuario puede pedir **estado**, **parada** (suave y forzosa), pausa, reintento, etc.
- R4. **Contenciones mínimas de permisos**, aun sabiendo que no se controlan todos.
- R5. Los workers **no hacen commit, push ni pull**: es competencia exclusiva del orquestador, con autorización.
- R6. Los workers **informan estado y resultado**; el orquestador decide: reintentar, reconducir, detener, o pasarte la petición de un permiso o herramienta (el pipeline se detiene y espera).
- R7. **Sin candado de exclusión de orquestadores** (descartado por ti). Sí se comprueba que no haya un worker vivo.
- R8. La **statusline de `arkana-workspace`** muestra una **tercera línea** cuando `arkana-agentic` está en uso: qué worker trabaja y sobre qué tarea, con una descripción muy breve (§13.4).
- R9. Una skill **`/arkana-workspace:agentic`** permite **activar o desactivar** esa tercera línea, y **solo funciona si `arkana-agentic` está instalado** (§13.5).

## 2. Evidencia que fundamenta el diseño (pruebas hechas, `claude` 2.1.314)

Laboratorio en `…/scratchpad/lab` (repos de mentira; coste total ≈ 0,64 $).

| # | Hecho comprobado | Consecuencia de diseño |
|---|---|---|
| E1 | `claude -p` en la carpeta de un repo carga **su** `CLAUDE.md` y **sus** reglas (`--setting-sources project,local`) | Un worker = un proceso lanzado desde su repo |
| E2 | Una denegación deja **código de salida 0**; consta en `permission_denials` del JSON | El lanzador lee `permission_denials` y lo trata como `bloqueada` |
| E3 | `--json-schema` devuelve `structured_output` conforme al esquema; el JSON trae `total_cost_usd`, `num_turns`, `is_error`, `subtype`, `terminal_reason`, `session_id` | Informe del worker estructurado y validable |
| E4 | `--max-budget-usd 0.002` cortó con código 1 y `subtype=error_max_budget_usd`, pero ya había gastado 0,117 $ | El tope de coste **no es duro**; se usa con margen y junto a `timeout` y turnos |
| E5 | `--bare` falla con "Not logged in" (no usa el login por navegador) | No se puede usar aquí |
| E6 | `--permission-mode auto` funciona en `-p` (ejecutó un `ls`) | No se usa en workers (ver §12) |
| E7 | Con `Bash(python3 *)` permitido, un script **escribió** en un repo con `Edit` denegado y **leyó** un secreto con `Read` denegado. `echo >` y `cat` sí se bloquearon | Las reglas `Read`/`Edit` **no son frontera** para Bash: los workers **no llevan Bash** |
| E8 | `--restricted`: sin Bash/PowerShell/Monitor/WebFetch; **confina** `Read`/`Edit`/`Write` a la carpeta de trabajo (leer `/etc/hostname`, un secreto fuera y otro repo: denegados; editar y crear en su repo: OK); **no carga el `CLAUDE.md`** del repo | Perfil de worker; las normas del repo viajan **en el prompt** |
| E9 | `--disallowedTools Agent WebSearch Skill` quita esas herramientas | Se cierran las herramientas con efectos laterales |
| E10 | El sandbox de Bash **falla cerrado** con `sandbox.failIfUnavailable`, pero `bwrap` no crea namespaces en este contenedor (Docker bloquea `unshare` por seccomp); falta además `socat` | No hay sandbox de SO; no se instala nada |
| E11 | `~/.git-credentials` (600) y `~/.ia4d` (700) no los leería otro usuario; `~/devbox/tools` es 777 | Un usuario aparte se descarta por ahora (coste y roturas), se deja como mejora futura |
| E12 | Disponibles: `timeout`, `setsid`, `flock`, `jq`, `python3`, `git`, `sha256sum`. **No** hay `python3 -m jsonschema` | Validación de esquemas con un validador mínimo propio (stdlib) |

## 3. Decisiones de diseño

| # | Decisión | Motivo |
|---|---|---|
| D1 | **El motor son scripts deterministas; el modelo solo propone.** Todo cambio de estado pasa por `agentic.sh act …`, que valida contra la máquina de estados y los límites | Los guardrails están en código, no en un prompt que se pueda ignorar |
| D2 | Workers = procesos `claude -p` lanzados desde la carpeta del repo, **sin shell** (`--restricted --tools Read,Edit,Write,Glob,Grep`) | E7, E8 |
| D3 | **Todo comando lo ejecuta el lanzador de confianza** (instalar, compilar, probar, `git`), con lista cerrada | El worker no necesita shell |
| D4 | Instrucciones por **push**: el orquestador pasa la tarea en el prompt desde su copia verificada; el worker **no descubre** tareas | Evita que cualquiera escriba "tareas" en `arkana` |
| D5 | Estado de ejecución en `<arkana>/.arkana/arkana-agentic/` (ignorado por git, modo 700); contratos, políticas, docs y planes **archivados** en ARKANA | Decisión del usuario (2026-11-03): los metadatos de los plugins van en una carpeta propia (`.arkana/`), no en los repos ni en `~/.claude/`. Riesgo asumido: una herramienta de sincronización podría replicar la carpeta de ARKANA sin ignores, también el estado, que se reescribe a menudo (`run/linea.json`, `planes/`) y puede dar conflictos entre los dos lados. |
| D6 | **Sin candado de orquestador.** Un worker vivo (PID) bloquea el lanzamiento de otro | R7 |
| D7 | Aislamiento por tarea: **una rama por tarea, `arkana-worker/<plan-id>/<tarea>`,** en el propio repo (los repos Angular tienen `node_modules`); `worktree` opcional para repos ligeros | Un `worktree` no trae `node_modules` |
| D8 | Commits **locales** en esa rama solo si el plan los autoriza; **push, pull y merge siempre piden confirmación aparte** | R5 |
| D9 | JSON en ambas colas; `id` con prefijo por tipo: `N…` novedad manual, `P…` plan, `T…` tarea | "subject|identificador" |
| D10 | Inyección de `claude` sustituible (`ARKANA_AGENTIC_CLAUDE_BIN`) para probar el motor con un `claude` falso, sin coste | Testabilidad |
| D11 | **La statusline no calcula nada**: lee un fichero pequeño y ya preparado (`run/linea.json`) que `state.py` reescribe en cada transición | La statusline se refresca muy a menudo; debe ser barata y no depender del motor |

## 4. Arquitectura

```
 TÚ ──pides──▶ SESIÓN DE arkana (orquestador = Claude + ORQUESTADOR.md)
                 │  skills: plan · run · status · stop · control · recover · archive · check
                 │  (solo puede ejecutar:  bash …/agentic.sh <subcomando>)
                 ▼
          agentic.sh  (plano de control, scripts deterministas)
           ├─ state (python3, JSON atómico)  ──▶ <arkana>/.arkana/arkana-agentic/planes/<plan>/…
           ├─ launch-worker.sh ──▶ snapshot ─▶ [claude -p, perfil sin shell, en el repo] ─▶ informe JSON
           │        └─ watchdog.sh  (timeout, STOP, dead-man switch)
           └─ verify-task.sh  (esquema · denegaciones · snapshot · rutas protegidas · verificaciones fijas)
                 ▲                                         │
                 └──────── decisión propuesta (act) ◀──────┘   límites y gates aplicados por el script
```

**Flujo de una petición.** (1) pides algo → (2) `/arkana-agentic:plan` redacta `plan.json` y te lo muestra → (3) lo apruebas (se guarda su hash) → (4) `/arkana-agentic:run`: `next` → `launch` (segundo plano) → aviso al terminar → `finish` (verifica) → `act` (decide) → repetir → (5) resumen final, `archive` y peticiones de commit/push.

**Reparto de funciones.**
- *Modelo (orquestador):* redactar el plan, elegir la acción tras cada informe, redactar el feedback de un reintento, hablar contigo.
- *Scripts:* lanzar y acotar workers, snapshots, verificación, límites, transiciones, parada, recuperación, commits (con el mensaje que valida `conventions/commits.md`).

## 5. Estructura de ficheros

### 5.1 Plugin `arkana-agentic` (nuevo)

```
plugins/arkana-agentic/
├── .claude-plugin/plugin.json                  0.1.0 → 1.0.0 tras el piloto
├── README.md
├── docs/ESPECIFICACION.md                      este documento
├── docs/VERIFICACION.md                        resultados de la fase 0
├── schemas/{plan,tarea,informe,politica}.schema.json
├── policy/{politica,comandos-permitidos,rutas-protegidas}.default.json
├── templates/{worker-rules.md,worker-prompt.md.tpl}
├── scripts/
│   ├── agentic.sh  recover.sh  doctor.sh       entradas (delegan en lib/control.py)
│   ├── launch-worker.sh  watchdog.sh  snapshot.sh  verify-task.sh
│   └── lib/{control,launch,watchdog,verify,snapshot,state,repos,matchers,commitmsg,validate,doctor}.py   (stdlib, sin dependencias)
├── skills/{plan,run,status,stop,control,recover,archive,check}/SKILL.md
└── tests/{unit,e2e}/  +  tests/fake-claude.py  +  tests/run-unit.sh  tests/run-e2e.sh
```

### 5.2 Runtime local (no versionado, fuera de las carpetas sincronizadas)

```
<arkana>/.arkana/arkana-agentic/                         permisos 700
├── politica.json                               (opcional) override local de la política
├── actual                                      id del plan en curso
├── run/  worker.json  linea.json  STOP  STOP-FORCE  PAUSE  watchdog.pid
└── planes/<plan-id>/
    ├── plan.json   plan.aprobado.sha256   registro.jsonl
    ├── tareas/<T>.json
    ├── informes/<T>.<intento>.json          informe del worker (crudo + normalizado)
    ├── verificacion/<T>.<intento>.json
    ├── snapshots/<T>.<intento>.{antes,despues}.json
    └── logs/<T>.<intento>.{salida,error}.log
```

### 5.3 En `arkana` (versionado, con tu autorización)

```
orquestacion/
├── LEEME.md                 para personas: qué es, cómo se usa
├── ORQUESTADOR.md           para Claude en arkana: reglas del orquestador (importado desde CLAUDE.md)
└── archivo/<plan-id>/       plan, tareas, informes finales y registro (se archiva al terminar)
```

`CLAUDE.md` importa `@orquestacion/ORQUESTADOR.md`: es una ruta **dentro del proyecto**, así que no dispara el diálogo de imports externos.

## 6. Modelo de datos

### 6.1 Identificadores

| Prefijo | Qué | Formato | Ejemplo |
|---|---|---|---|
| `N` | Novedad manual | `N<AAMMDD>-<HHMM>-<xxxx>` | `N261030-1829-k3x9` |
| `P` | Plan | `P<AAMMDDHHMI>-<xxxx>` (hora local en 24 h; `xxxx` = 4 letras minúsculas al azar) | `P2610301830-abcd` |
| `T` | Tarea de un plan | `T<nnn>` (`T001`…`T999`; se cita `P…:T002`, y `T002` basta con un plan activo) | `P2610301830-abcd:T002` |

Todo mensaje lleva además `asunto` (≤80 caracteres).

### 6.2 Plan (`plan.json`)

```json
{
  "id": "P2610301830-abcd", "version": 1,
  "asunto": "Validación de NIF en el alta de usuario",
  "peticion": "texto original del usuario",
  "estado": "borrador",
  "autoriza": {"commits_locales": true, "rama": "arkana-worker/P2610301830-abcd"},
  "politica": {"max_tasks": 12, "max_attempts_per_task": 2, "max_plan_changes": 3,
               "total_budget_usd": 5.0, "max_duration_min": 180, "checkpoint_every": 3},
  "tareas": ["T001", "T002", "T003"],
  "creado": "2026-10-30T18:30:55Z", "aprobado": null, "historial": []
}
```

Estados del plan: `borrador → aprobado → en_ejecucion ⇄ pausado → {completado, detenido, fallido}`; estado transversal `esperando_usuario` (con `gate` abierto).

### 6.3 Tarea (`tareas/T002.json`)

```json
{
  "id": "T002", "plan": "P2610301830-abcd", "version": 1,
  "asunto": "Añadir validación de NIF en el formulario de alta",
  "repo": "app", "tipo": "tarea", "perfil": "edicion",
  "objetivo": "una frase clara",
  "instrucciones": ["1. …", "2. …"],
  "criterios_aceptacion": [{"id": "C1", "descripcion": "…", "verificacion": "test-unit"}],
  "contexto": {"ficheros": ["src/app/alta/alta.component.ts"],
               "extractos": [{"origen": "api:docs/api.md", "lineas": "10-40", "texto": "copia verificada por el orquestador"}]},
  "rutas_permitidas": ["src/**"],
  "verificaciones": [{"id": "test-unit", "comando": ["npm", "test"], "timeout_s": 600}],
  "depende_de": ["T001"],
  "limites": {"max_turns": 40, "timeout_s": 1200, "budget_usd": 0.75, "max_attempts": 2},
  "estado": "pendiente", "intentos": 0, "feedback": [], "historial": []
}
```

- `tipo`: `tarea` · `revision` · `investigacion` (los dos últimos usan perfil `lectura`).
- `perfil`: `lectura` (Read, Glob, Grep) · `edicion` (+ Edit, Write). El perfil `ejecucion` **queda fuera de v1**.
- `contexto.extractos`: cómo un worker confinado a su repo "ve" otro repo: el orquestador copia el fragmento verificado en el prompt.
- `feedback[]`: texto que añade el orquestador en un reintento (no altera las instrucciones aprobadas).

Estados de la tarea:

```
pendiente ─▶ lista ─▶ en_curso ─▶ verificando ─▶ completada
                         │            └▶ rechazada ─▶ (reintento ▶ lista) | fallida_definitiva
                         ├▶ bloqueada ─▶ esperando_usuario ─▶ (lista | omitida | cancelada)
                         ├▶ parcial ─▶ (reintento ▶ lista) | (dividir)
                         ├▶ interrumpida ─▶ (recover) ─▶ lista | cancelada
                         └▶ cancelada (stop --force)
```

Una transición no listada la **rechaza** `state.py`.

### 6.4 Informe del worker (`--json-schema`)

```json
{
  "estado": "hecha | parcial | fallida | bloqueada",
  "resumen": "≤600 caracteres",
  "criterios": [{"id": "C1", "cumplido": true, "evidencia": "dónde se ve"}],
  "cambios": [{"ruta": "src/…", "tipo": "creado|modificado|borrado", "nota": "…"}],
  "hallazgos": ["…"],
  "necesita": [{"tipo": "permiso|herramienta|dato|decision|otro", "detalle": "…", "comando_sugerido": "…"}],
  "siguiente_sugerido": "…"
}
```

`additionalProperties: false`. Se valida con `lib/validate.py` (stdlib) además de lo que haga el flag.

### 6.5 Otros ficheros

- `registro.jsonl`: una línea por decisión `{ts, quien: orchestrator|script|user, accion, tarea, motivo, contadores}`.
- `run/worker.json`: `{pid, pgid, plan, tarea, intento, inicio, owner_pid|null}`.
- Gates (en `plan.json`): `{"gate": "G07", "motivo": "permiso|herramienta|dato|decision|ruta_protegida|violacion|limite|checkpoint|plan_modificado|push|error", "detalle": "…", "opciones": ["…"], "desde": "…", "tarea": "T002|null", "reanuda": "reverify|retry|continue|none"}`. `reanuda` dice qué hace `approve`: `reverify` (autoriza lo que bloqueó y vuelve a verificar), `retry` (descarta los cambios y reintenta con la nota del usuario como feedback), `continue` (solo cierra el gate) o `none` (una violación solo admite detener).

## 7. Perfiles de worker y lanzamiento

### 7.1 Ensamblaje (lo hace `launch-worker.sh`; el worker no elige nada)

```
cd <repo>                                   # rama pipeline/<plan>; repo limpio
timeout --kill-after=10 <timeout_s> setsid  "$CLAUDE_BIN" -p "<prompt de la tarea>" \
   --output-format json  --json-schema "$(cat schemas/informe.schema.json)" \
   --restricted  --permission-mode dontAsk  --permission-prompts none \
   --tools "Read,Edit,Write,Glob,Grep"          # lectura: "Read,Glob,Grep"
   --disallowedTools Agent WebSearch Skill \
   --settings '<JSON de reglas>'  \
   --append-system-prompt-file templates/worker-rules.md \
   --max-turns <n>  --max-budget-usd <usd>  --no-session-persistence \
   [--model <m>] [--effort <e>]   < /dev/null
```

`--settings` (lo genera el lanzador con la ruta absoluta del repo, formato `//ruta`):

```json
{"permissions": {
  "allow": ["Read(//<repo>/**)", "Edit(//<repo>/**)"],
  "deny":  ["Edit(//<repo>/.git/**)", "Edit(//<repo>/.husky/**)", "Edit(//<repo>/.claude/**)",
            "Edit(//<repo>/CLAUDE.md)", "Edit(//<repo>/CLAUDE.local.md)", "Edit(//<repo>/.env*)",
            "Read(//<repo>/.env*)", "Read(//<HOME>/.git-credentials)", "Read(//<HOME>/.ia4d/**)",
            "Read(//<HOME>/.claude/**)", "Read(//<HOME>/.npmrc)"]}}
```

`Edit(...)` cubre también `Write`. `--restricted` ya confina las herramientas de fichero (E8); la lista `deny` es defensa en profundidad.

### 7.2 Prompt

`templates/worker-prompt.md.tpl` se rellena con: asunto y objetivo, instrucciones numeradas, criterios de aceptación, contexto (ficheros y extractos), `rutas_permitidas`, **normas del repo** (contenido de su `CLAUDE.md` sin la semilla, copiado por el lanzador), feedback de intentos anteriores y el esquema del informe.

`templates/worker-rules.md` (system prompt, reglas duras): no tienes shell ni `git`; no salgas de tu repo; no leas ni escribas credenciales ni ajustes; si te falta un permiso, herramienta, dato o decisión, **no lo rodees**: devuelve `bloqueada` con `necesita`; contesta solo con el informe JSON.

### 7.3 Cómo se interpreta el resultado

| Observado | Se trata como |
|---|---|
| `permission_denials` no vacío | `bloqueada` (motivo = permiso), aunque el worker diga `hecha` |
| `subtype = error_max_budget_usd` | `fallida` (límite de coste) |
| salida de `timeout` (124/137) | `fallida` (tiempo), `interrumpida` si lo mató el watchdog |
| fin por turnos agotados | `parcial` (tras verificar con P0-2) |
| JSON ausente o sin `structured_output` válido | `fallida` (informe inválido) |
| `estado = hecha` | pasa a verificación; **no se da por buena** |

## 8. Verificadores (los ejecuta el script, no el worker)

### 8.1 Snapshot antes y después
Para los siete repos (`arkana`, `app`, `api`, `app-web`, `app-ui`, `docs`, `dsa`): `git status --porcelain=v1 -z`, rama y SHA de `HEAD`, remotos (sin credenciales), nº de stashes y commits sin subir. Además, para ficheros vigilados (`~/.claude/settings.json`, `~/.git-credentials`, `~/.ia4d/.env`, `~/.npmrc`, `~/.gitconfig`, `.claude/settings.local.json`): **tamaño, mtime e inodo** (no se lee su contenido). Cualquier diferencia **fuera del repo de la tarea** = `violacion` (§9.5).

### 8.2 Alcance de los cambios
`git diff --name-status` dentro del repo, contra `rutas_permitidas`. Un cambio fuera de ellas = `rechazada`.

### 8.3 Rutas protegidas (`rutas-protegidas.default.json`)
`.git/**`, `.husky/**`, `.claude/**`, `CLAUDE.md`, `CLAUDE.local.md`, `.gitignore`, `.gitattributes`, `.env*`, `package.json` (cualquier cambio en `scripts`, `dependencies`, `devDependencies`, `overrides`), `package-lock.json`, `angular.json`, `tsconfig*.json`, `webpack*.js`, `*.config.{js,cjs,mjs,ts}`, `.github/**`, `.gitlab-ci.yml`. Si el worker las toca: **no se ejecuta ninguna verificación** y se abre el gate `ruta_protegida` (ves el diff y decides). Motivo: lo que el verificador ejecuta (`npm test`, `husky`) corre con tu identidad.

**Dos vías al gate `ruta_protegida`.** (1) *Escritura detectada* tras la tarea (inventario de ficheros): rutas protegidas que los ajustes del worker no deniegan; `approve` autoriza y se re-verifica. (2) *Escritura impedida*: los ajustes del worker deniegan `.git/**`, `.husky/**`, `.claude/**`, `CLAUDE.md`, `CLAUDE.local.md` y `.env*`; la denegación aparece en `permission_denials` y `finish` la convierte en un gate `ruta_protegida` (no en un `permiso` genérico) que dice qué ruta y qué quería escribir. Solo `CLAUDE.md` y `CLAUDE.local.md` son **autorizables**: `approve` los guarda en `tarea.autorizado.rutas_protegidas` y `launch` levanta esa denegación (solo esa) en los ajustes del siguiente intento. `.git`, `.husky`, `.claude` y `.env*` no se levantan nunca: su gate solo admite omitir o detener. Un gate `permiso` genérico no cambia los permisos del worker; su opción es «reintentar» con la nota del usuario como feedback.

### 8.4 Verificaciones por comandos (lista cerrada)
`comandos-permitidos.default.json` lista argv exactos o patrones anclados, sin metacaracteres de shell: `["npm","test"]`, `["npm","run","lint"]`, `["npm","run","build"]`, `["ng","build"]`, `["ng","test","--watch=false"]`, `["git","diff","--stat"]`. Un comando fuera de la lista **no se ejecuta** (se abre gate `herramienta`).

Ejecución: argv directo (sin `bash -c`), `timeout`, `cwd` = repo, `PATH` = las carpetas `bin` de las herramientas declaradas en `tools.json` (`/arkana-workspace:config tools`) más `/usr/local/bin:/usr/bin:/bin` (y `JAVA_HOME` si hay `jdk`), `HOME` = carpeta temporal con un `.npmrc` solo con los registros por ámbito declarados allí (`npm_config_userconfig`), de modo que el código del repo no encuentra `~/.git-credentials` por la vía habitual. **Es un obstáculo, no una frontera** (§12).

### 8.5 Criterios de aceptación
Cada criterio apunta a una verificación; el resultado es `{criterio, cumplido, salida_resumida}`. Se guarda en `verificacion/`. `completada` exige: esquema válido + sin denegaciones + snapshot limpio + alcance correcto + rutas protegidas sin tocar (o aprobadas) + todos los criterios cumplidos.

## 9. Orquestador

### 9.1 Bucle de `/arkana-agentic:run`
1. `agentic.sh doctor --quick`.
2. `agentic.sh next --json` → próxima tarea ejecutable, o la razón (`gate`, `limite`, `terminado`, `pausado`).
3. `agentic.sh launch <tarea>` **en segundo plano** (el límite de ~10 min del primer plano no aplica). Aviso al terminar.
4. `agentic.sh finish <tarea>`: interpreta, verifica y devuelve JSON con el resultado y las acciones permitidas.
5. Elijo una acción y la registro con `agentic.sh act <acción> …` (el script la valida).
6. Vuelta al paso 2 hasta `terminado`, `esperando_usuario`, `detenido` o `limite`. Cada `checkpoint_every` tareas, gate `checkpoint`.
7. Al terminar: resumen, `archive` (con tu autorización) y gates de commit y push.

### 9.2 Tabla de decisión (lo que el orquestador puede proponer)

| Situación | Acción por defecto |
|---|---|
| `hecha` + verificada | `act continue` |
| `hecha` + `rechazada` (criterio falla), causa nueva y quedan intentos | `act retry` con feedback (salida de la verificación truncada) |
| Misma causa que el intento anterior | `act escalate` (no se repite) |
| `parcial` | `act retry` con instrucciones de continuación, o `act split` |
| `fallida` por tiempo, turnos o coste | `act split` en tareas menores, o `act escalate` |
| `bloqueada` (permiso, herramienta) | gate `permiso`/`herramienta`: ejecuto yo un comando de la lista, amplío `rutas_permitidas`, omito o detengo; tú decides |
| `bloqueada` (dato, decisión) | gate: te lo pregunto |
| Worker pide información de otro repo | `act investigate`: añade una tarea `lectura` (cuenta como cambio de plan) |
| Violación de snapshot | `act stop`; sin reintento |
| Ruta protegida tocada | gate `ruta_protegida` |

Acciones de `act`: `continue`, `retry [--feedback-file]`, `split --tasks-file <fichero>`, `investigate --repo --subject --instructions-file`, `escalate --reason`, `skip`, `stop`.

### 9.3 Límites (`politica.default.json`; el script los impone)

| Límite | Valor por defecto |
|---|---|
| Intentos por tarea | 2 |
| Tareas por plan | 12 |
| Cambios de plan | 3 (estructurales: **exigen reaprobación** salvo `investigate`, que se puede preautorizar (`autoriza.investigate_without_gate`)) |
| Misma causa dos veces | no se reintenta |
| Presupuesto total | 5 USD (con margen: tope por tarea = mínimo entre lo declarado y lo que queda; E4) |
| Duración del plan | 180 min |
| Turnos / tiempo / coste por tarea | 40 · 20 min · 0,75 USD |
| Checkpoint | cada 3 tareas |

### 9.4 Aprobación del plan
`plan approve` guarda el hash de `plan.json` y de sus tareas. El lanzador **se niega** a ejecutar si el hash difiere, de modo que un plan alterado a mano o por el orquestador sin reaprobación no corre.

### 9.5 Gates (paradas obligatorias)
El pipeline queda en `esperando_usuario` y el orquestador te pregunta (`AskUserQuestion`) en: permiso o herramienta, dato o decisión, ruta protegida, violación, límite alcanzado, checkpoint, plan modificado, **cualquier push, pull o merge**, y error inesperado. Tu respuesta se registra y se reanuda con `approve`/`reject`.

### 9.6 Commits (solo el orquestador, solo si el plan lo autoriza)
Todo el trabajo de un plan en cada repo va en **una sola rama `arkana-worker/<plan-id>`**, que crea el script `launch` (el worker no tiene `git`) antes de lanzar la primera tarea de ese repo, y que activa antes de cada lanzamiento posterior; repo limpio como precondición (si no, gate). El nombre de la rama se pasa al worker en el prompt solo como información. Tras `completada`: `git add` de las rutas permitidas y `git commit` local con mensaje validado por `lib/commitmsg.py` según `conventions/commits.md` (IA4D; `app-ui` con dos puntos; ≤72; sin `Co-Authored-By`; y el autor con el dominio de correo que el componente declare en `git.email_domains`). Los hooks del repo **se respetan** (nunca `--no-verify`); por eso §8.3 va antes. Al terminar, el orquestador **evalúa** (`integrate review`: commits por tarea, `git diff --stat` contra la rama original y avisos entre repos) y el **usuario decide por repo**: **integrar en la rama original** (`integrate merge --repo <r>`, merge local `--no-ff`, que conserva los commits del plan como un grupo fácil de revertir con `git revert -m 1`; con `--up-to <Tnnn>` solo hasta esa tarea, conservando la rama con el resto), **dejar la rama** para revisión (`keep`) o **descartarla** (`discard`). El **push** sigue siendo un gate aparte.

**Reglas de la rama (salvaguarda de git):**
- **La crea el script, no el worker ni el modelo**, con el repo **limpio** (si no, gate), desde el `develop` local, con la primera tarea del plan en ese repo. Las tareas siguientes de ese repo, y los reintentos, solo la activan. El worker no usa `git`: trabaja en el árbol de ficheros de esa rama.
- **Una rama por plan y repo, un commit por tarea aceptada.** Un plan tiene muchas tareas y muchos workers (un worker = un repo): el orquestador elige el orden (siempre una tarea del plan con sus dependencias cumplidas), puede reinvocar al mismo worker y solo tras aceptar una tarea pasa a la siguiente. Un reintento vuelve al último commit aceptado (lo no aceptado se descarta; lo aceptado, nunca). Una tarea aceptada no se reabre: se corrige con una tarea nueva.
- **La decisión final es por repo**: `integrate review|merge|keep|discard [--repo R] [--up-to Tnnn]`. Sin `--repo` se aplica a los repos que aún no tienen decisión (`plan.ramas[repo].decision`).
- Si durante una tarea `HEAD` cambia de rama, es una **violación** (el snapshot lo detecta).
- Mientras corre el pipeline no se debe trabajar en ese repo (el árbol de ficheros está en la rama del plan, y una herramienta de sincronización podría replicarlo).

## 10. Plano de control (`agentic.sh`)

| Subcomando | Qué hace |
|---|---|
| `plan new <fichero>` · `plan show` · `plan validate` · `plan approve` | Crea, muestra, valida contra esquemas y aprueba (hash) |
| `next [--json]` | Próxima tarea ejecutable y por qué |
| `launch <tarea>` | Lanza el worker (comprueba que no hay otro vivo, límites, hash y snapshot) |
| `finish <tarea>` | Interpreta el resultado, verifica y propone acciones |
| `act <acción> …` | Registra la decisión; valida transición y contadores |
| `status [--json] [--plan id]` | Estado legible (ejemplo abajo) |
| `stop` | **Suave**: no empieza más tareas; la actual termina; plan `pausado` |
| `stop --force` | **Forzosa**: `SIGTERM` al grupo del worker, `SIGKILL` a los 10 s; tarea `cancelada`; plan `detenido` |
| `pause` · `resume` | Pausa tras la tarea actual · reanuda |
| `retry <tarea>` · `skip <tarea>` | Reintento manual · omitir |
| `approve <gate>` · `reject <gate>` | Resuelve un gate |
| `log <tarea> [--tail N]` | Salida del worker |
| `recover` | Tras una caída (§11) |
| `archive` | Copia el plan cerrado a `orquestacion/archivo/<plan>/` |
| `retry <tarea>` · `skip <tarea>` | Versiones del usuario de `reintentar` y `omitir` |
| `integrate merge|keep|discard` | Con `merge`, un merge local `--no-ff` de la última rama de cada repo (que contiene las de todas las tareas; mensaje validado, sin push) y borra las ramas de las tareas; con `keep`, las deja para revisarlas; con `discard`, las borra; restaura la rama original |
| `policy show` · `policy set <clave> <valor> [--ceiling]` | Muestra y cambia los límites de la política local (nunca por encima del techo) |
| `doctor [--quick|--deep]` | Salud del entorno (§16.3) |

**Códigos de salida:** 0 ok · 1 error · 2 uso · 3 precondición (worker vivo, plan sin aprobar, hash distinto) · 4 violación · 5 esperando usuario · 6 límite · 7 detenido.

**Salida de `status` (ejemplo):**

```
Plan P2610301830-abcd · «Validación de NIF en el alta»       estado: en_ejecucion
Gasto 1,42 / 5,00 USD · 38 / 180 min · cambios de plan 0/3 · checkpoint en 1 tarea

 Tarea  Repo     Asunto                              Estado        Intentos
 T001    api  Endpoint de validación               completada    1/2
 T002    app     Validación de NIF en el formulario   en_curso      1/2    worker 48211 · 6 min
 T003    app     Mensajes de error                    pendiente     0/2

Gate abierto: ninguno
```

## 11. Recuperación y *dead-man switch*

- **`watchdog.sh`** (lo arranca el lanzador): cada 5 s comprueba el tiempo máximo, `STOP-FORCE` y si el proceso dueño (`owner_pid`, el `claude` ancestro de la sesión, si se logra determinar) sigue vivo; si no, mata el grupo del worker y marca `interrumpida`. El `timeout` del sistema es el tope final.
- **Un solo worker:** `launch` se niega si `run/worker.json` apunta a un PID vivo cuyo `cmdline` contiene `claude`.
- **`recover`**: detecta tareas `en_curso` sin worker vivo → `interrumpida`; compara el repo con el snapshot previo; te propone `--action discard` (cancela la tarea y deja el árbol en el último commit de la rama de la tarea) o `--action retry` (descarta lo hecho a medias y deja la tarea lista). `verificar lo hecho` queda fuera de la v1. Nunca reintenta solo.
- Caídas del contenedor: el estado local sobrevive a un reinicio; se pierde al recrear el contenedor (los planes archivados en `arkana` no).

## 12. Seguridad: lo que se garantiza y lo que no

| Nivel | Salvaguarda | Base |
|---|---|---|
| **Garantizado y probado** | El worker no tiene herramientas de comandos; no puede salir de su carpeta con las herramientas de fichero; las denegaciones se detectan; el informe se valida | E1–E3, E8, E9 |
| **Garantizado por construcción** (se prueba en fase 7) | Los workers no ejecutan `git`; un solo worker vivo; límites, hash del plan y transiciones | Código + tests |
| **Detectado, no impedido** | Cambios en ficheros no vigilados; exfiltración por red; trabajo incorrecto | Snapshot y revisión |
| **No garantizable** | Inyección de prompts; exactitud del tope de coste (E4); código que el worker escribe y que el verificador ejecuta | Naturaleza del modelo y de los comandos |

**Contenciones sobre la sesión de `arkana` (orquestador)** — las genera `arkana/scripts/setup-permissions.sh` (modelo de `arkana-module`, §14), solo para `arkana`, y `arkana-workspace/scripts/repos-config.sh` las replica (un test comprueba que no divergen):
- `allow`: `Read(//<base>/.arkana/arkana-agentic/**)` (**solo lectura**: el estado no se escribe a mano) y `Bash(bash <base>/plugins/arkana-agentic/scripts/agentic.sh *)` más `Bash(bash <HOME>/.claude/plugins/cache/arkana/arkana-agentic/*/scripts/agentic.sh *)`: **dos raíces explícitas**, porque con un marketplace de tipo `directory` los skills expanden `${CLAUDE_PLUGIN_ROOT}` a la copia de trabajo y no a la caché (descubierto al arrancar el piloto; la primera versión solo cubría la caché).
- `ask` (pesa más que `allow`; confirmación del usuario aunque el modelo se salte la pregunta): `agentic.sh plan approve*`, `approve*`, `reject*`, `policy set*`, `integrate merge*`, `integrate discard*`.
- `deny`: `Bash(claude -p *)`, `Bash(claude --print *)`, `Bash(claude --bg *)`.
- **Comprobado con `claude` real** (haiku, ~0,02 USD): la regla `Bash` **solo casa si la ruta va sin comillas**; una orden compuesta (`&&`, `cd … &&`) o con la ruta entre comillas no casa. Por eso los skills y `ORQUESTADOR.md` imponen **una sola orden por llamada, sin comillas ni encadenados**. `ask` gana a `allow`; una ruta de otro sitio no casa con el comodín de versión.
- **Claude Code protege las escrituras bajo `.claude/` con independencia de las reglas `allow`** (comprobado). Con el estado fuera de `.claude/` esa protección ya no existe: la sustituye una regla `deny Edit(//<base>/.arkana/arkana-agentic/**)` que generan `setup-permissions.sh` y `repos-config.sh` para todos los módulos (y `launch.py` deniega lectura y edición de `.arkana/` a los workers). Los borradores de plan siguen yendo al directorio *scratchpad* de la sesión.
- `ORQUESTADOR.md` prohíbe además: ejecutar `claude` directamente, editar los JSON de estado a mano, aprobar por el usuario y hacer commit o push sin gate.

**Riesgos residuales aceptados en v1:** exfiltración por red y código plantado que ejecuta el verificador. **Mejoras futuras** si hicieran falta: usuario Linux aparte para los workers o contenedor aparte, y sandbox (exige recrear el contenedor con otro seccomp).

## 13. Actualización de `arkana-workspace` (cola manual v2)

Versión **3.0.0** (rompe el formato). Ficheros: `scripts/messages.sh`, `skills/{put,get}/SKILL.md`, `README.md`, `scripts/check-statusline.sh`, `scripts/repos-config.sh`, `scripts/messages.sh` (`local-file`), y `arkana/novedades/LEEME.md`.

### 13.1 Formato JSON (`novedades/<repo>/<id>.json`)

```json
{
  "id": "N261030-1829-k3x9", "asunto": "El endpoint X cambia de formato",
  "tipo": "notice | task | review | question",
  "de": "api", "para": "app", "autor": "usuario", "fecha": "2026-10-30T18:29:55Z",
  "rama": "develop", "prioridad": "normal | high",
  "cuerpo": "markdown", "instrucciones": ["…"], "criterios": ["…"], "refs": ["N261029-…"],
  "estado": "open | done | discarded",
  "historial": [{"fecha": "…", "autor": "…", "accion": "creada|hecha|descartada|comentario", "nota": "…"}]
}
```

- `notice` no tiene estado. `task` exige `instrucciones` claras y `criterios`; `review` exige qué revisar y qué se espera; `question` se cierra con la respuesta.
- **Tipos antiguos (`feature`, `fix`, `docs`)**: desaparecen (eran todos `notice`).

### 13.2 Comandos

- `put --repo <id> --type … --subject "…" [--to <id>] [--priority high] [--body-file f] [--instructions-file f]`.
- `put --done <id> --result "…"` · `put --discard <id> --reason "…"` · `put --comment <id> --note "…"`.
- `get [--id] [--type] [--state] [--to] [--from] [--pending] [--user] [--since] [--n] [--json] [--detail <id>]`. Por defecto, tabla legible con `id`, asunto, tipo, estado, de→para.
- **Escritura sin conflictos con varios usuarios:** `put`/`--done` trabajan en el `worktree` temporal actual; en cada reintento se hace `fetch`, se **reinicia el worktree a `origin`** y se **reaplica la mutación** (idempotente) antes de commit y push, de modo que no hay conflictos de git aunque dos personas cierren la misma novedad.
- `migrate`: convierte las **6 novedades `.md` ya publicadas** a JSON (ids derivados de su fecha), en un solo commit; v2 solo lee JSON.

### 13.3 Integración
- `novedades.md` de `.arkana/core/` (generado por `local-file`) dice a cada sesión que, al abrir un repo, consulte `get --pending --to <su id>` y **proponga** atender lo abierto y marcarlo `done` con su confirmación.
- `check-statusline.sh`: comprobación `novedades-formato` (ningún `.md` residual), `agentic-installed` (informativo) y `linea3` (render de prueba, §13.4).

### 13.4 Tercera línea de la statusline: indicador de `arkana-agentic`

**Qué muestra.** Solo cuando hay un pipeline activo; sin pipeline, la statusline sigue con sus dos líneas de siempre.

```
 ⚙ P261030-1830 · T002/3 · app · «Validación de NIF en el formulario» · 6 min · 1,42 $
 ⏸ P261030-1830 · esperando tu respuesta (permiso) · T002 · app
 ◌ P261030-1830 · pausado · 2/3 tareas
 ⚠ P261030-1830 · worker interrumpido · T002 · ejecuta /arkana-agentic:recover
```

Contenido: **repo del worker** (el id de la línea 2: `app`, `api`…), **tarea** (`T002/3`) y **descripción muy breve** (el `asunto` de la tarea recortado a ~40 caracteres con `…`), más tiempo en curso y gasto. Colores: en curso en verde, pausado y gate en amarillo, interrumpido en rojo. Mismo estilo de bloques que la línea 2 (`txt_block`, `rev_block`, `fit_path` para recortar al ancho).

**Cómo se alimenta (D11).** `lib/state.py` reescribe `<arkana>/.arkana/arkana-agentic/run/linea.json` en cada transición del plan o de la tarea, de forma atómica:

```json
{"ts": "2026-10-30T18:37:02Z", "plan": "P2610301830-abcd", "estado": "en_ejecucion",
 "tarea": "T002", "tareas": {"hechas": 1, "total": 3}, "repo": "app",
 "asunto_corto": "Validación de NIF en el formulario", "worker_pid": 48211,
 "inicio": "2026-10-30T18:31:10Z", "gasto_usd": 1.42, "gate": null}
```

**Cómo lo lee `statusline-command.sh`** (`arkana-workspace`): un único `jq` sobre ese fichero; si no existe, no pinta nada. Para no mostrar datos viejos tras una caída, comprueba con `kill -0 <worker_pid>` (función interna de bash, sin procesos nuevos) y que `ts` no sea anterior a 10 minutos: si el worker ya no existe pero el plan sigue `en_ejecucion`, muestra el estado `⚠ interrumpido`. La ruta del directorio se puede sustituir con `ARKANA_AGENTIC_DIR` (para pruebas).

**Compatibilidad.** El script instalado en `~/.claude/statusline-command.sh` se actualiza con `/arkana-workspace:install` (paso de script) y `check-statusline.sh` acepta 2 o 3 líneas. **Pendiente de comprobar (P0-13):** que Claude Code repinte bien una statusline que cambia de 2 a 3 líneas en caliente.

### 13.5 Skill `/arkana-workspace:agentic` (activar o desactivar la línea 3)

- **Uso:** `/arkana-workspace:agentic` sin argumentos muestra el estado y pregunta (`AskUserQuestion`: *Activar* / *Desactivar* / *Dejar como está*); también `on`, `off` y `status`.
- **Precondición: `arkana-agentic` instalado.** Se comprueba que `~/.claude/settings.json` tenga `enabledPlugins["arkana-agentic@arkana"] = true` y que el plugin exista en el marketplace. Si no, la skill **no cambia nada**: explica que falta y muestra `claude plugin install arkana-agentic@arkana`. `on` se rechaza; `status` informa de que no está instalado.
- **Dónde se guardaba:** una clave `linea3=on|off` en un fichero de rutas heredado que ya no existe (la statusline actual pinta el plan en su primera línea y no tiene este indicador).
- **Cómo lo respeta la statusline:** `statusline-command.sh` lee la clave en cada refresco (como ya lee las rutas) y solo pinta la línea 3 si es `on` **y** existe `run/linea.json`. No hace falta reiniciar.
- **Implementación:** subcomandos `flag get|set linea3` y `agentic-installed` en `scripts/statusline-config.sh` (reutiliza el escritor con copia `.bak`); la skill es una envoltura delgada. `check-statusline.sh` informa del estado (`linea3-flag`).
- **Versión:** entra en `arkana-workspace` 3.0.0.
- `repos-config.sh`: la regla de cobertura sigue; el modelo de permisos se actualiza en `setup-permissions.sh` y se replica aquí para que `sync` no diverja de `arkana-module:check`.

## 14. Cambios en `arkana-module`, `arkana` y documentación

| Pieza | Cambio | Versión |
|---|---|---|
| `arkana/scripts/setup-permissions.sh` | Reglas del orquestador solo para `arkana` (§12) | `arkana-module` 1.2.0 |
| `plugins/arkana-module/{README,skills/fix}` | Documentar las reglas nuevas | — |
| `plugins/.claude-plugin/marketplace.json` | Añadir `arkana-agentic` | — |
| `CLAUDE.md` | Importar `@orquestacion/ORQUESTADOR.md` | — |
| `orquestacion/{LEEME,ORQUESTADOR}.md` | Nuevos | — |
| `arkana/README.md`, `organizacion-proyecto.md` | Árbol, plugin nuevo, sección «Orquestación», modelo de permisos | catálogo |
| `shared/estado-proyecto.md`, `catalogo.json` | Vía `/arkana-shared:add` (versión nueva + archivo) | — |
| `WORKSTATION-SETUP-IA.md` | Instalación de `arkana-agentic`, primer pipeline guiado, qué hacer si se cae; marcar lo no verificado | — |
| `WORKSTATION-SETUP-DEVELOPER.md` | `agentic.sh status|stop|log` usables desde bash sin Claude | — |
| `conventions/commits.md` (workspace) | Nota: los commits de pipeline siguen la misma convención | — |

## 15. Plan de implementación por fases

Cada fase termina en **estado verificable** y un commit por repo (formato IA4D; `app-ui` no se toca).

### Fase 0 — Verificación en laboratorio (sin código del plugin; ≈ 1–2 USD)
Dudas abiertas que se cierran con pruebas, resultado en `docs/VERIFICACION.md`:

| Id | Prueba | Si falla |
|---|---|---|
| P0-1 | `--tools "Read,Edit,Write,Glob,Grep"` deja exactamente esas herramientas | Usar `--disallowedTools` explícito |
| P0-2 | `--max-turns`: código de salida y `subtype` al alcanzarse | Acotar solo con tiempo y coste |
| P0-3 | `--restricted` + `--add-dir <otro repo>` (¿lectura de otro repo?) | Extractos en el prompt (ya previsto) |
| P0-4 | Matar la sesión padre: ¿sobrevive el worker lanzado con `setsid`? | Watchdog como única defensa |
| P0-5 | `kill -TERM -<pgid>` y `-KILL`: ¿cae todo el árbol de `claude -p`? | Ajustar `stop --force` |
| P0-6 | Robustez de `--json-schema` (rechazo del modelo, enums, `additionalProperties:false`) | Reintento por informe inválido |
| P0-7 | `--settings` JSON junto con `--restricted`: ¿se aplica el `allow`/`deny`? | Pasar solo `--tools` |
| P0-8 | `--append-system-prompt-file` existe y se aplica con `--restricted` | Pasarlo con `--append-system-prompt` |
| P0-9 | Detección de `owner_pid` (ancestro `claude` desde un `Bash` de la sesión) | Solo `timeout` + STOP |
| P0-10 | Aviso al terminar una tarea en segundo plano de **>10 min** (stub de 12 min) | Sondeo con `status` |
| P0-11 | Coste y duración base de una tarea real pequeña por perfil | Ajustar límites por defecto |
| P0-12 | `--restricted` no ejecuta hooks ni plugins de usuario | Añadir `--setting-sources` |
| P0-13 | La statusline cambia de 2 a 3 líneas en caliente y vuelve a 2 sin dejar restos ni cortar texto | Mostrar el indicador al final de la línea 2 |

### Fase 1 — Contratos
F1.1 `schemas/*.json` y `lib/validate.py` (validador mínimo stdlib). F1.2 `lib/state.py`: escritura atómica (temporal + `rename`, `flock` corto), máquina de estados, contadores, generación de ids. F1.3 `policy/*.json` y `docs/ESPECIFICACION.md`. **Aceptación:** tests unitarios de transiciones ilegales, ids únicos, validación de esquemas válidos e inválidos.

### Fase 2 — Motor
F2.1 `snapshot.sh`. F2.2 `launch-worker.sh` (comprobación de worker vivo, hash, rama, snapshot, ensamblaje §7, `setsid` + `timeout`). F2.3 `watchdog.sh`. F2.4 `verify-task.sh` (§8). F2.5 `tests/fake-claude.py` (emite informes enlatados: hecha, parcial, bloqueada, fallida, denegaciones, informe inválido, tarda N s, toca otro repo). **Aceptación:** e2e **sin coste** de los 11 escenarios de §16.2.

### Fase 3 — Control
F3.1 `agentic.sh` completo con salida legible y `--json`. F3.2 `stop`/`stop --force`/`pause`/`resume`. F3.3 `recover.sh`. F3.4 `doctor.sh` + skill `check`. F3.5 `state.py` escribe `run/linea.json` en cada transición (§13.4). **Aceptación:** `status` y `stop --force` sobre el fake con worker en marcha; `recover` tras matar el lanzador.

### Fase 4 — Orquestador
F4.1 `skills/{plan,run,status,stop,control,recover,archive}`. F4.2 `orquestacion/ORQUESTADOR.md` (+ import en `CLAUDE.md`). F4.3 `act` con todas las acciones y la tabla §9.2. **Aceptación:** una sesión real de `arkana` conduce un plan de 3 tareas con el `claude` falso de principio a fin, incluidos gate y reintento.

### Fase 5 — `arkana-workspace` 3.0.0
F5.1 `messages.sh` v2 (JSON, ids, tipos, `--done`, `get` con filtros, mutación idempotente). F5.2 `migrate` y migración de las 6 novedades. F5.3 `local-file`, `LEEME.md`, skills `put`/`get`. F5.4 `check`. F5.5 **Tercera línea de la statusline** (`statusline-command.sh` lee `run/linea.json`, §13.4), actualización del script instalado y `check` de `linea3`. F5.6 **Skill `agentic`** (§13.5): interruptor `linea3`, comprobación de `arkana-agentic` instalado y pruebas con y sin el plugin. **Aceptación:** con un `linea.json` de muestra por cada estado (en curso, pausado, esperando, interrumpido, ausente) la salida tiene 3 o 2 líneas según toca y el texto se recorta al ancho; pruebas con repo remoto `bare` temporal: 4 cierres concurrentes de la misma novedad sin conflicto; `get --pending`; migración idempotente.

### Fase 6 — Integración
F6.1 `setup-permissions.sh` y `repos-config.sh` alineados; `arkana-module` 1.2.0. F6.2 marketplace, README, `organizacion-proyecto`, catálogo (`/arkana-shared:add`), guías `WORKSTATION-SETUP*`. **Aceptación:** `arkana-module:check` en los cinco módulos con 0 FAIL; comprobador de enlaces con 0 rotos.

### Fase 7 — Pruebas con `claude` real
F7.1 `tests/containment/*`: la batería t1–t15 y r1–r7 convertida en aserciones (≈ 0,6 USD), repetible con `doctor --deep`. F7.2 Escenarios con workers reales en el laboratorio: tarea de edición, de revisión, bloqueada por permiso, rechazada por criterio, intento de salir del repo. **Aceptación:** todas las aserciones de contención en verde.

### Fase 8 — Piloto y publicación
F8.1 Un pipeline real, mínimo, supervisado (en `docs` o `arkana`, repos de bajo riesgo). F8.2 Corrección de lo aprendido. F8.3 Versión **1.0.0** de `arkana-agentic`, commit y push por repo con aprobación.

## 16. Estrategia de pruebas

1. **Unitarias (sin API):** `state.py` (transiciones, contadores, concurrencia de escritura), `validate.py`, `commitmsg.py` (IA4D / dos puntos / longitud / coautor), matcher de rutas protegidas, matcher de comandos permitidos, diff de snapshots.
2. **E2E con `claude` falso (sin coste), 11 escenarios:** camino feliz de 3 tareas · tarea bloqueada → gate → reanuda · reintento y fallo definitivo · misma causa dos veces → escala · `stop` suave · `stop --force` con worker dormido · caída del lanzador + `recover` · ruta protegida modificada · worker que toca otro repo (violación) · informe inválido · dos `launch` simultáneos (el segundo se niega).
3. **`doctor`:** IDs `claude-version` (≥ 2.1.259), `claude-flags` (`--restricted`, `--tools`, `--json-schema`, `--permission-prompts`), `utilidades` (`timeout`, `setsid`, `flock`, `python3`, `jq`, `git`, `sha256sum`), `permisos-arkana`, `runtime-700`, `politica-valida`, `worker-huerfano`, `instrucciones-version`.
4. **Contención con `claude` real (≈ 0,6 USD):** lectura y escritura fuera del repo, lectura de un secreto, `Bash` ausente, `Agent`/`WebSearch` ausentes, denegaciones registradas, presupuesto bajo, esquema.
5. **Regresión de `arkana-workspace`:** el `check` completo con 0 FAIL y 0 WARN tras migrar.
6. **Statusline (línea 3):** unitaria del render con `linea.json` de muestra (sin worker, con PID muerto, `ts` viejo, descripción larga); e2e: durante un worker falso dormido, la statusline de prueba (`ARKANA_AGENTIC_DIR`) muestra el repo, la tarea y la descripción breve, y al terminar vuelve a dos líneas.

## 17. Riesgos y mitigaciones

| Riesgo | Gravedad | Mitigación |
|---|---|---|
| Código plantado que el verificador ejecuta con tu identidad | Alta | Revisión de diff y gate de rutas protegidas **antes** de ejecutar; lista cerrada de comandos; entorno reducido |
| Inyección de prompts por contenido leído | Alta | Tarea por push desde copia verificada; perfil sin shell ni web; no ver credenciales |
| Bucle infinito o coste | Media | Límites en código, repetición, presupuesto con margen (E4), checkpoint, parada |
| Autoevaluación del worker | Media | Criterios y verificación por el script |
| Caída a mitad de tarea | Media | Rama aislada, snapshot, watchdog, `recover` con tu confirmación |
| Divergencia entre `setup-permissions.sh`, `repos-config.sh` y `arkana-module:check` | Media | Cobertura de reglas y prueba de regresión en fase 6 |
| El modelo ignora `ORQUESTADOR.md` | Media | Las reglas críticas (límites, hash, transiciones, un worker) están **en código** |
| Dependencia de flags de una CLI en "research preview" | Media | `doctor` comprueba versión y flags; `claude` inyectable |
| Los hooks de IA4D (commit) interfieren | Baja | Los commits los hace el script; se valida el mensaje antes |

## 18. Fuera de alcance (v1)

Perfil con shell para workers · paralelismo · orquestador sin sesión abierta (demonio) · coordinación entre máquinas · push, pull o merge automáticos · modo `auto` en workers · sandbox de Bash · usuario o contenedor aparte para workers · panel con `claude --bg`.

## 19. Decisiones por confirmar (con valor por defecto)

| # | Decisión | Por defecto |
|---|---|---|
| C1 | Autorización de commits | El plan autoriza commits **locales** en la rama `arkana-worker/<plan>` de cada repo; push siempre aparte |
| C7 | Integración en `develop` | Gate `integrate` tras evaluar; merge local `--no-ff` solo con tu confirmación; el push, aparte |
| C2 | Aislamiento por tarea | Rama en el propio repo; `worktree` solo para repos ligeros |
| C3 | Modelo y esfuerzo de los workers | Hereda el modelo de la sesión; esfuerzo `medium` (configurable) |
| C4 | Tipos de la cola manual | `aviso`, `tarea`, `revision`, `pregunta` |
| C5 | Reaprobación de cambios de plan | Estructurales sí; `investigate` preautorizable |
| C6 | Directorio de runtime | `<arkana>/.arkana/arkana-agentic/` |

## 20. Verificación de extremo a extremo y criterio de «hecho»

1. `bash scripts/doctor.sh --deep` → todo OK (incluida la batería de contención).
2. Tests unitarios y e2e con el `claude` falso → verdes.
3. Un plan de 3 tareas con el falso: completado; plan con una tarea bloqueada: se detiene y pregunta; `stop --force` mata al worker; `recover` tras una caída.
4. En el laboratorio, un worker real intenta leer un secreto, escribir en otro repo y ejecutar `git`: **todo bloqueado y registrado**.
5. `get` y `put` v2 con `--done` concurrente sin conflictos; migración de las 6 novedades.
5b. Con un pipeline en marcha, la statusline real muestra la **tercera línea** (worker, tarea y descripción breve) y desaparece al terminar. `/arkana-workspace:agentic off` la oculta y `on` la devuelve; sin `arkana-agentic` instalado, la skill se niega a activarla y no modifica nada.
6. `arkana-workspace:check`, `arkana-module:check` (5 módulos) y `arkana-agentic:check`: 0 FAIL, 0 WARN; enlaces de documentación: 0 rotos.
7. Piloto real supervisado completado, con commits locales en rama y sin push automático.
8. Siete repos sincronizados y sin cambios sin commitear.

## 21. Versionado, commits y publicación

- `arkana-agentic` 0.1.0 (fases 1–4) → **1.0.0** tras el piloto. `arkana-workspace` **3.0.0**. `arkana-module` **1.2.0**.
- Commits por repo con su formato: `arkana` en IA4D (`verbo(scope) descripción`, ≤72, sin coautor). Un commit por fase o sub-fase coherente; push solo con tu confirmación.
- Tras cada subida: `claude plugin marketplace update arkana` y `claude plugin update <plugin>@arkana`; el usuario ejecuta `/reload-plugins` y `/arkana-workspace:sync` (la convención de commits desplegada cambia con la versión).

## 22. Desviaciones respecto al plan inicial (lo construido)

| Tema | Plan inicial | Construido | Motivo |
|---|---|---|---|
| Lenguaje del motor | `lib/common.sh` + `state.py` | Todo en Python (stdlib) con envoltorios `.sh` de una línea | Estado, JSON y procesos son más robustos y comprobables en Python |
| `claude` falso | `tests/fake-claude.sh` | `tests/fake-claude.py` con 16 modos | Emite JSON y toca ficheros reales |
| Detección de cambios | `git status` y `git diff` | **Inventario de ficheros (manifiesto)** antes y después, independiente del `.gitignore` | Un `src/` ignorado ocultaba cambios (incluso `.env`) |
| `recover` | descartar, verificar lo hecho o reintentar | descartar o reintentar | `verificar` queda fuera de la v1 |
| Subcomandos | los del §10 | además `integrate`, `policy`, `retry`, `skip` | Integración de ramas con gate y límites configurables |
| Gates | `{gate, motivo, detalle, opciones, desde}` | además `tarea` y `reanuda` | `approve` debe saber qué reanudar |
| Límites | valores fijos por defecto | **mínimo de cuatro niveles** (por defecto con techos, política local, plan, tarea) | Un plan solo puede bajar los límites, nunca superar los techos |
| Esquemas | incluía `verificacion.schema.json` | no existe | El resultado de la verificación lo genera el propio script |
| Permisos de `arkana` | `Read/Edit/Write` sobre `<arkana>/.arkana/arkana-agentic/**` | solo `Read` y `deny Edit` sobre el estado; los borradores van al scratchpad; reglas `ask` en las decisiones humanas | el estado ya no está bajo `.claude/` (protegido por Claude Code): lo protege la regla `deny` y no debe tocarse a mano |
| Comando de control | `bash <ruta>/agentic.sh *` | dos raíces explícitas (copia de trabajo de `arkana` y caché con comodín de versión), **sin comillas**, una orden por llamada | Comprobado: la regla no casa con comillas ni con órdenes compuestas |
| Fase 4, aceptación | sesión real conduce un plan de 3 tareas | `test_flow.py` recorre el bucle documentado con solo `agentic.sh`; la sesión real queda para el piloto | Una sesión real cuesta dinero y exige el plugin instalado |
| Novedades migradas | 6 | 9 | Ya eran 9 las publicadas |
| Fase 7: batería de contención | `tests/containment/*` con la batería t1–t15 y r1–r7 (≈ 0,6 USD) | 26 pruebas con workers reales a través del lanzador completo, con canarios y comprobación de **efectos**; **segunda pasada adversaria** (`ARKANA_AGENTIC_RULES_FILE`, reglas neutras) para medir la contención estructural sin depender de la obediencia del modelo; coste real ≈ 0,1 USD con haiku | Con las reglas puestas, un modelo obediente puede pasar sin que los permisos actúen; ver `docs/VERIFICACION.md` |
| Coste de `doctor --deep` | ≈ 0,6 USD | ≈ 0,1 USD y ~4 min, con tope de seguridad `ARKANA_CONTAINMENT_MAX_USD` (2 USD) | Se usa haiku para los workers de prueba |
| Fase 8: lecciones del primer piloto (0.1.1) | — | `commits_locales` rechazado/avisado cuando deja el repo sin commitear; `integrate discard` admite el árbol sucio de la rama del pipeline; `act continue` siempre se registra; las verificaciones informativas (`git diff --stat`) no cuentan como evidencia de un criterio; `plan validate` avisa de instrucciones que piden ejecutar comandos | Detectado por el piloto con una sesión real; ver `docs/VERIFICACION.md` |
| Tercera línea de la statusline (§13.4) | Aparece solo con un pipeline activo; `⚙ P… · T002/3 · app · «descripción» · 6 min · 1,42 $` | **Siempre visible con el plugin instalado** (se comprueba `enabledPlugins` en cada refresco), con el formato `[estado] AAA/TTT worker@plan:tarea descripción P0,09$ S1,23$` (contador de tareas con tres dígitos; colores brillantes por elemento: worker amarillo, `@` y `:` rojos, plan y tarea azules, marcos, descripción, `P` y `S` grises; importes del plan y de la sesión —suma corriente, de `cost.total_cost_usd`— siempre en rojo normal y `$` siempre en verde normal, también sin plan; el contador cuenta las tareas resueltas —hechas más omitidas— y, si hay omitidas, añade `(✗N)`). **El plan solo se muestra en la sesión de Claude que lo gobierna** (`linea.json` lleva `session_id`, de `CLAUDE_CODE_SESSION_ID`; la statusline lo compara con el `session_id` de su entrada), de modo que una sesión nueva empieza sin plan y sin coste. La statusline anota el último coste de cada sesión en `sesiones/<id>` y `agentic.sh totals` suma planes y sesiones, símbolos Unicode sin emojis (▶ ‖ ? ■ ✗ ✓) coloreados por estado; sin plan muestra «sin plan activo»; el motor conserva `linea.json` con el estado terminal 30 min; la descripción se ajusta al ancho con degradación progresiva | Petición del usuario tras el primer piloto |
| Verbos de la línea de órdenes | En español (`integrar`, `continuar`, `--detener`, `--hecha`…) | **En inglés**: `act continue\|retry\|split\|investigate\|escalate\|skip\|stop`, `integrate merge\|keep\|discard`, `recover --action retry\|discard`, `reject --stop`, valores de `reanuda` (`reverify\|retry\|continue\|none`), `autoriza.investigate_without_gate` y, en `messages.sh put`, `--done`, `--discard` y `--comment`. Los nombres de campos, estados y banderas que son sustantivos siguen en español | Petición del usuario; sin alias en español, para que las reglas `ask` no se puedan esquivar con el nombre antiguo |
| Banderas de la línea de órdenes | `--tarea`, `--mensaje`, `--motivo`, `--nota`, `--asunto`, `--detalle`, `--intento`, `--techo`, `--para`, `--quien`, `--instrucciones-file`, `--tareas-file`, `--rapido`, `--profundo` | **En inglés**: `--task`, `--message`, `--reason`, `--note`, `--subject`, `--detail`, `--attempt`, `--ceiling`, `--for`, `--actor`, `--instructions-file`, `--tasks-file`, `--quick`, `--deep`. En `messages.sh`: `--type`, `--subject`, `--to`, `--from`, `--priority`, `--body-file`, `--instructions-file`, `--criteria-file`, `--result`, `--reason`, `--note`, `--state`, `--pending`, `--detail` | Petición del usuario: toda la interfaz en inglés (los valores de datos, como `aviso` o `abierta`, y los campos del JSON siguen en español) |
| Ramas de los workers | Una rama por plan y repo, `arkana-agentic/<plan>`, con un commit por tarea | **Una rama por plan y repo, `arkana-worker/<plan>`**, creada por el script `launch` (no por el worker ni por el modelo) con la primera tarea del repo, un commit por tarea aceptada. El plan guarda `ramas[repo] = {original, nombre, decision?}`. `integrate merge\|keep\|discard [--repo R] [--up-to Tnnn]` decide **por repo** (sin `--repo`, los repos sin decisión), y `integrate review` resume cada repo sin cambiar nada. Se probó un modelo de una rama por tarea encadenadas y se descartó por ingobernable (un merge por tarea) | Petición del usuario |
| Identificadores | Plan `P<AAMMDD>-<HHMM>-<xxxx>` y tarea `T<NN>` | Plan `P<AAMMDDHHMI>-<xxxx>` (hora local, 4 letras minúsculas al azar) y tarea `T<nnn>` (`T001`…`T999`) | Petición del usuario |
| Valores que se teclean | `--type aviso\|tarea\|revision\|pregunta`, `--state abierta\|hecha\|descartada`, `--priority alta`, `--actor orquestador\|usuario`, tipos del catálogo `leccion\|pendiente\|contrato\|referencia`, claves de `policy set` en español (`presupuesto_usd`…) | **En inglés**: `--type notice\|task\|review\|question`, `--state open\|done\|discarded`, `--priority normal\|high`, `--actor orchestrator\|user`, tipos del catálogo `decision\|lesson\|pending\|contract\|reference` (ids y carpetas de las notas migrados: `lesson-troubleshooting`, `conocimiento/pending/…`) y claves de política `max_turns`, `timeout_s`, `budget_usd`, `max_attempts_per_task`, `max_tasks`, `max_plan_changes`, `total_budget_usd`, `max_duration_min`, `checkpoint_every` (en las tareas, `limites`: `max_turns`, `timeout_s`, `budget_usd`, `max_attempts`) | Petición del usuario: «todo en inglés». Los nombres de campos del JSON (`tipo`, `estado`, `asunto`, `politica`, `limites`…), los estados de planes y tareas, las carpetas (`novedades/`, `conocimiento/`, `orquestacion/`) y los textos de los mensajes siguen en español |
| Gate de ruta protegida denegada (0.3.3) | Gate `ruta_protegida` solo si el worker escribia una ruta protegida; las denegadas de sus ajustes (CLAUDE.md…) salian como `permiso` genérico con «autorizar y reintentar», que no cambiaba nada | Una denegación sobre una ruta protegida es un gate `ruta_protegida` con la ruta y lo que quería escribir; `CLAUDE.md` y `CLAUDE.local.md` son autorizables (se levanta esa denegación en el siguiente intento), `.git`/`.husky`/`.claude`/`.env*` no; un `permiso` genérico ya no ofrece «autorizar» | Piloto 3: T003 se omitió tras dos intentos idénticos |
