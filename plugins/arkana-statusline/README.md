# arkana-statusline

Barra de estado de Claude Code para Arkana. Muestra **en dos líneas** ARKANA y cada componente del proyecto (el workspace es ARKANA más el proyecto) con su estado git, el plan activo de `arkana-agentic`, el coste (del plan y de la sesión), el modelo y el uso (contexto, sesión de 5 h y semana). Funciona dentro y fuera de un workspace y se adapta al ancho del terminal.

```
ARKANA@develop:◌13✚113●84⇡2⇣3 · [▶] 002/007 api@P2611030652-ysov:T002 Añadir el perfil · P0.40 S1.23 · Sonnet 5.5 (medium) · C61 S0 W19
app@develop:✓⇣? · api@develop:◌1 · app-web@develop:✓⇣? · app-ui@develop:●2⇣5
```

Visión de conjunto de los seis plugins de Arkana: [`../README.md`](../README.md).

## Contenido

1. [Cómo encaja con los demás plugins](#cómo-encaja-con-los-demás-plugins)
2. [Formato](#formato)
3. [Skills (referencia)](#skills-referencia): [`install`](#arkana-statuslineinstall), [`check`](#arkana-statuslinecheck), [`fix`](#arkana-statuslinefix), [`refresh`](#arkana-statuslinerefresh)
4. [Coste real de la sesión](#coste-real-de-la-sesión)
5. [Variables de entorno](#variables-de-entorno)
6. [Instalación](#instalación)
7. [Pruebas y desarrollo](#pruebas-y-desarrollo)

## Cómo encaja con los demás plugins

| Plugin | Relación |
|---|---|
| `arkana-workspace` | De su **manifiesto** (`core/workspace.json`) salen los componentes, su **orden** (ARKANA primero, después los del manifiesto), el **alias** que se muestra de cada uno y la marca `statusline` (ver «Qué componentes se muestran»). Localiza el repo de Arkana con `$ARKANA_HOME` o subiendo desde el directorio del proyecto. `/arkana-workspace:sync` hace lo mismo que `/arkana-statusline:refresh` (ambos dejan `⇣` al día). |
| `arkana-agentic` | **Lee** el plan: la statusline pinta `run/linea.json`, que el motor reescribe en cada transición (aquí no se calcula nada del plan). A la inversa, la statusline es la **única escritora del coste real de la sesión**, que los hooks de `arkana-agentic` leen para su libro de sesiones (`/arkana-agentic:costs`). Ver [Coste real de la sesión](#coste-real-de-la-sesión). |
| `arkana-messaging` | **Sin relación directa**: ni la statusline lee ni escribe nada de la mensajería, ni la mensajería de la statusline (no hay referencias en su código ni en sus hooks). |
| `arkana-knowledge` | Sin relación. |
| `arkana-todo` | Sin relación. |

`arkana-plugin.json` no declara dependencias: el plugin es autónomo y lleva su propia copia del núcleo `arkana_core` (necesaria porque la statusline la ejecuta Claude Code como comando de usuario, sin raíz de plugin).

## Formato

### Estructura

```
Línea 1:  ARKANA@rama:indicadores · [estado] descripción del plan · P S coste · modelo (esfuerzo) · C S W uso
Línea 2:  componente · componente · componente …
(línea extra, solo si procede)  ⚠ workspace no cargado: …
```

- **Línea 1.** El componente ARKANA va siempre entero, seguido de las secciones del plan, el coste, el modelo y el uso.
- **Línea 2.** Los demás componentes, en el orden del manifiesto. Si no caben, pasan a más líneas (ver «Ancho estrecho»). Si no hay más componentes, no hay segunda línea.
- **Fuera de un workspace** (sin ARKANA localizable) solo hay **una pieza**: el directorio de trabajo, mostrado con su nombre de carpeta como alias y como componente actual; la statusline es una sola línea (más plan, coste, modelo y uso).
- **Separador.** Entre componentes y entre secciones va ` · ` con el punto en **azul oscuro**.
- Las secciones sin dato se omiten: sin modelo no hay bloque de modelo; los porcentajes que Claude Code no envía (`C`, `S`, `W`) no se pintan.

### Un componente: `ALIAS@rama:indicadores`

| Parte | Color |
|---|---|
| `ALIAS` del componente actual (el del directorio de trabajo) | **naranja brillante**, negrita |
| `ALIAS` de los demás | **naranja** |
| `@` y `:` | **rojo** |
| nombre de la rama | **gris brillante** si es el componente actual, **gris** si no |
| indicador `◌` | en **inverso** (texto negro sobre **rojo**) |
| indicadores `✚ ● ⇡ ⇣N` | en inverso, sobre **amarillo** |
| indicador `⇣?` | en inverso, sobre **cian** |
| indicador `✓` | en inverso, sobre **verde** |

Cada indicador lleva su símbolo y su cantidad dentro del mismo bloque (`◌353`, `⇣?`) y los bloques van **pegados, sin espacios** (`◌353●6⇣?`): el fondo de color ya los separa. Si no hay indicadores, se muestra solo `ALIAS@rama`.

| Indicador | Significado | Origen |
|---|---|---|
| `◌N` | N ficheros sin seguimiento (`-uall`: uno por fichero) | git local |
| `✚N` | N ficheros con cambios preparados (staged) | git local |
| `●N` | N ficheros modificados sin preparar (los conflictos sin resolver cuentan aquí) | git local |
| `⇡N` | N commits locales sin subir | git local; necesita rama remota |
| `⇣N` | N commits por bajar | **remoto**; necesita rama remota y `fetch` reciente |
| `⇣?` | hay rama remota pero no se sabe cuántos hay por bajar | el último `fetch` es de hace 30 min o más, o no existe |
| `✓` | local limpio: ni `◌`, ni `✚`, ni `●`, ni `⇡` | git local |
| ` —` | tras el alias (`app —`): la carpeta no existe o no es un repo git | |

Solo se muestran los indicadores distintos de cero y siempre en este orden: `◌ ✚ ● ⇡ ✓ ⇣`. `✓` no excluye a `⇣`.

**Cuándo se conoce `⇣`.** Todo lo demás se calcula en cada refresco con `git status` local (sin red, `--no-optional-locks`, tope de 4 s por repo, hasta 8 repos en paralelo). `⇣` es lo único que depende del remoto: se muestra como número si `FETCH_HEAD` del componente (se resuelven worktrees y submódulos) es **más reciente de 30 minutos**; si no, se pinta `⇣?` en su mismo hueco. Sin rama remota configurada no hay `⇡` ni `⇣`. Para actualizarlo, `/arkana-statusline:refresh` (o `/arkana-workspace:sync`).

### Qué componentes se muestran

ARKANA siempre, más los componentes del manifiesto con `statusline: true`; si un componente no tiene la marca, se muestra salvo que sea de tipo `docs`. Con `statusline: false` se oculta. La marca se fija con `/arkana-workspace:component edit --alias <alias> --statusline` (o `--no-statusline`). El **orden** en la barra es el de `components` en el manifiesto, con ARKANA siempre primero.

### Plan activo (`arkana-agentic`)

Sección `[estado] descripción`. El símbolo entre corchetes va **en inverso** (texto negro sobre el color de su estado); el resto del texto, en gris, fuera del bloque.

```
[▶] 002/007 (✗1) api@P2611030652-ysov:T002 Añadir el perfil
[■] sin plan activo
```

| Símbolo | Color | Cuándo | Descripción mostrada |
|---|---|---|---|
| `▶` | verde | plan en ejecución con un worker vivo | asunto corto de la tarea (o `tarea en curso`) |
| `▶` | verde | en ejecución, sin worker y de menos de 10 min | `el orquestador decide el siguiente paso` |
| `✗` | rojo | en ejecución y el proceso del worker ya no existe | `worker interrumpido: ejecuta /arkana-agentic:fix` |
| `✗` | rojo | en ejecución, sin worker y 10 min o más sin actividad | `sin actividad desde hace N min` |
| `?` | cian | esperando tu respuesta (gate) | `asunto (esperando tu respuesta: <gate>)` |
| `‖` | amarillo | pausado | `pausado` |
| `✓` | verde | completado | `plan completado` |
| `■` | rojo | detenido | `plan detenido` |
| `✗` | rojo | fallido | `plan fallido` |
| `■` | gris | sin plan | `sin plan activo` |

Detalles:

- `002/007` es la tarea actual (o las hechas) sobre el total; `(✗N)` indica N tareas omitidas. Con tarea, el identificador es `repo@plan:tarea` (repo en amarillo brillante, `@` y `:` en rojo brillante, plan y tarea en azul brillante); sin tarea, solo el id del plan.
- Los estados terminales (`completado`, `detenido`, `fallido`) se ocultan pasados **30 min**.
- El plan se muestra **solo en la sesión de Claude que lo gobierna**: si `session_id` de `linea.json` no coincide con el de la sesión actual, se ve `sin plan activo`.
- La fuente es `.arkana/arkana-agentic/state/run/linea.json` (o `.arkana/arkana-agentic/run/linea.json`).

### Coste, modelo y uso

| Sección | Ejemplo | Color | Fuente |
|---|---|---|---|
| Costes | `P0.40 S1.23` | rojo oscuro, sin fondo | `P`: gasto del plan (`gasto_usd` de `linea.json`); `S`: coste de la sesión (`cost.total_cost_usd` de Claude Code). Dos decimales, en dólares; `S0.00` si no hay dato |
| Modelo | `Sonnet 5.5 (medium)` | magenta, sin fondo | `model.display_name` y, si existe, `effort.level` entre paréntesis |
| Uso | `C61 S0 W19` | color del texto por tramo, sin fondo | `C` contexto (`context_window.used_percentage`), `S` ventana de 5 h (`rate_limits.five_hour`), `W` semana (`rate_limits.seven_day`) |

Tramos del uso (valor redondeado): **0–40 verde, 41–75 amarillo, 76–100 rojo brillante**.

### Ancho estrecho

El ancho útil es el del terminal menos 5 columnas (Claude Code reserva unas 4 a la derecha, más 1 de holgura). El ancho sale de `$COLUMNS` o, si no, del terminal (stderr, stdout, stdin, `/dev/tty`); por defecto, 120.

`fit_line1` (función pura) ajusta los componentes de la línea 2 en este orden, parando en cuanto caben:

1. se acortan con `…` las **ramas** de los componentes que no son el actual (a 8, a 5 caracteres);
2. se acortan los **alias** de los demás (a 4, luego a 3);
3. los componentes pasan a **más líneas**, empaquetados por orden.

**Nunca se recortan**: los contadores de los indicadores, ARKANA, el componente actual ni el plan, el coste, el modelo y el uso. En la línea 1 solo cede la **descripción del plan** (se acorta con `…` y, si quedan menos de 6 caracteres, se omite); a anchos muy estrechos la línea 1 puede pasarse de ancho.

### Aviso `⚠ workspace no cargado: …`

Si el manifiesto no se puede leer o validar, no hay componentes que mostrar: la statusline lo dice en una línea extra (en amarillo brillante) en vez de degradar en silencio, y sigue mostrando una sola pieza (el directorio actual) con plan, coste, modelo y uso:

```
⚠ workspace no cargado: <motivo> (¿copia de la statusline desactualizada? /arkana-statusline:fix)
```

La causa típica es una copia instalada desactualizada del núcleo `arkana_core` (esquema o formato del manifiesto más nuevos que la copia). Se arregla con `/arkana-statusline:fix`. El motivo se acorta a 110 caracteres.

Ante cualquier excepción inesperada la statusline imprime `arkana-statusline: <TipoDeError>` y termina con código 0: nunca rompe la sesión.

## Skills (referencia)

Los cuatro skills están en `skills/`. `install`, `check` y `fix` ejecutan `scripts/lib/ops.py <subcomando>`; `refresh`, `scripts/lib/refresh.py`.

| Skill | Escribe | Red | Para qué |
|---|---|---|---|
| `install` | `~/.claude/arkana-statusline/`, `~/.claude/settings.json` | no | Instala o actualiza la copia y activa `statusLine` |
| `check` | nada | no | Diagnóstico de solo lectura |
| `fix` | igual que `install` (sin `--replace`) | no | Repara copia desactualizada o `statusLine` ausente |
| `refresh` | solo referencias remotas de git (`git fetch`) | sí | Deja `⇣` al día |

**Salida común.** Una línea por comprobación `ESTADO|ID|detalle` (estados `OK`, `WARN`, `FAIL`, `INFO`, `DRY`) y al final `RESUMEN|n FAIL|n WARN`. Con `--json`: `{"plugin","skill","status","items":[{"id","status","detail","component"}],"summary":{"fail","warn","ok","info","dry"}}`. Códigos de salida: **0** sin fallos (los `WARN` no cuentan), **1** hay algún `FAIL`, **2** uso incorrecto (argumento desconocido o falta el subcomando; `-h` sale con 0), **3** precondición no cumplida (solo `refresh`, ver abajo).

### `/arkana-statusline:install`

**Para qué.** Instala la statusline en la máquina del usuario y la activa. Es el primer paso y también el modo de actualizarla tras cambiar el plugin. Funciona también fuera de un workspace.

**Cuándo.** Una vez por máquina y después de cada actualización del plugin; con `--replace`, solo si el usuario decide sustituir una `statusLine` ajena.

**Orden exacta.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" install [--replace] [--dry-run] [--json]
```

| Parámetro | Valores / por defecto | Efecto |
|---|---|---|
| `--replace` | opcional; por defecto no | Sustituye una `statusLine` ya configurada que **no es de Arkana** (un script propio, el antiguo `statusline-command.sh`, otro plugin). Sin él, una ajena se respeta y se avisa con `WARN`. Hace copia previa de los ajustes. |
| `--dry-run` | opcional; por defecto no | No escribe nada: cada cambio se informa como `DRY` y no se ejecuta la prueba de humo. |
| `--json` | opcional; por defecto texto | Salida en JSON. |

Cualquier otro argumento termina con código 2.

**Qué hace.**

1. Compara por SHA-256 cada fichero instalado con su fuente: `statusline.sh`, `statusline.py` y todo `arkana_core/` (sin `tests` ni `__pycache__`). Si **alguno** difiere o falta, copia el conjunto completo a `~/.claude/arkana-statusline/` y deja `statusline.sh` ejecutable (`0755`). Si todo está igual: `OK|copia|copia al día`.
2. Activa `statusLine` en `~/.claude/settings.json` como `{"type": "command", "command": "bash ~/.claude/arkana-statusline/statusline.sh"}`:
   - si ya es la de Arkana: `OK` sin cambios;
   - si no hay ninguna: la activa;
   - si hay otra y **no** se pasó `--replace`: `WARN` y no la toca (el comando sigue exigiendo decisión del usuario);
   - si hay otra y se pasó `--replace`: la sustituye.
3. Habilita `enabledPlugins["arkana-statusline@arkana"] = true` en los mismos ajustes si no lo estaba.
4. Si cambia `settings.json` y ya existía, deja antes una **copia de seguridad** en `~/.claude/arkana-statusline/bak/settings.json.<AAAAMMDDTHHMMSS>`; la escritura es atómica. Informa `INFO|recarga`: reinicia Claude Code o recarga los plugins para ver la nueva barra.
5. **Prueba de humo** (no en `--dry-run`): ejecuta `bash ~/.claude/arkana-statusline/statusline.sh` con una entrada JSON mínima (`COLUMNS=120`, tope de 10 s). Pasa si el código de salida es 0, imprime **al menos una línea** y no contiene `arkana-statusline:` (el mensaje de error interno). Detalle: `N líneas, rc 0`; si falla, `WARN|humo|prueba de humo fallida (…)`.

**Ejemplos.**

```
$ /arkana-statusline:install --dry-run
DRY|copia|18 ficheros se copiarían a ~/.claude/arkana-statusline
WARN|statusline|hay otra statusLine activa (bash ~/.claude/statusline-command.sh): usa install --replace para sustituirla
DRY|plugin|arkana-statusline@arkana habilitado
RESUMEN|0 FAIL|1 WARN

$ /arkana-statusline:install --replace
OK|copia|18 ficheros copiados a ~/.claude/arkana-statusline
OK|statusline|sustituye la statusLine anterior (copia de los ajustes en ~/.claude/arkana-statusline/bak/)
INFO|recarga|reinicia Claude Code o recarga los plugins para ver la nueva statusline
OK|humo|3 líneas, rc 0
RESUMEN|0 FAIL|0 WARN
```

(Los ejemplos son ilustrativos: el número de ficheros y de líneas depende de la versión y del entorno.) **Regla del skill:** hacer siempre `--dry-run` primero y enseñar qué cambiaría; si hay una `statusLine` ajena, no pisarla sin preguntar al usuario. No usar a la vez otro plugin de statusline con autoinstalación (`check` los detecta).

### `/arkana-statusline:check`

**Para qué.** Diagnóstico de **solo lectura**. Nunca corrige.

**Cuándo.** Tras instalar, si la barra no aparece o sale `⚠ workspace no cargado`, y tras actualizar el plugin.

**Orden exacta.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" check [--json]
```

| Parámetro | Valores / por defecto | Efecto |
|---|---|---|
| `--json` | opcional; por defecto texto | Salida en JSON. |

`check` no admite `--dry-run` (ya es de solo lectura): pasarlo termina con código 2.

**Qué comprueba** (ids de la salida):

| Id | `OK` | `WARN` / `FAIL` / `INFO` |
|---|---|---|
| `python3` | `python3` disponible | `FAIL` si falta |
| `git` | `git` disponible | `FAIL` si falta |
| `instalada` | (solo aparece si no hay copia) | `WARN`: no existe `~/.claude/arkana-statusline` → `/arkana-statusline:install` |
| `copia` | todos los ficheros instalados coinciden (SHA-256) con los del plugin | `WARN`: **copia desactualizada** (cuántos ficheros y los tres primeros) → `/arkana-statusline:fix` |
| `statusline` | `statusLine` apunta a `arkana-statusline/statusline.sh` | `WARN`: no hay `statusLine` → `install`; `WARN`: hay **otra `statusLine` ajena** activa → `install --replace`; `INFO`: no existe `~/.claude/settings.json` |
| `otros-plugins` | ningún otro plugin habilitado cuyo nombre contenga «statusline» | `WARN`: lista los **plugins de statusline habilitados** (`enabledPlugins`) que pueden pisarla |
| `humo` | la statusline instalada imprime al menos una línea con código 0 | `WARN`: `no está instalada`, no se pudo ejecutar, o falló |

**Códigos de salida.** 0 si no hay `FAIL` (los `WARN` no cambian el código); 1 si falta `python3` o `git`.

**Qué hacer con el resultado** (regla del skill): una sola línea si todo está `OK`; con `WARN`, proponer `/arkana-statusline:fix` (copia desactualizada) o `/arkana-statusline:install` (no instalada) y, si hay otra `statusLine`, `install --replace` con confirmación.

```
$ /arkana-statusline:check
OK|python3|disponible
OK|git|disponible
OK|copia|copia al día
OK|statusline|statusLine apunta a arkana-statusline
OK|otros-plugins|ningún otro plugin de statusline
OK|humo|1 líneas, rc 0
RESUMEN|0 FAIL|0 WARN
```

### `/arkana-statusline:fix`

**Para qué.** Reinstala la copia si está desactualizada y activa `statusLine` si no hay ninguna. **Nunca sustituye la `statusLine` de otro**: eso es `install --replace`.

**Cuándo.** Cuando `check` avisa de `copia` desactualizada o de que no hay `statusLine`, o cuando la barra muestra `⚠ workspace no cargado` por una copia vieja del núcleo.

**Orden exacta.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/ops.py" fix [--dry-run] [--json]
```

| Parámetro | Valores / por defecto | Efecto |
|---|---|---|
| `--dry-run` | opcional; por defecto no | No escribe nada; cada cambio sale como `DRY`. |
| `--json` | opcional; por defecto texto | Salida en JSON. |

`fix` **no** admite `--replace` (exit 2). En la práctica ejecuta la misma lógica que `install` sin `--replace`: mismas escrituras (`~/.claude/arkana-statusline/`, `~/.claude/settings.json` con copia en `bak/`), misma prueba de humo, misma salida (la etiqueta del informe es `fix`). Si hay una `statusLine` ajena, la deja como está y avisa con `WARN`.

**Pasos del skill.** 1) `check`; 2) si hay `WARN` de `copia` o de `statusline` (sin ninguna activa), `fix --dry-run` y, con confirmación del usuario, `fix`; 3) si hay una `statusLine` ajena, informar y dejar la decisión (`install --replace`) al usuario.

```
$ /arkana-statusline:fix --dry-run
DRY|copia|4 ficheros se copiarían a ~/.claude/arkana-statusline
OK|statusline|statusLine ya apunta a arkana-statusline
RESUMEN|0 FAIL|0 WARN
```

### `/arkana-statusline:refresh`

**Para qué.** Hace `git fetch` de ARKANA y de los componentes para que `⇣` (commits por bajar) esté al día. **Solo descarga referencias**: no toca ficheros ni ramas locales. El estado local (`◌ ✚ ● ⇡` y la rama) no lo necesita: se recalcula en cada refresco de la barra.

**Relación con `arkana-workspace`.** Es **equivalente a `/arkana-workspace:sync`**: mismo propósito, mismas opciones (`--component`, `--no-fetch`, `--json`) y misma contención de red. `refresh` existe en este plugin para que la statusline sea autosuficiente sin `arkana-workspace` instalado.

**Orden exacta.**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/refresh.py" [--component <alias>]... [--no-fetch] [--json]
```

| Parámetro | Valores / por defecto | Efecto |
|---|---|---|
| `--component <alias>` | repetible; por defecto, **todos** los del manifiesto, ARKANA incluida | Limita el `fetch` a esos componentes. El alias se normaliza (minúsculas, sinónimos históricos). Un alias que no existe en el manifiesto es un error `FAIL\|workspace` (código 3). |
| `--no-fetch` | opcional; por defecto se hace `fetch` | No toca la red: solo muestra el estado local actual de cada componente. |
| `--json` | opcional; por defecto texto | Salida en JSON (cada ítem lleva su `component`). |
| `--home <dir>` | opcional; por defecto se localiza el repo de Arkana | Ruta del repo de Arkana. Existe en el script pero **no figura en el `SKILL.md`**; útil para pruebas. |

**Qué hace por componente** (hasta 4 en paralelo):

1. Si la carpeta no es un repo git: `WARN|<alias>|no es un repositorio git`.
2. Sin `--no-fetch`: comprueba el **DNS del host remoto** (`remote_host` del manifiesto, tope de 3 s, una vez por host). **Sin VPN no intenta nada**: `WARN|<alias>|sin red: …`.
3. Si el repo tiene algún remoto, ejecuta `git fetch --quiet --prune` con **tope de 20 s** en su propio grupo de procesos. El **cortacircuitos** de red (compartido entre procesos, 60 s) evita esperar a los demás `fetch` tras un fallo o timeout del mismo host. Si falla: `WARN|<alias>|fetch falló: …`. Un repo sin remoto no se consulta.
4. Calcula el estado y lo imprime: `OK|<alias>|<rama> <indicadores>` (por ejemplo `develop ✓`, `develop ●2 ⇣5`; `sin estado git` si no se pudo leer).

El `fetch` actualiza `FETCH_HEAD`, de modo que `⇣` pasa de `⇣?` a su número durante los 30 minutos siguientes.

**Códigos de salida.** 0 (los `WARN` no cuentan); 1 si hay algún `FAIL`; 2 uso incorrecto; **3** si el workspace no se puede cargar o un `--component` no existe (`FAIL|workspace`).

**Pasos del skill.** Ejecutar el script y presentar una línea por componente; si hay `WARN` por red, sugerir `/arkana-workspace:check` (VPN, credenciales). **No** hacer `pull`, `merge`, `rebase`, `push` ni commit: integrar lo descargado es decisión del usuario.

```
$ /arkana-statusline:refresh
OK|arkana|develop ✓
OK|app|develop ✓ ⇣2
OK|api|develop ●3
WARN|app-web|sin red: no resuelve el DNS de <host>
OK|app-ui|develop ◌1 ⇣5
RESUMEN|0 FAIL|1 WARN

$ /arkana-statusline:refresh --component api --component app --no-fetch
```

(Ejemplo ilustrativo; el detalle exacto del `WARN` de red lo da el núcleo.)

## Coste real de la sesión

La statusline es la **única escritora** del coste real de cada sesión de Claude, porque Claude Code solo se lo entrega a ella (`cost.total_cost_usd` en su entrada JSON).

| Aspecto | Valor |
|---|---|
| Fichero | `<arkana>/.arkana/arkana-statusline/state/sessions/<sid>.json` |
| Contenido | `{"session_id": "…", "cost_usd": 1.23, "ts": 1730000000}` (`ts` en segundos Unix) |
| Permisos | fichero **modo 600**, carpeta 700; escritura atómica (fichero temporal + `rename`) |
| Cuándo se escribe | solo **si cambia** el coste respecto a lo ya guardado, solo con coste > 0, solo con un `session_id` válido (`[A-Za-z0-9_-]+`) y solo dentro de un workspace |
| Quién lo lee | los hooks de `arkana-agentic`, para su libro de sesiones (`/arkana-agentic:costs`) |

**Limitación conocida.** Sin statusline interactiva (`claude -p`, sesiones que no se renderizan) no se recibe coste, y de las sesiones renderizadas solo se guarda el último valor visto. Está anotada como mejora pendiente (un método más fiable que no resida en la statusline).

## Variables de entorno

Las únicas que lee el código del plugin y el núcleo que usa:

| Variable | Dónde | Efecto |
|---|---|---|
| `COLUMNS` | statusline | Ancho del terminal para el ajuste (si no, se mide el terminal; por defecto 120) |
| `ARKANA_HOME` | núcleo (`locate`) | Carpeta del repo de Arkana; tiene prioridad sobre buscarla subiendo desde el directorio del proyecto |
| `ARKANA_STATUSLINE_DIR` | statusline | Sustituye a `<arkana>/.arkana/arkana-statusline` como base del coste de sesión (las pruebas la usan) |
| `ARKANA_AGENTIC_DIR` | statusline | Sustituye a `<arkana>/.arkana/arkana-agentic` como base donde buscar `run/linea.json` |
| `ARKANA_NET_BREAKER_FILE` | núcleo (`netguard`) | Fichero del cortacircuitos de red de `refresh` (por defecto, uno en el directorio temporal por usuario) |

`statusline.sh` arranca Python con `-I` (modo aislado): ignora `PYTHONPATH` y el directorio de usuario, pero las variables `ARKANA_*` y `COLUMNS` se leen igual. El plugin no usa más variables de entorno.

## Instalación

```bash
claude plugin marketplace add <ruta>/plugins      # una vez, si no está ya
claude plugin install arkana-statusline@arkana
```

Después, `/arkana-statusline:install` (con `--dry-run` primero), reiniciar Claude Code o recargar los plugins y `/arkana-statusline:check`. Una statusline la ejecuta Claude Code como **comando de usuario, sin raíz de plugin**: por eso `install` **copia** los ficheros a `~/.claude/arkana-statusline/` (`statusline.sh`, `statusline.py` y `arkana_core/`, que viajan juntos) y apunta `statusLine` a esa copia. Cuando se actualiza el plugin, hay que volver a ejecutar `install` (o `fix`) para refrescar la copia; `check` avisa si está desactualizada.

Dentro de `~/.claude/arkana-statusline/`: `statusline.sh`, `statusline.py`, `arkana_core/` y `bak/` (copias de `settings.json`).

## Pruebas y desarrollo

```bash
bash tests/run-tests.sh [-v|-q] [-k <patrón>]      # sin red, sin API y sin tocar ~/.claude (repos git locales)
```

| Fichero | Cubre |
|---|---|
| `tests/test_render.py` | render y ajuste de ancho |
| `tests/test_cost.py` | escritura del coste de sesión |
| `tests/test_ops.py` | `install`, `check` y `fix` |
| `tests/test_refresh.py` | `refresh` |
| `tests/lab.py` | utilidades de las pruebas |

- **Render como función pura.** `render(data, width)` y `fit_line1(items, usable)` no leen nada: reciben los datos ya recogidos (`collect`) y devuelven las líneas. Las **pruebas doradas** fijan la salida a **200, 120, 80 y 50 columnas**.
- **Entrada/salida.** `statusline.sh` hace `exec python3 -I statusline.py` (el `.py` hermano, resolviendo enlaces simbólicos); el render es Python estándar (solo biblioteca estándar) para poder probar el ancho como función pura. Lee el JSON de Claude Code por stdin y escribe las líneas por stdout. Se puede probar a mano:

  ```bash
  echo '{"workspace":{"project_dir":"."},"model":{"display_name":"Sonnet 5.5"},"effort":{"level":"medium"},"session_id":"demo","context_window":{"used_percentage":61}}' | COLUMNS=120 bash statusline/statusline.sh
  ```
- **Núcleo vendorizado.** La fuente de `arkana_core` está en `lib/arkana_core/`; este plugin lleva su copia en `scripts/_core/` (un plugin instalado no puede leer a otro). Se regenera con `bash ../../scripts/vendor-core.sh` (y `--check` verifica que está al día). `install` copia esa copia a `~/.claude/arkana-statusline/arkana_core/`.
- `arkana-plugin.json` declara los skills (`install`, `check`, `fix`, `refresh`), el comando de `check` y el dato local `arkana-statusline/state/sessions/`.
