"""Utilidades de las pruebas de arkana-workspace: rutas del plugin y el manifiesto de pruebas (`seed`). No tocan nada real."""
import json
import os
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(AQUI, ".."))
SCRIPTS = os.path.join(PLUGIN, "scripts")
sys.dont_write_bytecode = True

def sh(cmd, cwd=None, env=None, entrada=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, input=entrada)


# Componentes de pruebas (alias neutros): alias, tipo, carpeta (relativa a la raíz del workspace), seed_file
SEED_COMPONENTS = [
    ("app", "node", "app", "CLAUDE.local.md"),
    ("api", "maven", "api", "CLAUDE.local.md"),
    ("app-web", "node", "app/src/web", "CLAUDE.local.md"),
    ("app-ui", "node", "app/src/ui", "CLAUDE.local.md"),
    ("docs", "docs", "docs", "CLAUDE.md"),
    ("specs", "docs", "specs", "CLAUDE.md"),
]


def seed(home, root, dry=False):
    """Escribe el manifiesto de pruebas (ARKANA + SEED_COMPONENTS, con el remoto git de cada carpeta si lo tiene) y llama a `layout.init` para lo demás
    (arkana.json, local.json, tools.json y el registro). Devuelve el informe de `init`."""
    sys.path.insert(0, os.path.join(SCRIPTS, "lib"))
    import layout
    data, _ = layout.build_manifest(home, root)
    for alias, tipo, carpeta, seed_file in SEED_COMPONENTS:
        ap = os.path.join(root, carpeta)
        c = {"alias": alias, "type": tipo, "path": carpeta, "seed_file": seed_file, "branches": {"main": "main", "develop": "develop"}}
        remote = layout.strip_credentials(layout.git(ap, "remote", "get-url", "origin")) if os.path.isdir(ap) else ""
        if remote:
            c["remote"], c["remote_host"] = remote, layout.host_of(remote)
        if tipo == "node":
            c["statusline"] = True
        data["components"].append(c)
    ws_json = os.path.join(home, ".arkana", "core", "workspace.json")
    if not dry and not os.path.isfile(ws_json):
        os.makedirs(os.path.dirname(ws_json), exist_ok=True)
        with open(ws_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    return layout.init(home, root, dry=dry)
