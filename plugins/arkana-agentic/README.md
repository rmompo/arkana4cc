# arkana-agentic

Orquestación multi-repo desde ARKANA (el repositorio de conciliación y gobierno del proyecto, la carpeta `arkana`) sobre los componentes del proyecto, cada uno un repositorio; el workspace es ARKANA más el proyecto. Tú pides algo; el **orquestador** (la sesión de Claude de ARKANA) redacta un **plan**; **tú lo apruebas**; y se ejecuta **una tarea cada vez** con un **worker sin shell** en el repo que toque. El resultado de cada tarea lo **verifica un script**, no el worker, y tú decides en las paradas obligatorias. **El modelo propone; el script decide.**

> Estado: **0.1.0**. Motor, plano de control y skills terminados; probados sin coste con un `claude` falso y con una batería de contención con `claude` real. Falta el piloto real supervisado para pasar a 1.0.0 (ver `docs/PILOTO.md`). Es una cola **distinta** de la manual de `arkana-messaging` (`put` / `get`).

Este plugin es uno de los seis del marketplace `arkana`; la visión de conjunto está en [`../README.md`](../README.md). Otros documentos: [`docs/GUIA.md`](docs/GUIA.md) (guía para personas), [`docs/ESPECIFICACION.md`](docs/ESPECIFICACION.md) (especificación), [`docs/VERIFICACION.md`](docs/VERIFICACION.md) y [`docs/PILOTO.md`](docs/PILOTO.md).

## Índice

