#!/usr/bin/env python3
"""Configuración general del workspace: Jira y herramientas (los componentes se gestionan con components.py).

  config.py jira  [--url URL] [--token-ref CLAVE] [--show]    jira → bloque `jira` del manifiesto (solo el NOMBRE de la clave del token)
  config.py tools [--tool T --version V [--path RUTA] [--package P[@V]]... [--registry ÁMBITO=URL]...] [--check-url URL]... [--port N]...
                                                              tools.json: herramientas {tool, version, path, packages, registries}, `urls` y `ports` que
                                                              comprueba `check`; la ruta no se exporta. Volver a registrar una herramienta conserva lo que
                                                              no se repite. Sin opciones lista
  Comunes: --home DIR  --dry-run  --json
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, HERE)
from arkana_core import datafiles, locate, manifest, output  # noqa: E402
import components as component  # noqa: E402
from components import _kv  # noqa: E402


def tools_path(home):
    return os.path.join(locate.state_dir(home), "arkana-workspace", "tools.json")


def read_tools(home):
    try:
        d = json.load(open(tools_path(home), encoding="utf-8"))
        return d if isinstance(d, dict) else {"schema_version": 1, "tools": d}
    except (OSError, ValueError):
        return {"schema_version": 1, "tools": []}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="config.py")
    ap.add_argument("cmd", choices=["jira", "tools"])
    ap.add_argument("--url")
    ap.add_argument("--token-ref")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--tool")
    ap.add_argument("--version")
    ap.add_argument("--path")
    ap.add_argument("--package", action="append")
    ap.add_argument("--registry", action="append")
    ap.add_argument("--check-url", dest="check_urls", action="append")
    ap.add_argument("--port", action="append", type=int)
    ap.add_argument("--home")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    home = os.path.realpath(a.home) if a.home else locate.find_home()
    if not home:
        print("FAIL|workspace|no se encontró un workspace de Arkana", file=sys.stderr)
        return 3
    rep = output.Report("arkana-workspace", f"config-{a.cmd}")
    try:
        if a.cmd == "jira":
            path, data = component._load(home)
            if a.url or a.token_ref:
                j = data.setdefault("jira", {})
                if a.url:
                    j["url"] = a.url
                if a.token_ref:
                    j["token_ref"] = a.token_ref
                component.save(home, path, data, a.dry_run)
                rep.add("DRY" if a.dry_run else "OK", "jira", "configuración guardada (el token vive en .credentials)")
            for k, v in (data.get("jira") or {}).items():
                rep.add("INFO", f"jira.{k}", v)
        else:
            d = read_tools(home)
            changed = False
            if a.tool:
                prev = next((t for t in d["tools"] if t.get("tool") == a.tool), {})
                if not (a.version or prev.get("version")):
                    raise ValueError("--tool necesita --version")
                t = dict(prev, tool=a.tool, version=a.version or prev["version"])
                if a.path:
                    t["path"] = a.path
                if a.package:
                    t["packages"] = sorted(set(t.get("packages", [])) | set(a.package))
                if a.registry:
                    t["registries"] = dict(t.get("registries", {}), **_kv(a.registry, "--registry"))
                d["tools"] = [x for x in d["tools"] if x.get("tool") != a.tool] + [t]
                changed = True
                rep.add("DRY" if a.dry_run else "OK", a.tool, f"versión {t['version']}" + (" (ruta local guardada)" if t.get("path") else "")
                        + (f" · {len(t['packages'])} paquetes" if t.get("packages") else "") + (f" · {len(t['registries'])} registros" if t.get("registries") else ""))
            elif a.package or a.registry:
                raise ValueError("--package y --registry necesitan --tool")
            for clave, valores in (("urls", a.check_urls), ("ports", a.port)):
                if valores:
                    d[clave] = sorted(set(d.get(clave, [])) | set(valores)) if clave == "ports" else list(dict.fromkeys(d.get(clave, []) + valores))
                    changed = True
                    rep.add("DRY" if a.dry_run else "OK", clave, ", ".join(map(str, d[clave])))
            if changed and not a.dry_run:
                datafiles.atomic_write_json(tools_path(home), d, mode=0o644)
            for t in d["tools"]:
                rep.add("INFO", t["tool"], f"{t.get('version', '?')}" + (" ruta local" if t.get("path") else "") + (f" · paquetes: {', '.join(t['packages'])}" if t.get("packages") else "")
                        + (f" · registros: {', '.join(sorted(t['registries']))}" if t.get("registries") else ""))
            if not changed:
                for clave in ("urls", "ports"):
                    if d.get(clave):
                        rep.add("INFO", clave, ", ".join(map(str, d[clave])))
    except (ValueError, OSError, KeyError, manifest.ManifestError) as e:
        rep.add("FAIL", a.cmd, str(e))
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
