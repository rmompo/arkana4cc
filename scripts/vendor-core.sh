#!/usr/bin/env bash
# Copia el núcleo (lib/arkana_core) dentro de cada plugin que lo usa: plugins/<p>/scripts/_core/ + .vendor.json (sha256).
# Los plugins instalados se leen de una copia en la caché, así que no pueden referenciarse entre sí: cada uno lleva su copia.
# Uso: bash scripts/vendor-core.sh [--check] [plugin...]   (--check no escribe: sale con 1 si alguna copia difiere)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/lib/arkana_core"
DEFAULT=(arkana-agentic arkana-knowledge arkana-messaging arkana-statusline arkana-todo arkana-workspace)
CHECK=0; plugins=()
for a in "$@"; do case "$a" in --check) CHECK=1 ;; *) plugins+=("$a") ;; esac; done
[ "${#plugins[@]}" -gt 0 ] || plugins=("${DEFAULT[@]}")

python3 -I - "$ROOT" "$CHECK" "${plugins[@]}" <<'PY'
import hashlib, json, os, shutil, sys
root, check, plugins = sys.argv[1], sys.argv[2] == "1", sys.argv[3:]
src = os.path.join(root, "lib", "arkana_core")
sys.path.insert(0, os.path.join(root, "lib"))
version = [l for l in open(os.path.join(src, "__init__.py")) if l.startswith("CORE_VERSION")][0].split('"')[1]

def files():
    for d, ds, fs in os.walk(src):
        ds[:] = sorted(x for x in ds if x not in ("tests", "__pycache__"))
        for f in sorted(fs):
            if f.endswith((".pyc",)): continue
            p = os.path.join(d, f)
            yield os.path.relpath(p, src), p

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

want = {rel: sha(p) for rel, p in files()}
bad = 0
for pl in plugins:
    dest = os.path.join(root, "plugins", pl, "scripts", "_core")
    if check:
        vj = os.path.join(dest, ".vendor.json")
        try: cur = json.load(open(vj))
        except (OSError, ValueError): print(f"FAIL|vendor:{pl}|falta .vendor.json"); bad += 1; continue
        ok = cur.get("version") == version and cur.get("files") == want
        for rel, h in want.items():
            q = os.path.join(dest, "arkana_core", rel) if not rel.endswith(".sh") else os.path.join(dest, rel)
            if not os.path.isfile(q) or sha(q) != h: ok = False
        print(f"{'OK' if ok else 'FAIL'}|vendor:{pl}|{'al día' if ok else 'copia distinta de lib/arkana_core (ejecutar scripts/vendor-core.sh)'}")
        bad += 0 if ok else 1
        continue
    if os.path.isdir(dest): shutil.rmtree(dest)
    for rel, p in files():
        q = os.path.join(dest, rel) if rel.endswith(".sh") else os.path.join(dest, "arkana_core", rel)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copy2(p, q)
    json.dump({"source": "lib/arkana_core", "version": version, "files": want}, open(os.path.join(dest, ".vendor.json"), "w"), indent=2, sort_keys=True)
    open(os.path.join(dest, ".vendor.json"), "a").write("\n")
    print(f"OK|vendor:{pl}|núcleo {version} copiado ({len(want)} ficheros)")
sys.exit(1 if bad else 0)
PY
