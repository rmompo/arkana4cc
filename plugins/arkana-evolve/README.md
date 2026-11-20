# arkana-evolve

Evolución de una instalación de Arkana. Arkana cambia con el tiempo (carpetas del repo, registro del proyecto, formato de los datos) y este plugin lleva cualquier instalación de una versión del layout a la siguiente con **migraciones numeradas, idempotentes y con `--dry-run`**, en lugar de una lista de pasos manuales que se desincroniza.

Es uno de los plugins del marketplace `arkana` (visión de conjunto en [`../README.md`](../README.md)). Solo usa la biblioteca estándar de Python 3. **No depende de ningún otro plugin**: debe poder ejecutarse cuando el layout está desactualizado, y es el único que conoce los formatos antiguos.


**Aviso de la statusline.** `check` y `apply` avisan (`WARN|statusline`) si la copia de `~/.claude/arkana-statusline` lleva un núcleo anterior al de esta instalación: es un dato de usuario fuera del repo que ninguna migración toca; se refresca con `/arkana-statusline:fix`.

## Skills

| Skill | Qué hace |
|---|---|
| `apply` | Aplica las migraciones pendientes en orden. Con `--dry-run` ensaya sin escribir; con `--to N` se detiene en una migración. |
| `check` | Solo lectura: sello de layout, migraciones aplicadas y pendientes, integridad. Lo ejecuta también el `/arkana-workspace:check` agregado. |

No ofrece `install` ni `fix` (no hay nada que instalar y reparar es aplicar): es la excepción al contrato común de [`../docs/PLUGIN-CONTRACT.md`](../docs/PLUGIN-CONTRACT.md).

```bash
python3 scripts/lib/evolve.py check [--home DIR] [--json]
python3 scripts/lib/evolve.py apply [--dry-run] [--to N] [--home DIR] [--json]
```

Salida `ESTADO|ID|detalle` y `RESUMEN|n FAIL|n WARN` ([`OUTPUT-CONTRACT`](../docs/OUTPUT-CONTRACT.md)). Códigos: `0` sin fallos, `1` fallo, `2` uso, `3` precondición no cumplida (sin workspace, sin git, o cambios sin commitear en lo que va a escribir la migración).

## Cómo funciona

- **Migraciones.** Módulos de `scripts/lib/migrations/` (`m0001_…`, `m0002_…`). Las `b*` son de **base** (formatos antiguos anteriores a la 0001) y se ejecutan antes que las numéricas. Cada una define `ID`, `TITLE`, `SCOPE`, `touches(ctx)`, `detect(ctx)` (¿está pendiente?), `apply(ctx, rep)` y `verify(ctx)`.
- **Ámbito.** `shared`: cambia ficheros **versionados** del repo de ARKANA. Una persona migra, revisa `git status`, commitea y empuja; el resto hace pull y vuelve a ejecutar `apply`, que solo aplica su parte local. `local`: cambia `.arkana/` (copia `tar.gz` previa en `.arkana/arkana-workspace/bak/`, modo 600).
- **Sellos.** El layout compartido está en `arkana-project.json` (`layout`; lo sube el motor tras cada migración numérica); lo aplicado en esta instalación, en `.arkana/arkana-evolve/state.json` (clase `local`).
- **Seguridad.** Nunca hace commit ni push. Las migraciones no pisan lo que ya existe. Las compartidas exigen repo git y que los ficheros **versionados** que van a escribirse no tengan cambios sin commitear. Si hace falta una herramienta que no está, se **pide** al usuario; nunca se instala.

## Migraciones

Las `b*` son de **base**: convierten formatos antiguos y se ejecutan antes que las numéricas; no hacen nada en instalaciones al día. Cuando ninguna instalación necesite una, se borra.

