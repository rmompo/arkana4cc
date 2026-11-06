#!/usr/bin/env python3
"""Statusline de Arkana (dos líneas). Lee el JSON de Claude Code por stdin y escribe las líneas a stdout. Solo biblioteca estándar.

Cada componente se muestra como `ALIAS@rama:indicadores`, sin fondos de relleno: el alias en naranja (brillante el del directorio actual), la `@` y los `:` en rojo, el nombre de la
rama en gris (gris brillante la del componente actual) e indicadores en inverso, pegados y sin espacios (`◌353●6⇣?`), cada uno con texto negro sobre el color de su estado: ◌ sin seguimiento (rojo), ✚ preparados,
● modificados, ⇡ commits sin subir y ⇣ por bajar (amarillo) y ✓ si el local está limpio (verde); todo git local salvo ⇣ y solo los distintos de cero. ⇣ es lo único que depende
del remoto: el número si el último fetch de ese componente fue hace menos de 30 min, `⇣?` en su mismo hueco si no se sabe; sin rama remota no hay ⇡ ni ⇣.
Línea 1: ARKANA y, separados por ` · ` (el punto en azul oscuro), `[■]` en inverso (texto negro sobre el color de su estado; gris en reposo) seguido de `sin plan activo` (con plan activo `[▶] 002/007 worker@plan:tarea descripción`), `P0.00 S0.00`
(texto rojo oscuro, sin fondo; P plan, S sesión), `Sonnet 5.5 (medium)` (texto magenta, sin fondo) y `C61 S0 W19` (sin fondo; el color del texto según el tramo: 0–40 verde,
41–75 amarillo, 76–100 rojo brillante). Línea 2: los demás componentes, separados también por ` · `.

Ancho estrecho (`fit_line1`, función pura, solo sobre los componentes de la línea 2): se acortan con `…` las ramas de los que no son el actual; luego sus alias; luego pasan
a más líneas. Nunca se recortan los contadores, ARKANA, el componente actual ni el plan, el coste, el modelo y el uso (en la línea 1 solo cede la descripción del plan).

Es la ÚNICA escritora de `.arkana/arkana-statusline/state/sessions/<sid>.json` (`{"session_id","cost_usd","ts"}`): el coste real de la sesión, que
solo recibe la statusline; los hooks de arkana-agentic lo leen para el libro de sesiones. Solo se reescribe si cambia.
"""
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "..", "scripts", "_core")):          # copia instalada (arkana_core al lado) o árbol del plugin
    if os.path.isdir(os.path.join(_p, "arkana_core")):
        sys.path.insert(0, _p)

RESET = "\033[0m"
GRAY = "\033[90m"
ALIAS_CUR = "\033[1;38;5;214m"                                                # alias actual: texto naranja brillante, sin fondo
ALIAS_OTHER = "\033[38;5;208m"                                                 # resto de alias: texto naranja, sin fondo
BRANCH_CUR, BRANCH_OTHER = "\033[37m", "\033[90m"                              # rama: gris brillante (la del componente actual) y gris normal
RED, GREEN = "\033[31m", "\033[32m"
B_RED, B_GREEN, B_YELLOW, B_BLUE, B_CYAN = "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[96m"
IND_BG = {B_RED: "\033[30;41m", B_YELLOW: "\033[30;43m", B_GREEN: "\033[30;42m", B_CYAN: "\033[30;46m"}   # indicadores en inverso: texto negro sobre el color de su estado
STATE_BG = {GRAY: "\033[30;100m", B_GREEN: "\033[30;102m", B_RED: "\033[30;101m", B_CYAN: "\033[30;106m", B_YELLOW: "\033[30;103m"}   # estado del plan `[■]` en inverso: texto negro sobre el color del símbolo
MAGENTA = "\033[35m"                                                          # modelo: texto magenta, sin fondo
DARK_BLUE = "\033[34m"                                                        # separador ·: azul oscuro
FRESH_SECONDS = 30 * 60
RESERVED = 5                      # Claude Code reserva ~4 columnas a la derecha; 1 de holgura
ANSI = re.compile(r"\033\[[0-9;]*m")


