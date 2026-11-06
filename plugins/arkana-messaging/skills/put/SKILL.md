---
name: put
description: Guarda un mensaje del componente actual para otros componentes (aviso, tarea, revisión o pregunta) en el almacén local, o lo cierra (hecho o descartado) o lo comenta. Quién envía lo decide el directorio de trabajo, no un argumento. Pide confirmación antes de guardar. Acepta --dry-run y --json.
---

# arkana-messaging:put

Los mensajes viven en `.arkana/arkana-messaging/state/messages/` (local, sin git ni red). **El remitente es el componente que contiene el directorio actual (o ARKANA)**; no existe `--repo` ni `--from`. Entre desarrolladores solo viajan por `arkana-workspace:export`/`import`.

Herramienta: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" put ...` (`--help` para todo).

## Tipos

| Tipo | Para qué | Estado | Exige |
|---|---|---|---|
| `notice` | Informar de algo | no tiene | — |
| `task` | Pedir que hagan algo | `open` → `done` / `discarded` | `--instructions-file` y `--criteria-file` |
| `review` | Pedir una revisión | igual | `--body-file` o `--instructions-file` |
| `question` | Preguntar | igual; se cierra con la respuesta | cuerpo o un asunto que la formule |

## Clases: una vez o permanente (`repeat`)

- **`once`** (por defecto): se atiende y se cierra. La confirmación (`done`/`discarded`) es **por destinatario** (`confirmaciones`); `estado` solo pasa a `done` cuando todos confirman. Si hay varios destinatarios, ARKANA o el remitente indican a quién con `--for <componente>`.
- **`repeat`** (`--repeat` al crear): directriz que debe tenerse en cuenta **siempre** (p. ej. una convención). No se cierra con `done`/`discard`: se da de baja con `delete` (solo el remitente o ARKANA) y se sustituye creando otro (un `repeat` no se reconcilia). Si lo crea ARKANA nace `vigente`; si lo crea otro componente nace `propuesto` y **no se entrega a ningún worker** hasta que ARKANA lo active (`put --activate <id>`, con confirmación del usuario). Con `--to all` el alcance es vivo: lo heredan los componentes que se añadan después.
- Cambiar la clase de uno existente: `put --set-repeticion <id> once|repeat` (remitente o ARKANA).

`para` guarda lo escrito (`all`, alias, lista) y `destinatarios` los reales en ese momento.

## Guardar un mensaje

1. **Destinatarios** (`--to`): lista de alias separados por comas, `arkana` o `all` (todos los demás, ARKANA incluida; por defecto). Si no es evidente, pregúntalo con `AskUserQuestion`.
2. **Borrador** a partir de lo hecho (no inventes): `--subject` (3 a 80 caracteres, una línea, en español), `--priority high` solo si es urgente, cuerpo (texto libre), instrucciones y criterios (uno por línea) en ficheros del scratchpad, `--refs "<id ...>"`, `--commits "<sha ...>"`. **Nunca incluyas credenciales, tokens ni datos personales.**
3. **Enséñalo y pide confirmación** (`AskUserQuestion`: «Guardar», «Editar», «Cancelar»). Puedes ensayar con `--dry-run`.
4. Ejecuta `put --type <tipo> --subject "<texto>" --to <destinos> [...]`. Devuelve `OK|put|<id> guardada ...`; el `id` es la referencia.
5. **Reconciliar:** si la salida trae `INFO|reconcile|...`, hay varios mensajes abiertos para el mismo destinatario. Revisa con `reconcile candidates --to <alias> --json` y, **solo si de verdad se solapan**, propón al usuario un único resumen (ver `sync`). No reconcilies sin su confirmación.

## Cerrar o comentar

Con confirmación, para una `task`, `review` o `question` abierta que te llega a ti (o que escribiste):

```bash
put --done <id> --result "<qué se hizo o la respuesta>"
put --discard <id> --reason "<por qué>"
put --comment <id> --note "<texto>"
```

`--done`/`--discard` son idempotentes (repetirlos dice «ya estaba»; cambiar de `done` a `discard` o al revés da error); `--comment` añade una entrada cada vez. En un mensaje con varios destinatarios, `--done`/`--discard` cierran solo el tuyo (o el de `--for <componente>`). Un `notice` no tiene estado y un `repeat` no se cierra.

Solo ARKANA (la orquesta de `arkana-agentic`) anota las entregas a workers: `put --delivered <id> --for <componente> --plan <P> --task <T>` y `put --executed <id> --for <componente> ...` (en un `repeat`, «ejecutado» significa «al menos una vez»). No las uses a mano.

## Reglas

- Un componente solo publica como él mismo y solo ve lo dirigido a él o escrito por él; ARKANA lo ve todo.
- Sin confirmación del usuario no guardes ni cierres nada.
