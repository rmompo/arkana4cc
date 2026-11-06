#!/usr/bin/env python3
"""Mensajes de arkana-messaging que se entregan a los workers. Solo lectura del almacén; las marcas las escribe `messaging.sh`.

Un worker no es un actor de la mensajería: no tiene shell, ni hooks, ni acceso a `.arkana`. Lo que sabe de los mensajes es lo que el
orquestador (este módulo, desde `launch`) copia en su prompt, como DATOS (nunca instrucciones).

Además de eso, el orquestador o el usuario pueden indicar mensajes concretos para una tarea con `--from-message <id>` (campo `mensajes_extra` de la tarea):
se entregan igual (como datos, con su entrega anotada y marcados ejecutados al aceptar la tarea) y el mensaje debe ir dirigido al componente de la tarea.

Qué se entrega a un componente (alias):
  - los `repeat` vigentes (directrices: en cada lanzamiento, hasta que se den de baja);
  - los `once` accionables (task | review | question) abiertos, que el componente no ha confirmado ni ejecutado ya.
  No se entregan: avisos `once`, `repeat` propuestos, borrados o reconciliados.

La lista de cada tarea se congela al arrancar el plan (`plan start`) para que lo que se entrega sea lo que el usuario vio al aprobar.
`mark` anota con `messaging.sh put --delivered|--executed` (solo ARKANA); si la mensajería no está instalada, avisa y no falla.
Variable de pruebas: ARKANA_MESSAGING_CMD (comando que sustituye a messaging.sh).
"""
import glob
import os
import shlex
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
import paths  # noqa: E402
import state  # noqa: E402
from arkana_core import datafiles, manifest, netguard  # noqa: E402

HIDDEN = ("deleted", "reconciled")
ACTIONABLE = ("task", "review", "question")
MAX_CHARS = 6000
MAX_ONE = 1500


def messages_dir():
    return os.path.join(paths.plugins_dir(), "arkana-messaging", "state", "messages")


def load_all():
    """{id: mensaje} de lo legible; almacén ausente → {}."""
    res = {}
    d = messages_dir()
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if f.endswith(".json"):
            m = datafiles.read_json(os.path.join(d, f))
            if isinstance(m, dict) and m.get("id") == f[:-5]:
                res[m["id"]] = m
    return res


def _dest(m, alias):
    if m.get("repeticion") == "repeat" and "all" in (m.get("para") or []):
        return alias != m.get("de")                                  # alcance vivo: los componentes de ahora
    return alias in (m.get("destinatarios") or m.get("para") or [])


def _confirmed(m, alias):
    c = (m.get("confirmaciones") or {}).get(alias)
    return bool(c)


def applies(m, alias):
    """¿Se entrega este mensaje a `alias` ahora?"""
    if m.get("estado") in HIDDEN or m.get("de") == alias or not _dest(m, alias):
        return False
    if m.get("repeticion") == "repeat":
        return m.get("vigencia", "vigente") == "vigente"
    return (m.get("tipo") in ACTIONABLE and m.get("estado") == "open" and not _confirmed(m, alias)
            and alias not in (m.get("ejecuciones") or {}))


def select(alias, msgs=None):
    """Mensajes para `alias`: primero los repeat, luego los once, cada grupo por id."""
    alias = manifest.canon(alias)
    msgs = load_all() if msgs is None else msgs
    sel = [m for m in msgs.values() if applies(m, alias)]
    return sorted(sel, key=lambda m: (m.get("repeticion") != "repeat", m["id"]))


# ---------- lista congelada por tarea ----------
def frozen_file(pid):
    return os.path.join(state.plan_dir(pid), "mensajes.json")


def freeze(pid, tareas):
    """Congela, por tarea, los ids que se entregarán. Se llama al arrancar el plan."""
    msgs = load_all()
    lista = {t["id"]: [m["id"] for m in select(t["repo"], msgs)] for t in tareas}
    state.save_json(frozen_file(pid), lista)
    return lista


def frozen_ids(pid, tid):
    f = frozen_file(pid)
    if not os.path.exists(f):
        return []
    return (state.load_json(f) or {}).get(tid, [])


def for_task(pid, tarea):
    """Mensajes (contenido actual) de la tarea: los de su lista congelada (se saltan los dados de baja o que ya no aplican) y, después, los indicados a mano
    con `--from-message` (`mensajes_extra`: los eligió el orquestador o el usuario, así que no se les exige `applies`, solo que no estén dados de baja)."""
    msgs = load_all()
    alias = manifest.canon(tarea["repo"])
    res = []
    for i in frozen_ids(pid, tarea["id"]):
        m = msgs.get(i)
        if m and m.get("estado") not in HIDDEN and (m.get("repeticion") != "repeat" or m.get("vigencia", "vigente") == "vigente") and _dest(m, alias):
            res.append(m)
    for i in extras(tarea):
        m = msgs.get(i)
        if m and m.get("estado") not in HIDDEN and all(i != x["id"] for x in res):
            res.append(m)
    return res


# ---------- mensajes indicados a mano (--from-message) ----------
def extras(tarea):
    """Ids de los mensajes que se indicaron a mano para esta tarea."""
    return [i for i in (tarea.get("mensajes_extra") or []) if isinstance(i, str)]


def ids_for(pid, tarea):
    """Ids que se le entregan a la tarea: lista congelada + indicados a mano (sin repetir)."""
    ids = list(frozen_ids(pid, tarea["id"]))
    return ids + [i for i in extras(tarea) if i not in ids]