1. [Objetivo](#1-objetivo)
2. [Cómo se complementa con los otros plugins](#2-cómo-se-complementa-con-los-otros-plugins)
3. [Cómo funciona](#3-cómo-funciona)
4. [Modelo](#4-modelo)
5. [Skills](#5-skills)
6. [Referencia de `agentic.sh`](#6-referencia-de-agenticsh)
7. [Variables de entorno](#7-variables-de-entorno)
8. [Instalación y requisitos](#8-instalación-y-requisitos)
9. [Pruebas](#9-pruebas)
10. [Dónde está cada cosa](#10-dónde-está-cada-cosa)

---

## 1. Objetivo

Repartir un trabajo que afecta a varios repos (o a varios ficheros de uno) en **tareas pequeñas y verificables**, ejecutarlas con un agente acotado y conservar siempre el control humano:

| Principio | Cómo se materializa |
|---|---|
| El orquestador solo propone | Solo puede ejecutar `bash …/agentic.sh <subcomando>`; no lanza `claude`, no edita el estado, no hace `git` por su cuenta. Los límites duros (estados, límites, hash del plan, un solo worker) los impone el script. |
| Tú apruebas | El plan, cada gate, `policy set` e `integrate merge|discard` piden tu confirmación (reglas `ask` de permisos, además de la pregunta del skill). |
| Una tarea cada vez | Un único worker vivo; cada tarea acaba en un veredicto del script antes de empezar la siguiente. |
| El worker no tiene shell ni git | `claude -p` con herramientas de lectura/edición de ficheros, ajustes de permisos propios y un prompt con las normas del repo. |
| Verifica el script | Esquema del informe, denegaciones, instantáneas, alcance, rutas protegidas, comandos de una lista cerrada y criterios de aceptación. |
| Todo es local y reversible | Una rama por plan y repo (`arkana-worker/<plan>`), un commit local por tarea aceptada; `develop` no se toca hasta que decides, repo a repo; el push es siempre otra decisión. |

## 2. Cómo se complementa con los otros plugins

| Plugin | Qué aporta a `arkana-agentic` | Dónde se nota |
|---|---|---|
| [`arkana-workspace`](../arkana-workspace/README.md) | **Obligatorio** (`requires` en `arkana-plugin.json`). El **manifiesto** (`.arkana/core/workspace.json`) define los repos válidos (alias), sus rutas, su `type` (`node`, `maven`, `docs`, `generic`: elige el adaptador), su `commit_format` (`ia4d` o `conventional`) y `git.email_domains` (dominios del correo del autor del commit). `tools.json` (`/arkana-workspace:config tools`) declara las herramientas del proyecto: sus carpetas `bin` forman el `PATH` de las verificaciones, la ruta del `jdk` da `JAVA_HOME` y los registros por ámbito dan el `.npmrc`. Las **reglas de permisos del orquestador** (`agentic.sh` en `allow`, `ask` en las decisiones humanas, `deny` de `claude -p|--print|--bg` y de edición del estado) las genera `/arkana-workspace:fix`. | `repos.py`, `adapters.py`, `commitmsg.py`; checks `permisos-arkana`, `adaptadores`, `red-vpn` |
| [`arkana-messaging`](../arkana-messaging/README.md) | Opcional. `launch` copia en el prompt del worker, **como datos**, los mensajes del componente de la tarea; `plan show` los enseña antes de aprobar; al aceptar la tarea se marcan entregados y ejecutados. **`--from-message <id>`** indica a mano un mensaje concreto (`plan new`, `launch`, `retry`, `act retry`, `act investigate`). Sin messaging instalada solo avisa. | `inbox.py` |
| [`arkana-statusline`](../arkana-statusline/README.md) | Pinta el plan en la **línea 1** de la barra (`[▶] 002/007 worker@plan:tarea descripción`, gasto del plan `P`, coste de sesión `S`) leyendo `state/run/linea.json`, que el plugin reescribe en cada transición. Solo la muestra la sesión que gobierna el plan (campo `session_id`). **Es también la única escritora del coste real de cada sesión**, que el libro de sesiones lee. | `state.render_status_line`, `ledger.py` |
| [`arkana-knowledge`](../arkana-knowledge/README.md) | Opcional. Es el lugar donde dejar el conocimiento común que el orquestador consulta al redactar un plan (`/arkana-knowledge:query`); no hay integración en código: el orquestador lo **lee** y copia lo relevante como `extractos` de la tarea, porque el worker no ve nada fuera de su repo. | skill `plan` |
| [`arkana-todo`](../arkana-todo/README.md) | Sin relación: el orquestador no lee ni escribe la lista de tareas. |

El orquestador solo existe en la sesión de **ARKANA** (ARKANA): `install` pone el bloque `arkana:agentic` (plantilla `templates/orquestador.md`) en su `CLAUDE.md`. Los hooks del plugin no hacen nada dentro de un worker (`ARKANA_WORKER=1`) ni fuera de un workspace.

## 3. Cómo funciona

```
 TÚ ──pides──▶ SESIÓN DE arkana (orquestador = Claude + bloque arkana:agentic)
                 │  solo puede ejecutar:  bash <plugin>/scripts/agentic.sh <subcomando>
                 ▼
          agentic.sh  (plano de control: scripts deterministas, estado en <arkana>/.arkana/arkana-agentic/)
           ├─ launch ──▶ rama del plan ─▶ instantánea ─▶ [claude -p, perfil SIN shell, en el repo] ─▶ informe JSON
           │       └─ watchdog (tiempo máximo, parada forzosa, dead-man switch)
           └─ finish ──▶ verificación: esquema · denegaciones · instantáneas · alcance · rutas protegidas · lista cerrada · criterios
                 ▲                                  │
                 └──── decisión propuesta (act) ◀───┘   estados, límites y gates los aplica el script
```

Ciclo de vida completo:

| Paso | Quién | Qué ocurre |
|---|---|---|
| 1 | tú + orquestador | `/arkana-agentic:plan`: el orquestador lee el código, redacta el plan (JSON), `plan new` lo valida y lo copia al estado en `borrador`. |
| 2 | tú | `plan show` y aprobación: `plan approve` (guarda el **hash** del contenido) y `plan start` (`en_ejecucion`; congela las entregas de mensajes). |
| 3 | script | `next --json` dice qué toca: tarea, espera, gate, límite, pausa, decisión pendiente o fin. |
| 4 | script | `launch <T>` (en segundo plano): comprueba precondiciones, crea o activa la rama `arkana-worker/<plan>`, toma la instantánea `antes`, lanza el worker, el vigilante lo acota y la instantánea `despues` se guarda. |
| 5 | script | `finish <T>`: interpreta el informe, verifica y deja un veredicto con las **acciones permitidas**. |
| 6 | orquestador | `act …` registra **una** acción permitida (`continue` hace el commit local; `retry`, `split`, `investigate`, `escalate`, `skip`, `stop`). |
| 7 | tú | En un gate: `approve` o `reject`. Cada `checkpoint_every` tareas hay un gate de confirmación. |
| 8 | tú | Al terminar: `integrate review`, y por repo `merge` / `keep` / `discard`; luego `archive`. |

## 4. Modelo

### 4.1 Plan

Un plan es un JSON que crea `plan new <fichero>` (el orquestador lo deja en el scratchpad de la sesión). Claves de primer nivel:

| Clave | Tipo | Descripción |
|---|---|---|
| `asunto` | texto ≤ 80 | Título corto. |
| `peticion` | texto | Lo que pidió el usuario. |
| `autoriza` | objeto | `commits_locales` (booleano, **`true` por defecto**: el commit es local, en la rama del plan; con `false` el trabajo queda sin commitear y `integrate merge` no puede integrarlo), `rama` (por defecto `arkana-worker/<plan>`), `investigate_without_gate` (si `true`, `act investigate` añade la tarea sin gate de plan modificado). |
| `politica` | objeto `{clave: número}` | Límites del plan; solo pueden **bajar** los de la política (ver 4.6). |
| `tareas` | lista | De 1 a `max_tasks` tareas (12 por defecto, techo 30). |

Ejemplo neutro con dos repos:

```json
{"asunto": "Alinear la validación del formulario entre app-ui y api",
 "peticion": "El campo de correo debe validarse igual en el formulario y en la API.",
 "autoriza": {"commits_locales": true},
 "politica": {"total_budget_usd": 3},
 "tareas": [
  {"asunto": "Validar el correo en la API", "repo": "api", "tipo": "tarea",
   "objetivo": "Rechazar correos sin dominio en el endpoint de alta",
   "instrucciones": ["1. Añade la comprobación en el servicio de alta.", "2. Cubre el caso con un test."],
   "criterios_aceptacion": [{"id": "C1", "descripcion": "Los tests de la API pasan", "verificacion": "v1"}],
   "contexto": {"ficheros": ["src/main/java/alta/AltaService.java"]},
   "rutas_permitidas": ["src/**"],
   "verificaciones": [{"id": "v1", "comando": ["mvn", "-B", "test"], "timeout_s": 900}]},
  {"asunto": "Mostrar el error en el formulario", "repo": "app-ui", "tipo": "tarea",
   "objetivo": "Mostrar el mensaje de la API en el campo de correo",
   "instrucciones": ["1. Muestra el error del campo `email` bajo el input."],
   "criterios_aceptacion": [{"id": "C1", "descripcion": "Los tests del formulario pasan", "verificacion": "v1"}],
   "rutas_permitidas": ["src/app/form/**"],
   "verificaciones": [{"id": "v1", "comando": ["npm", "test"]}],
   "depende_de": ["T001"]}]}
```

Identificadores: el plan recibe `P` + diez cifras (fecha y hora local: año de dos cifras, mes, día, hora y minuto) + `-` + cuatro letras minúsculas al azar (p. ej. `P2611041030-abcd`); las tareas, `T001`, `T002`… por orden. Al aprobar, el script guarda el **hash** (SHA-256) del contenido aprobado (`asunto`, `peticion`, `autoriza`, `politica`, `tareas` y, de cada tarea, id, versión, asunto, repo, tipo, perfil, objetivo, instrucciones, criterios, contexto, rutas permitidas, verificaciones, dependencias y límites; **no** el estado, los intentos, el feedback ni el historial). Si el contenido cambia después, `plan start` y `launch` se niegan. Un cambio legítimo (`split`, `investigate`) deja un gate `plan_modificado` y, al aprobarlo, se recalcula el hash.

### 4.2 Tarea

| Campo | Obligatorio | Descripción |
|---|---|---|
| `asunto` | sí | 3–80 caracteres. |
| `repo` | sí | Alias de un componente del manifiesto (`app`, `api`, `app-web`, `app-ui`, `docs`, `specs`…; `arkana` es ARKANA). **Una tarea = un repo.** |
| `tipo` | sí | `tarea` (perfil `edicion`), `revision` o `investigacion` (perfil `lectura`). |
| `perfil` | no | `edicion` o `lectura`; si falta se deduce del tipo. Una tarea de tipo distinto de `tarea` con perfil `edicion` es un error. |
| `objetivo` | sí | Una frase. |
| `instrucciones` | sí | Lista de pasos, **autosuficientes**: el worker no ve tu conversación ni otros repos, y no puede ejecutar nada. |
| `criterios_aceptacion` | sí | Lista de `{id, descripcion, verificacion?}`; `verificacion` apunta al `id` de una verificación. |
| `contexto` | no | `ficheros` (rutas que conviene leer), `repos_lectura` (otros repos accesibles **solo en lectura**), `extractos` (`{origen, lineas?, texto}`: copias verificadas de otros repos). |
| `rutas_permitidas` | no | Globs de lo que puede cambiar; lo más estrecho posible. Cambios fuera de ellas → `rechazada` (alcance). |
| `verificaciones` | no | `{id, comando (argv), timeout_s? (600 por defecto)}`; las ejecuta el script **después** de la tarea. |
| `depende_de` | no | Ids de tareas que deben estar `completada`. |
| `limites` | no | `max_turns`, `timeout_s`, `budget_usd`, `max_attempts_per_task`: solo pueden bajar. |
| `mensajes_extra`, `feedback`, `autorizado`, `commit`, `intentos`, `estado`, `historial` | no | Los gestiona el script (`mensajes_extra` también con `--from-message`). |

### 4.3 Estados

**Tarea.** Transiciones permitidas (cualquier otra se rechaza):

| Desde | Hacia |
|---|---|
| `pendiente` | `lista`, `omitida`, `cancelada` |
| `lista` | `en_curso`, `omitida`, `cancelada` |
| `en_curso` | `verificando`, `parcial`, `fallida`, `bloqueada`, `interrumpida`, `cancelada` |
| `verificando` | `completada`, `rechazada`, `bloqueada`, `cancelada` |
| `rechazada`, `parcial`, `fallida` | `lista`, `fallida_definitiva`, `esperando_usuario`, `omitida` |
| `bloqueada` | `esperando_usuario`, `lista`, `omitida`, `cancelada` |
| `esperando_usuario` | `lista`, `verificando`, `omitida`, `cancelada`, `fallida_definitiva` |
| `interrumpida` | `lista`, `verificando`, `cancelada` |
| `completada`, `fallida_definitiva`, `omitida`, `cancelada` | (finales) |

**Plan.** `borrador → aprobado → en_ejecucion ⇄ pausado | esperando_usuario → completado | detenido | fallido`. Un plan `aprobado` puede volver a `borrador` o `detenido`; `borrador` solo a `aprobado` o `detenido`. Finales: `completado`, `detenido`, `fallido`. Activos (los que pinta la statusline): `en_ejecucion`, `pausado`, `esperando_usuario`. El plan pasa a `completado` cuando todas las tareas están `completada` u `omitida`, y a `fallido` si no quedan tareas ejecutables (dependencias fallidas u omitidas).

### 4.4 Veredictos y acciones permitidas

`finish` deja un veredicto y las acciones que `act` aceptará del orquestador (lo demás se rechaza con exit 3; con `--actor user` o con `retry` / `skip` manuales no se aplica esta tabla):

| Veredicto | Cuándo | Acciones permitidas |
|---|---|---|
| `completada` | Todo verificado y criterios cumplidos | `continue` |
| `rechazada` | Criterios o verificaciones fallan, cambios fuera de alcance, un worker de lectura modificó ficheros | `retry`, `split`, `escalate`, `skip`, `stop` |
| `parcial` | El worker se quedó a medias o se agotaron los turnos | `retry`, `split`, `escalate`, `skip`, `stop` |
| `fallida` | Tiempo, coste, salida sin JSON, informe inválido o error de `claude` | `retry`, `split`, `escalate`, `skip`, `stop` |
| `bloqueada` | Falta un permiso, herramienta, dato o decisión; ya hay gate | `escalate`, `skip`, `stop` |
| `violacion` | Instantáneas distintas de lo esperado | `stop` |

Motivos que el script registra (campo `motivo`): `tiempo` (exit 124/137), `informe_invalido`, `coste` (`error_max_budget_usd`), `turnos` (`error_max_turns`), `permiso` (hubo denegaciones), `error_claude`, `informe`, `perfil_lectura`, `alcance`, `criterios`, `ok`. Un reintento con la **misma causa** que el intento anterior se rechaza (exit 6) y hay que usar `escalate`.

### 4.5 Gates (paradas obligatorias)

Un gate deja el plan en `esperando_usuario` con un identificador `G01`, `G02`… y se resuelve con `approve` o `reject`. El campo `reanuda` dice qué hace `approve`:

| `reanuda` | Qué hace `approve` |
|---|---|
| `retry` | Descarta lo no aceptado, deja la tarea `lista` para un nuevo intento y pasa tu `--note` al worker como feedback («Respuesta del usuario: …»). En un `ruta_protegida` de denegación, autoriza esa edición **para esa tarea**. |
| `reverify` | Autoriza las rutas protegidas tocadas o los comandos fuera de lista de esa tarea y la deja en `verificando`: el siguiente paso es `finish <T>`. |
| `continue` | Solo cierra el gate; el plan sigue. En `plan_modificado` recalcula el hash aprobado. |
| `none` | `approve` se rechaza (exit 3): solo `reject`. |

| Motivo | Origen | Reanuda | Notas |
|---|---|---|---|
| `permiso` | El worker intentó algo no permitido (p. ej. leer fuera de su repo) | `retry` | **No cambia los permisos del worker**: tu nota llega como feedback, nada más. |
| `herramienta` | El worker pide una herramienta o un comando fuera de la lista, o una verificación del plan está fuera de la lista cerrada | `retry` / `reverify` | Autorizar una verificación la permite solo a esa tarea. |
| `dato`, `decision` | El worker necesita un dato o una decisión; o `act escalate` | `retry` | |
| `ruta_protegida` | (a) El worker **escribió** una ruta protegida que sus ajustes no deniegan (p. ej. `package.json`, `angular.json`): enseña el diff, `approve` autoriza y se vuelve a verificar. (b) El worker **intentó** editar `CLAUDE.md` o `CLAUDE.local.md` y sus ajustes se lo impidieron: `approve` autoriza esa edición para esa tarea. (c) Intentó editar `.git`, `.husky`, `.claude` o `.env*`: **no se puede autorizar** | `reverify`, `retry` o `none` | En (c) solo `reject` (omitir) o `reject --stop`. |
| `violacion` | Las instantáneas no cuadran | `none` | Solo detener el plan (`reject <G> --stop`). El script no impide `reject` sin `--stop` (omitiría la tarea), pero la regla del orquestador y del skill es detener. |
| `limite` | Presupuesto total o duración máxima del plan agotados | `continue` | Sube el límite en la política local (`policy set`, ≤ techo) y `approve`, o detén. |
| `checkpoint` | Cada `checkpoint_every` tareas completadas | `continue` | Confirmar que se sigue. |
| `plan_modificado` | `act split` o `act investigate` | `continue` | Enséñale las tareas nuevas con `plan show`. |
| `push`, `error` | Definidos en el esquema del plan, reservados: el código actual no los abre | | |

### 4.6 Límites y techos

Política por defecto (`policy/politica.default.json`), sobrescribible en local con `policy set` (`config/politica.json`). Para cada clave, el valor efectivo es **el mínimo** de política → plan (`politica`) → tarea (`limites`), y **nunca supera el techo**:

| Clave | Por defecto | Techo | Qué limita |
|---|---|---|---|
| `max_turns` | 40 | 80 | Turnos del worker por intento (`--max-turns`). |
| `timeout_s` | 1200 | 3600 | Tiempo máximo por intento (`timeout`, y el vigilante a `timeout_s + 15`). |
| `budget_usd` | 0,75 | 3,0 | Coste por intento (`--max-budget-usd`, con el mínimo entre este valor y lo que queda del total). No es un tope duro. |
| `max_attempts_per_task` | 2 | 3 | Intentos por tarea (alias `max_attempts`). |
| `max_tasks` | 12 | 30 | Tareas por plan (incluye las añadidas por `split` / `investigate`). |
| `max_plan_changes` | 3 | 8 | Cambios de plan (`split`, `investigate`). |
| `total_budget_usd` | 5,0 | 25,0 | Gasto total del plan; al agotarse, gate `limite`. |
| `max_duration_min` | 180 | 480 | Duración del plan desde `plan start`; al agotarse, gate `limite`. |
| `checkpoint_every` | 3 | 10 | Gate `checkpoint` cada n tareas completadas; `0` lo desactiva. |
| `ledger_retention_days` | 90 | 3650 | Retención del detalle del libro (`costs --purge`). |

`validate` avisa si un límite del plan supera el techo (se aplicará el techo).

### 4.7 Adaptadores por tipo de componente

El **tipo** sale de `components[].type` del manifiesto (`node`, `maven`, `docs`, `generic`; uno desconocido es `generic`). Cada adaptador (`policy/adapters/<tipo>.json`) **se suma** a `common.json` y declara: `herramientas` (las que necesita el verificador), `comandos` (lista cerrada, argv exacto sin shell), `rutas_protegidas` y `package_json_campos` (campos de `package.json` que no se pueden tocar).

| Adaptador | Herramientas | Comandos de verificación | Rutas protegidas propias |
|---|---|---|---|
| `common` (todos) | — | `git diff --stat` | `.git/**`, `.husky/**`, `.claude/**`, `CLAUDE.md`, `CLAUDE.local.md`, `.gitignore`, `.gitattributes`, `.env*`, `.github/**`, `.gitlab-ci.yml` |
| `node` | `node`, `npm` | `npm test`, `npm run lint`, `npm run build`, `ng build`, `ng test --watch=false` | `package-lock.json`, `angular.json`, `tsconfig*.json`, `webpack*.js`, `*.config.{js,cjs,mjs,ts}`; en `package.json`: `scripts`, `dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies`, `overrides`, `bin` |
| `maven` | `jdk`, `maven` | `mvn -B -q compile`, `mvn -B test`, `mvn -B verify` | `pom.xml`, `**/pom.xml`, `.mvn/**`, `mvnw`, `mvnw.cmd`, `**/settings*.xml`, `**/*.credentials` |
| `docs`, `generic` | — | (solo los comunes) | (solo las comunes) |

- Los **comandos** de un plan son la **unión** de los adaptadores de los repos de sus tareas; las **rutas protegidas**, las del adaptador del repo de **cada** tarea (nunca la unión: lo protegido en `maven` no lo está en `node`). Un patrón sin `/` se aplica a cualquier profundidad.
- Aditivo local: `config/comandos-permitidos.json` con `{"permitidos": [["comando", "arg"], …]}`.
- **La herramienta del adaptador debe estar en el `PATH` del verificador.** El verificador **no hereda el `PATH` de tu shell**: ve las carpetas `bin` de las herramientas declaradas en `tools.json` **con ruta** (`config tools --tool node --version <v> --path <ruta>`; `npm` viene con `node`) más `/usr/local/bin:/usr/bin:/bin`. El check `adaptadores` lo valida exactamente así: da `WARN` si una herramienta requerida no está declarada con ruta ni se encuentra en ese `PATH` básico (`jdk` se busca como `java`, `maven` como `mvn`).
- Entorno de cada verificación: `PATH` como arriba, `HOME` en una carpeta temporal, `npm_config_userconfig` con un `.npmrc` generado desde los registros por ámbito de `tools.json` (`ámbito:registry=url`), `JAVA_HOME` (ruta del `jdk` declarado, si la hay), `LANG=C.UTF-8`, `CI=1`, `NO_COLOR=1`. Se ejecuta en el repo con argv directo y el tiempo `timeout_s` (600 s por defecto); el resultado guarda código, duración y las últimas 40 líneas.

### 4.8 Rutas protegidas

Un worker no puede tocar las rutas protegidas del adaptador de su repo (tabla anterior). Se aplica de tres formas:

1. **Denegación en sus ajustes** (`Edit` sobre `.git`, `.husky`, `.claude`, `CLAUDE.md`, `CLAUDE.local.md`, `.env*`; lectura de `.env*`, `~/.git-credentials`, `~/.ia4d`, `~/.claude`, `~/.npmrc` y de la carpeta de metadatos `.arkana`).
2. **Detección posterior**: el verificador compara el inventario de ficheros (excluye `.git`, `node_modules`, `dist`, `.angular`, `coverage`, `target`) antes y después; lo protegido que cambió abre el gate `ruta_protegida` (`reverify`); en `package.json` solo cuentan los campos sensibles.
3. **Gate con diff**: antes de autorizar enséñate el diff y la ruta exacta (`git -C <repo> diff`).

### 4.9 Rama del plan y commits

- **Una rama por plan y repo: `arkana-worker/<plan>`.** La crea `launch` (el worker no tiene `git`) con la primera tarea de ese repo, **desde `develop`** (debe existir en local), recuerda la rama original y la activa antes de cada lanzamiento. Si el repo estaba en la rama de otro plan, la «original» se toma como `develop`. Mientras corre un plan no se trabaja en los repos implicados.
- Los planes anteriores usaron el prefijo **`m3a/<plan>`**; se **reconocen** (el plan guarda el nombre real de su rama y `repos.is_plan_branch` acepta ambos prefijos), así que `act`, `integrate` y `archive` siguen funcionando con ellos.
- **Un commit local por tarea aceptada** (`act continue --message`), en esa rama, con el **formato del componente** (`commit_format` del manifiesto): `conventional` (por defecto) → `tipo(scope): descripción` (con dos puntos), `ia4d` (opcional) → `verbo(scope) descripción` (sin dos puntos). Reglas comunes: en inglés, ≤ 72 caracteres, sin punto final, una línea de asunto, **sin `Co-Authored-By`**, tipos `feat|fix|docs|chore|refactor|test|style|perf|build|ci|revert`, scope en minúsculas (`[a-z0-9._-]+`; usa el id del repo, p. ej. `docs(api): add environment section` en `conventional` o `docs(api) add environment section` en `ia4d`). Si el componente declara `git.email_domains`, el correo del autor (`git config user.email` del repo) debe ser de uno de esos dominios. Solo se añaden las rutas que cambió la tarea y no están ignoradas.
- Un reintento vuelve al último commit aceptado (`reset --hard` + `clean -fd`: se descarta lo no aceptado, nunca lo aceptado). Una tarea aceptada **no se reabre**: se corrige con una tarea nueva.
- Al terminar, **tú decides por repo**: `integrate merge` (merge local `--no-ff` en la rama original; mensaje `chore(<repo>) merge <rama>` o `chore(<repo>): merge <rama>` según el formato), `keep` o `discard`. **No hay push.**

### 4.10 Verificación (`finish`)

Orden de las comprobaciones; la primera que falla decide:

| # | Comprobación | Resultado si falla |
|---|---|---|
| 1 | El worker terminó en tiempo (no exit 124/137) y devolvió JSON | `fallida` (`tiempo` / `informe_invalido`) |
| 2 | `error_max_budget_usd` / `error_max_turns` | `fallida` (`coste`) / `parcial` (`turnos`) |
| 3 | Sin denegaciones de permisos | `bloqueada` + gate `permiso` o `ruta_protegida` |
| 4 | Informe válido contra `schemas/informe.schema.json`; estado `hecha`, `parcial`, `fallida` o `bloqueada` (con `necesita`: permiso, herramienta, dato, decisión, otro) | `fallida`; `parcial` y `fallida` del worker pasan directos; `bloqueada` abre gate |
| 5 | Instantáneas: repos y ficheros vigilados (`~/.claude/settings.json`, `~/.git-credentials`, `~/.ia4d/.env`, `~/.npmrc`, `~/.gitconfig`, ajustes locales de `arkana`) por tamaño, fecha e inodo, **sin leer su contenido** | `violacion` (exit 4) |
| 6 | Rutas protegidas tocadas y no autorizadas | gate `ruta_protegida` (exit 5) |
| 7 | Un worker de lectura no cambió nada | `rechazada` (`perfil_lectura`) |
| 8 | Cambios dentro de `rutas_permitidas` | `rechazada` (`alcance`) |
| 9 | Verificaciones dentro de la lista cerrada (o autorizadas) | gate `herramienta` (exit 5) |
| 10 | Ejecución de las verificaciones y de cada criterio: con `verificacion`, cuenta el código de salida; sin ella (o con un comando informativo como `git diff --stat`, que no puede fallar) es **autoevaluado**; si el propio worker dice que no lo cumple, no se da por cumplido | `rechazada` (`criterios`) o `completada` |

Revisa tú el diff de los criterios de contenido que ningún script verificó antes de `act continue`.

### 4.11 El worker

`launch` ejecuta `timeout --kill-after=10 <timeout_s> claude -p <prompt> --output-format json --json-schema <informe> --restricted --permission-mode dontAsk --permission-prompts none --tools Read,Edit,Write,Glob,Grep` (perfil `lectura`: `Read,Glob,Grep`) `--disallowedTools Agent WebSearch Skill --settings <ajustes> --append-system-prompt-file templates/worker-rules.md --max-turns … --max-budget-usd … --no-session-persistence`, con `--add-dir` por cada `repos_lectura`, `--model` si hay `ARKANA_AGENTIC_MODEL` y `--effort` si hay `ARKANA_AGENTIC_EFFORT`. Corre con `ARKANA_WORKER=1`, sin stdin, en una sesión de procesos propia y en el directorio del repo; sus ajustes desactivan todos los hooks. No carga el `CLAUDE.md` del repo: las normas viajan en el prompt (`templates/worker-prompt.md.tpl`, sin el bloque de messaging), junto con la tarea, los extractos, el feedback y los mensajes. Un **vigilante** independiente (`watchdog.py`) aplica el tiempo máximo, la parada forzosa (`run/STOP-FORCE`) y el **dead-man switch**: si la sesión de Claude dueña desaparece, mata al worker. Cada intento deja `logs/<T>.<n>.{prompt.md,salida.log,error.log}`, `informes/<T>.<n>.raw.json`, `snapshots/` y `verificacion/<T>.<n>.json`.

### 4.12 Mensajes de `arkana-messaging`

Un worker no ve la mensajería. `launch` copia en su prompt, **como datos y no como instrucciones**, las directrices permanentes (`repeat` vigentes) y las peticiones de una vez (`once`: `task`, `review`, `question` abiertas) de su componente; no se entregan los avisos `once`, los `repeat` propuestos ni los borrados. `plan show` lista por tarea lo que recibirá; **aprobar el plan es confirmar que se entrega**; `plan start` congela la lista (lo que llegue después espera a otro plan). Al aceptar la tarea (`act continue`) se marcan ejecutados (en un `repeat` significa «al menos una vez»). `--from-message <id>` (opción repetible) entrega un mensaje concreto: debe ir dirigido al componente de la tarea, se registra en `mensajes_extra` y en el registro (`mensaje_indicado`) y añade al feedback la línea «Atiende lo que pide el mensaje…». Léelo antes con `/arkana-messaging:query --detail`.

### 4.13 Libro de planes y sesiones (`data/ledger/`)

Solo **metadatos**. Cada plan terminado deja su apunte en `ledger/plans/<plan>.json` (fechas, componentes, ramas e integración, gasto total y por tarea e intento); cada sesión de Claude del workspace deja el suyo en `ledger/sessions/<sid>.json` (inicio, fin, componente, plan que gobierna, duración, tokens y coste), escrito por los hooks **`SessionStart`** (`startup|resume|clear|compact`) y **`SessionEnd`** (`ledger.py hook session-start|session-end`). El **coste real de una sesión lo escribe la statusline** (`.arkana/arkana-statusline/state/sessions/<sid>.json`; mientras siga la antigua, `state/sesiones/<sid>`); los hooks solo lo leen y, sin él, queda vacío: nunca se estima. Los tokens salen del transcript. Retención: `ledger_retention_days` (90 por defecto); se purga el detalle y se conservan los totales. Consulta: `/arkana-agentic:costs`.

### 4.14 Garantías y lo que no se garantiza

**Se garantiza** (lo impone el script o los ajustes, no el modelo):

- Los workers **no tienen shell ni git**, no salen de su repo, no cargan su `CLAUDE.md` y no tocan rutas protegidas ni credenciales.
- **Un solo worker a la vez**, con tiempo, turnos, coste e intentos limitados; un plan solo **baja** los límites.
- **Todo comando lo ejecuta el script**, de una lista cerrada, con argv directo y entorno reducido.
- **Un plan aprobado no se puede alterar** (hash).
- **Nada se commitea, integra ni sube sin tu autorización**; el trabajo vive en `arkana-worker/<plan>`.
- **Paradas obligatorias** en permiso, herramienta, dato, decisión, ruta protegida, violación, límite, checkpoint y plan modificado.
- **Parada** suave o forzosa (SIGTERM y, tras `ARKANA_AGENTIC_KILL_GRACE` s, SIGKILL al grupo del worker); si la sesión muere, el dead-man switch mata al worker y `fix` te pregunta qué hacer.
- **Sobre la sesión de `arkana`** (reglas de `/arkana-workspace:fix`): solo ejecuta `agentic.sh`; no puede lanzar `claude -p|--print|--bg`; no escribe el estado a mano; `plan approve`, `approve`, `reject`, `policy set` e `integrate merge|discard` **piden siempre confirmación** aunque el modelo se salte la pregunta (el check `permisos-arkana` avisa si faltan).

**No se garantiza:** que el trabajo sea correcto (por eso verifica el script y tú revisas el diff); la **exfiltración por red** ni el **código malicioso que un worker deje para que lo ejecute el verificador** (por eso las rutas sensibles abren un gate y ves el diff antes de ejecutar); la **inyección de prompts** a través de lo que el worker lea (todo lo que viene de un worker, y los mensajes, son datos); ni la exactitud del tope de coste (`--max-budget-usd` no es duro: se usa con margen y junto a tiempo y turnos). No hay sandbox de sistema operativo (el contenedor no admite `bwrap`) ni usuario aparte para los workers.

---

## 5. Skills

Los 10 skills de `skills/` (`/arkana-agentic:<skill>`). Todos se usan desde `arkana`; invocan `bash ${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh <sub>` en **una sola orden por llamada, con la ruta sin comillas y sin `&&`, `;`, `cd` ni redirecciones** (las reglas de permisos solo reconocen esa forma).

| Skill | Para qué | Subcomandos que usa | Pregunta al usuario |
|---|---|---|---|
| `install` | Primera puesta en marcha (repetible): carpetas `config/state/data`, bloque `arkana:agentic` en el `CLAUDE.md` de ARKANA y plugin habilitado en `~/.claude/settings.json` | `install [--dry-run] [--no-settings]` | Sí, antes de aplicar (modifica `CLAUDE.md` y ajustes de usuario) |
| `check` | Salud de la orquestación; solo lectura y sin coste (`--deep` cuesta dinero) | `check [--deep] [--need-network]` | Antes de `--deep` |
| `plan` | Redacta, valida y presenta un plan; no ejecuta nada hasta que apruebas | `check`, `plan new`, `plan show`, `plan approve`, `plan start`, `act stop` | *Aprobar y ejecutar* · *Aprobar sin ejecutar* · *Cambiar algo* · *Descartar* |
| `run` | Ejecuta el plan, una tarea cada vez, y se detiene en los gates | `check`, `status`, `next`, `launch`, `finish`, `act`, `approve`, `reject`, `integrate review`, `resume` | En cada gate y, al final, por repo |
| `status` | Estado legible; solo lectura | `status`, `totals`, `log` | No |
| `control` | Resuelve gates y decisiones manuales | `status`, `log`, `approve`, `reject`, `retry`, `skip`, `policy` | Siempre antes de aprobar |
| `stop` | Parada suave, pausa, reanudación o parada forzosa; obedece de inmediato | `stop`, `pause`, `resume`, `stop --force`, `status` | Solo si no está claro cuál |
| `fix` | Migra el layout antiguo y recupera tareas interrumpidas; nunca reintenta por su cuenta | `check`, `status`, `fix [--dry-run] [--task T --action …]`, `act stop` | *Reintentar* · *Descartar* · *Detener el plan* |
| `archive` | Integra, deja o descarta las ramas por repo y archiva el plan terminado | `status`, `integrate review|merge|keep|discard`, `archive` | Por repo y para archivar |
| `costs` | Costes del libro: workers por plan y tarea, y coste real de las sesiones | `costs [--plan --session --component --since --by --purge] [--json]` | Antes de `--purge` real |

### `/arkana-agentic:install`

Hace tres cosas: (1) crea `.arkana/arkana-agentic/{config,state,data}` con modo 700; (2) pone en el `CLAUDE.md` de ARKANA el bloque `<!-- arkana:agentic:start -->…<!-- arkana:agentic:end -->` con las reglas del orquestador (`templates/orquestador.md`) y sustituye la referencia antigua `@orquestacion/ORQUESTADOR.md`; (3) habilita `arkana-agentic@arkana` en `~/.claude/settings.json` (copia previa en `.arkana/arkana-agentic/bak/`). Pasos: `--dry-run` primero, pedir confirmación, aplicar, recordar que el `CLAUDE.md` queda modificado **sin commit** y que hay que recargar los plugins; con layout antiguo, el siguiente paso es `/arkana-agentic:fix`. Después, `/arkana-workspace:fix` para las reglas de permisos.

### `/arkana-agentic:check`

Ejecuta `agentic.sh check` y presenta una tabla (comprobación · estado · detalle) con los `FAIL` primero, luego los `WARN`, y agrupa las `OK`. **`red-vpn` es un `WARN`, no un `FAIL`**: agentic solo edita y hace commits locales en la rama del plan (no hace `fetch`, `pull` ni `push`), así que sin VPN el trabajo sigue y `launch` avisa y lanza; `--need-network` lo convierte en `FAIL` para algo que sí necesite los remotos. Con un `FAIL` no se inicia ni se reanuda ningún plan. `--deep` ejecuta la batería de contención con `claude` real (cuesta dinero, ver [Pruebas](#9-pruebas)): confirmación previa. Tabla de salidas por comprobación en [`check`](#check).

### `/arkana-agentic:plan`

Pasos: `check` (con un `FAIL`, no seguir); entender la petición (preguntar si es ambigua) y **leer el código** de los repos necesarios; escribir el borrador en el scratchpad; `plan new <borrador>` hasta que no haya `FAIL` (contar los `WARN`); `plan show` y un resumen claro (tareas, repo, orden, criterios, verificaciones, límites, qué autoriza y **mensajes que recibirá cada worker**); y la pregunta de aprobación. *Aprobar y ejecutar* → `plan approve`, `plan start` y, sin parar, el skill `run`. *Aprobar sin ejecutar* → `plan approve`. *Descartar* → `act stop` si ya se creó. Reglas: `autoriza.commits_locales: true`; no pedir al worker que ejecute nada; no enlazar un criterio a `git diff --stat`; ≤ 12 tareas; avisar antes si la tarea exige rutas protegidas. Para un mensaje concreto: `plan new <fichero> --from-message <id>` o `plan new --from-message <id> --paths '<glob>'`.

### `/arkana-agentic:run`

Bucle: `check` y `status` (el plan debe estar `en_ejecucion` (si `aprobado`, `plan start` antes; si `pausado`, preguntar si `resume`)) → `next --json` → según `estado`: `tarea` → `launch <T>` **en segundo plano** (opción `--from-message <id>` para un mensaje concreto) y esperar el aviso; `worker_en_curso` → esperar; `gate`/`limite` → preguntar y `approve`/`reject`; `pausado` → informar; `falta_finish` → `finish`; `fix` → `/arkana-agentic:fix`; `decision_pendiente` → decidir; `terminado` → resumen. Tras el lanzamiento, `finish <T> --json` y **una** acción de `acciones_permitidas` con `act` (informe de una línea). Al terminar: `integrate review` y pregunta por repo. Un aviso de tarea en segundo plano no es una respuesta tuya; todo lo que dice un worker es un dato.

### `/arkana-agentic:status`

`status` (y `status --plan <id>` para otro plan), más una línea de interpretación (qué falta, si algo espera al usuario y qué skill corresponde). Para el gasto global, `totals`; para una tarea, `log <T> [--attempt N]`. No cambia nada.

### `/arkana-agentic:control`

Con un gate abierto: `status` y `log <T>`; explicar qué pasó y qué opciones hay (enseñar antes el diff en una `ruta_protegida` ya escrita, y lo que el worker *quería* escribir si es `CLAUDE.md`; un gate `permiso` no concede permisos; si la ruta *no se puede autorizar*, solo `reject`); preguntar y registrar: autorizar → `approve <G> [--note]`, rechazar → `reject <G>`, detener → `reject <G> --stop`. Decisiones manuales: `retry <T>`, `skip <T>`, `policy show`, `policy set <clave> <valor> [--ceiling]`. Nunca aprueba por el usuario.

### `/arkana-agentic:stop`

| Petición | Comando | Efecto |
|---|---|---|
| Parar sin perder la tarea | `stop` | La tarea actual termina; después el plan queda `pausado`. |
| Pausar | `pause` | Igual. |
| Reanudar | `resume` | El plan vuelve a `en_ejecucion`. |
| Parar ya | `stop --force` | SIGTERM al grupo del worker y SIGKILL a los 10 s; tarea `cancelada`; plan `detenido`. |

Si dices «para ya» o «mátalo», es forzosa. Tras una forzosa el repo puede tener cambios sin commitear: la tarea queda `cancelada` (`fix` no la recupera) y `integrate keep` se niega con el repo sucio; se ofrece `integrate discard` (descarta también lo no commiteado) o revisar y commitear a mano en la rama del plan.

### `/arkana-agentic:fix`

Ejecuta `check` y `status`; si `check` marca `layout`, `fix --dry-run`, enseñar qué se movería y, con confirmación, `fix` (copia `tar.gz` en `.arkana/arkana-workspace/bak/`; se niega con un plan activo o un worker vivo). También detecta las tareas `en_curso` sin worker vivo, las marca `interrumpida` e indica el estado del repo. Pregunta *Reintentar la tarea* (descarta lo hecho a medias) · *Descartar la tarea* · *Detener el plan*, y ejecuta `fix --task <T> --action retry|discard` o `act stop`. Nunca reintenta por su cuenta ni mata un worker que no reconoce. Para seguir: `/arkana-agentic:run`.

### `/arkana-agentic:archive`

`status` (el plan debe ser `completado`, `detenido` o `fallido`); `integrate review` y, **por repo**, *Integrar (merge local, sin push)* · *Dejar la rama* · *Descartar la rama* con `integrate merge|keep|discard --repo <r>` (`--up-to <Tnnn>` solo con `merge`; con un plan `detenido` o `fallido` no se ofrece integrar); y `archive` si quieres conservar el plan en `data/archive/<plan>/` (local, no se versiona; viaja solo con `arkana-workspace:export --include-data`).

### `/arkana-agentic:costs`

`costs [--plan <id>] [--session <id>] [--component <alias>] [--since AAAA-MM-DD] [--by plan|session|component|day] [--json]`. Dos orígenes que no se mezclan: **workers** (`plan-task`: lo que costaron los `claude -p` de cada tarea e intento) y **sesiones** (coste real de la statusline; sin él queda vacío y se indica «N sesiones sin coste»). `costs --purge [--dry-run]` aplica la retención.

---

## 6. Referencia de `agentic.sh`

`bash scripts/agentic.sh <subcomando> [opciones]` (`${CLAUDE_PLUGIN_ROOT}/scripts/agentic.sh`). Hay **22 subcomandos**; los de varias acciones (`plan`, `act`, `integrate`, `policy`) se detallan por acción. `bash scripts/agentic.sh <sub> --help` es de solo lectura. Atajos: `scripts/check.sh` (= `agentic.sh check`), `launch-worker.sh <plan> <tarea>`, `verify-task.sh <plan> <tarea> [--json]`, `snapshot.sh` y `watchdog.sh` (motores internos).

### 6.1 Convenciones

**Opciones comunes** (todos los subcomandos las aceptan): `--plan <id>` (por defecto el plan actual, el último creado con `plan new`) y `--json` (salida estructurada donde aplica; `act`, `launch`, `approve`, `reject`, `install`, `archive`, `fix`, `integrate` y otros imprimen siempre líneas de texto). Sin plan actual y sin `--plan`, los subcomandos que lo necesitan salen con 3 (`status` lo cuenta con exit 0).

**Salida de texto:** una línea `ESTADO|ID|detalle` (`OK`, `WARN`, `FAIL`, `DRY`) y, en `check`, `RESUMEN|n FAIL|n WARN`. Los decimales de los informes legibles llevan coma.

**Códigos de salida:**

| Código | Significado | Ejemplos |
|---|---|---|
| 0 | Correcto | Acción registrada; `check` sin `FAIL` (los `WARN` no cuentan) |
| 1 | Error | Plan inválido, fichero ilegible, commit rechazado, merge fallido, `check` con algún `FAIL` |
| 2 | Uso | Falta un argumento, opción no admitida en esa acción, valor no numérico, error de `argparse` |
| 3 | Precondición | Sin plan actual, estado incorrecto, worker vivo, repo sucio o fuera de la rama del plan, plan alterado, gate inexistente |
| 4 | Violación | `finish` detectó una violación (instantáneas) |
| 5 | Esperando al usuario | Hay un gate abierto o se acaba de abrir (`finish`, `next`, `act escalate|split|investigate`, `fix` con tareas interrumpidas) |
| 6 | Límite | Intentos, presupuesto, duración o cambios de plan agotados; `policy set` por encima del techo; reintento con la misma causa |
| 7 | Detenido o pausado | `launch` con parada o pausa pedida o tarea cancelada por `stop --force`; `next` con el plan `pausado` |

### 6.2 Resumen

| Subcomando | Efecto | Opciones propias |
|---|---|---|
| `plan new|show|validate|approve|start` | Crea, ve, valida, aprueba (hash) e inicia un plan | `file`, `--from-message`, `--repo`, `--paths` |
| `next` | Qué toca ahora (puede cerrar el plan o abrir un gate) | — |
| `launch <T>` | Lanza el worker de una tarea y espera a que termine | `--from-message` |
| `finish <T>` | Interpreta y verifica el resultado del worker | — |
| `act <acción> [<T>]` | Registra la decisión del orquestador | `--message`, `--reason`, `--feedback-file`, `--tasks-file`, `--repo`, `--from-message`, `--subject`, `--instructions-file`, `--for`, `--gate`, `--detail`, `--actor` |
| `status` | Estado del plan | — |
| `log <T>` | Salida y verificación de una tarea | `--attempt`, `--tail` |
| `stop` | Parada suave o forzosa | `--force` |
| `pause` / `resume` | Pausa y reanudación | — |
| `retry <T>` / `skip <T>` | Reintento u omisión manual (usuario) | `--from-message` (solo `retry`) |
| `approve <G>` / `reject <G>` | Resuelve un gate | `--note`; `reject`: `--reason`, `--stop` |
| `fix` | Migra el layout y recupera tareas interrumpidas | `--dry-run`, `--task`, `--action` |
| `archive` | Archiva un plan terminado | — |
| `totals` | Gasto acumulado | — |
| `costs` | Costes del libro | `--session`, `--component`, `--since`, `--by`, `--purge`, `--dry-run` |
| `integrate review|merge|keep|discard` | Integra o descarta las ramas del plan | `--repo`, `--up-to`, `--message` |
| `policy show|set` | Límites y techos | `key`, `value`, `--ceiling` |
| `install` | Puesta en marcha | `--dry-run`, `--no-settings` |
| `check` | Salud del entorno | `--quick`, `--deep`, `--need-network` |

### `plan`

`agentic.sh plan {new,show,validate,approve,start} [file] [--plan ID] [--json] [--from-message ID]… [--repo REPO]… [--paths GLOB]…`

**`plan new [<fichero>]`** — Crea un plan en `borrador` y lo deja como **plan actual**. El fichero es el JSON de la sección 4.1 (el script añade ids, estado, `intentos`, `feedback`, `historial`; `autoriza.commits_locales` vale `true` si no se indica y `autoriza.rama` se rellena). Valida antes de guardar: esquemas de plan y tarea; dependencias que existen y sin ciclos; criterios que apuntan a verificaciones definidas; `edicion` solo para `tipo: tarea`; repo conocido en el manifiesto; `commits_locales: false` con varias tareas de edición en un repo (error); máximo de tareas. Avisos (no impiden crear): ruta permitida que cae en una protegida; instrucción que parece pedir al worker que ejecute comandos; verificación fuera de la lista cerrada (abrirá gate); criterio enlazado a un comando informativo (`git diff --stat`), que se tratará como autoevaluado; límite del plan por encima del techo; ruta del repo que no es repositorio git; `commits_locales: false`.

| Opción | Efecto |
|---|---|
| `file` | Fichero del plan. Opcional si hay `--from-message`. |
| `--from-message ID` (repetible) | **Con fichero:** el mensaje se entrega a las tareas cuyo repo es destinatario (si ninguna lo es, error exit 2) y se añade a su feedback; si el plan no trae `peticion`, se rellena con «Atender <id> («asunto»)». **Sin fichero:** el plan se **genera** a partir de los mensajes: una tarea de edición por mensaje y componente destinatario, con las instrucciones, los criterios y el asunto del mensaje, el feedback «Atiende lo que pide el mensaje…» y `mensajes_extra`. |
| `--repo REPO` (repetible) | Solo en el plan generado: componentes que reciben una tarea (obligatorio si el mensaje va a varios componentes: una vez por componente; también lo restringe si va a uno). |
| `--paths GLOB` (repetible) | Solo en el plan generado: **obligatorio**, las `rutas_permitidas` de cada tarea (p. ej. `--paths 'src/**'`). |

Errores: sin fichero ni `--from-message` → 2; `--from-message` sin fichero y sin `--paths` → 2; mensaje inexistente, dado de baja o no dirigido a ese componente → 2; fichero ilegible o plan con `FAIL` de validación → 1.

```bash
agentic.sh plan new /scratch/alinear-validacion.json
agentic.sh plan new /scratch/alinear-validacion.json --from-message <id-mensaje>
agentic.sh plan new --from-message <id-mensaje> --paths 'src/**' --repo api --repo app-ui
```

**`plan show [--plan ID] [--json]`** — Muestra el plan: asunto, estado, petición, qué autoriza, **límites efectivos**, y por tarea repo, tipo/perfil, dependencias, objetivo, instrucciones, criterios y **mensajes que recibirá el worker**. Con `--json`: `{"plan", "tareas"}`. Exit 0.

**`plan validate`** — Repite la validación de `plan new` sobre el plan guardado. Exit 0 sin `FAIL`, 1 con alguno.

**`plan approve`** — Solo desde `borrador` (si no, exit 3); revalida (1 si hay errores), guarda el hash y pasa a `aprobado`. **Es una decisión tuya**: la regla `ask` de permisos pide confirmación.

**`plan start`** — Solo con el plan `aprobado` y sin alteraciones (si no, exit 3): pasa a `en_ejecucion`, arranca el reloj de duración y **congela** la lista de mensajes que recibirá cada worker (indica cuántas entregas).

### `next`

`agentic.sh next [--plan ID] [--json]` — Dice qué toca y, a veces, **cambia el estado** (cierra el plan, abre un gate de límite o de checkpoint, convierte una marca de parada suave en `pausado`). Salida: `estado` y datos; con `--json` un objeto.

| `estado` | Significado | Exit |
|---|---|---|
| `tarea` | Hay una ejecutable (`tarea`, `repo`, `asunto`, `perfil`): `launch <T>` | 0 |
| `terminado` | El plan acabó (`detalle`: `completado`, `detenido` o `fallido`) | 0 |
| `gate` | Hay un gate abierto (`gate`) | 5 |
| `limite` | Presupuesto total o duración agotados; abre el gate `limite` | 6 |
| `pausado` | Plan pausado (o marca de parada suave recién aplicada) | 7 |
| `worker_en_curso` | Hay un worker vivo (`tarea`, `pid_worker`): es una espera normal | 0 |
| `falta_finish` | Una tarea terminó sin `finish` o está `verificando`: `finish <T>` | 3 |
| `fix` | Una tarea `en_curso` sin informe ni worker: `fix` | 3 |
| `no_iniciado` | El plan no está en ejecución (`detalle`) | 3 |
| `decision_pendiente` | Tareas `rechazada`/`parcial`/`fallida`/`interrumpida`/`bloqueada`/`esperando_usuario` (`tareas`) que esperan un `act` | 0 |

Antes de elegir tarea comprueba (por este orden) worker vivo, marcas de parada, tareas sin informe, presupuesto y duración, fin del plan, y por último el **checkpoint** (gate cada `checkpoint_every` tareas completadas). Un plan sin tareas ejecutables (dependencias omitidas o fallidas) pasa a `fallido`.

### `launch`

`agentic.sh launch <task> [--plan ID] [--json] [--from-message ID]…` — Lanza el worker de la tarea y **espera a que termine** (invócalo en segundo plano). Precondiciones (si no, exit 3, salvo lo indicado): sin parada ni pausa pedida (exit 7); plan `en_ejecucion` y hash intacto; un solo worker vivo; tarea `pendiente` o `lista` con dependencias completadas; límites (tareas, intentos, presupuesto total, duración: exit 6); repo válido, **árbol limpio** y rama `develop` local (para crear la del plan). Sin red solo avisa (`WARN|red`, por stderr): el trabajo es local. Prepara la rama `arkana-worker/<plan>`, incrementa `intentos`, toma la instantánea `antes`, copia los mensajes (anota su entrega), lanza el worker con el vigilante, guarda `informes/<T>.<n>.raw.json`, suma el coste y toma `despues`.

| Opción | Efecto |
|---|---|
| `--from-message ID` (repetible) | Antes de lanzar, entrega esos mensajes a la tarea (y a sus reintentos). Deben ir dirigidos al componente de la tarea y no estar dados de baja; si no, exit 3 sin tocar nada (tarea inexistente: exit 2). |

Salida y códigos: 0 el worker corrió (**falta `finish`**) o se marcó `interrumpida` (sesión dueña muerta, señal al lanzador, tiempo del vigilante); 7 `cancelada` por `stop --force`; 6 límite; 3 precondición; 2 uso; 1 error.

```bash
agentic.sh launch T001                              # normalmente con run_in_background
agentic.sh launch T002 --from-message <id-mensaje>
```

### `finish`

`agentic.sh finish <task> [--plan ID] [--json]` — Interpreta el informe y verifica el trabajo (sección 4.10), deja `verificacion/<T>.<n>.json` con el veredicto y las **acciones permitidas** y mueve la tarea a su estado. Exige tarea `en_curso` o `verificando` (también tras un gate `reverify`), sin worker vivo y con informe crudo; si no, exit 3. Salida de texto: `OK|finish|<T> completada…` o `FAIL|finish|<T> <veredicto>: <motivo> <detalle>` más `ACCIONES|a,b,c`. Con `--json`, el objeto de verificación (veredicto, motivo, detalle, informe, coste, criterios, verificaciones, rutas cambiadas…).

Exit: 0 resultado registrado (completada, rechazada, parcial, fallida), 4 violación, 5 gate abierto, 3 precondición, 1 error.

### `act`

`agentic.sh act {continue,retry,split,investigate,escalate,skip,stop} [task] [--message M] [--reason R] [--feedback-file F] [--tasks-file F] [--repo R] [--from-message ID]… [--subject S] [--instructions-file F] [--for T] [--gate G] [--detail D] [--actor orchestrator|user] [--plan ID]` — Registra **una** decisión; el script la valida contra el veredicto y los límites. Salvo `stop` e `investigate`, necesita la tarea (si no, exit 2; inexistente, exit 1). Del orquestador (`--actor orchestrator`, por defecto) solo se aceptan las acciones de la tabla 4.4 (si no, exit 3); `--actor user` se salta esa comprobación y la de «misma causa», no el límite de intentos. `--from-message` solo se admite en `retry` e `investigate` (en otra acción, exit 2).

| Opción | Se usa en | Efecto |
|---|---|---|
| `--message M` | `continue` | Mensaje del commit local (en `act`, **`--message` es siempre el commit**; la opción de mensajería se llama `--from-message`). |
| `--reason R` | `retry`, `skip`, `stop`, `escalate` | Motivo para el historial (`escalate` lo usa también como detalle del gate). |
| `--feedback-file F` | `retry` | Fichero de texto que se añade al feedback del worker (primeros 4000 caracteres): breve y concreto, con la salida truncada de la verificación. |
| `--tasks-file F` | `split` | JSON con la lista de tareas nuevas. |
| `--repo R` | `investigate` | Repo de la investigación (con `--from-message`, por defecto el destinatario único). |
| `--from-message ID` | `retry`, `investigate` | Mensaje a entregar (`investigate` admite uno solo). |
| `--subject S` | `investigate` | Asunto de la tarea (≤ 80). |
| `--instructions-file F` | `investigate` | Una instrucción por línea no vacía. |
| `--for T` | `investigate` | La tarea `T` pasa a depender de la nueva. |
| `--gate G` | `escalate` | Motivo del gate (por defecto `decision`; valores de la sección 4.5). |
| `--detail D` | `escalate` | Texto del gate para el usuario. |
| `--actor` | todas | `orchestrator` (por defecto) o `user`. |

**`continue <T>`** — Solo tras `completada` (si no, exit 3). Marca ejecutados los mensajes entregados (una vez por tarea). Si el plan autoriza commits locales y aún no hay commit de la tarea: exige `--message` (si falta, exit 2), comprueba que el repo esté en la rama del plan (3), valida el mensaje según el `commit_format` del componente y el correo del autor (`FAIL|commit|…`, exit 1), añade solo las rutas cambiadas no ignoradas y hace `git commit` (un hook que lo rechaza: exit 1). Sin nada que commitear no falla. Imprime `OK|act|<T> commit <sha> en <rama>`.

**`retry <T>`** — Solo desde `rechazada`, `parcial`, `fallida` o `interrumpida`. Exit 6 si agotó `max_attempts_per_task` o si repite la misma causa que el intento anterior; 3 en otro estado. Si hay `--from-message`, lo valida **antes** de tocar nada. Descarta lo no commiteado (`reset --hard` + `clean -fd` en la rama del plan), añade el feedback y deja la tarea `lista`.

**`split <T> --tasks-file F`** — Solo desde un estado pendiente de decisión o `pendiente`. `F` es una **lista JSON** de tareas con los mismos campos que las de un plan; el repo por defecto es el de `T`, y cada una depende de la anterior (la primera, de lo que dependía `T`). Las tareas que dependían de `T` pasan a depender de la última. `T` queda `omitida`. Cuenta como **cambio de plan** (exit 6 si se agotó `max_plan_changes`) y abre el gate `plan_modificado` (exit 5).

**`investigate --repo R --subject S --instructions-file F [--for T] [--from-message ID]`** — Añade una tarea `investigacion` de perfil `lectura` con un criterio (`C1`: el informe responde con referencias a ficheros). Con `--from-message` el asunto, el repo (si el mensaje va a un solo componente) y las instrucciones salen del mensaje y se copian a la tarea (el usuario las aprueba en el gate); `--repo`, `--subject` e `--instructions-file` los sustituyen. Cuenta como cambio de plan y abre `plan_modificado` (exit 5), salvo que el plan tenga `autoriza.investigate_without_gate` (exit 0). Sin repo, asunto e instrucciones: exit 2.

**`escalate <T> [--detail D] [--gate G]`** — Pasa la decisión al usuario: tarea `esperando_usuario` (si no estaba `bloqueada`) y gate con `reanuda: retry`; opciones «reintentar con tu indicación», «omitir», «detener». Exit 5.

**`skip <T> [--reason R]`** — Pasa a `omitida` (descarta lo no commiteado) desde cualquier estado no final ni en ejecución; si no, exit 3.

**`stop [--reason R]`** — Plan `detenido`. Con un worker vivo, exit 3 (usa `stop --force`).

```bash
agentic.sh act continue T001 --message "feat(api): validate email domain"      # conventional; en ia4d: "feat(api) validate email domain"
agentic.sh act retry T002 --feedback-file /scratch/fb.txt
agentic.sh act retry T002 --feedback-file /scratch/fb.txt --from-message <id-mensaje>
agentic.sh act split T003 --tasks-file /scratch/partes.json
agentic.sh act investigate --repo specs --subject "Revisar el contrato del alta" --instructions-file /scratch/ins.txt --for T004
agentic.sh act escalate T003 --detail "Falta decidir el formato del error"
agentic.sh act skip T005 --reason "ya no hace falta"
agentic.sh act stop --reason "lo cambio por otro plan"
```

### `status`

`agentic.sh status [--plan ID] [--json]` — Estado legible: plan y estado; gasto frente al total, minutos frente al máximo, cambios de plan y tareas que faltan para el checkpoint; tabla de tareas (id, repo, asunto, estado, intentos/máximo, worker) y el gate abierto con su motivo, detalle y `reanuda`. Sin plan actual imprime «Sin plan actual…» con exit 0. `--json`: `plan`, `asunto`, `estado`, `gate`, `gasto_usd`, `total_budget_usd`, `minutos`, `max_duration_min`, `cambios_plan`, `max_plan_changes`, `checkpoint_en`, `worker` y `tareas` (con `commit`).

### `log`

`agentic.sh log <task> [--attempt N] [--tail N] [--plan ID] [--json]` — Qué pasó con una tarea: estado, salida del worker (exit, duración, parada, rama, subtipo, turnos, coste), informe estructurado (truncado), veredicto con acciones, las últimas `--tail` líneas (40 por defecto) del `error.log` y la ruta del prompt enviado. `--attempt N` elige el intento (por defecto el último; sin intentos, «todavía no se ha ejecutado»). Tarea inexistente: exit 1.

### `stop`, `pause`, `resume`

`agentic.sh stop [--force] [--plan ID]` · `agentic.sh pause [--plan ID]` · `agentic.sh resume [--plan ID]`

| Orden | Efecto |
|---|---|
| `stop` / `pause` | **Suave.** Con un worker vivo crea la marca `run/PAUSE`: la tarea termina y, en el siguiente `next`, el plan pasa a `pausado`. Sin worker, un plan `en_ejecucion` pasa a `pausado` al momento. |
| `stop --force` | **Forzosa.** SIGTERM al grupo del worker y SIGKILL tras `ARKANA_AGENTIC_KILL_GRACE` s (10); espera hasta 20 s a que el lanzador cierre (si no, el control deja la tarea en orden); tarea `cancelada`; retira las marcas; plan `detenido`. Sin worker, solo detiene el plan. |
| `resume` | Retira `PAUSE` y `STOP`; un plan `pausado` vuelve a `en_ejecucion` (con otro estado solo retira las marcas). |

Exit 0 (3 si el plan no existe). `launch` se niega mientras haya marcas de parada (exit 7).

### `retry`, `skip` (usuario)

`agentic.sh retry <task> [--from-message ID]… [--plan ID]` · `agentic.sh skip <task> [--plan ID]` — Equivalen a `act retry` y `act skip` con `--actor user`: no aplican la tabla de acciones permitidas ni la regla de «misma causa» (el límite de intentos sí, exit 6). No admiten feedback ni motivo: para eso, `act retry --actor user --feedback-file …`.

### `approve`, `reject`

`agentic.sh approve <gate> [--note N] [--plan ID]` · `agentic.sh reject <gate> [--reason R] [--note N] [--stop] [--plan ID]` — Resuelven el gate abierto (`<gate>` es su id: `G01`…; si no coincide, exit 3). **Son decisiones tuyas**: piden confirmación y el orquestador debe preguntarte antes (un aviso automático no es tu respuesta).

| Orden | Efecto |
|---|---|
| `approve <G> [--note N]` | Según `reanuda` (sección 4.5). `--note` llega al worker como feedback cuando el gate reintenta. Sobre un gate con `reanuda: none`, exit 3. |
| `reject <G>` | Cierra el gate; si la tarea esperaba al usuario, queda `omitida` (descartando lo no commiteado). `--reason R` queda en el registro; `--note` se acepta pero no se usa en `reject`. |
| `reject <G> --stop` | Cierra el gate y deja el plan `detenido`. Es lo único apropiado ante una `violacion`. |

```bash
agentic.sh approve G02 --note "Autorizo, pero solo el campo scripts"
agentic.sh reject G02
agentic.sh reject G03 --stop
```

### `fix`

`agentic.sh fix [--dry-run] [--task T] [--action retry|discard] [--plan ID]` — Dos cosas. (1) **Layout:** si el directorio de ejecución tiene el layout antiguo (`planes/`, `run/`… o una carpeta `orquestacion/archivo`), lo migra a `config/`, `state/` y `data/` con copia `tar.gz` en `.arkana/arkana-workspace/bak/`; se niega (exit 3) con un plan activo o un worker vivo. `--dry-run` solo enseña qué se movería. (2) **Recuperación:** marca `interrumpida` las tareas `en_curso` sin worker vivo, limpia un `worker.json` obsoleto y, por cada una, avisa de su repo, rama y si tiene cambios sin commitear; exit 5 hasta que decidas. `--task T --action retry` descarta lo hecho a medias y deja la tarea `lista`; `--action discard` la deja `cancelada` y descarta los cambios; `--task` sin `--action`, exit 2; una tarea que no está `interrumpida`, exit 3. Nunca reintenta por su cuenta.

```bash
agentic.sh fix --dry-run
agentic.sh fix
agentic.sh fix --task T003 --action retry
```

### `archive`

`agentic.sh archive [--plan ID]` — Copia un plan **terminado** (`completado`, `detenido` o `fallido`; si no, exit 3) a `data/archive/<plan>/`: `plan.json`, `registro.jsonl`, `tareas/`, `informes/` y `verificacion/` (sin logs ni instantáneas). Si el destino ya existe, exit 3. Es local: no se versiona.

### `totals`

`agentic.sh totals [--json]` — Gasto acumulado de **todos los planes** (en curso y archivados) y de **todas las sesiones** que la statusline ha anotado. Solo lectura.

### `costs`

`agentic.sh costs [--plan ID] [--session ID] [--component ALIAS] [--since AAAA-MM-DD] [--by plan|session|component|day] [--purge [--dry-run]] [--json]` — Costes del libro (`data/ledger/`) y de los planes en curso y archivados.

| Opción | Efecto |
|---|---|
| `--plan ID` | Solo ese plan (opción común: filtra, no elige el plan actual). |
| `--session ID` | Solo esa sesión de Claude. |
| `--component ALIAS` | Solo ese componente (sin distinguir mayúsculas). |
| `--since AAAA-MM-DD` | Desde ese día (por la fecha de creación del plan o de fin de la sesión). |
| `--by plan|session|component|day` | Agrupa y suma (workers y sesiones por separado); sin `--by`, lista las primeras 50 filas. |
| `--purge` | Aplica la retención `ledger_retention_days`: purga el detalle y conserva los totales. Con `--dry-run` solo cuenta lo que purgaría. |
| `--dry-run` | Solo con `--purge`. |

Total = workers (`plan-task`, de los informes) + sesiones (coste de la statusline; nunca se estima: «N sesiones sin coste»). Exit 0.

### `integrate`

`agentic.sh integrate {review,merge,keep,discard} [--repo REPO] [--up-to TASK] [--message M] [--plan ID]` — Gestiona las ramas `arkana-worker/<plan>` al terminar. Se niega con un worker vivo (exit 3); si el plan no creó ramas, no hace nada. **No hace push.**

| Acción | Efecto |
|---|---|
| `review` | Por repo: rama, rama original, decisión, commits por tarea, avisos (cambios sin commitear; tareas que dependen de otro repo: integra o descarta esos repos de forma coherente), `diff --stat` y gasto. |
| `merge` | Cambia a la rama original (`develop` por defecto) y hace un merge local `--no-ff` de la rama del plan; si queda completamente integrada, la borra. |
| `keep` | Vuelve a la rama original y deja la rama del plan para revisarla. |
| `discard` | Vuelve a la rama original y borra la rama del plan (descarta también lo no commiteado de la rama del plan). |

| Opción | Efecto |
|---|---|
| `--repo REPO` | Aplica la acción solo a ese repo (debe tener rama del plan; si no, exit 2); permite cambiar una decisión ya tomada. Sin él, se aplica a los repos que aún no tienen decisión. |
| `--up-to TASK` | Solo con `merge` y `--repo` (si no, exit 2): integra hasta el commit de esa tarea (debe ser una tarea de ese repo con commit en la rama, si no exit 2) y **conserva la rama** con el resto. |
| `--message M` | Solo `merge`: mensaje del commit de merge (por defecto `chore(<repo>) merge <rama>[ up to <T>]`, o `chore(<repo>): …` si el componente es `conventional`); se valida como un commit. |

Errores: repo con cambios sin commitear fuera de la rama del plan, o dentro de ella con el plan sin commits locales (exit 3; con `discard` sobre la rama del plan se descartan); mensaje inválido o merge con conflicto (exit 1: el merge se aborta y se vuelve a la rama del plan); `merge` sin commits nuevos borra la rama y lo anota. La decisión por repo queda en el plan. `merge` y `discard` piden confirmación.

```bash
agentic.sh integrate review
agentic.sh integrate merge --repo api
agentic.sh integrate merge --repo app-ui --up-to T002
agentic.sh integrate keep --repo docs
agentic.sh integrate discard --repo specs
```

### `policy`

`agentic.sh policy show [--json]` · `agentic.sh policy set <clave> <valor> [--ceiling]` — **`show`** muestra una fila por clave: valor, nivel (`por defecto` o `local`), valor por defecto y techo. **`set`** guarda el valor en `.arkana/arkana-agentic/config/politica.json` (el valor es un número ≥ 0; la clave debe existir, ver 4.6): sin `--ceiling` fija el **límite** y se rechaza si supera el techo (exit 6); con `--ceiling` fija el **techo** (sin comprobación). Clave desconocida, valor no numérico o negativo, o falta de clave y valor: exit 2. `set` pide confirmación.

```bash
agentic.sh policy show
agentic.sh policy set total_budget_usd 8
agentic.sh policy set total_budget_usd 40 --ceiling
```

### `install`

`agentic.sh install [--dry-run] [--no-settings]` — Ver el skill `install`. Imprime `ESTADO|install:<id>|detalle` para `carpetas`, `bloque`, `referencia` y `plugin`. `--dry-run` no cambia nada (`DRY`); `--no-settings` omite la habilitación del plugin en `~/.claude/settings.json`. Exit 1 si hay algún `FAIL` (no existe la carpeta de ARKANA); un `CLAUDE.md` ausente es un `WARN`.

### `check`

`agentic.sh check [--quick] [--deep] [--need-network] [--json]` — Salud del entorno; **solo lectura, sin coste** (salvo `--deep`). Una línea por comprobación y `RESUMEN|n FAIL|n WARN`; con `--json`, una lista de `{estado, id, detalle}`. Exit 1 si hay algún `FAIL`; 0 en otro caso (los `WARN` no cuentan).

| Opción | Efecto |
|---|---|
| `--quick` | El modo por defecto (sin coste); se acepta por simetría. |
| `--deep` | Añade la batería de contención con `claude` real (`tests/containment/run-containment.sh -q`): **cuesta dinero** (el script la estima en 0,3–0,6 USD con haiku; tope de seguridad 2 USD) y tarda unos minutos. Comprobación `contencion`; un fallo es `FAIL`. Hasta 30 minutos de tiempo máximo. |
| `--need-network` | `red-vpn` sin DNS de los remotos pasa de `WARN` a `FAIL`. |

| ID | Qué comprueba | Si no está OK |
|---|---|---|
| `claude-version` | `claude` ≥ 2.1.259 (`ARKANA_AGENTIC_CLAUDE_BIN` o el del `PATH`) | `FAIL`: actualiza Claude Code. **No se orquesta.** |
| `claude-flags` | `claude --help` ofrece `--restricted`, `--tools`, `--json-schema`, `--permission-prompts`, `--max-budget-usd`, `--no-session-persistence`, `--settings` | `FAIL`: sin ellos no se garantiza la contención. |
| `utilidades` | `timeout`, `setsid`, `flock`, `python3`, `jq`, `git`, `sha256sum` | `FAIL`: instala lo que falte. |
| `metadatos-ubicacion` | Dónde está `.arkana` (informativo) | — |
| `layout` | Layout `config/state/data` | `WARN`: `/arkana-agentic:fix` migra. |
| `runtime-700` | Modo 700 del directorio de ejecución | `WARN`: `chmod 700`. |
| `politica-valida` | Política por defecto válida y ningún límite por encima de su techo | `FAIL`: `policy show`. |
| `worker-huerfano` | Sin worker vivo ni `worker.json` obsoleto | `WARN`: `fix`. |
| `permisos-arkana` | En `.claude/settings.local.json`: `agentic.sh` en `allow`, `claude -p` en `deny` y `ask` en `plan approve`, `approve`, `reject`, `policy set`, `integrate merge`, `integrate discard` | `WARN`: `/arkana-workspace:fix`. |
| `red-vpn` | DNS de los hosts de los remotos del manifiesto (si hay) | **`WARN`** (el trabajo y el commit son locales; `launch` avisa y sigue); `FAIL` con `--need-network`. |
| `adaptadores` | Para los tipos del workspace, cada herramienta requerida está en el `PATH` del verificador (carpetas `bin` de `tools.json` con ruta + `/usr/local/bin:/usr/bin:/bin`) | `WARN` con el nombre de lo que falta y cómo declararlo: `/arkana-workspace:config tools --tool <nombre> --version <v> --path <ruta>`. |
| `instrucciones` | Bloque `arkana:agentic` al día en el `CLAUDE.md` de ARKANA | `WARN`: `/arkana-agentic:install`. |
| `contencion` | Solo con `--deep` | `FAIL`: **no orquestes** hasta resolverlo. |

---

## 7. Variables de entorno

Las que **lee** el plugin (comprobadas en el código):

| Variable | Dónde | Para qué |
|---|---|---|
| `ARKANA_HOME` | `paths.py`, hooks | Carpeta del repo de Arkana (`arkana`, o `shared`, nombre heredado); si falta, se prueba `ARKANA_SHARED`, el ancestro del plugin y la raíz git del directorio actual. |
| `ARKANA_SHARED` | `paths.py` | Alternativa a `ARKANA_HOME`. |
| `ARKANA_PLUGINS_DIR` | `paths.py` | Carpeta de metadatos (por defecto `<arkana>/.arkana`). |
| `ARKANA_AGENTIC_DIR` | `state.py` | Directorio de ejecución (por defecto `<.arkana>/arkana-agentic`). |
| `ARKANA_AGENTIC_CLAUDE_BIN` | `launch.py`, `doctor.py` | Binario de `claude` (las pruebas usan uno falso). |
| `ARKANA_AGENTIC_MODEL` | `launch.py` | Modelo de los workers (`--model`). |
| `ARKANA_AGENTIC_EFFORT` | `launch.py` | Esfuerzo de los workers (`--effort`). |
| `ARKANA_AGENTIC_OWNER_PID` | `launch.py` | Pid de la sesión dueña que debe seguir viva; `none` desactiva el dead-man switch (por defecto se detecta). |
| `ARKANA_AGENTIC_WATCH_INTERVAL` | `watchdog.py` | Segundos entre comprobaciones del vigilante (5). Para pruebas. |
| `ARKANA_AGENTIC_KILL_GRACE` | `launch.py`, `watchdog.py` | Segundos entre SIGTERM y SIGKILL (10). |
| `ARKANA_AGENTIC_RULES_FILE` | `launch.py` | Sustituye las reglas del worker; **solo** para la pasada adversaria de la batería de contención. |
| `ARKANA_MESSAGING_CMD` | `inbox.py` | Comando que sustituye a `messaging.sh` (pruebas). |
| `ARKANA_SKIP_NET_PREFLIGHT` | `repos.py` | Con `1`, no hay hosts que comprobar (sin preflight de red). |
| `CLAUDE_CODE_SESSION_ID` | `state.py`, `ledger.py` | Sesión que gobierna el plan y sesión del libro. |
| `ARKANA_CONTAINMENT_MODEL`, `ARKANA_CONTAINMENT_MODEL_CARO`, `ARKANA_CONTAINMENT_MAX_USD` | `tests/containment` | Modelo (haiku por defecto), modelo caro (sonnet) y tope de seguridad (2,0 USD) de la batería. |

La que **establece** el plugin: `ARKANA_WORKER=1` en el entorno del worker (los hooks no hacen nada con ella). `CLAUDE_PLUGIN_ROOT` la pone Claude Code.

## 8. Instalación y requisitos

```bash
claude plugin marketplace add <ruta>/plugins
claude plugin install arkana-agentic@arkana
```

Después, en `arkana` y en este orden: `/arkana-agentic:install` (carpetas y bloque `arkana:agentic`; recarga los plugins), `/arkana-workspace:fix` (reglas de permisos del orquestador), `/arkana-agentic:check` y, para ver el plan en la barra, `/arkana-statusline:install`. Antes, el workspace debe tener su manifiesto (`/arkana-workspace:install`, `component add`) y las herramientas declaradas (`/arkana-workspace:config tools`).

Requiere `claude` ≥ 2.1.259 con los flags `--restricted`, `--tools`, `--json-schema`, `--permission-prompts`, `--max-budget-usd`, `--no-session-persistence` y `--settings`; `timeout`, `setsid`, `flock`, `python3`, `jq`, `git` y `sha256sum`; y la rama `develop` local en cada repo que vaya a recibir tareas de edición.

## 9. Pruebas

Sin red ni API (usan un `claude` falso inyectable con `ARKANA_AGENTIC_CLAUDE_BIN`) y sin tocar `~/.claude`:

```bash
bash tests/run-unit.sh                         # máquina de estados, esquemas, adaptadores, comandos y rutas, commits, mensajes, libro, layout
bash tests/run-e2e.sh                          # lanzador, verificador, parada, recuperación, control, mensajes y un flujo completo (~3 min)
bash tests/containment/run-containment.sh      # CON claude real: cuesta dinero; también con  agentic.sh check --deep
```

La batería de **contención** lanza workers reales con tareas adversarias (leer o escribir fuera del repo, `.env`, rutas protegidas, `git`, inyección, límites) y comprueba el **efecto**; una segunda pasada con reglas neutras mide la contención estructural con independencia de la obediencia del modelo. Usa el `HOME` real (el login lo necesita) y solo canarios de prueba. Coste: ver `ARKANA_CONTAINMENT_MODEL` y `ARKANA_CONTAINMENT_MAX_USD`; el script lo estima en 0,3–0,6 USD con haiku. Resultados y alcance en `docs/VERIFICACION.md`; repítela al cambiar de versión de `claude` o de modelo. Desde la raíz del repo de Arkana, `bash scripts/run-all-tests.sh [--quick] [--only <texto>]` ejecuta el núcleo y los seis plugins.

## 10. Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Plano de control | `scripts/agentic.sh` → `scripts/lib/control.py` (`build_parser` y los `cmd_*`) |
| Lanzador, vigilante y verificador | `scripts/lib/launch.py`, `watchdog.py`, `verify.py`, `snapshot.py` (envoltorios `launch-worker.sh`, `verify-task.sh`, `snapshot.sh`, `watchdog.sh`) |
| Estado, transiciones y límites | `scripts/lib/state.py`, `validate.py`, `matchers.py` |
| Repos, adaptadores y commits | `scripts/lib/repos.py`, `adapters.py`, `commitmsg.py` |
| Salud, instalación y migración | `scripts/lib/doctor.py`, `install.py`, `migrate.py` |
| Mensajes y libro | `scripts/lib/inbox.py`, `ledger.py` (hooks en `hooks/hooks.json`) |
| Código común del workspace | `scripts/_core/` (copia vendorizada de `lib/arkana_core/`; se regenera con `bash scripts/vendor-core.sh` desde la raíz de Arkana) |
| Política por defecto y techos | `policy/politica.default.json` |
| Lista cerrada de comandos y rutas protegidas | `policy/adapters/{common,node,maven,docs,generic}.json` |
| Esquemas de plan, tarea, informe y política | `schemas/` |
| Reglas del orquestador, reglas y prompt del worker | `templates/orquestador.md`, `worker-rules.md`, `worker-prompt.md.tpl` |
| Skills y contrato del plugin | `skills/<skill>/SKILL.md`, `arkana-plugin.json` |
| Documentación | `docs/GUIA.md`, `ESPECIFICACION.md`, `VERIFICACION.md`, `PILOTO.md` (y los planes de referencia del piloto) |

Estado de ejecución, dentro de `arkana` y **ignorado por git** (modo 700), en `<arkana>/.arkana/arkana-agentic/`:

```
config/                  politica.json y comandos-permitidos.json locales (portables: se exportan)
state/                   estado local de ejecución
  actual                   id del plan actual
  planes/<plan>/           plan.json · plan.aprobado.sha256 · registro.jsonl
                           tareas/ · informes/ · verificacion/ · logs/ · snapshots/
  run/                     worker.json · killed.json · PAUSE · STOP · STOP-FORCE · linea.json (lo lee la statusline)
  sesiones/                coste visto por la statusline antigua
data/                    datos del usuario (se exportan con --include-data)
  ledger/{plans,sessions}/ libro de planes y sesiones
  archive/<plan>/          planes archivados
bak/                     copias de lo que install modifica (fix guarda su copia tar.gz en .arkana/arkana-workspace/bak/)
```

Aviso: si una herramienta de sincronización de ficheros replica la carpeta de ARKANA sin ignores, también copiará esta; el estado se reescribe a menudo y puede dar conflictos entre los dos lados.
