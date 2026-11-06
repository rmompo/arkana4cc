# arkana-messaging

Mensajería **entre ARKANA y los componentes del proyecto** de un workspace de Arkana (el workspace es ARKANA más el proyecto; el proyecto son sus componentes, cada uno un repositorio). Permite que un componente (`app`, `api`, `docs`…) o ARKANA deje a otro un **aviso**, una **tarea**, una **revisión**, una **pregunta** o una **directriz permanente**, y que el destinatario lo vea al abrir su sesión de Claude Code, lo atienda y lo cierre dejando constancia.

Todo es **local y sin red**: un fichero JSON por mensaje en `.arkana/arkana-messaging/state/messages/` y un índice pequeño en `state/index.json`. No usa git ni servidor. Entre desarrolladores los mensajes solo viajan con `/arkana-workspace:export` e `import` (la carpeta de mensajes es de clase `data`).

Visión de conjunto de los seis plugins de Arkana: [`../README.md`](../README.md).

Instalación: `/plugin install arkana-messaging --marketplace <owner>/<repo>` (o `claude plugin marketplace add <ruta>/plugins` y después `claude plugin install arkana-messaging@arkana`).

## Índice

1. [Para qué sirve](#para-qué-sirve)
2. [Cómo se complementa con los otros plugins](#cómo-se-complementa-con-los-otros-plugins)
3. [Modelo de datos](#modelo-de-datos)
4. [Salida y códigos de salida](#salida-y-códigos-de-salida)
5. [Referencia de skills](#referencia-de-skills): [`put`](#put), [`get`](#get), [`query`](#query), [`delete`](#delete), [`sync`](#sync), [`install`](#install), [`check`](#check), [`fix`](#fix)
6. [Hooks](#hooks)
7. [Semilla `arkana:messaging`](#semilla-arkanamessaging)
8. [Reconciliación](#reconciliación)
9. [Variables de entorno, pruebas y desarrollo](#variables-de-entorno-pruebas-y-desarrollo)

---

## Para qué sirve

| Necesidad | Tipo de mensaje |
|---|---|
| Informar de algo sin esperar respuesta («`api` ya expone el campo nuevo») | `notice` (aviso) |
| Pedir que otro componente haga algo, con instrucciones y criterios de aceptación | `task` (tarea) |
| Pedir que otro componente revise algo | `review` (revisión) |
| Preguntar y quedarse con la respuesta | `question` (pregunta) |
| Fijar una norma que cada componente debe tener en cuenta **siempre** (convención, restricción) | cualquiera de los anteriores con `--repeat` (**directriz**) |

El ciclo habitual: un componente publica con `put`; el destinatario, al abrir la sesión, recibe el mensaje **inyectado** en su contexto (hook `SessionStart`) o en su siguiente prompt (`UserPromptSubmit`); el modelo **propone** al usuario atenderlo; al terminar se cierra con `put --done <id> --result "..."`. El usuario ve una línea resumen `[ARKANA messaging] …` con lo recibido y el estado de las tareas.

Reglas de oro: **nunca** se cierra ni se guarda nada sin confirmación del usuario, y **nunca** se incluyen credenciales ni datos personales en un mensaje.

## Cómo se complementa con los otros plugins

| Plugin | Relación con `arkana-messaging` |
|---|---|
| [`arkana-workspace`](../arkana-workspace/README.md) | **Dependencia obligatoria** (`arkana-plugin.json` → `requires`). Su manifiesto (`core/workspace.json`) dice quién es cada componente, dónde está y cuál es su carpeta: de ahí sale el **actor** de cada comando y la lista de destinatarios válidos (`all` = los componentes del manifiesto). Su hook `SessionStart` (resumen `BRIEF`) lee `state/index.json` y `state/read/<actor>.json` para contar los mensajes sin leer por componente. Su `/arkana-workspace:check` comprueba que la semilla está al día, y `export`/`import` mueven la carpeta de mensajes entre máquinas. |
| [`arkana-agentic`](../arkana-agentic/README.md) | Orquestación multi-repo con workers sin shell. Un worker no ve la mensajería: al lanzarlo (`launch`) el orquestador copia en su prompt, **como datos y no como instrucciones**, los `repeat` **vigentes** de su componente y los `once` **accionables** (`task`, `review`, `question` abiertas que el componente no ha confirmado ni ejecutado ya). No entrega avisos `once`, directrices `propuesto`, borrados ni reconciliados. La lista se congela en `plan start` (lo que el usuario aprobó). Anota la entrega con `put --delivered` y, al **aceptar** la tarea (`act continue`), la ejecución con `put --executed` (ambos solo ARKANA). `--from-message <id>` (en `launch`, `act retry`, `act investigate` y `plan new`) indica un mensaje concreto a una tarea aunque no le llegara solo (p. ej. un `notice`); debe ir dirigido al componente de la tarea y no estar borrado ni reconciliado. |
| [`arkana-statusline`](../arkana-statusline/README.md) | Sin relación directa: no lee ni escribe mensajes. |
| [`arkana-knowledge`](../arkana-knowledge/README.md) | Sin relación directa. Se reparten el terreno: la mensajería es **efímera y dirigida** (alguien debe hacer o saber algo ahora); el conocimiento es **duradero y común** (lo que todos deben saber siempre, versionado en git). Una directriz `repeat` es la forma ligera de lo primero que no merece una nota de conocimiento. |

## Modelo de datos

### Esquema de un mensaje (`schema_version: 2`)

Fichero `state/messages/<id>.json`:

| Campo | Contenido |
|---|---|
| `id` | `N<aammdd>-<HHMM>-<4 caracteres [a-z0-9]>` (UTC), p. ej. `N261104-1530-k3x9`. Coincide con el nombre del fichero |
| `tipo` | `notice` \| `task` \| `review` \| `question` |
| `asunto` | De 3 a 80 caracteres, una sola línea |
| `de` | Remitente: alias del componente o `arkana` |
| `para` | Lo **escrito** en `--to`: `["all"]`, o lista de alias ordenada |
| `destinatarios` | Los destinatarios **reales** en el momento de crearlo (con `all`: todos los alias del manifiesto salvo el remitente) |
| `prioridad` | `normal` (por defecto) \| `high` |
| `repeticion` | `once` (por defecto) \| `repeat` |
| `vigencia` | Solo en un `repeat`: `vigente` \| `propuesto` |
| `estado` | `open` \| `done` \| `discarded` \| `deleted` \| `reconciled`. Un `notice` **no tiene** estado (salvo `deleted`/`reconciled`) |
| `cuerpo`, `instrucciones`, `criterios` | Texto libre; las dos últimas son listas (una línea del fichero = un elemento) |
| `refs`, `commits` | Listas: ids de otros mensajes relacionados y hashes de commit (informativo) |
| `autor` | Usuario que lo escribió: parte local de `git config user.email`, o `$USER`, o `anon` |
| `fecha`, `updated` | ISO 8601 UTC (`2026-11-04T15:30:00Z`): creación y última modificación |
| `rama` | Rama git actual del remitente en ese momento (`desconocida` si no hay) |
| `confirmaciones` | `{alias: {estado: done\|discarded, resultado\|motivo, fecha, autor}}`: cierre **por destinatario** |
| `resultado` / `motivo_descarte` | Texto con el que se cerró el mensaje cuando confirmaron todos |
| `entregas` | `{alias: {n, primera, ultima, plan, tarea}}`: veces que `arkana-agentic` lo entregó a un worker de `alias` |
| `ejecuciones` | Igual que `entregas`, pero al **aceptar** la tarea (en un `repeat`: «al menos una vez») |
| `historial` | Lista de `{fecha, autor, accion, nota}`. Acciones: `created`, `done`, `discarded`, `comment`, `activate`, `repeticion`, `delivered`, `executed`, `deleted`, `reconciled` |
| `origins` | En un resumen de reconciliación: ids de los mensajes que sustituye |
| `reconciled_into` | En un original reconciliado: id del resumen que lo sustituyó |
| `estado_previo` | Estado que tenía antes de `delete` |

Un `task` exige `instrucciones` y `criterios`; una `review`, `cuerpo` o `instrucciones`; una `question`, `cuerpo` o un asunto de al menos 10 caracteres que la formule. El remitente nunca es destinatario de su propio mensaje.

### Tipos y clases

| Tipo | Para qué | Estado | Exige |
|---|---|---|---|
| `notice` | Informar | ninguno | — |
| `task` | Pedir una acción | `open` → `done` \| `discarded` | `--instructions-file` y `--criteria-file` |
| `review` | Pedir una revisión | igual | `--body-file` o `--instructions-file` |
| `question` | Preguntar | igual; se cierra con la respuesta | cuerpo, o asunto que la formule |

| Clase | Significado |
|---|---|
| `once` (por defecto) | Se atiende y se cierra. La confirmación es **por destinatario**; `estado` pasa a `done`/`discarded` cuando **todos** los destinatarios han confirmado (`done` si al menos uno lo hizo, `discarded` si todos descartaron) |
| `repeat` (`--repeat`) | **Directriz permanente**: no se cierra con `done`/`discard`. Se da de baja con `delete` (solo remitente o ARKANA). Si la crea ARKANA nace `vigente`; si la crea otro componente nace `propuesto` y no se entrega ni se cuenta como sin leer hasta que ARKANA la active (`put --activate`). Con `--to all` el alcance es **vivo**: la heredan los componentes que se den de alta después. No se reconcilia |

### Almacén (`.arkana/arkana-messaging/`)

| Ruta | Clase | Contenido |
|---|---|---|
| `state/messages/<id>.json` | `data` (viaja en export/import) | Un JSON por mensaje |
| `state/index.json` | local | Índice derivado (`schema_version`, `generated`, `messages{id → asunto, tipo, de, para, destinatarios, estado, prioridad, fecha, updated, repeticion, vigencia, confirmaciones, ejecutados}`); se reconstruye con `sync` y tras cada escritura. Los hooks lo leen en vez de los mensajes |
| `state/read/<actor>.json` | local | `{schema_version, ids{id → fecha en que se leyó}}`: mensajes leídos por cada componente |
| `state/sessions/<session_id>.json` | local | Latido de los hooks por sesión: `ts`, `event`, `actor`, `seen`, `sig`, `reminded`. Se purgan a los 14 días |
| `state/.lock` | local | Cerrojo entre procesos |
| `bak/` | local | Copias `.bak` de lo que modifica `install`/`fix` (`settings.json.<fecha>` y `<alias>/…`) |

**Cerrojo.** Toda mutación (`put`, `delete`, `sync`, `reconcile apply`, `adopt` y el marcado de leídos) toma `flock` exclusivo sobre `state/.lock`: varias sesiones publicando o cerrando a la vez no se pisan. Las escrituras son atómicas (fichero temporal + renombrado). El borrado es **lógico**: el fichero se conserva con `estado: deleted`, de modo que la marca viaja en export/import (la marca de borrado gana siempre).

### Quién actúa y qué ve cada uno

El **actor** lo decide el directorio de trabajo y el manifiesto: el componente cuya carpeta contiene el `cwd` (el más específico si están anidados) o ARKANA. **No existen `--repo` ni `--from`.** Si no hay workspace, o el `cwd` no es de ningún componente, los comandos terminan con código 3.

| Actor | Ve | Publica como | Cierra / comenta | Borra | Activa un `repeat`, anota entregas/ejecuciones |
|---|---|---|---|---|---|
| Componente | Lo dirigido a él (`destinatarios`, o `all` en un `repeat`) y lo escrito por él | él mismo | Lo que le llega a él; como remitente puede cerrar **por** un destinatario con `--for` | Solo lo que escribió | No |
| ARKANA | Todo | `arkana` | Cualquier mensaje, con `--for` | Cualquier mensaje | Sí (único actor) |

Los `deleted` y `reconciled` no se muestran salvo `--state <estado>` o `--include-hidden`, y no admiten cambios.

### Qué significa «leído»

Un mensaje está **leído para un actor** cuando consta en `state/read/<actor>.json`. Se marca solo en dos casos:

1. un hook lo **inyectó completo** en el contexto del modelo (SessionStart o UserPromptSubmit);
2. se recuperó con **`get --detail <id>`**.

`query` **nunca** marca leído (ni con `--detail`). Marcar como leído no es cerrar: la tarea sigue `open` hasta que el destinatario la cierra con `put --done`/`--discard`. «Sin leer» para un actor = mensajes visibles, no leídos, escritos por otro, que le tienen como destinatario, no `deleted`/`reconciled` y no `repeat propuesto`.

## Salida y códigos de salida

Todos los subcomandos (salvo `get` y `query`, que imprimen tabla o JSON propios) emiten una línea `ESTADO|ID|detalle` por resultado (`OK`, `WARN`, `FAIL`, `INFO`, `DRY`) y al final `RESUMEN|n FAIL|n WARN`; con `--json`, un objeto `{plugin, skill, status, items[{id,status,detail,component}], summary{fail,warn,ok,info,dry}}`.

| Código | Significado |
|---|---|
| `0` | Sin fallos (los `WARN` no cuentan) |
| `1` | Fallo (mensaje inexistente o no visible, permiso denegado, acción no válida para ese mensaje, error de ficheros) |
| `2` | Uso incorrecto (opción desconocida o inválida, falta un argumento obligatorio, mensaje que no pasa la validación, destinatario desconocido) |
| `3` | Precondición no cumplida: no hay workspace, el `cwd` no pertenece a ningún componente, o no existe la carpeta de origen de `adopt` |

## Referencia de skills

Herramienta común: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" <subcomando> [opciones]`. Los subcomandos `install`, `check` y `fix` los atiende `scripts/lib/ops.py`; el resto, `scripts/lib/messages.py`. Hay 8 skills (`skills/*/SKILL.md`); además `messaging.sh` expone los subcomandos `reconcile` y `adopt`, que se usan a través de `put` y `sync` (ver [Reconciliación](#reconciliación)).

| Skill | Escribe | Lee | Pide confirmación al usuario |
|---|---|---|---|
| `put` | mensajes, índice | manifiesto, almacén | Sí (guardar, cerrar, comentar) |
| `get` | `read/<actor>.json` solo con `--detail <id>` | almacén | No |
| `query` | **nada** | almacén, `read/<actor>.json` | No |
| `delete` | mensaje (marca `deleted`), índice | almacén | Sí |
| `sync` | índice; con `reconcile apply`, mensajes | almacén | Sí, para reconciliar |
| `install` | almacén, `~/.claude/settings.json`, semillas | manifiesto | Sí |
| `check` | nada | almacén, settings, latidos, semillas | No |
| `fix` | igual que `install`, solo lo que `check` marca | igual | Sí |

---

### `put`

**Para qué sirve.** Es el único skill que **crea** mensajes y el que **cambia su estado**: guarda un `notice`/`task`/`review`/`question`, lo cierra (`--done`, `--discard`), lo comenta (`--comment`), activa una directriz (`--activate`), cambia su clase (`--set-repeticion`) y, solo para ARKANA, anota entregas y ejecuciones a workers (`--delivered`, `--executed`).

**Cuándo usarlo.** Cuando el usuario pide dejar un mensaje a otro componente, o al terminar una tarea, revisión o pregunta recibidas. No lo uses a mano para `--delivered`/`--executed`: las anota `arkana-agentic`.

**Orden.** `put <opciones>` con **dos modos excluyentes**:

- **Crear**: sin ninguna de las opciones de cambio de estado; exige `--type` y `--subject`.
- **Cambiar un mensaje existente**: exactamente **una** de `--done`, `--discard`, `--comment`, `--activate`, `--set-repeticion`, `--delivered`, `--executed`. Si hay más de una, error (código 2). En este modo se ignoran las opciones de creación.

#### Opciones al crear

| Opción | Valores | Por defecto | Efecto y restricciones |
|---|---|---|---|
| `--type` | `notice`, `task`, `review`, `question` | — (obligatoria) | Tipo. Otro valor: error de uso (2) |
| `--subject` | texto | — (obligatoria) | Asunto: 3 a 80 caracteres, una sola línea (se recortan los espacios de los extremos) |
| `--to` | lista de alias separados por coma o espacio, `arkana` o `all` | `all` | `all` = todos los demás componentes **incluida ARKANA**, y se conserva como `all` en `para`. Si se mezcla `all` con alias, gana `all`. El propio remitente se descarta de la lista; si no queda nadie, error. Alias desconocido: error con la lista de componentes |
| `--priority` | `normal`, `high` | `normal` | `high` solo si es urgente: además de resaltarse, hace que el hook `Stop` pueda bloquear (ver [Hooks](#hooks)) |
| `--body-file` | ruta | — | Contenido de `cuerpo` (texto íntegro, recortado). El fichero debe existir (si no, error 2) |
| `--instructions-file` | ruta | — | `instrucciones`: **una por línea** (se ignoran las líneas vacías). Obligatorio en `task` |
| `--criteria-file` | ruta | — | `criterios`: **uno por línea**. Obligatorio en `task` |
| `--refs` | `"ID ID …"` | — | Ids de mensajes relacionados, separados por espacios; cada uno debe tener formato de id válido |
| `--commits` | `"SHA SHA …"` | — | Hashes relacionados, separados por espacios (informativo) |
| `--repeat` | indicador | desactivado | Crea una **directriz** (`repeticion: repeat`). `vigente` si el remitente es ARKANA; `propuesto` si no |
| `--dry-run` | indicador | desactivado | Ejecuta **las mismas validaciones que la ejecución real** (ficheros, destinatarios, formato, reglas por tipo, generación de id) y solo se salta la escritura. Salida `DRY|put|se guardaría <id> (…)` |
| `--json` | indicador | desactivado | Salida JSON (ver [Salida](#salida-y-códigos-de-salida)) |

Para evitar que los textos pasen por la línea de comandos, el cuerpo, las instrucciones y los criterios se dejan en ficheros del scratchpad de la sesión.

#### Opciones para cambiar un mensaje

| Opción | Requiere | Quién | Efecto y errores |
|---|---|---|---|
| `--done <id>` | `--result "<texto>"` | Destinatario; el remitente o ARKANA pueden hacerlo por otro con `--for` | Registra en `confirmaciones[alias]` el cierre con su resultado. Cuando todos los destinatarios han confirmado, `estado` pasa a `done`. Idempotente: repetirlo responde «ya estaba». Errores: `notice` (no tiene estado), `repeat` (no se cierra), ya confirmado con otro estado, varios destinatarios sin `--for`, el alias de `--for` no es destinatario, o no tienes permiso para confirmar por otro |
| `--discard <id>` | `--reason "<texto>"` | Igual que `--done` | Igual, con estado `discarded` y `motivo`. Si todos confirman y ninguno hizo `done`, `estado` = `discarded` |
| `--comment <id>` | `--note "<texto>"` | Cualquiera que vea el mensaje | Añade una entrada `comment` al historial sin cambiar el estado. Vale también en un `notice` y en un `repeat` |
| `--activate <id>` | — | **Solo ARKANA** | Pasa un `repeat` de `propuesto` a `vigente`. Si no es `repeat`: error; si ya era vigente: «ya estaba vigente». Requiere confirmación del usuario |
| `--set-repeticion <id> <once\|repeat>` | — (dos valores) | ARKANA o el remitente | Cambia la clase. A `repeat` nace `vigente` (ARKANA) o `propuesto` (otro); no se puede pasar a `repeat` un mensaje ya `done`/`discarded`. A `once` se elimina `vigencia`. Si ya era de esa clase: «ya era …» |
| `--delivered <id>` | `--for <alias>` | **Solo ARKANA** | Incrementa `entregas[alias].n` y guarda `ultima`, `plan` y `tarea`. `alias` debe ser destinatario real (en un `repeat` a `all`, cualquier componente salvo el remitente) |
| `--executed <id>` | `--for <alias>` | **Solo ARKANA** | Igual sobre `ejecuciones` (en un `repeat`: «al menos una vez») |

Opciones auxiliares de este modo:

| Opción | Efecto |
|---|---|
| `--result "<texto>"` | Resultado o respuesta; obligatoria con `--done` |
| `--reason "<texto>"` | Motivo; obligatoria con `--discard` |
| `--note "<texto>"` | Texto del comentario; obligatoria con `--comment` |
| `--for <alias>` | Destinatario concreto: obligatorio con `--delivered`/`--executed`; con `--done`/`--discard` es necesario si hay varios destinatarios y quien actúa no es uno de ellos |
| `--plan <P>`, `--task <T>` | Identificadores del plan y la tarea de `arkana-agentic`, anotados en `entregas`/`ejecuciones`. Sin efecto en otras acciones |

Restricciones comunes: el id debe tener formato válido (error 2); el mensaje debe existir y ser visible para el actor (error 1: «no existe la comunicación»); un mensaje `deleted`/`reconciled` no admite cambios. Con `--dry-run` se recorren todas las comprobaciones sobre una copia en memoria y solo se omite `store.save`: salida `DRY|put|<id>: se registraría «<acción>» (…)`.

**Salida.**

```text
OK|put|N261104-1530-k3x9 guardada (task, app→api): Exponer el campo estado
INFO|reconcile|2 mensajes abiertos para api: evalúa si se solapan (reconcile candidates --to api)
RESUMEN|0 FAIL|0 WARN
```

Un `repeat` añade « repeat» (o « repeat propuesto: ARKANA debe activarlo (put --activate)») tras el tipo. La línea `INFO|reconcile` aparece cuando, tras guardar, hay **dos o más** mensajes abiertos (no `repeat`) con el mismo conjunto de destinatarios visibles para el actor.

**Pasos recomendados.** (1) Fijar destinatarios (`AskUserQuestion` si no es evidente). (2) Redactar el borrador a partir de lo hecho, sin inventar. (3) Enseñarlo y pedir confirmación («Guardar», «Editar», «Cancelar»); se puede ensayar con `--dry-run`. (4) Ejecutar. (5) Si sale `INFO|reconcile`, valorar la [reconciliación](#reconciliación) **solo con confirmación del usuario**.

**Ejemplos.**

```bash
# aviso a todos
put --type notice --subject "api ya expone el campo estado" --to all

# tarea a dos componentes, con ficheros del scratchpad
put --type task --subject "Mostrar el campo estado en la ficha" --to app-web,app-ui \
    --instructions-file "$SCRATCH/instr.txt" --criteria-file "$SCRATCH/crit.txt" --priority high

# directriz permanente de ARKANA (nace vigente)
put --type notice --subject "Los textos de la interfaz van en español" --to all --repeat \
    --body-file "$SCRATCH/norma.txt"

# cerrar, descartar, comentar
put --done N261104-1530-k3x9 --result "Hecho en la rama de trabajo; criterios cumplidos"
put --discard N261104-1530-k3x9 --reason "Ya cubierto por otra tarea" --for app-ui
put --comment N261104-1530-k3x9 --note "Falta confirmar el formato de la fecha"

# solo ARKANA
put --activate N261104-1600-ab12
put --set-repeticion N261104-1600-ab12 once
put --delivered N261104-1530-k3x9 --for app-web --plan P2611040815-abcd --task T001
put --executed  N261104-1530-k3x9 --for app-web --plan P2611040815-abcd --task T001

# ensayo
put --type question --subject "¿Qué formato de fecha usa la API?" --to api --dry-run
```

---

### `get`

**Para qué sirve.** Lista o detalla los mensajes del actor, con filtros. Es el skill para **consumir** un mensaje: `get --detail <id>` lo muestra entero y lo marca como leído.

**Cuándo usarlo.** Al abrir una sesión en un componente: `get --pending` y, si hay algo, **proponer** al usuario atenderlo. Para leer un mensaje concreto. Para ver el historial completo (`--detail`).

**Orden.** `get [filtros]`. Lee del almacén local; solo escribe `state/read/<actor>.json` cuando se usa `--detail <id>`. No usa git ni red.

| Opción | Valores | Por defecto | Efecto |
|---|---|---|---|
| `--pending` | indicador | — | Solo `task`/`review`/`question` de clase `once`, `open`, **dirigidos a ti** y que **no has confirmado**. Las directrices `repeat` y los `notice` no cuentan |
| `--repeat` | indicador | — | Solo directrices permanentes (`propuesto` o `vigente`) |
| `--id <id>` | id | — | Filtro exacto |
| `--type <t>` | `notice`, `task`, `review`, `question` | — | Filtro exacto |
| `--state <e>` | `open`, `done`, `discarded`, `deleted`, `reconciled` | — | Filtro exacto; con `deleted` o `reconciled` muestra esos ocultos |
| `--to <alias>` | alias | — | Mensajes cuyo destinatario es ese componente (un `repeat` a `all` cuenta para todos salvo el remitente) |
| `--from <alias>` | alias | — | Remitente |
| `--user <u>` | texto | — | Usuario autor (`autor`) |
| `--since AAAA-MM-DD` | fecha | — | Solo de esa fecha en adelante (comparación de texto sobre `fecha`; no se valida el formato) |
| `--n <N>` | entero | `20` | Máximo de filas, de más reciente a más antiguo |
| `--include-hidden` | indicador | — | Incluye `deleted` y `reconciled` |
| `--detail <id>` | id | — | Detalle completo de **ese** mensaje (ignora el resto de filtros): cabecera, asunto, autor, fecha y rama, destinatarios reales, refs/commits/origins, cuerpo, instrucciones, criterios, resultado, confirmaciones, entregas, ejecuciones e historial. **Lo marca como leído** para el actor. Si no existe o no es visible: error (1) |
| `--json` | indicador | — | Array de mensajes completos (con `--detail`, el objeto del mensaje) |

**Salida.** Tabla `ID TIPO ESTADO DE→PARA PRI ASUNTO`; en un `repeat` la columna de estado muestra `vigente` o `propuesto`; `PRI` = `ALTA` si es `high`. Sin resultados: `OK|get|no hay comunicaciones …`. Si hay ficheros ilegibles en el almacén: `WARN|get|n ficheros ilegibles en el almacén (sync los lista)` (por stderr con `--json`). Código 0 salvo error.

**Ejemplos.**

```bash
get --pending                         # lo que hay que atender
get --type task --state open --to api
get --from arkana --since 2026-11-01 --n 50 --json
get --repeat                          # directrices vigentes y propuestas
get --detail N261104-1530-k3x9        # lee y marca como leído
```

#### `get` frente a `query`

| | `get` | `query` |
|---|---|---|
| Marca leído | Solo con `--detail <id>` | **Nunca** |
| Escribe en el almacén | `read/<actor>.json` con `--detail <id>` | No |
| Salida por fila | Tabla con tipo, estado y prioridad | `ID`, `DE`, `PARA`, `ASUNTO` |
| Texto del mensaje | Solo con `--detail <id>` | Con `--detail` (todo lo listado) o `--detail <id>` |
| Filtro `--unread` | No existe | Sí |
| Pie de aviso | No | Sí, **solo en texto** |
| Uso típico | Atender un mensaje | Ver qué hay sin consumirlo |

---

### `query`

**Para qué sirve.** Consulta de **solo lectura**: muestra id, remitente, asunto y destinatarios. **No marca como leído, no cierra, no cambia ningún estado y no deja huella** en el almacén (ni siquiera con `--detail`).

**Cuándo usarlo.** Para mirar qué hay sin que el hook deje de avisar; para saber exactamente qué cuenta la línea `[ARKANA messaging] … sin leer` (`--unread`); para que un orquestador o un usuario inspeccionen un mensaje antes de decidir (por ejemplo, antes de pasarlo a un worker con `--from-message`).

**Orden.** `query [filtros]`. Mismas reglas de visibilidad que `get`; los `deleted` y `reconciled` no salen salvo `--state` o `--include-hidden`.

| Opción | Valores | Por defecto | Efecto |
|---|---|---|---|
| `--unread` | indicador | — | Solo lo **sin leer** para ti, con los mismos criterios que el hook (de otros, dirigidos a ti, no leídos, no `propuesto`) |
| `--pending` | indicador | — | Igual que en `get`: `task`/`review`/`question` `once` abiertas, dirigidas a ti y no confirmadas |
| `--detail [id]` | opcional | — | Sin valor: añade bajo cada fila el **texto del mensaje** (cuerpo, instrucciones y criterios, sin metadatos ni historial; `(sin texto)` si no hay). Con id: equivale a `--id <id>` más el texto. **No marca leído** |
| `--id`, `--type`, `--state` | como en `get` | — | Filtros exactos |
| `--to`, `--from`, `--user`, `--since`, `--n` | como en `get` | `--n` 20 | Filtros y límite |
| `--repeat` | indicador | — | Solo directrices permanentes |
| `--include-hidden` | indicador | — | Incluye `deleted` y `reconciled` |
| `--json` | indicador | — | Array de `{id, de, asunto, para}`; con `--detail`, más `cuerpo`, `instrucciones` y `criterios` cuando existen |

**Salida.** Tabla `ID DE PARA ASUNTO` (`PARA` como se escribió: `all` se queda en `all`). Sin resultados: `OK|query|no hay comunicaciones …` (con «sin leer» si se usó `--unread`). **Al final de la salida en texto** (no en `--json`) añade un pie fijo: «Consulta de solo lectura: no se ha marcado ningún mensaje como leído ni se ha cambiado ningún estado. Para consumir un mensaje … usa /arkana-messaging:get --detail <id>».

**Ejemplos.**

```bash
query --unread                      # lo que cuenta el hook, sin consumirlo
query --unread --detail             # con el texto, sigue sin marcar leído
query --detail N261104-1530-k3x9    # ese mensaje con su texto
query --pending --json
```

---

### `delete`

**Para qué sirve.** Borrado **lógico** de un mensaje (y baja de una directriz `repeat`). El fichero se conserva con `estado: deleted` y `estado_previo`; así el borrado se propaga al importar un ZIP.

**Cuándo usarlo.** Para retirar un mensaje enviado por error o una directriz que ya no aplica. No hay «deshacer»: si fue un error, hay que crear otro mensaje.

**Orden.** `delete <id> [--dry-run] [--json]`

| Parámetro | Efecto y restricciones |
|---|---|
| `<id>` (obligatorio) | Formato de id válido (si no, error 2). Debe existir y ser visible para el actor (si no, error 1) |
| `--dry-run` | Ejecuta las mismas comprobaciones y responde `DRY|delete|<id>: se marcaría como borrada` sin escribir |
| `--json` | Salida JSON |

Permisos: **ARKANA** borra cualquier mensaje; un componente, **solo los que escribió** (error 1 en caso contrario). Es **idempotente** (`<id> ya estaba borrada`). Escribe el mensaje (`estado`, `estado_previo`, entrada `deleted` en el historial) y reconstruye el índice.

**Pasos.** (1) Mostrar el mensaje (`get --detail <id>` o `query --detail <id>`) y pedir confirmación («Borrar» / «Cancelar»). (2) Ejecutar `delete`.

**Salida.** `OK|delete|<id> borrada (borrado lógico: se conserva la marca)`.

**Ejemplo.** `delete N261104-1530-k3x9`

---

### `sync`

**Para qué sirve.** Mantenimiento del almacén y reconciliación de mensajes solapados. Reconstruye `state/index.json` desde los mensajes, lista ficheros ilegibles, completa una reconciliación cortada a medias y, con `--reconcile`, informa de candidatos. Sus subcomandos auxiliares `reconcile` y `adopt` completan el skill.

**Cuándo usarlo.** Tras importar un ZIP, si el índice parece desactualizado, si `check`/`get` avisan de ficheros ilegibles, o cuando `put` sugiere reconciliar. `adopt`, una sola vez, para recoger mensajes del formato antiguo.

#### `sync [--reconcile] [--dry-run] [--json]`

| Opción | Efecto |
|---|---|
| `--reconcile` | Añade una línea `reconcile`: número de grupos de mensajes abiertos que comparten destinatario (`INFO` si hay, `OK` si no) |
| `--dry-run` | No escribe nada (ni el índice ni las reparaciones); informa de lo que haría |
| `--json` | Salida JSON |

Efectos: lista cada fichero ilegible o cuyo `id` no coincide con el nombre (`WARN|sync:<fichero>`); si un resumen de reconciliación tiene `origins` que no están `reconciled`, los pasa a `reconciled` (`OK|sync-reparar|n mensajes originales pasados a reconciled`); reconstruye el índice y resume el conteo: `OK|sync|12 mensajes; índice reconstruido: done 4, notice 3, open 5`. Toma el cerrojo.

#### `reconcile candidates [--to <alias>] [--json]`

Solo lectura. Devuelve grupos de **mensajes con el mismo conjunto de destinatarios** visibles para el actor, con al menos dos, **abiertos o avisos** (sin estado), y que no sean `repeat`. `--to` limita a los que tienen a ese destinatario. Texto: `GRUPO|<destinatarios>|<n> mensajes abiertos` y una línea por mensaje; JSON: `[{para[], mensajes[{id, tipo, de, asunto, prioridad, fecha, cuerpo (≤400 caracteres)}]}]`.

#### `reconcile apply --origins "ID ID …" --subject T [--type T] [--priority P] [--body-file F] [--instructions-file F] [--criteria-file F] [--dry-run] [--json]`

| Opción | Por defecto | Efecto y restricciones |
|---|---|---|
| `--origins` (obligatoria) | — | Al menos **dos** ids distintos y válidos. Todos deben existir, ser visibles, estar abiertos (o ser avisos), no ser `repeat` y tener **el mismo conjunto de destinatarios**. El actor no puede ser el destinatario |
| `--subject` (obligatoria) | — | Asunto del resumen (3 a 80 caracteres) |
| `--type` | `notice` | `notice`, `task`, `review` o `question`; con `task`, el resumen exige instrucciones y criterios |
| `--priority` | `normal` | `normal` o `high`; si algún original es `high`, el resumen es `high` |
| `--body-file`, `--instructions-file`, `--criteria-file` | — | Como en `put` |
| `--dry-run` | — | Valida y responde `DRY|reconcile|se crearía <id> resumiendo n mensajes` |

Crea **un** mensaje resumen (con `origins`, destinatarios = los de los originales, remitente = actor) y pasa los originales a `reconciled` (con `reconciled_into`), de modo que dejan de mostrarse. Primero se guarda el resumen y luego se marcan los originales: si se corta, `sync` completa el resto.

#### `adopt [--source DIR] [--dry-run] [--json]`

Adopta **una sola vez** los mensajes JSON del formato antiguo (carpeta `novedades/` del repo de ARKANA, o `--source DIR`). Los convierte al esquema actual, **no sobrescribe** los que ya están en el almacén, avisa (`WARN`) de los `.md` y de los JSON no convertibles. Si la carpeta no existe: código 3. Resumen: `OK|adopt|n adoptadas, m ya estaban en el almacén`.

**Pasos de reconciliación** (decide el modelo, confirma el usuario): (1) `reconcile candidates [--to <alias>] --json`. (2) Decidir **cuáles se solapan de verdad** (misma petición repetida, información superada por otra posterior); si no, no hacer nada. (3) Redactar un único resumen que conserve todo lo accionable; enseñarlo y pedir confirmación. (4) `reconcile apply …`. Nunca reconciliar mensajes de destinatarios distintos ni ya cerrados.

**Ejemplos.**

```bash
sync --dry-run
sync --reconcile
reconcile candidates --to api --json
reconcile apply --origins "N261104-1100-aaaa N261104-1230-bbbb" --subject "Cambios pedidos a api (consolidado)" \
    --type task --instructions-file "$SCRATCH/i.txt" --criteria-file "$SCRATCH/c.txt"
adopt --dry-run
```

---

### `install`

**Para qué sirve.** Puesta en marcha (repetible) de la mensajería.

**Cuándo usarlo.** La primera vez, y cuando `check` avise de que los hooks no corren en la sesión.

**Orden.** `install [--dry-run] [--no-settings] [--json]`

| Opción | Efecto |
|---|---|
| `--dry-run` | Informa de lo que cambiaría sin escribir nada (se ejecuta **siempre primero**) |
| `--no-settings` | No toca `~/.claude/settings.json` (instalación a nivel de proyecto, o sin permiso) |
| `--json` | Salida JSON |

Hace, por este orden: (1) crea `.arkana/arkana-messaging/state/messages/`; (2) habilita `arkana-messaging@arkana` en `~/.claude/settings.json` (copia previa en `.arkana/arkana-messaging/bak/settings.json.<fecha>`; si ya está habilitado, no hace nada); (3) pone el bloque `<!-- arkana:messaging:start -->…<!-- arkana:messaging:end -->` en el `CLAUDE.md` de ARKANA y de cada componente (en `CLAUDE.local.md`, que se crea si falta, para los que lo declaran como `seed_file`; copia en `bak/<alias>/`); (4) quita del `CLAUDE.md` de ARKANA la importación obsoleta `@.arkana/core/novedades.md`. Si falta un `CLAUDE.md` versionado **no lo crea** (`WARN`): eso lo hace `/arkana-workspace:fix`. Un bloque ya al día se deja igual.

**Pasos.** (1) `--dry-run` y enseñar qué cambiaría; pedir confirmación, porque modifica ficheros de varios repos y los ajustes del usuario. (2) Aplicar. (3) Avisar de que **los cambios en los repos no están commiteados** y de que hay que **recargar los plugins** (`/reload-plugins`) o reiniciar la sesión para que arranquen los hooks. (4) No hacer commit ni push.

**Salida.** `OK|almacen|almacén creado`, `OK|plugin|arkana-messaging@arkana habilitado: recarga …`, `OK|semilla-<alias>|semilla añadido|reemplazado|creado en <ruta>`, o `OK|install|nada que hacer: todo está al día`.

---

### `check`

**Para qué sirve.** Diagnóstico de **solo lectura**. Nunca corrige: propone `install` o `fix`.

**Cuándo usarlo.** Lo pide la semilla en el **primer turno** de cada sesión.

**Orden.** `check [--component <alias>|--all] [--json]`

| Opción | Por defecto | Efecto |
|---|---|---|
| `--component <alias>` | el componente actual | Revisa la semilla de ese componente |
| `--all` | — | Revisa la semilla de ARKANA y de **todos** los componentes (es lo que usa `arkana-plugin.json` → `check`) |
| `--json` | — | Salida JSON |

Comprobaciones: `almacen` (existe `state/messages/`), `plugin` (habilitado en `~/.claude/settings.json`; `INFO` si no hay ese fichero), `latido` (los hooks han corrido **en esta sesión**, buscando `state/sessions/$CLAUDE_CODE_SESSION_ID.json`; respaldo: latido del componente en los últimos 15 minutos) y `semilla-<alias>` (`OK`, o `WARN` con `DESACTUALIZADO`, `SIN-BLOQUE` o `SIN-FICHERO`). Los `WARN` no cambian el código de salida (0).

**Pasos.** (1) Ejecutarlo y resumir en una línea si todo está `OK`. (2) Si el `latido` es `WARN`, proponer `/arkana-messaging:install` y recargar los plugins, **una sola vez por sesión**. (3) Si hay otras advertencias, proponer `/arkana-messaging:fix`.

---

### `fix`

**Para qué sirve.** Corrige solo lo que `check --all` marca con `WARN`: almacén ausente, plugin deshabilitado, semillas ausentes o desactualizadas. Lo que ya está `OK` no se toca.

**Orden.** `fix [--dry-run] [--no-settings] [--json]`

| Opción | Efecto |
|---|---|
| `--dry-run` | Muestra qué cambiaría |
| `--no-settings` | No habilita el plugin en `~/.claude/settings.json` |
| `--json` | Salida JSON |

**Pasos.** (1) `check --all` y, si hay `WARN`, `fix --dry-run`. (2) Pedir confirmación y aplicar. (3) Si falta un `CLAUDE.md` versionado no lo crea (`/arkana-workspace:fix`). (4) Repetir `check --all` y mostrar el resultado.

---

## Hooks

Declarados en `hooks/hooks.json` y atendidos por `scripts/hooks.py`; cada uno tiene un tiempo máximo de 5 s. **No tocan los mensajes** (solo leen el índice y, de lo que van a inyectar, el mensaje completo; sin git ni red) y solo escriben estado local: latido, marcas de leído y purga de sesiones antiguas.

**No hacen nada** dentro de un worker (`ARKANA_WORKER=1`), fuera de un workspace o si el `cwd` no es de ningún componente. Cualquier error se traga: un hook nunca rompe la sesión. Si el índice falta o está corrupto, lo reconstruyen.

| Evento | Cuándo | Qué hace |
|---|---|---|
| `SessionStart` (`startup`, `resume`, `clear`, `compact`) | Al abrir, reanudar, limpiar o compactar la sesión | Inyecta los mensajes sin leer, las directrices vigentes y un recordatorio de lo que sigue abierto; purga latidos de más de 14 días |
| `UserPromptSubmit` | En cada prompt del usuario | Inyecta **solo lo nuevo** sin leer |
| `Stop` | Cuando Claude va a terminar el turno | Bloquea **una sola vez por mensaje** si queda algo urgente sin leer |

### Qué se inyecta al modelo (`additionalContext`)

- **Cabecera**: `[arkana-messaging] Mensajes sin leer para <actor> (n). Propón al usuario atenderlos; no los des por hechos ni cierres nada sin su confirmación.`
- **Cada mensaje sin leer**, en este orden: prioridad alta primero, luego por fecha. Se inyecta **completo** (`id · tipo · ALTA · de→para · asunto`, cuerpo, instrucciones y criterios) si cabe: **hasta 1500 caracteres por mensaje y 6000 en total**. Los inyectados completos se marcan **leídos**.
- Los que no caben se listan solo con asunto e id y el comando `/arkana-messaging:get --detail <id>`; **no** se marcan leídos.
- **Solo en `SessionStart`**: `Directrices vigentes para <actor>` (los `repeat` vigentes no inyectados ya, con su `get --detail`) y `Siguen abiertos para <actor>` (tareas, revisiones y preguntas abiertas que el componente aún no ha confirmado).

### Qué ve el usuario (`systemMessage`)

Una línea cuando el componente tiene algo recibido o pedido:

```text
[ARKANA messaging] api: 2 sin leer · 1 leídos en el último turno · tareas para ti: 3 abiertas · 4 hechas · 1 descartadas · directrices vigentes para ti: 2 · tareas pedidas por ti: 1 hechas de 3 · directrices dadas por ti: 2 → /arkana-messaging:query --unread
```

| Fragmento | Significado |
|---|---|
| `N sin leer` | Mensajes sin leer para el actor |
| `M leídos en el último turno` | Los que se marcaron leídos desde la última emisión (por inyección o `get --detail`) |
| `tareas para ti: A abiertas · H hechas [· D descartadas]` | Tareas/revisiones/preguntas `once` que **le han pedido** al componente, por su confirmación |
| `directrices vigentes para ti: K` | `repeat` dirigidos a él (no `propuesto`) |
| `tareas pedidas por ti: X hechas de Y` | Tareas/revisiones/preguntas `once` que **él** ha enviado y su estado global |
| `directrices dadas por ti: G` | `repeat` que **él** ha creado (vigentes o propuestos, no borrados) |
| `→ …` | Con mensajes sin leer, `query --unread`; si no, con tareas abiertas, `get --pending` |

Se emite: en `SessionStart` solo si la causa no es `startup` ni `resume` (es decir, tras `clear` o `compact`); en `UserPromptSubmit` solo si **hubo actividad** (mensajes nuevos o leídos en el turno) o **cambió el recuento** de tareas, directrices o pedidas respecto a la última emisión. Si al componente nadie le ha escrito ni ha pedido nada, no hay línea.

### Bloqueo único del Stop

Bloquea (`decision: block`, con la lista de mensajes y la orden `/arkana-messaging:get --pending`) solo si, **sin leer** para el actor y no recordados antes en esta sesión, hay un mensaje de **prioridad alta**, una **tarea** o una **pregunta**. Cada mensaje bloquea **una vez** (se anota en `reminded` del latido) y nunca cuando `stop_hook_active` es cierto, para no encadenar bloqueos. Claude Code muestra cada bloqueo al usuario como «Stop hook error». El Stop no marca como leído.

### Latido de sesiones

Cada ejecución (también las que no emiten nada) escribe `state/sessions/<session_id>.json` con `ts`, `event`, `actor`, `seen` (leídos conocidos), `sig` (recuento para detectar cambios) y `reminded`. Lo usa `check` para saber si los hooks corren **en esta sesión**. El identificador sale del evento o de `CLAUDE_CODE_SESSION_ID`.

## Semilla `arkana:messaging`

`install` (y `fix`) mantienen en el `CLAUDE.md` de ARKANA y de cada componente (`CLAUDE.local.md` en los que lo declaran como `seed_file`) un bloque gestionado `<!-- arkana:messaging:start -->` … `<!-- arkana:messaging:end -->`, **autocontenido** (no importa ficheros). Le dice al modelo:

1. En el primer turno, ejecutar `/arkana-messaging:check`; si los hooks no han corrido, ejecutar `/arkana-messaging:install` y avisar de recargar los plugins.
2. Los mensajes sin leer llegan inyectados; proponer al usuario atenderlos, nunca darlos por hechos ni cerrarlos sin su confirmación (`/arkana-messaging:get --pending`).
3. Al terminar una tarea, revisión o pregunta, proponer `put --done <id> --result "..."`; nunca incluir credenciales ni datos personales.

Lo que está fuera del bloque no se toca y se deja copia `.bak`. `/arkana-workspace:check` también comprueba su estado.

## Reconciliación

Evita que se acumulen mensajes que dicen lo mismo. **El script solo elige candidatos** (mismo conjunto de destinatarios, abiertos o avisos, no `repeat`, ni `reconciled` ni `deleted`); **el modelo decide cuáles se solapan** de verdad, redacta un único resumen y **el usuario confirma**. El resumen conserva `origins`; los originales pasan a `reconciled` (con `reconciled_into`) y dejan de mostrarse. Se sugiere tras cada `put` (línea `INFO|reconcile`) y con `sync --reconcile`. Detalle en [`sync`](#sync).

## Variables de entorno, pruebas y desarrollo

| Variable | Efecto |
|---|---|
| `ARKANA_WORKER=1` | Los hooks no hacen nada (la fija `arkana-agentic` en los workers) |
| `ARKANA_HOME` | Carpeta del repo de ARKANA; si existe, se usa en vez de buscar `.arkana/arkana.json` subiendo desde el `cwd` y en el registro de workspaces |
| `CLAUDE_CODE_SESSION_ID` | Identifica la sesión: `check` busca su latido; los hooks la usan si el evento no trae `session_id` |
| `CLAUDE_PLUGIN_ROOT` | Carpeta del plugin; la usan los skills para localizar `scripts/messaging.sh` |
| `USER` | Respaldo del campo `autor` si no hay `user.email` de git |
| `ARKANA_MESSAGING_CMD` | Solo pruebas de `arkana-agentic`: comando que sustituye a `messaging.sh` |

**Pruebas.** `bash tests/run-tests.sh [-v|-q] [-k <patrón>]` (sin red, sin API real y sin tocar `~/.claude`; `unittest` sobre `test_messages.py`, `test_hooks.py` y `test_ops.py`). Desde la raíz del marketplace, `bash scripts/run-all-tests.sh --only messaging`.

**Desarrollo.** Los comandos son `scripts/messaging.sh` (despacha `install|check|fix` a `scripts/lib/ops.py` y el resto a `scripts/lib/messages.py`) y los hooks, `scripts/hooks.py`. El código común (localizador, manifiesto, esquemas, salida, red, bloques gestionados) es el **núcleo vendorizado** en `scripts/_core/`, copia de `lib/arkana_core/`; un plugin instalado no puede leer a otro, así que se regenera con `bash ../../scripts/vendor-core.sh` (y `--check` comprueba que está al día). Contrato del plugin: `arkana-plugin.json`.