def listing(pid, tarea):
    """Lo que recibirá el worker, para `plan show`: lista congelada (o lo que se entregaría ahora si aún no hay) más los indicados a mano."""
    if os.path.exists(frozen_file(pid)):
        return for_task(pid, tarea)
    base = select(tarea["repo"])
    msgs = load_all()
    return base + [msgs[i] for i in extras(tarea) if i in msgs and msgs[i].get("estado") not in HIDDEN and all(i != x["id"] for x in base)]


def check_for(mid, alias, msgs=None):
    """(mensaje, None) si existe, no está dado de baja y va dirigido a `alias`; si no, (None, motivo)."""
    msgs = load_all() if msgs is None else msgs
    m = msgs.get(mid)
    if not m:
        return None, f"no existe el mensaje {mid} (se busca en {messages_dir()})"
    if m.get("estado") in HIDDEN:
        return None, f"el mensaje {mid} está {m['estado']}: no se puede indicar"
    alias = manifest.canon(alias)
    if m.get("de") == alias or not _dest(m, alias):
        return None, f"el mensaje {mid} no va dirigido a {alias} (destinatarios: {', '.join(m.get('destinatarios') or m.get('para') or [])})"
    return m, None


def recipients(m):
    """Componentes (no ARKANA) a los que va dirigido el mensaje, en el orden del manifiesto."""
    import repos
    return [r for r in repos.repo_ids() if r != "arkana" and _dest(m, manifest.canon(r)) and m.get("de") != r]


def instruction_lines(m, tope=40):
    """Instrucciones del mensaje para copiarlas a una tarea: sus `instrucciones`; si no tiene, las líneas de su cuerpo; si tampoco, el asunto."""
    ins = [str(x).strip()[:600] for x in (m.get("instrucciones") or []) if str(x).strip()]
    if not ins:
        ins = [l.strip()[:600] for l in str(m.get("cuerpo") or "").splitlines() if l.strip()]
    return (ins or [str(m.get("asunto") or m["id"])])[:tope]


def criteria_of(m):
    """Criterios de aceptación de una tarea a partir de los `criterios` del mensaje (o uno genérico si no los tiene)."""
    cr = [{"id": f"C{i}", "descripcion": str(x).strip()[:600]} for i, x in enumerate(m.get("criterios") or [], 1) if str(x).strip()]
    return cr or [{"id": "C1", "descripcion": f"Se cumple lo que pide el mensaje {m['id']}: {' '.join(str(m.get('asunto', '')).split())[:200]}"}]


def pointer(m):
    """Línea para el feedback del worker: lo que el orquestador le pide es atender ese mensaje (el texto va en «Mensajes para este componente», como dato)."""
    return f"Atiende lo que pide el mensaje {m['id']} («{' '.join(str(m.get('asunto', '')).split())[:80]}»): su texto está en la sección «Mensajes para este componente»."


def preview(tareas):
    """{tarea: [mensajes]} de lo que se entregaría ahora (lo que enseña `plan show` antes de aprobar)."""
    msgs = load_all()
    return {t["id"]: select(t["repo"], msgs) for t in tareas}


def one_line(m):
    clase = "repeat" if m.get("repeticion") == "repeat" else "once"
    return f"{m['id']} · {clase} · {m.get('tipo')} · de {m.get('de')} · {' '.join(str(m.get('asunto', '')).split())[:80]}"


# ---------- texto para el prompt ----------
def _text(m):
    t = one_line(m)
    if m.get("cuerpo"):
        t += "\n" + m["cuerpo"]
    for lab, k in (("Instrucciones", "instrucciones"), ("Criterios", "criterios")):
        if m.get(k):
            t += f"\n{lab}:\n" + "\n".join(f"- {x}" for x in m[k])
    return t


def render(msgs):
    """Sección del prompt. Si un mensaje no cabe (por mensaje o en total) se da asunto + id."""
    if not msgs:
        return "(ninguno)"
    out, used = [], 0
    for m in msgs:
        t = _text(m)
        if len(t) > MAX_ONE or used + len(t) > MAX_CHARS:
            t = one_line(m) + "\n(texto demasiado largo para incluirlo: pide al orquestador el detalle si lo necesitas)"
        used += len(t)
        out.append(t)
    return "\n\n".join(f"--- {x}" for x in out)


# ---------- marcas ----------
def messaging_cmd():
    env = os.environ.get("ARKANA_MESSAGING_CMD")
    if env:
        return shlex.split(env)
    plugin = os.path.dirname(os.path.dirname(HERE))                  # .../arkana-agentic
    for c in (os.path.join(os.path.dirname(plugin), "arkana-messaging", "scripts", "messaging.sh"),
              *sorted(glob.glob(os.path.expanduser("~/.claude/plugins/cache/arkana/arkana-messaging/*/scripts/messaging.sh")), reverse=True)):
        if os.path.isfile(c):
            return ["bash", c]
    return None


def mark(accion, mid, alias, pid, tid):
    """accion: delivered | executed. (ok, detalle). Nunca lanza: la mensajería ausente o con error es un aviso."""
    cmd = messaging_cmd()
    if not cmd:
        return False, "arkana-messaging no está instalado: no se anota"
    p = netguard.run(cmd + ["put", f"--{accion}", mid, "--for", manifest.canon(alias), "--plan", pid, "--task", tid], timeout=20, cwd=paths.arkana_dir())
    return p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()[-1][:200] if (p.stdout + p.stderr).strip() else f"rc {p.returncode}"