def plain(s):
    return ANSI.sub("", s)


def c(color, text):
    return f"{color}{text}{RESET}"


def trunc(text, n):
    return text if len(text) <= n else text[:max(n - 1, 1)] + "…"


def money(x):
    return f"{float(x):.2f}"


# ---------- git local ----------
def fetch_age(path):
    g = os.path.join(path, ".git")
    try:
        if os.path.isfile(g):                                            # worktree o submódulo: «gitdir: <ruta>»
            with open(g, encoding="utf-8") as f:
                d = f.read().strip().split(":", 1)[1].strip()
            g = d if os.path.isabs(d) else os.path.join(path, d)
        return time.time() - os.stat(os.path.join(g, "FETCH_HEAD")).st_mtime
    except (OSError, IndexError):
        return None


def git_state(path):
    """dict (branch, untracked, staged, modified, ahead, behind|None, has_remote) o None si no es un repo. Solo git local, sin red."""
    try:
        p = subprocess.run(["git", "--no-optional-locks", "-C", path, "status", "--porcelain=v2", "--branch", "-uall"], capture_output=True, text=True,
                           timeout=4, env=dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C"), stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if p.returncode != 0:
        return None
    s = {"branch": "", "untracked": 0, "staged": 0, "modified": 0, "ahead": 0, "behind": None, "has_remote": False}
    upstream = False
    for l in p.stdout.splitlines():
        if l.startswith("# branch.head "):
            s["branch"] = l.split(" ", 2)[2]
        elif l.startswith("# branch.upstream "):
            upstream = True
        elif l.startswith("# branch.ab "):
            a, b = l.split()[2:4]
            s["ahead"], behind = int(a[1:]), int(b[1:])
            age = fetch_age(path)
            s["behind"] = behind if age is not None and age < FRESH_SECONDS else None
        elif l.startswith("? "):
            s["untracked"] += 1
        elif l[:2] in ("1 ", "2 "):
            xy = l.split()[1]
            s["staged"] += xy[0] != "."
            s["modified"] += xy[1] != "."
        elif l.startswith("u "):
            s["modified"] += 1
    s["has_remote"] = upstream
    if not upstream:
        s["ahead"] = 0
    return s


# ---------- línea 1 (funciones puras) ----------
def branch_parts(s, branch_max=None):
    """[(símbolo, cantidad, color|None)] de la rama y sus indicadores. Solo la cantidad lleva color (el símbolo conserva el del bloque); ✓ va entero en verde."""
    br = s["branch"] or "?"
    parts = [(trunc(br, branch_max) if branch_max else br, "", None)]
    for sym, key, col in (("◌", "untracked", B_RED), ("✚", "staged", B_YELLOW), ("●", "modified", B_YELLOW), ("⇡", "ahead", B_YELLOW)):
        if s[key]:
            parts.append((sym, str(s[key]), col))
    if not (s["untracked"] or s["staged"] or s["modified"] or s["ahead"]):
        parts.append(("", "✓", B_GREEN))
    if s["has_remote"]:
        if s["behind"] is None:
            parts.append(("⇣", "?", B_CYAN))
        elif s["behind"]:
            parts.append(("⇣", str(s["behind"]), B_YELLOW))
    return parts


def branch_label(s, branch_max=None):
    """` develop ◌13 ✚113 ●84 ⇡2 ⇣3 ` sin los espacios de los extremos. Los contadores nunca se recortan."""
    return " ".join(p + q for p, q, _ in branch_parts(s, branch_max))


def entry(item, branch_max=None, alias_max=None):
    """(texto plano, texto con ANSI) de un componente: `ALIAS@rama:indicadores`. @ y : rojos, rama en gris (más claro la del actual) e indicadores en inverso."""
    alias = item["alias"] if not alias_max or item["current"] else trunc(item["alias"], alias_max)
    a_ansi = f"{ALIAS_CUR if item['current'] else ALIAS_OTHER}{alias}{RESET}"
    s = item["state"]
    if s is None:
        return alias + " —", a_ansi + " " + c(GRAY, "—")
    parts = branch_parts(s, None if item["current"] else branch_max)
    branch, ind = parts[0][0], parts[1:]
    base = BRANCH_CUR if item["current"] else BRANCH_OTHER
    head = f"{a_ansi}{c(RED, '@')}{base}{branch}{RESET}"
    if not ind:
        return f"{alias}@{branch}", head
    plain_ind = "".join(p + q for p, q, _ in ind)                                # sin espacios: cada indicador ya es un bloque de color
    ansi_ind = "".join(f"{IND_BG[col]}{p}{q}{RESET}" for p, q, col in ind)
    return f"{alias}@{branch}:{plain_ind}", f"{head}{c(RED, ':')}{ansi_ind}"


SEP_PLAIN, SEP_ANSI = " · ", f" {DARK_BLUE}·{RESET} "                  # separador entre componentes y entre secciones: · en azul oscuro
LEVELS = [(None, None), (8, None), (5, None), (5, 4), (3, 3)]            # (máx. rama, máx. alias) de los componentes NO actuales


def fit_line1(items, usable):
    """Líneas (con ANSI) que contienen los componentes sin pasar de `usable` columnas: acorta ramas, luego alias y, por último, reparte en más líneas."""
    def build(level):
        bm, am = level
        return [entry(it, bm, am) for it in items]

    def width(es):
        return sum(len(p) for p, _ in es) + len(SEP_PLAIN) * max(len(es) - 1, 0)

    for level in LEVELS:
        es = build(level)
        if width(es) <= usable:
            return [SEP_ANSI.join(a for _, a in es)]
    lines, cur = [], []
    for e in build(LEVELS[-1]):                                          # empaqueta por orden: ARKANA primero, nada se recorta
        if cur and width(cur + [e]) > usable:
            lines.append(cur)
            cur = []
        cur.append(e)
    if cur:
        lines.append(cur)
    return [SEP_ANSI.join(a for _, a in ln) for ln in lines]


# ---------- línea 2 ----------
def pct_block(label, value):
    """`C35` sin fondo: color del texto según el tramo (0–40 verde, 41–75 amarillo, 76–100 rojo brillante)."""
    v = round(float(value))
    fg = 32 if v <= 40 else 33 if v <= 75 else 91
    return f"\033[{fg}m{label}{v}{RESET}", f"{label}{v}"


def plan_view(linea, sid, now, pid_alive):
    """Estado del plan para la línea 2 a partir de linea.json (lo reescribe el motor en cada transición; aquí no se calcula nada)."""
    estado = (linea or {}).get("estado") or ""
    ts = (linea or {}).get("ts")
    age = 0
    if ts:
        try:
            age = int((now - datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp()) / 60)
        except ValueError:
            age = 0
    if estado in ("completado", "detenido", "fallido") and age > 30:
        estado = ""
    if sid and (linea or {}).get("session_id") != sid:
        estado = ""                                                      # el plan es de otra sesión de Claude: en esta no hay plan
    v = {"sym": "■", "color": GRAY, "desc": "sin plan activo", "cuenta": "", "omit": 0, "ident": None, "gasto": 0.0}
    if not estado or not linea.get("plan"):
        return v
    t = linea.get("tareas") or {}
    plan, tarea, repo, pid = linea["plan"], linea.get("tarea"), linea.get("repo"), linea.get("worker_pid")
    v["ident"] = (repo, plan, tarea) if tarea and repo else (None, plan, None)
    if t.get("total"):
        v["cuenta"] = "%03d/%03d" % (int(t.get("actual") or t.get("hechas") or 0), int(t["total"]))
        v["omit"] = int(t.get("omitidas") or 0)
    v["gasto"] = float(linea.get("gasto_usd") or 0)
    asunto, gate = linea.get("asunto_corto") or "", linea.get("gate")
    if estado == "en_ejecucion":
        if pid and not pid_alive(int(pid)):
            v.update(sym="✗", color=B_RED, desc="worker interrumpido: ejecuta /arkana-agentic:fix")
        elif not pid and age >= 10:
            v.update(sym="✗", color=B_RED, desc=f"sin actividad desde hace {age} min")
        elif not pid:
            v.update(sym="▶", color=B_GREEN, desc="el orquestador decide el siguiente paso")
        else:
            v.update(sym="▶", color=B_GREEN, desc=asunto or "tarea en curso")
    elif estado == "esperando_usuario":
        v.update(sym="?", color=B_CYAN, desc=(asunto + " " if asunto else "") + "(esperando tu respuesta" + (f": {gate}" if gate else "") + ")")
    elif estado == "pausado":
        v.update(sym="‖", color=B_YELLOW, desc="pausado")
    elif estado == "completado":
        v.update(sym="✓", color=B_GREEN, desc="plan completado")
    elif estado == "detenido":
        v.update(sym="■", color=B_RED, desc="plan detenido")
    elif estado == "fallido":
        v.update(sym="✗", color=B_RED, desc="plan fallido")
    return v


def line2(plan, session_cost, model, effort, usage, usable):
    """Segmentos separados por ` · `: plan | `P0.00 S0.00` (rojo oscuro) | modelo (magenta) | `C35 S2 W6`. Solo se recorta la descripción del plan."""
    cost = f"P{money(plan['gasto'])} S{money(session_cost or 0)}"
    model_txt = f"{model}" + (f" ({effort})" if effort else "") if model else ""
    blocks = [pct_block(l, v) for l, v in usage if v is not None]

    def compose(desc):
        pa = [f"{STATE_BG[plan['color']]}[{plan['sym']}]{RESET}"]                  # el estado va en inverso, con el color de fondo de su símbolo
        pp = [f"[{plan['sym']}]"]
        if plan["cuenta"]:
            pa.append(c(GRAY, plan["cuenta"])); pp.append(plan["cuenta"])
        if plan["omit"]:
            pa.append(c(GRAY, "(") + c(RED, "✗") + c(GRAY, f"{plan['omit']})")); pp.append(f"(✗{plan['omit']})")
        if plan["ident"]:
            repo, pl, tarea = plan["ident"]
            if repo:
                pa.append(c(B_YELLOW, repo) + c(B_RED, "@") + c(B_BLUE, pl) + c(B_RED, ":") + c(B_BLUE, tarea)); pp.append(f"{repo}@{pl}:{tarea}")
            else:
                pa.append(c(B_BLUE, pl)); pp.append(pl)
        if desc:
            pa.append(c(GRAY, desc)); pp.append(desc)
        segs = [(" ".join(pa), " ".join(pp)), (c(RED, cost), cost)]
        if model_txt:
            segs.append((c(MAGENTA, model_txt), model_txt))
        if blocks:
            segs.append((" ".join(a for a, _ in blocks), " ".join(p for _, p in blocks)))
        return SEP_ANSI.join(a for a, _ in segs), len(SEP_PLAIN.join(p for _, p in segs))

    desc = plan["desc"]
    out, n = compose(desc)
    if n > usable and desc:
        avail = usable - (n - len(desc))
        desc = trunc(desc, avail) if avail >= 6 else ""
        out, n = compose(desc)
    return out


def render(data, width):
    """Todas las líneas de la statusline como lista de cadenas con ANSI (función pura: no lee nada)."""
    usable = width - RESERVED
    head, rest = data["items"][:1], data["items"][1:]
    first = ""
    room = usable
    if head:                                                             # ARKANA (o la única pieza) va entera delante del plan, el coste, el modelo y el uso
        plain, ansi = entry(head[0])
        first = ansi + SEP_ANSI
        room = usable - len(plain) - len(SEP_PLAIN)
    lines = [first + line2(data["plan"], data["session_cost"], data["model"], data["effort"], data["usage"], room)]
    if rest:                                                             # el resto de componentes, en la línea siguiente (más si no caben)
        lines += fit_line1(rest, usable)
    if data.get("aviso"):
        lines.append(c(B_YELLOW, "⚠ " + data["aviso"]))
    return lines


# ---------- entrada/salida ----------
def term_width():
    if os.environ.get("COLUMNS", "").isdigit():
        return int(os.environ["COLUMNS"])
    for fd in (2, 1, 0):
        try:
            return os.get_terminal_size(fd).columns
        except OSError:
            pass
    try:
        with open("/dev/tty") as f:
            return os.get_terminal_size(f.fileno()).columns
    except OSError:
        return 120


def pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write_session_cost(home, sid, cost):
    """ÚNICA escritora del coste real de la sesión. Solo si cambia; modo 600 en carpeta 700."""
    if not sid or not re.fullmatch(r"[A-Za-z0-9_-]+", sid) or not cost or cost <= 0:
        return
    base = os.environ.get("ARKANA_STATUSLINE_DIR") or os.path.join(home, ".arkana", "arkana-statusline")
    d = os.path.join(base, "state", "sessions")
    f = os.path.join(d, sid + ".json")
    prev = read_json(f)
    if isinstance(prev, dict) and prev.get("cost_usd") == cost:
        return
    try:
        os.makedirs(d, mode=0o700, exist_ok=True)
        tmp = f + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"session_id": sid, "cost_usd": cost, "ts": int(time.time())}, fh)
        os.replace(tmp, f)
    except OSError:
        pass


