#!/usr/bin/env python3
"""Despachador de la statusline de usuario: decide en cada render qué statusline se ve. Solo biblioteca estándar.

Claude Code admite UNA `statusLine` por ámbito. Esta es la de usuario (~/.claude/settings.json) y reparte según dónde estés (cwd):

  1. carpeta de ARKANA (el orquestador)                          → la statusline de Arkana
  2. componente gobernado por ARKANA (registrado en su manifiesto)
       elección «arkana» (la persona usuaria la pidió)           → la statusline de Arkana
       cualquier otra cosa (sin elegir, «other»)                 → proveedores, abajo
  3. cualquier otro sitio                                        → proveedores

Proveedores = las demás statuslines, en `~/.arkana/statusline.json` (`providers`: `id`, `command`, `priority`; gana la de menor prioridad):
plugin4cc (20) antes que cualquier otra (30). Si no hay ninguna, no se imprime nada.

En ARKANA y en sus componentes la de Arkana se ejecuta siempre (es la única escritora del coste real de la sesión) y solo se muestra si toca.
Una statusline nunca debe romper la sesión: ante cualquier error no se imprime nada.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (HERE, os.path.join(HERE, "..", "scripts", "_core")):          # copia instalada (arkana_core al lado) o árbol del plugin
    if os.path.isdir(os.path.join(_p, "arkana_core")):
        sys.path.insert(0, _p)
sys.path.insert(0, HERE)
TIMEOUT = 8


def prefs_path():
    return os.path.join(os.path.expanduser("~"), ".arkana", "statusline.json")


def load_prefs():
    try:
        with open(prefs_path(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    d.setdefault("version", 1)
    if not isinstance(d.get("providers"), list):
        d["providers"] = []
    if not isinstance(d.get("components"), dict):
        d["components"] = {}
    return d


def choice_key(home, alias):
    return f"{home}|{alias}"


def providers(prefs):
    """Proveedores válidos ordenados por prioridad (menor primero)."""
    ok = [p for p in prefs.get("providers", []) if isinstance(p, dict) and isinstance(p.get("command"), str) and p["command"].strip()]
    return sorted(ok, key=lambda p: (p.get("priority") if isinstance(p.get("priority"), (int, float)) else 100, str(p.get("id", ""))))


def context(inp):
    """(home, alias del dueño del cwd) si el cwd es de ARKANA o de un componente suyo; (None, None) si no."""
    cwd = (inp.get("workspace") or {}).get("project_dir") or (inp.get("workspace") or {}).get("current_dir") or inp.get("cwd") or os.getcwd()
    try:
        from arkana_core import locate, manifest
        home = locate.find_home(cwd)
        if not home:
            return None, None
        owner = manifest.load(home).owner_of(cwd)
    except Exception:
        return None, None
    return (home, owner) if owner else (None, None)


def decide(inp, prefs):
    """('arkana'|'delegate', gobernado) según el cwd y la elección guardada."""
    home, owner = context(inp)
    if not owner:
        return "delegate", False
    if owner == "arkana":
        return "arkana", True
    return ("arkana" if prefs["components"].get(choice_key(home, owner)) == "arkana" else "delegate"), True


def run_arkana(raw):
    p = subprocess.run([sys.executable, "-I", os.path.join(HERE, "statusline.py")], input=raw, capture_output=True, text=True, timeout=TIMEOUT)
    return p.stdout


def run_provider(prefs, raw):
    for p in providers(prefs):
        try:
            r = subprocess.run(p["command"], shell=True, input=raw, capture_output=True, text=True, timeout=TIMEOUT)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    return ""


def main():
    raw = sys.stdin.read()
    try:
        inp = json.loads(raw or "{}")
    except ValueError:
        inp = {}
    try:
        prefs = load_prefs()
        quien, gobernado = decide(inp, prefs)
        arkana_out = run_arkana(raw) if gobernado else ""
        out = arkana_out if quien == "arkana" else run_provider(prefs, raw)
        sys.stdout.write(out)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
