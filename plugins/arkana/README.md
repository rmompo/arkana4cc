# arkana

Punto de entrada de Arkana: **un solo comando** que monta el espacio de trabajo mínimo encadenando la instalación del resto de plugins. No añade componentes del proyecto: al terminar sugiere dar de alta el primero.

```
/plugin marketplace add <repositorio de Arkana>
/plugin install arkana@arkana           # y el resto de plugins arkana-*
/arkana:install
```

## Skills

| Skill | Qué hace |
|-------|----------|
| `install` | Comprueba plugins, crea `.arkana/` y el registro del proyecto, instala statusline, mensajería, orquestación, conocimiento, tareas y notas, aplica permisos, revisa credenciales y herramientas, verifica y sugiere el primer componente. |

## Pipeline

Orden fijo; cada paso se ensaya (`--dry-run`), se confirma y se aplica. Repetir `/arkana:install` solo añade lo que falta.

| # | Paso | Plugin | Escribe en |
|---|------|--------|------------|
| 1 | `git` | arkana | `git init` de la carpeta de ARKANA (si no es un repo) y su usuario y correo, a nivel de repo; sin commits |
| 2 | `layout` | arkana-workspace | `.arkana/` (arkana.json, manifiesto, local.json, tools.json) y `~/.arkana/workspaces.json` |
| 3 | `evolve` | arkana-evolve | registro del proyecto (`arkana-project.json`) y carpetas fijas; sin commit |
| 4 | `statusline` | arkana-statusline | despachador en `~/.claude/arkana-statusline/` y `statusLine` de `~/.claude/settings.json` (si hay otra, pasa a ser un proveedor: con Arkana instalada, Arkana gobierna las statuslines) |
| 5 | `messaging` | arkana-messaging | `.arkana/arkana-messaging/` y ajustes de usuario |
| 6 | `agentic` | arkana-agentic | `.arkana/arkana-agentic/` y ajustes de usuario |
| 7 | `knowledge` | arkana-knowledge | `arkana-incoming/`, `arkana-knowledge/`, `arkana-docs/{src,md,out}/` (andamiaje completo) |
| 8 | `todo` | arkana-todo | `.arkana/arkana-todo/` |
| 9 | `note` | arkana-note | `.arkana/arkana-note/` |
| 10 | `permisos` | arkana-workspace | `.claude/settings.local.json` de ARKANA |
| 11 | `credenciales` | arkana-workspace | nada (diagnóstico) |
| 12 | `herramientas` | arkana-workspace | `tools.json` solo si se declaran; **nunca instala nada** |
| 13 | `verificacion` | arkana-workspace | nada (diagnóstico) |

Después: `/arkana-workspace:component add` para el primer componente (pide usuario y correo git y, si tiene remoto, su token).

**Andamiaje.** La instalación deja en el repo de ARKANA todas las carpetas finales con su `.gitkeep` (para que git las versione y existan en cualquier clon): `arkana-incoming/` (además con su `.gitignore`, que ignora todo salvo `.gitignore` y `.gitkeep`), `arkana-knowledge/` y `arkana-docs/src/`, `md/` y `out/`. `arkana-docs/` solo las agrupa y no lleva `.gitkeep`. Lo crean `evolve` (migración `0001`) y `knowledge install`, ambos idempotentes, y `tests/test_scaffolding.py` lo comprueba de punta a punta. Lo local (`.arkana/`) queda ignorado.

**Credenciales.** El paso `git` pregunta el usuario y el correo de ARKANA (`gitinit.py --name --email`; sin ellos no se escribe nada). Si ARKANA va a un remoto, se piden la URL, el usuario y el **nombre** de la clave del token (`GIT_TOKEN_ARKANA` por defecto) y la persona guarda el valor **en su propia terminal** con `credentials.py set` (lo pide sin mostrarlo): el token no pasa por la conversación ni por ningún argumento. Lo mismo ocurre al añadir un componente con remoto.

## Plan de solo lectura

```bash
python3 scripts/lib/pipeline.py plan [--home <dir>] [--json]
python3 scripts/lib/gitinit.py --home <dir> [--name N] [--email E] [--branch main] [--dry-run]   # el paso `git`
```

Localiza cada plugin (hermano de este en el repo, o la versión más reciente de `~/.claude/plugins/cache/arkana/<plugin>/`), resuelve la carpeta de Arkana (`--home`, `$ARKANA_HOME`, un ancestro con `.arkana/arkana.json` o la raíz git del directorio actual) y devuelve las órdenes con rutas absolutas: `ESTADO|ID|detalle` y `PASO|id|plugin|ensayo|aplicar`. Código de salida 1 si falta un plugin o no hay dónde crear el workspace. No escribe nada.

## Reglas

- No instala plugins ni herramientas: pide a la persona usuaria la orden exacta.
- No hace commit ni push.
- Sin núcleo vendorizado: solo biblioteca estándar de Python.

## Pruebas

```bash
bash tests/run-tests.sh [-q]     # desde plugins/arkana
claude plugin validate plugins/arkana
```
