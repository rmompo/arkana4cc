#!/usr/bin/env python3
"""`arkana-workspace:check` agregado: componentes, herramientas, credenciales y el `check` que declare cada plugin en su `arkana-plugin.json`.

  all.py [--home DIR] [--json] [--network] [--plugins-dir DIR] [--component A]...

Solo lectura. Por defecto no usa la red (`--network` activa tools/vpn contra hosts remotos). El `check` de un plugin es una orden relativa a
su carpeta que imprime el formato común `ESTADO|ID|detalle`; se ejecuta con tiempo límite y sin stdin.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
sys.path.insert(0, HERE)
from arkana_core import contract, manifest, output  # noqa: E402
import component as comp_check  # noqa: E402
import credentials  # noqa: E402
import proc  # noqa: E402
import tools  # noqa: E402


def merge(rep, sub, prefix):
    for i in sub.items:
        rep.add(i["status"], f"{prefix}:{i['id']}", i["detail"], component=i.get("component"))


def plugin_checks(rep, plugins_dir, home):
    if not os.path.isdir(plugins_dir):
        return
    for name in sorted(os.listdir(plugins_dir)):
        pdir = os.path.join(plugins_dir, name)
        if name == "arkana-workspace" or not os.path.isfile(os.path.join(pdir, contract.CONTRACT_FILE)):
            continue
        try:
            c = contract.load(pdir)
        except contract.ContractError as e:
            rep.add("FAIL", f"{name}:contrato", str(e))
            continue
        if not c.get("check"):
            rep.add("INFO", f"{name}:check", "el plugin no declara `check`")
            continue
        rc, out = proc.run(["bash", "-c", c["check"]], 120, dict(os.environ, ARKANA_HOME=home, CLAUDE_PLUGIN_ROOT=pdir), cwd=pdir)
        if rc == 124:
            rep.add("FAIL", f"{name}:check", "tiempo agotado")
            continue
        n = 0
        for l in out.splitlines():
            p = l.split("|", 2)
            if len(p) == 3 and p[0] in output.STATUSES:
                rep.add(p[0], f"{name}:{p[1]}", p[2]); n += 1
        if n == 0:
            rep.add("FAIL" if rc else "WARN", f"{name}:check", "sin salida en el formato común")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="all.py")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--plugins-dir")
    ap.add_argument("--component", action="append")
    a = ap.parse_args(argv)
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        comps = [manifest.canon(c) for c in a.component] if a.component else ws.aliases()
        for c in comps:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = output.Report("arkana-workspace", "check", secrets=credentials.secrets(ws.home))
    for c in comps:
        if os.path.isdir(ws.path(c)):
            merge(rep, comp_check.check(ws, c, a.network), c)
        else:
            rep.add("WARN", f"{c}:carpeta", "no existe", component=c)
    merge(rep, tools.check(ws, a.network), "tools")
    merge(rep, credentials.check(ws.home), "credenciales")
    plugin_checks(rep, os.path.realpath(a.plugins_dir) if a.plugins_dir else os.path.join(ws.home, "plugins"), ws.home)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
