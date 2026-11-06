"""doctor: salud del entorno de arkana-agentic. Una linea ESTADO|ID|detalle por comprobacion y RESUMEN|n FAIL|n WARN.
--quick (por defecto): sin coste. --deep: ademas ejecuta la bateria de contencion con claude real (si esta instalada).
--need-network: sin DNS de los remotos, red-vpn es un FAIL (por defecto es un WARN: agentic solo trabaja en local)."""
import json
import os
import shutil
import stat as st
import subprocess
import sys

import launch
import paths
import repos
import state
import validate

MIN_VERSION = (2, 1, 259)
FLAGS = ["--restricted", "--tools", "--json-schema", "--permission-prompts", "--max-budget-usd", "--no-session-persistence", "--settings"]
# --max-turns y --append-system-prompt-file no salen en --help (verificados en la fase 0); los ejercita --deep
REQUIRED_TOOLS = ["timeout", "setsid", "flock", "python3", "jq", "git", "sha256sum"]


def claude_bin():
    return os.environ.get("ARKANA_AGENTIC_CLAUDE_BIN", "claude")


def checks(profundo, necesita_red=False):
    res = []

    def r(estado, id_, detalle):
        res.append((estado, id_, detalle))

    cb = claude_bin()
    exe = shutil.which(cb) if os.sep not in cb else (cb if os.access(cb, os.X_OK) else None)
    if not exe:
        r("FAIL", "claude-version", f"no se encuentra '{cb}'")
        r("FAIL", "claude-flags", "sin claude no se pueden comprobar los flags")
    else:
        try:
            v = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
            num = tuple(int(x) for x in v.split()[0].split(".")[:3])
            r("OK" if num >= MIN_VERSION else "FAIL", "claude-version", f"{v} (minima {'.'.join(map(str, MIN_VERSION))})")
        except (ValueError, IndexError, subprocess.SubprocessError, OSError):
            r("WARN", "claude-version", "no se pudo leer la version")
        try:
            h = subprocess.run([exe, "--help"], capture_output=True, text=True, timeout=30).stdout
            falta = [f for f in FLAGS if f not in h]
            r("OK" if not falta else "FAIL", "claude-flags", "todos presentes" if not falta else "faltan: " + " ".join(falta))
        except (subprocess.SubprocessError, OSError):
            r("WARN", "claude-flags", "no se pudo ejecutar claude --help")
    falta = [u for u in REQUIRED_TOOLS if not shutil.which(u)]
    r("OK" if not falta else "FAIL", "utilidades", "presentes" if not falta else "faltan: " + " ".join(falta))
    r("OK", "metadatos-ubicacion", paths.plugins_dir().replace(os.path.expanduser("~"), "~"))
    import migrate
    base = state.base_dir()
    viejo = migrate.pending(base) if os.path.isdir(base) else []
    r("WARN" if viejo else "OK", "layout", ("layout antiguo (" + ", ".join(o for o, _ in viejo) + "): ejecuta fix") if viejo else "layout config/state/data")
    if os.path.isdir(base):
        modo = st.S_IMODE(os.stat(base).st_mode)
        r("OK" if modo == 0o700 else "WARN", "runtime-700", f"{base.replace(os.path.expanduser('~'), '~')} modo {oct(modo)[2:]}")
    else:
        r("OK", "runtime-700", "el directorio de ejecucion aun no existe (se crea con 700 al usarlo)")
    try:
        pol = state.load_policy()
        pdef = state.load_json(os.path.join(state.PLUGIN, "policy", "politica.default.json"))
        errs = validate.check_schema(pdef, state.load_json(os.path.join(state.PLUGIN, "schemas", "politica.schema.json")))
        malos = [k for k, v in pol["limites"].items() if v > pol["techos"][k]]
        r("OK" if not errs and not malos else "FAIL", "politica-valida", "valida" if not (errs or malos) else "; ".join(errs[:3] + [f"{k} supera su techo" for k in malos]))
    except (ValueError, KeyError, FileNotFoundError) as e:
        r("FAIL", "politica-valida", str(e)[:150])
    w = launch.live_worker()
    ruta_w = os.path.join(state.run_dir(), "worker.json")
    if w:
        r("WARN", "worker-huerfano", f"hay un worker vivo ({w['plan']}/{w['tarea']}, pid {w['pid']})")
    elif os.path.exists(ruta_w):
        r("WARN", "worker-huerfano", "worker.json apunta a un proceso que ya no existe: ejecuta /arkana-agentic:fix")
    else:
        r("OK", "worker-huerfano", "ninguno")
    sh = repos.repo_path("arkana")
    ajustes = os.path.join(sh, ".claude", "settings.local.json")
    try:
        with open(ajustes, encoding="utf-8") as fh:
            perm = json.load(fh).get("permissions", {})
        ask = "\n".join(perm.get("ask", []))
        faltan = [h for h in ("plan approve", "approve", "reject", "policy set", "integrate merge", "integrate discard")
                  if f"agentic.sh {h}" not in ask]
        if "agentic.sh" not in json.dumps(perm.get("allow", [])) or "claude -p" not in json.dumps(perm.get("deny", [])):
            r("WARN", "permisos-arkana", "faltan las reglas del orquestador (agentic.sh en allow, 'claude -p' en deny): /arkana-workspace:fix")
        elif faltan:
            r("WARN", "permisos-arkana", f"faltan reglas 'ask' (esas decisiones se ejecutarian SIN pedir confirmacion): {', '.join(faltan)}: /arkana-workspace:fix")
        else:
            r("OK", "permisos-arkana", "reglas del orquestador presentes (allow, ask en las decisiones humanas, deny de claude -p)")
    except (OSError, ValueError):
        r("WARN", "permisos-arkana", f"no se pudo leer {ajustes}")
    if repos.net_hosts():
        ok, det = repos.net_preflight()
        # agentic solo edita y hace commits locales en la rama del plan (no hace fetch, pull ni push): sin red es un aviso, no una parada.
        # Con --need-network (antes de algo que sí use los remotos) vuelve a ser un FAIL.
        if ok:
            r("OK", "red-vpn", det)
        elif necesita_red:
            r("FAIL", "red-vpn", det)
        else:
            r("WARN", "red-vpn", f"{det}. No bloquea: el plan solo edita y hace commits locales, sin fetch ni push; con la red caída no podrás bajar ni subir (--need-network lo exige)")
    import adapters
    tipos = adapters.types_of()
    falt = []
    # El verificador NO hereda el PATH del shell: solo ve las carpetas bin de las herramientas declaradas en tools.json (con ruta) y VERIFIER_PATH.
    declaradas = {t.get("tool") for t in adapters._tools_json() if t.get("path") and os.path.isdir(os.path.join(os.path.expanduser(t["path"]), "bin"))}
    if "node" in declaradas:
        declaradas.add("npm")                                                 # npm vive en la carpeta bin de node
    for tool in adapters.tools_required():
        cmd = {"jdk": "java", "maven": "mvn"}.get(tool, tool)
        if tool not in declaradas and not shutil.which(cmd, path=adapters.VERIFIER_PATH):
            falt.append(tool)
    r("WARN" if falt else "OK", "adaptadores", ("tipos " + ", ".join(tipos) + "; el verificador no encuentra: " + ", ".join(falt) + " (declara su ruta: arkana-workspace:config tools --tool <nombre> --version <v> --path <ruta>)") if falt else "tipos " + ", ".join(tipos) + ": herramientas requeridas disponibles")
    import install
    bs = install.block_state()
    r("OK" if bs == "OK" else "WARN", "instrucciones", "bloque arkana:agentic al día en el CLAUDE.md de ARKANA" if bs == "OK" else f"bloque arkana:agentic: {bs} (ejecuta /arkana-agentic:install)")
    if profundo:
        bat = os.path.join(state.PLUGIN, "tests", "containment", "run-containment.sh")
        if os.path.exists(bat):
            try:
                p = subprocess.run(["bash", bat, "-q"], capture_output=True, text=True, timeout=1800)
                ultima = (p.stdout.strip().splitlines() or ["sin salida"])[-1]
                r("OK" if p.returncode == 0 else "FAIL", "contencion", ultima.replace("RESUMEN|contencion|", "")[:200])
            except subprocess.TimeoutExpired:
                r("FAIL", "contencion", "la bateria de contencion supero los 30 minutos")
        else:
            r("WARN", "contencion", "la bateria de contencion aun no esta instalada")
    return res


def main(a):
    res = checks(getattr(a, "deep", False), getattr(a, "necesita_red", False))
    if getattr(a, "json", False):
        print(json.dumps([{"estado": e, "id": i, "detalle": d} for e, i, d in res], ensure_ascii=False, indent=2))
    else:
        for e, i, d in res:
            print(f"{e}|{i}|{d}")
    fails = sum(1 for e, _, _ in res if e == "FAIL")
    warns = sum(1 for e, _, _ in res if e == "WARN")
    if not getattr(a, "json", False):
        print(f"RESUMEN|{fails} FAIL|{warns} WARN")
    return 1 if fails else 0
