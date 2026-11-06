#!/usr/bin/env python3
"""sync: `git fetch` de los remotos de ARKANA y de los componentes para que ⇣ (commits por bajar) esté al día.
Solo descarga referencias: no toca ficheros ni ramas locales (nada de pull, merge, rebase ni push).

  sync.py [--component ALIAS]... [--no-fetch] [--home DIR] [--json]

Contención de red: comprueba antes el DNS de cada host (3 s; sin VPN no se intenta nada y se avisa), cada fetch tiene tope de 20 s en su propio
grupo de procesos y, si uno vence, los siguientes de ese host no se intentan (cortacircuitos). Sin remoto, no hay nada que bajar.
"""
import argparse
import concurrent.futures
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, HERE)
from arkana_core import manifest, netguard, output  # noqa: E402
import gitstate  # noqa: E402


def sync_one(ws, alias, fetch, hosts, lock):
    """-> (nivel, detalle) para un componente."""
    p = ws.path(alias)
    if not os.path.isdir(p):
        return "WARN", "la carpeta no existe"
    if gitstate.state(p) is None:
        return "WARN", "no es un repositorio git"
    if fetch and netguard.git(p, "remote").stdout.strip():
        host = ws.get(alias).get("remote_host") or ""
        if host:
            with lock:
                if host not in hosts:
                    hosts[host] = netguard.preflight(host)
            if not hosts[host][0]:
                return "WARN", "sin red: " + hosts[host][1]
        r = netguard.git(p, "fetch", "--quiet", "--prune", net=True)
        if r.returncode:
            return "WARN", "fetch falló: " + ((r.stderr or r.stdout).strip().splitlines() or ["?"])[0][:100]
    s = gitstate.state(p)
    return "OK", f"{manifest.display(alias)}{gitstate.badge(s)}".rstrip()


def build(ws, components=None, fetch=True):
    rep = output.Report("arkana-workspace", "sync")
    als = components or ws.aliases()
    hosts, lock = {}, threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for al, (nivel, det) in zip(als, ex.map(lambda a: sync_one(ws, a, fetch, hosts, lock), als)):
            rep.add(nivel, al, det, component=al)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sync.py")
    ap.add_argument("--component", action="append")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        comps = [manifest.canon(c) for c in a.component] if a.component else None
        for c in comps or []:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = build(ws, comps, not a.no_fetch)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
