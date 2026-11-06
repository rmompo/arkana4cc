#!/usr/bin/env python3
"""Red/VPN y acceso a los remotos de ARKANA y de cada componente (antes `arkana-vpn:check`). Solo lectura.

  vpn.py [--component <alias>] [--home <dir>] [--json] [--no-write] [--no-network]

Por host distinto: DNS y HTTPS (VPN). Por repo: lectura (`git ls-remote`) y escritura (`git push --dry-run` sin hooks: contacta con el
servidor y no sube nada). Si falla distingue red/VPN, credenciales, permisos y repo inexistente. NUNCA imprime credenciales:
las URLs se muestran sin usuario ni contraseña.
"""
import argparse
import concurrent.futures
import os
import re
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

ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", LC_ALL="C")


def org_of(host):
    """Etiqueta con la que se muestra un host: el propio host (el workspace no conoce organizaciones)."""
    return host


def host_of(url):
    u = url.split("://", 1)[1] if "://" in url else url.split("@", 1)[-1]
    u = u.split("@", 1)[-1]
    return re.split(r"[/:]", u, maxsplit=1)[0]


def clean_url(url):
    return re.sub(r"(://)[^/@]*@", r"\1", url)


def classify(out):
    o = out.lower()
    if re.search(r"could not resolve host|name or service not known|temporary failure in name|timed out|timeout|connection refused|no route to host|network is unreachable|failed to connect|ssl.*(error|connect)|unable to access.*(connect|resolve)", o):
        return "red"
    if re.search(r"authentication failed|could not read username|could not read password|invalid username|http (basic: )?access denied|returned error: 401|permission denied \(publickey\)", o):
        return "cred"
    if re.search(r"returned error: 403|you are not allowed|access denied|not authorized|forbidden|protected branch|pre-receive hook declined", o):
        return "perm"
    if re.search(r"repository not found|not found|returned error: 404|does not appear to be a git repository", o):
        return "noexiste"
    return "otro"


def git(repo, *args, timeout=25):
    rc, out = proc.run(["git", "-C", repo, *args], timeout, ENV)
    return rc, ("timed out" if rc == 124 else out)


def check_repo(alias, path, write, network=True):
    url = git(path, "remote", "get-url", "origin")[1].strip() if os.path.isdir(path) else ""
    if not url:
        return ("WARN", f"repo-{alias}", f"sin remoto 'origin' ({path})")
    h = host_of(url)
    org, shown = org_of(h), clean_url(url)
    if h and not network:
        return ("INFO", f"repo-{alias}", f"[{org}] omitido (--no-network) · {shown}")
    branch = git(path, "symbolic-ref", "--quiet", "--short", "HEAD")[1].strip() or "(detached)"
    rc, out = git(path, "ls-remote", "--heads", "origin")
    if rc != 0:
        cls = classify(out if rc != 124 else "timed out")
        msg = {"red": f"sin acceso: no se alcanza {h} (¿VPN?)", "cred": f"credenciales rechazadas o ausentes para {h}",
               "perm": "sin permiso de lectura en el servidor", "noexiste": "el repositorio no existe o no es visible con tu usuario"}.get(cls, "error al leer el remoto")
        return ("FAIL", f"repo-{alias}", f"[{org}] {msg} · {shown}")
    brmsg = "" if branch == "(detached)" or re.search(rf"refs/heads/{re.escape(branch)}$", out, re.M) else f" · la rama '{branch}' no existe en el remoto"
    if write and branch != "(detached)":
        rc, o2 = git(path, "-c", "core.hooksPath=/dev/null", "push", "--dry-run", "origin", f"HEAD:refs/heads/{branch}")
        if rc == 0:
            wr = "escritura OK"
        else:
            cls = classify(o2)
            wr = {"perm": "SIN escritura (permiso o rama protegida)", "cred": "SIN escritura (permiso o rama protegida)", "red": "escritura no verificable (red)"}.get(cls, "escritura no verificada")
    else:
        wr = "escritura no comprobada"
    st = "WARN" if wr.startswith("SIN") or "no verificable" in wr or "no verificada" in wr or brmsg else "OK"
    return (st, f"repo-{alias}", f"[{org}] lectura OK · {wr} · rama {branch}{brmsg} · {shown}")


def check(ws, components=None, write=True, network=True):
    rep = output.Report("arkana-workspace", "check-vpn", secrets=credentials.secrets(ws.home))
    aliases = components or ws.aliases()
    targets = []
    for a in aliases:
        p = ws.path(a)
        if os.path.exists(os.path.join(p, ".git")):
            targets.append((a, p))
        else:
            rep.add("WARN", f"repo-{a}", "no es un repositorio git o no existe", component=a)
    hosts = {}
    for a, p in targets:
        url = git(p, "remote", "get-url", "origin")[1].strip()
        if url:
            hosts[host_of(url)] = org_of(host_of(url))
    for h in sorted(h for h in hosts if h and network):
        org = hosts[h]
        if proc.run(["getent", "hosts", h], 8)[0] != 0:
            rep.add("FAIL", f"red-{h}", f"{h} no resuelve el nombre del host (¿VPN desconectada?)")
            continue
        try:
            with urllib.request.urlopen(f"https://{h}", timeout=10) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception:
            code = 0
        rep.add("OK" if code else "FAIL", f"red-{h}", f"https://{h} responde (HTTP {code})" if code else f"https://{h} no responde (¿VPN desconectada o cortafuegos?)")
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for (a, _), res in zip(targets, ex.map(lambda t: check_repo(t[0], t[1], write, network), targets)):
            rep.add(res[0], res[1], res[2], component=a)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vpn.py")
    ap.add_argument("--component", action="append")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-write", action="store_true")
    ap.add_argument("--no-network", action="store_true", help="no resuelve ni contacta con hosts remotos (los remotos locales sí se comprueban)")
    a = ap.parse_args(argv)
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        comps = [manifest.canon(c) for c in a.component] if a.component else None
        for c in comps or []:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    rep = check(ws, comps, not a.no_write, not a.no_network)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
