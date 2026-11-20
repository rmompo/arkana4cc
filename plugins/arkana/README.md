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
| 1 | `layout` | arkana-workspace | `.arkana/` (arkana.json, manifiesto, local.json, tools.json) y `~/.arkana-workspaces.json` |
| 2 | `evolve` | arkana-evolve | registro del proyecto (`arkana-project.json`) y carpetas fijas; sin commit |
| 3 | `statusline` | arkana-statusline | `~/.claude/arkana-statusline/` y `statusLine` de `~/.claude/settings.json` |
| 4 | `messaging` | arkana-messaging | `.arkana/arkana-messaging/` y ajustes de usuario |
| 5 | `agentic` | arkana-agentic | `.arkana/arkana-agentic/` y ajustes de usuario |
| 6 | `knowledge` | arkana-knowledge | `arkana-incoming/`, `arkana-knowledge/`, `arkana-docs/` |
| 7 | `todo` | arkana-todo | `.arkana/arkana-todo/` |
| 8 | `note` | arkana-note | `.arkana/arkana-note/` |
| 9 | `permisos` | arkana-workspace | `.claude/settings.local.json` de ARKANA |
| 10 | `credenciales` | arkana-workspace | nada (diagnóstico) |
| 11 | `herramientas` | arkana-workspace | `tools.json` solo si se declaran; **nunca instala nada** |
| 12 | `verificacion` | arkana-workspace | nada (diagnóstico) |

Después: `/arkana-workspace:component add` para el primer componente.

## Plan de solo lectura

```bash
python3 scripts/lib/pipeline.py plan [--home <dir>] [--json]
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
