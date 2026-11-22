---
name: install
description: Monta de una vez el espacio de trabajo mínimo de Arkana - comprueba que están los plugins arkana-*, inicia el git de ARKANA y pide usuario y correo (y el token si va a un remoto), crea la disposición de .arkana y el registro del proyecto, instala statusline, mensajería, orquestación, conocimiento, tareas y notas, aplica los permisos, revisa credenciales y herramientas y verifica todo. No añade componentes - al terminar sugiere dar de alta el primero. Repetible e idempotente, con ensayo previo de cada paso. Also invoked explicitly as /arkana:install
allowed-tools: [AskUserQuestion]
version: 9
---

# arkana:install

Pone en marcha el workspace entero con **un solo comando**, en el orden correcto, reutilizando la instalación de cada plugin. Todo es repetible: lo que ya está bien no se toca. Lo único que no hace es dar de alta los **componentes** del proyecto: eso es lo último que se sugiere.

El plan lo calcula un script de solo lectura que localiza dónde está cada plugin (cada uno vive en su propia copia de la caché) y devuelve las órdenes con rutas absolutas:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/pipeline.py" plan [--home <dir>] [--json]
```

Líneas `ESTADO|ID|detalle` (`OK`, `INFO`, `WARN`, `FAIL`) y una línea `PASO|id|plugin|ensayo|aplicar` por paso.

## Pasos

1. **Plan.** Ejecuta `plan`. Si hay `FAIL`:
   - `plugin:<nombre>` = ese plugin no está instalado. **No lo instales tú** (es de la persona usuaria): dile exactamente qué ejecutar (`/plugin install <nombre>@arkana`, luego `/reload-plugins`) y para.
   - `home` = la carpeta no sirve (es `/` o su carpeta personal): que cree una carpeta propia para Arkana y ejecute desde ella (o pase `--home`). Explícalo y para.
   Con `INFO git` no pares: el paso `git` lo resuelve (más abajo).
2. **Confirma el sitio.** Enséñale la carpeta de Arkana resuelta (`home`), si el workspace es nuevo o ya existe y si ya es un repo git (`git.repo` del `--json`). Si es nuevo, pregunta con `AskUserQuestion` si crearlo ahí («Sí, crear aquí» / «Cancelar»); si no es un repo git, di que se iniciará (la statusline necesita git para mostrar la rama y el estado).
3. **Ejecuta cada `PASO`, en el orden devuelto**, con esta rutina: lanza su orden `ensayo`, resume lo que cambiaría (líneas `DRY`) y, tras confirmar, lanza `aplicar`. Ofrece en la primera confirmación «Aplicar todos los pasos» para no preguntar cada vez; los pasos marcados con ⚠ se confirman siempre.

   | Paso | Qué hace | Notas |
   |------|----------|-------|
   | `git` | `git init` de la carpeta de ARKANA (rama `main`, sin commits) y su **usuario y correo** (a nivel de repo, nunca `~/.gitconfig`) | ver «Usuario, correo, remoto y token»: añade `--name` y `--email` a sus dos órdenes |
   | `layout` | `.arkana/` (y `/.arkana/` en el `.gitignore` de ARKANA), manifiesto con ARKANA, `local.json`, `tools.json`, registro del workspace | se niega si hay un plan activo |
   | `evolve` | migraciones: registro del proyecto con UUID y carpetas fijas | exige git; no hace commit |
   | `statusline` ⚠ | copia la statusline a `~/.claude/arkana-statusline/` y activa `statusLine` | si ya hay otra, explícalo: Arkana gobierna las statuslines y la ajena pasa a ser un proveedor (no se pierde; se sigue viendo fuera de ARKANA) |
   | `messaging` ⚠ | almacén de mensajes y plugin habilitado en `~/.claude/settings.json` | toca ajustes de usuario |
   | `agentic` ⚠ | carpetas de orquestación y plugin habilitado | toca ajustes de usuario |
   | `knowledge` | andamiaje de ARKANA: `arkana-incoming/` (con su `.gitignore`), `arkana-knowledge/` y `arkana-docs/{src,md,out}/`, cada carpeta final con su `.gitkeep`, e índice | `evolve` ya las crea; este paso lo garantiza |
   | `todo` | lista de tareas local | — |
| `note` | almacén de notas local | — |
   | `permisos` | permisos de ARKANA (modelo en `/arkana-workspace:rew-grants`) | solo añade lo que falta; deja copia |
   | `credenciales` | diagnóstico | si falta una clave, indica `credentials.py set <CLAVE>` (valor por stdin); nunca pidas un token por argumento |
   | `herramientas` | lista las herramientas declaradas | ver abajo |
   | `verificacion` | diagnóstico agregado de todo el workspace | solo lectura |

4. **Usuario, correo, remoto y token** (lo pide la propia instalación; nada de esto se inventa ni se deduce):
   - **Paso `git`**: si `git.repo` es falso o `git.identity` es falso, pregunta con `AskUserQuestion` el **nombre de usuario** y el **correo** para los commits de ARKANA (la persona los escribe en «Other»; si ya hay `git.name`/`git.email` del repo, ofrécelos como primera opción) y lanza el ensayo y el aplicar del paso con `--name "<nombre>" --email "<correo>"` añadidos al final. Sin ellos el script sale con código 2 y no escribe la identidad. Con identidad ya puesta, el paso solo informa.
   - **Remoto de ARKANA** (justo después del paso `layout`, cuando ya existe el manifiesto): pregunta si ARKANA se guardará en un repositorio remoto. Si es que sí (o `git.remote` ya era verdadero), pide: **URL** del remoto (sin usuario ni contraseña dentro), **usuario git** y el **nombre de la clave del token** (por defecto `GIT_TOKEN_ARKANA`). Aplica `python3 <components.py de arkana-workspace> edit --alias arkana --remote <URL> --git-username <usuario> --token-ref <CLAVE>` (la ruta sale de la orden del paso `layout`: cambia `layout.py init` por `components.py edit …`) y, si el repo aún no tiene `origin`, `git -C <home> remote add origin <URL>` (con confirmación).
   - **El token no pasa por la conversación ni por un argumento.** Pide a la persona que lo guarde ella en **su propia terminal**: `python3 <credentials.py> set <CLAVE>` (la ruta sale de la orden del paso `credenciales`: cambia `check` por `set <CLAVE>`; lo pide sin mostrarlo). Cuando confirme, comprueba con `credentials.py has <CLAVE>` (solo el código de salida) y ejecuta `credentials.py wire-git arkana`. No lo leas, no lo repitas y no lo pegues en ninguna orden.
   - Sin remoto, no se pide token: ARKANA queda solo local.
5. **Herramientas** (aquí, no en los plugins, vive todo lo específico del stack). Si no hay ninguna declarada, pregunta qué usa el proyecto (por ejemplo `node`, `jdk`, `maven`) y su versión, y decláralas con `/arkana-workspace:config tools`. **Arkana nunca instala herramientas**: si falta alguna (`pdftotext` para convertir PDF, `git-lfs` si el repo lo usa, la declarada…), dile cuál, para qué y el comando exacto, y que lo instale él (puede pedir su contraseña de sudo).
6. **Si un paso falla**, no sigas ni fuerces: explica la causa (código de salida 3 = sin git o cambios sin commitear en lo que escribiría la migración) y deja que la persona la resuelva; al relanzar `/arkana:install` se reanuda donde se quedó, porque cada paso es idempotente.
7. **Resumen.** Tabla con cada paso (hecho / ya estaba / pendiente / falló) y los `FAIL` y `WARN` de la verificación. Recuerda **recargar los plugins** (`/reload-plugins`) o reiniciar Claude Code para ver la statusline y los hooks. Todo queda **sin commitear**: que revise `git status` y haga él commit y push. Si la verificación deja `FAIL` o `WARN` corregibles (identidad git del repo, `.gitignore` de `.env`, `.gitattributes`, `.env.example`), ofrece `/arkana-workspace:fix`, que los arregla uno a uno con confirmación; no los corrijas tú dentro de la instalación.
8. **Cierre: sugiere el primer componente.** El workspace mínimo ya está, pero aún no hay ningún repo del proyecto. Termina siempre proponiendo darlo de alta: «Siguiente paso: añade tu primer componente con `/arkana-workspace:component add` (alias, ruta, tipo y remoto; te pedirá usuario y correo git y, si tiene remoto, su token). Después, `/arkana-workspace:check` y `/arkana-workspace:fix`». Si ya había componentes, dilo en su lugar y sugiere `/arkana-workspace:check`.

## Reglas

- No hagas `commit`, `push` ni `git add`. No toques otros ajustes de `settings.json` que los de cada paso.
- No instales plugins ni herramientas; pídeselos a la persona usuaria con la orden exacta.
- **Nunca pidas, leas ni pases un token** (ni como argumento ni por la conversación): solo el **nombre** de su clave; el valor lo teclea la persona en su terminal.
- La identidad git (usuario y correo) se fija solo **a nivel de repo**; no toques `~/.gitconfig`.
- No muestres valores de `.env`, tokens ni credenciales.
- No des de alta componentes por tu cuenta: solo se sugiere.
