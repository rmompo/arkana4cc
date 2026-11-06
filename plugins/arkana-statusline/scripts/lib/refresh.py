#!/usr/bin/env python3
"""refresh: `git fetch` de los componentes para que ⇣ (commits por bajar) esté al día. Solo descarga referencias: no toca ficheros ni ramas locales.

  refresh.py [--component ALIAS]... [--no-fetch] [--home DIR] [--json]

Contención de red: comprueba antes el DNS de cada host (3 s; sin VPN no se intenta nada y se avisa), cada fetch tiene tope de 20 s en su propio grupo de
procesos y, si uno vence, los siguientes de ese host no se intentan (cortacircuitos).
"""
import argparse
import concurrent.futures
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "statusline"))
from arkana_core import manifest, netguard, output  # noqa: E402
import statusline as sl  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(prog="refresh.py")
    ap.add_argument("--component", action="append")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    rep = output.Report("arkana-statusline", "refresh")
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        als = [manifest.canon(c) for c in a.component] if a.component else ws.aliases()
        for x in als:
            ws.get(x)
    except (manifest.ManifestError, KeyError) as e:
        rep.add("FAIL", "workspace", str(e))
        sys.stdout.write(rep.render(a.json))
        return 3
    hosts_ok = {}

    def one(al):
        p = ws.path(al)
        if not os.path.isdir(os.path.join(p, ".git")) and not os.path.isfile(os.path.join(p, ".git")):
            return al, "WARN", "no es un repositorio git"
        if not a.no_fetch:
            host = (ws.get(al).get("remote_host") or "")
            if host and host not in hosts_ok:
                hosts_ok[host] = netguard.preflight(host)
            if host and not hosts_ok[host][0]:
                return al, "WARN", "sin red: " + hosts_ok[host][1]
            if netguard.git(p, "remote").stdout.strip():
                r = netguard.git(p, "fetch", "--quiet", "--prune", net=True)
                if r.returncode:
                    return al, "WARN", "fetch falló: " + ((r.stderr or r.stdout).strip().splitlines() or ["?"])[0][:100]
        s = sl.git_state(p)
        return al, "OK", sl.branch_label(s) if s else "sin estado git"
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for al, st, det in ex.map(one, als):
            rep.add(st, al, det, component=al)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
