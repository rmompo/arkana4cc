---
name: install
description: Monta de una vez el espacio de trabajo mínimo de Arkana - comprueba que están los plugins arkana-*, crea la disposición de .arkana y el registro del proyecto, instala statusline, mensajería, orquestación, conocimiento y tareas, aplica los permisos, revisa credenciales y herramientas y verifica todo. No añade componentes - al terminar sugiere dar de alta el primero. Repetible e idempotente, con ensayo previo de cada paso. Also invoked explicitly as /arkana:install
allowed-tools: [AskUserQuestion]
version: 1
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
   - `home` = no hay dónde crear el workspace: debe ejecutarse dentro del repo git de Arkana (o con `--home`). Explícalo y para.
   Con `WARN git`, pide que haga `git init` y un primer commit (las migraciones de `arkana-evolve` lo necesitan) y para.
2. **Confirma el sitio.** Enséñale la carpeta de Arkana resuelta (`home`) y si el workspace es nuevo o ya existe. Si es nuevo, pregunta con `AskUserQuestion` si crearlo ahí («Sí, crear aquí» / «Cancelar»).
3. **Ejecuta cada `PASO`, en el orden devuelto**, con esta rutina: lanza su orden `ensayo`, resume lo que cambiaría (líneas `DRY`) y, tras confirmar, lanza `aplicar`. Ofrece en la primera confirmación «Aplicar todos los pasos» para no preguntar cada vez; los pasos marcados con ⚠ se confirman siempre.

   | Paso | Qué hace | Notas |
   |------|----------|-------|
   | `layout` | `.arkana/`, manifiesto con ARKANA, `local.json`, `tools.json`, registro del workspace | se niega si hay un plan activo |
   | `evolve` | migraciones: registro del proyecto con UUID y carpetas fijas | exige git; no hace commit |
   | `statusline` ⚠ | copia la statusline a `~/.claude/arkana-statusline/` y activa `statusLine` | si ya hay otra, **no la pises**: explica y pregunta; solo entonces repite con `--replace` |
   | `messaging` ⚠ | almacén de mensajes y plugin habilitado en `~/.claude/settings.json` | toca ajustes de usuario |
   | `agentic` ⚠ | carpetas de orquestación y plugin habilitado | toca ajustes de usuario |
   | `knowledge` | carpetas `arkana-incoming/`, `arkana-knowledge/`, `arkana-docs/` e índice | — |
   | `todo` | lista de tareas local | — |
   | `permisos` | permisos de ARKANA (modelo en `/arkana-workspace:rew-grants`) | solo añade lo que falta; deja copia |
   | `credenciales` | diagnóstico | si falta una clave, indica `credentials.py set <CLAVE>` (valor por stdin); nunca pidas un token por argumento |
   | `herramientas` | lista las herramientas declaradas | ver abajo |
   | `verificacion` | diagnóstico agregado de todo el workspace | solo lectura |

4. **Herramientas** (aquí, no en los plugins, vive todo lo específico del stack). Si no hay ninguna declarada, pregunta qué usa el proyecto (por ejemplo `node`, `jdk`, `maven`) y su versión, y decláralas con `/arkana-workspace:config tools`. **Arkana nunca instala herramientas**: si falta alguna (`pdftotext` para convertir PDF, `git-lfs` si el repo lo usa, la declarada…), dile cuál, para qué y el comando exacto, y que lo instale él (puede pedir su contraseña de sudo).
5. **Si un paso falla**, no sigas ni fuerces: explica la causa (código de salida 3 = sin git o cambios sin commitear en lo que escribiría la migración) y deja que la persona la resuelva; al relanzar `/arkana:install` se reanuda donde se quedó, porque cada paso es idempotente.
6. **Resumen.** Tabla con cada paso (hecho / ya estaba / pendiente / falló) y los `FAIL` y `WARN` de la verificación. Recuerda **recargar los plugins** (`/reload-plugins`) o reiniciar Claude Code para ver la statusline y los hooks. Todo queda **sin commitear**: que revise `git status` y haga él commit y push.
7. **Cierre: sugiere el primer componente.** El workspace mínimo ya está, pero aún no hay ningún repo del proyecto. Termina siempre proponiendo darlo de alta: «Siguiente paso: añade tu primer componente con `/arkana-workspace:component add` (alias, ruta, tipo y remoto). Después, `/arkana-workspace:check` y `/arkana-workspace:fix`». Si ya había componentes, dilo en su lugar y sugiere `/arkana-workspace:check`.

## Reglas

- No hagas `commit`, `push` ni `git add`. No toques otros ajustes de `settings.json` que los de cada paso.
- No instales plugins ni herramientas; pídeselos a la persona usuaria con la orden exacta.
- No muestres valores de `.env`, tokens ni credenciales.
- No des de alta componentes por tu cuenta: solo se sugiere.