| Id | Ámbito | Qué hace |
|---|---|---|
| `b001` | local | Layout de `arkana-agentic`: `planes/ run/ sesiones/ …` → `config/ state/ data/`; se niega con un plan activo o un worker vivo; copia a `data/archive/` los planes de `orquestacion/archivo/`. |
| `b002` | local | `novedades/` (comunicaciones antiguas) → mensajes de `arkana-messaging`; no sobrescribe ni toca el origen. Después, `/arkana-messaging:sync`. |
| `b003` | shared | `conocimiento/` → `arkana-knowledge/` con `git mv`; `tipo/modulos` → `topic/components`; el historial pasa al `## Changelog`; borra `.historial/` y `catalogo.json`. |
| `b004` | local + shared | Alias histórico `shared` → `arkana` en mensajes, planes, libro, tareas, `local.json` y notas. |
| `0001` | shared + local | Crea `arkana-project.json` (registro compartido: UUID del workspace y de cada pieza —`arkana` incluida— con su alias, sello `layout`) y las carpetas fijas con `.gitkeep`: `arkana-incoming/` (cuyo `.gitignore` interno ignora todo salvo `.gitignore` y `.gitkeep`), `arkana-knowledge/`, `arkana-docs/` y `arkana-docs/md/`. Si el registro ya existe (otra persona migró) no regenera ningún UUID. |
| `0002` | local + shared | Arkana deja de escribir en `CLAUDE.md` / `CLAUDE.local.md` de los repos: quita de ellos los bloques gestionados (`arkana:messaging`, `arkana:commits`, `arkana:agentic`), renombra `CLAUDE.local.md` a `ARKANA.local.md`, añade `.claude/`, `.claude-session/` y `ARKANA.local.md` a `.git/info/exclude` y retira `seed_file` del manifiesto. No toca un fichero versionado con cambios sin commitear. Las directrices las inyectan los hooks. |
| `0003` | shared + local | Cada componente lleva su `id` (UUID del registro del proyecto) en el manifiesto local; da de alta en el registro lo que solo esté en el manifiesto; no reescribe ningún id y avisa si el registro llama de otro modo a un componente (renombrado por otra persona). |
| `0004` | shared | Conocimiento con identidad UUID: cada nota recibe un `id` UUID (el identificador antiguo pasa a `slug`), sus `components` pasan de alias a ids del registro, gana `fuentes`, las notas sueltas se mueven a `arkana-knowledge/<topic>/` (con `git mv`) y se retira el `catalog.json` versionado (el índice ahora es local y derivado). No cambia versiones ni Changelogs. |
| `0005` | shared | Layout 5: solo estampa el sello. El manifiesto admite los campos de componente de esquema 2 (`watch` y los de referencia) y los plugins nuevos avisan, ante un layout superior al que conocen, de que hay que actualizar el plugin. No cambia ningún dato. |
| `0006` | local | Layout 6: las tareas de `arkana-todo` pasan al modelo de estados nuevo (`open`→`pending`, `deleted`→`removed`, `normal`→`medium`, `all`/vacío→`*`). Reescribe `.arkana/arkana-todo/todos.json` con copia previa; no toca el resto de campos. Sin `todos.json` o ya migrado no hace nada (el sello sube igual). |
| `0007` | shared | Layout 7: el repo de ARKANA ignora `.arkana/` (datos locales y `.credentials`): añade `/.arkana/` a su `.gitignore` si git no lo ignora ya por otra vía. Si algún fichero de `.arkana/` ya estaba versionado lo **avisa** (`git rm -r --cached .arkana`, rotar credenciales): ignorarlo no lo saca de git. Cambio versionado: una sola persona lo aplica y commitea. |

## Pruebas

```bash
bash tests/run-tests.sh [-v|-q]      # sin red ni API; repos git temporales y HOME falso
```

El núcleo común es la copia vendorizada de `lib/arkana_core/` en `scripts/_core/` (se regenera con `bash scripts/vendor-core.sh` desde la raíz del repo; no se edita aquí).
