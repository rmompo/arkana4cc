#!/usr/bin/env python3
"""Herramientas y entorno del workspace: las herramientas declaradas (versión, ruta, paquetes y registros), git, credenciales, red y, si está configurado, Jira (extensión opcional).

  tools.py [--home <dir>] [--json] [--no-network]

Solo lectura. NUNCA imprime valores de `.env`, tokens ni credenciales: solo nombres de variable y hosts. Lo que se espera sale de lo que se declara
con `/arkana-workspace:config tools` (`.arkana/arkana-workspace/tools.json`: `tools[{tool, version, path, packages, registries}]`, `urls` y `ports`; opciones `--package`, `--registry`, `--check-url` y `--port`) y de
`tools[]` de cada componente; en el código no hay ninguna herramienta, versión, paquete ni registro fijados.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
from arkana_core import manifest, output  # noqa: E402
import credentials  # noqa: E402
import proc  # noqa: E402

# Cómo se invoca cada herramienta conocida para saber su versión; cualquier otra se prueba como `<nombre> --version`.
COMMAND = {"node": "node", "npm": "npm", "jdk": "java", "maven": "mvn"}
VERSION_ARGS = {"jdk": ["-version"], "maven": ["-v"], "node": ["-v"], "npm": ["-v"]}


def run(cmd, timeout=6, env=None):
    return proc.run(cmd, timeout, env)


def http_code(url, timeout=8):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def pkg_version(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("version", "")
    except (OSError, ValueError):
        return ""


def tools_file(ws):
    try:
        d = json.loads(Path(os.path.join(ws.state, "arkana-workspace", "tools.json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return d if isinstance(d, dict) else {"tools": d}


def tools_json(ws):
    return [t for t in tools_file(ws).get("tools", []) if isinstance(t, dict) and t.get("tool")]


def declared(ws):
    """{herramienta: {version, path, packages, registries}}: tools.json y, para la versión, `tools[]` de los componentes (tools.json manda)."""
    res = {}
    for a in ws.aliases(include_arkana=False):
        for t in ws.get(a).get("tools", []):
            res.setdefault(t["tool"], {"version": t.get("version", "")})
    for t in tools_json(ws):
        d = res.setdefault(t["tool"], {})
        for k in ("version", "path", "packages", "registries"):
            if t.get(k):
                d[k] = t[k]
    return res


def binary(name, info):
    """Ejecutable de una herramienta: `<path>/bin/<cmd>` si se declaró la ruta; si no, el del PATH."""
    cmd = COMMAND.get(name, name)
    if info.get("path"):
        for c in (os.path.join(os.path.expanduser(info["path"]), "bin", cmd), os.path.join(os.path.expanduser(info["path"]), cmd)):
            if os.path.isfile(c):
                return c
        return None
    return shutil.which(cmd)


def version_of(name, info, java_home=None):
    """Primera versión (números separados por puntos) que imprime la herramienta, o ''. `java_home`: la carpeta del `jdk` declarado (Maven la necesita)."""
    b = binary(name, info)
    if not b:
        return ""
    env = dict(os.environ)
    if info.get("path"):
        env["PATH"] = os.path.join(os.path.expanduser(info["path"]), "bin") + os.pathsep + env.get("PATH", "")
    if java_home:
        env["JAVA_HOME"] = os.path.expanduser(java_home)
    rc, out = run([b] + VERSION_ARGS.get(name, ["--version"]), 8, env)
    m = re.search(r"\d+(?:\.\d+)+|\b\d+\b", out or "")
    return m.group(0) if m else ""


def version_ok(have, want):
    """La versión declarada es un prefijo de la instalada (21 → 21.0.13; 1.8 → 1.8.0)."""
    return not want or have == want or have.startswith(want.rstrip(".") + ".")


def global_packages(name, info):
    """{paquete: versión} instalados globalmente (solo se sabe para Node: `npm ls -g`)."""
    if name != "node":
        return None
    b = binary("npm", {"path": info.get("path")}) if info.get("path") else shutil.which("npm")
    if not b:
        return None
    env = dict(os.environ)
    if info.get("path"):
        env["PATH"] = os.path.join(os.path.expanduser(info["path"]), "bin") + os.pathsep + env.get("PATH", "")
    rc, out = run([b, "ls", "-g", "--depth=0", "--json"], 20, env)
    try:
        return {k: v.get("version", "") for k, v in (json.loads(out).get("dependencies") or {}).items()}
    except (ValueError, AttributeError):
        return {}


def npmrc_registries():
    res = {}
    try:
        for l in Path(os.path.join(os.path.expanduser("~"), ".npmrc")).read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(@[^:]+):registry=(.*)$", l.strip())
            if m:
                res[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return res


def check(ws, network=True):
    home = os.path.expanduser("~")
    rep = output.Report("arkana-workspace", "check-tools", secrets=credentials.secrets(ws.home))
    add = rep.add
    cfg = tools_file(ws)
    add("INFO", "entorno", f"{ws.get('arkana')['alias']} {ws.home}")
    # 1. herramientas declaradas: versión, paquetes globales y registros
    decl = declared(ws)
    if not decl:
        add("INFO", "herramientas", "ninguna herramienta declarada: /arkana-workspace:config tools --tool <nombre> --version <v> [--path <ruta>]")
    for name, info in sorted(decl.items()):
        want = info.get("version", "")
        b = binary(name, info)
        if not b:
            add("FAIL", name, f"{name} no está disponible" + (f" en {info['path']}" if info.get("path") else " en el PATH") + (f" (se espera {want})" if want else ""))
            continue
        have = version_of(name, info, (decl.get("jdk") or {}).get("path"))
        if not have:
            add("OK", name, f"{name} disponible (versión no determinada)")
        elif version_ok(have, want):
            add("OK", name, f"{name} {have}" + (f" (se espera {want})" if want and have != want else ""))
        else:
            add("WARN", name, f"{name} {have} (se espera {want})")
        pk = info.get("packages") or []
        if pk:
            inst = global_packages(name, info)
            for spec in pk:
                m = re.match(r"^(@?[^@]+)(?:@(.+))?$", spec)               # nombre[@versión]; los ámbitos npm empiezan por @
                pname, pver = (m.group(1), m.group(2) or "") if m else (spec, "")
                if inst is None:
                    add("INFO", f"{name}-paquete-{pname}", f"no se sabe comprobar paquetes globales de {name}")
                elif pname not in inst:
                    add("FAIL", f"{name}-paquete-{pname}", f"{pname} no está instalado globalmente" + (f" (se espera {pver})" if pver else ""))
                elif pver and inst[pname] != pver:
                    add("WARN", f"{name}-paquete-{pname}", f"{pname} {inst[pname]} (se espera {pver})")
                else:
                    add("OK", f"{name}-paquete-{pname}", f"{pname} {inst[pname]}")
        regs = info.get("registries") or {}
        if regs:
            have_regs = npmrc_registries()
            for scope, url in sorted(regs.items()):
                got = have_regs.get(scope)
                if not got:
                    add("FAIL", f"registro-{scope}", f"~/.npmrc sin '{scope}:registry=' (se espera {url})")
                elif got.rstrip("/") != url.rstrip("/"):
                    add("WARN", f"registro-{scope}", f"{scope} apunta a {got} (se espera {url})")
                else:
                    code = http_code(url) if network else 1
                    add("OK" if code else "WARN", f"registro-{scope}", f"{scope} → {url}" + (f" (responde HTTP {code})" if network and code else "") if code else f"{scope} → {url} no responde (¿VPN?)")
    # 2. Node activo (Claude Code y sus plugins lo necesitan, sea cual sea el proyecto)
    if shutil.which("node"):
        nv = run(["node", "-v"])[1].lstrip("v")
        major = int(nv.split(".")[0]) if nv.split(".")[0].isdigit() else 0
        if major >= 20:
            add("OK", "node-claude", f"Node activo {nv} (≥ 20 para Claude Code y sus plugins)")
        else:
            add("WARN", "node-claude", f"Node activo {nv}: Claude Code y sus plugins piden ≥ 20")
    else:
        add("FAIL", "node-claude", "node no está en el PATH (Claude Code y sus plugins lo necesitan)")
    # 3. git
    add("OK" if shutil.which("git") else "FAIL", "git", "git " + run(["git", "--version"])[1].split()[-1] if shutil.which("git") else "git no instalado")
    lp = run(["git", "config", "--global", "core.longpaths"])[1]
    add("OK" if lp == "true" else "WARN", "git-longpaths", "core.longpaths=true" if lp == "true" else "core.longpaths no está a true (rutas largas, p. ej. node_modules)")
    ch = run(["git", "config", "--global", "credential.helper"])[1]
    add("OK" if ch else "WARN", "git-credential-helper", "credential.helper configurado" if ch else "sin credential.helper (los repos pueden llevar el asistente de Arkana: credentials.py wire-git)")
    # 4. credenciales por host (solo existencia; jamás se muestran)
    hosts = sorted({ws.get(a).get("remote_host") for a in ws.aliases() if ws.get(a).get("remote_host")})
    gc = ""
    try:
        gc = Path(os.path.join(home, ".git-credentials")).read_text(encoding="utf-8")
    except OSError:
        pass
    store = credentials.load(ws.home)
    for h in hosts:
        via_token = any((ws.get(a).get("remote_host") == h and (ws.get(a).get("git") or {}).get("token_ref") in store) for a in ws.aliases())
        if f"@{h}" in gc or via_token:
            add("OK", f"cred-{h}", f"credencial guardada para {h}" + (" en .credentials" if via_token else ""))
        else:
            add("FAIL", f"cred-{h}", f"sin credencial guardada para {h}")
    # 5. red: los remotos de los componentes y las URL declaradas (config tools --url)
    if network:
        for url in [f"https://{h}" for h in hosts] + [u for u in cfg.get("urls", []) if isinstance(u, str)]:
            code = http_code(url)
            add("OK" if code else "WARN", f"red-{url.split('//')[1]}", f"{url} responde (HTTP {code})" if code else f"{url} no responde (¿VPN?)")
    # 6. puertos declarados (config tools --port)
    for p in [p for p in cfg.get("ports", []) if isinstance(p, int)]:
        s = socket.socket(); s.settimeout(0.5)
        busy = s.connect_ex(("127.0.0.1", p)) == 0
        s.close()
        add("WARN" if busy else "OK", f"puerto-{p}", "ocupado dentro del contenedor (¿servidor en marcha?)" if busy else "libre (no verificable desde fuera del contenedor)")
    # 7. auxiliares
    for t in ("jq", "python3"):
        add("OK" if shutil.which(t) else "FAIL", t, f"{t} disponible" if shutil.which(t) else f"{t} no instalado (lo usan la statusline y los scripts)")
    # Jira es una extensión OPCIONAL: solo se comprueba si el manifiesto tiene el bloque `jira` (config jira).
    if ws.data.get("jira"):
        # 11. Jira (conector global; credenciales en ~/.ia4d/.env o en .credentials)
        jenv = os.path.join(home, ".ia4d", ".env")
        if not os.path.isfile(jenv):
            jenv = os.path.join(home, ".claude", ".env")
        if os.path.isfile(jenv):
            vals = dict(l.rstrip("\n").split("=", 1) for l in Path(jenv).read_text(encoding="utf-8", errors="replace").splitlines() if "=" in l and not l.startswith("#"))
            missing = [v for v in ("JIRA_HOST", "JIRA_API_TOKEN") if v not in vals]
            empty = [v for v in ("JIRA_HOST", "JIRA_API_TOKEN") if v in vals and (not vals[v].strip() or re.match(r"^<.*>$", vals[v].strip()))]
            if missing:
                add("FAIL", "jira-env", f"faltan variables en {jenv}: {' '.join(missing)}")
            elif empty:
                add("WARN", "jira-env", f"variables sin valor en {jenv}: {' '.join(empty)}")
            else:
                add("OK", "jira-env", f"{jenv} con JIRA_HOST y JIRA_API_TOKEN (valores no mostrados)")
        else:
            add("FAIL", "jira-env", "no existe ~/.ia4d/.env (credenciales globales del conector: JIRA_HOST, JIRA_AUTH_TYPE, JIRA_API_TOKEN)")
        # 11b. el conector Jira solo lee ~/.ia4d/.env: un .env de proyecto con JIRA_* no sirve
        for comp in ws.aliases(include_arkana=False):
            pe = os.path.join(ws.path(comp), ".env")
            if os.path.isfile(pe):
                try:
                    if re.search(r"(?m)^JIRA_", Path(pe).read_text(encoding="utf-8", errors="replace")):
                        add("WARN", "jira-env-proyecto", f"{os.path.relpath(pe, ws.root)} define variables JIRA_*, pero el conector no lee el .env del proyecto (moverlas a ~/.ia4d/.env)", )
                        break
                except OSError:
                    pass
        # 11c. conector Jira (MCP) del plugin ia4d-project-bridge: definido, con dependencias y sin duplicado en ajustes
        pb_root = ""
        rc, out = run(["claude", "plugin", "list"], timeout=8)
        if rc == 0:
            m = re.search(r"ia4d-project-bridge@[^\n]*\n(?:[^\n]*\n)*?\s*Read from:\s*(\S+)", out)
            pb_root = m.group(1) if m else ""
        pb_root = pb_root or os.path.join(home, ".claude", "plugins", "marketplaces", "ia4d-expert-agents-marketplace", "plugins", "ia4d-project-bridge")
        jc = os.path.join(pb_root, "mcp", "jira-connector")
        if not os.path.isfile(os.path.join(jc, "index.js")):
            add("FAIL", "jira-mcp", f"plugin ia4d-project-bridge no instalado o sin conector ({os.path.join(jc, 'index.js')})")
        else:
            add("OK", "jira-mcp", f"conector definido por el plugin ia4d-project-bridge ({jc})")
            add("OK" if os.path.isdir(os.path.join(jc, "node_modules")) else "FAIL", "jira-mcp-deps",
                "dependencias instaladas" if os.path.isdir(os.path.join(jc, "node_modules")) else f"faltan las dependencias del conector (npm install en {jc}): el servidor no arranca")
        sett = os.path.join(home, ".claude", "settings.json")
        if os.path.isfile(sett):
            try:
                c = (json.loads(Path(sett).read_text(encoding="utf-8")).get("mcpServers") or {}).get("jira-connector")
            except ValueError:
                c = None
            if not c:
                add("OK", "jira-mcp-duplicado", "sin definición duplicada en ~/.claude/settings.json")
            else:
                args = c.get("args") or [""]
                rota = "${CLAUDE_PLUGIN_ROOT}" in args[0] or not os.path.exists(args[0])
                add("FAIL" if rota else "WARN", "jira-mcp-duplicado", "'jira-connector' duplicado en ~/.claude/settings.json" + (" con ruta rota" if rota else "") + ": sobra, la definición buena es la del plugin")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tools.py")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-network", action="store_true")
    a = ap.parse_args(argv)
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
    except manifest.ManifestError as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = check(ws, not a.no_network)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