def collect(inp):
    """Lee el entorno (workspace, git, plan) y devuelve los datos de render."""
    cwd = (inp.get("workspace") or {}).get("project_dir") or (inp.get("workspace") or {}).get("current_dir") or os.getcwd()
    home = ws = None
    aviso = None
    try:
        from arkana_core import locate, manifest
        home = locate.find_home(cwd)
        ws = manifest.load(home) if home else None
    except Exception as e:                                               # sin manifiesto legible no hay componentes: se dice, no se pierde la línea en silencio
        aviso = "workspace no cargado: " + " ".join(str(e).split())[:110] + " (¿copia de la statusline desactualizada? /arkana-statusline:fix)"
        home = ws = None
    if ws is not None:
        cur = ws.owner_of(cwd)
        aliases = ["arkana"] + [a for a in ws.aliases(False) if ws.get(a).get("statusline", ws.get(a).get("type") != "docs") is not False]
        paths = {a: ws.path(a) for a in aliases}
        names = {a: manifest.display(a) for a in aliases}
    else:
        base = os.path.basename(cwd.rstrip("/")) or "~"
        aliases, paths, names, cur = [base], {base: cwd}, {base: base}, base
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        states = dict(zip(aliases, ex.map(lambda a: git_state(paths[a]) if os.path.isdir(paths[a]) else None, aliases)))
    items = [{"alias": names[a], "current": a == cur, "state": states[a]} for a in aliases]
    sid = inp.get("session_id")
    linea = None
    if home:
        ad = os.environ.get("ARKANA_AGENTIC_DIR") or os.path.join(home, ".arkana", "arkana-agentic")
        linea = read_json(os.path.join(ad, "state", "run", "linea.json")) or read_json(os.path.join(ad, "run", "linea.json"))
    cost = (inp.get("cost") or {}).get("total_cost_usd")
    cost = float(cost) if isinstance(cost, (int, float)) else None
    if home:
        write_session_cost(home, sid, cost)
    cw, rl = inp.get("context_window") or {}, inp.get("rate_limits") or {}
    return {"aviso": aviso, "items": items, "plan": plan_view(linea, sid, time.time(), pid_alive), "session_cost": cost,
            "model": (inp.get("model") or {}).get("display_name") or "", "effort": (inp.get("effort") or {}).get("level"),
            "usage": [("C", cw.get("used_percentage")), ("S", (rl.get("five_hour") or {}).get("used_percentage")),
                      ("W", (rl.get("seven_day") or {}).get("used_percentage"))]}


def main():
    try:
        inp = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        inp = {}
    try:
        print("\n".join(render(collect(inp), term_width())))
    except Exception as e:                                               # una statusline nunca debe romper la sesión
        print(f"arkana-statusline: {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
