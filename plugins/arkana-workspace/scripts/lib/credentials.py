#!/usr/bin/env python3
"""Credenciales del workspace: `<home>/.arkana/.credentials` (CLAVE=valor, modo 600, nunca se exporta ni se versiona).

El manifiesto y los ficheros exportables guardan solo el NOMBRE de la clave (`git.token_ref`, `jira.token_ref`…); el valor vive aquí.
Este módulo es el único resolvedor. Nunca imprime un valor (ni su longitud): los informes pasan por `output.Report(secrets=...)`.

  credentials.py keys                          lista las claves (sin valores)
  credentials.py has <CLAVE>                   sale con 0 si existe y no está vacía
  credentials.py set <CLAVE>                   lee el valor de stdin (nunca de argumentos, que quedan en el historial del shell)
  credentials.py unset <CLAVE>
  credentials.py check                         modo 600, ignorado por git, sin valores vacíos
  credentials.py import-maven <settings.xml> [--server <id>] [--prefix REGISTRY]
                                               copia usuario/contraseña de un settings.xml antiguo a <PREFIX>_USER y <PREFIX>_PASSWORD
  credentials.py wire-git <alias> [--dry-run]  configura el asistente de git (git-credential-arkana) en el repo de ese componente
"""
import argparse
import os
import re
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, netguard, output  # noqa: E402

FILE = ".credentials"
KEY_RX = re.compile(r"^[A-Z][A-Z0-9_]*$")


def path(home):
    return os.path.join(locate.state_dir(home), FILE)


def load(home):
    """{clave: valor}. Fichero ausente o ilegible → {}."""
    res = {}
    try:
        with open(path(home), encoding="utf-8") as f:
            for linea in f:
                linea = linea.rstrip("\r\n")
                if not linea.strip() or linea.lstrip().startswith("#") or "=" not in linea:
                    continue
                k, v = linea.split("=", 1)
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                    v = v[1:-1]
                res[k.strip()] = v
    except OSError:
        pass
    return res


def get(home, key):
    return load(home).get(key) or None


def save(home, creds):
    body = "# Credenciales de Arkana (modo 600; nunca se versiona ni se exporta)\n" + "".join(f"{k}={v}\n" for k, v in sorted(creds.items()))
    datafiles.atomic_write(path(home), body, mode=0o600)


def set_key(home, key, value):
    if not KEY_RX.match(key):
        raise ValueError(f"nombre de clave no válido: {key!r} (MAYÚSCULAS, dígitos y _)")
    if "\n" in value or "\r" in value or not value:
        raise ValueError("el valor no puede estar vacío ni tener saltos de línea")
    c = load(home)
    c[key] = value
    save(home, c)


def unset_key(home, key):
    c = load(home)
    existed = c.pop(key, None) is not None
    if existed:
        save(home, c)
    return existed


def secrets(home):
    """Valores a redactar en cualquier salida."""
    return [v for v in load(home).values() if v]


def environ(home, keys=None):
    """Entorno con las credenciales (o solo `keys`) para ejecutar un comando; las claves ya definidas fuera no se pisan."""
    c = load(home)
    return {k: v for k, v in c.items() if (keys is None or k in keys) and k not in os.environ}


def import_maven(home, xml_path, server="registry", prefix="REGISTRY"):
    """Lee usuario y contraseña del <server> de un settings.xml y los guarda. Devuelve las claves escritas, nunca los valores."""
    import xml.etree.ElementTree as ET
    root = ET.parse(xml_path).getroot()
    ns = {"m": root.tag[1:root.tag.index("}")]} if root.tag.startswith("{") else None
    q = (lambda t: f"m:{t}") if ns else (lambda t: t)
    for s in root.iterfind(f".//{q('server')}", ns) if ns else root.iter("server"):
        if (s.findtext(q("id"), namespaces=ns) if ns else s.findtext("id")) == server:
            u = (s.findtext(q("username"), namespaces=ns) if ns else s.findtext("username")) or ""
            p = (s.findtext(q("password"), namespaces=ns) if ns else s.findtext("password")) or ""
            if not u or not p:
                raise ValueError(f"el servidor {server!r} no tiene usuario y contraseña")
            set_key(home, f"{prefix}_USER", u.strip())
            set_key(home, f"{prefix}_PASSWORD", p.strip())
            return [f"{prefix}_USER", f"{prefix}_PASSWORD"]
    raise ValueError(f"no hay un <server> con id {server!r}")


def check(home):
    rep = output.Report("arkana-workspace", "credentials-check", secrets=secrets(home))
    f = path(home)
    if not os.path.isfile(f):
        return rep.add("INFO", "credentials", "no hay .credentials (se crea con `credentials.py set <CLAVE>`)")
    mode = stat.S_IMODE(os.stat(f).st_mode)
    rep.add("OK" if mode == 0o600 else "FAIL", "credentials-modo", "modo 600" if mode == 0o600 else f"modo {oct(mode)[2:]}: debe ser 600 (chmod 600)")
    ig = netguard.git(home, "check-ignore", "-q", f).returncode
    rep.add("OK" if ig == 0 else "FAIL", "credentials-ignorado", "ignorado por git" if ig == 0 else "git NO lo ignora: añade /.arkana/ al .gitignore")
    vacias = [k for k, v in load(home).items() if not v]
    rep.add("WARN" if vacias else "OK", "credentials-valores", f"claves vacías: {', '.join(vacias)}" if vacias else f"{len(load(home))} claves con valor")
    return rep


def helper_wrapper(home):
    return os.path.join(locate.state_dir(home), "arkana-workspace", "bin", "git-credential-arkana")


def wire_git(home, alias, dry=False):
    ws = manifest.load(home)
    c = ws.get(alias)
    ref = (c.get("git") or {}).get("token_ref")
    rep = output.Report("arkana-workspace", "credentials-wire-git")
    if not ref:
        return rep.add("FAIL", "token_ref", f"{manifest.display(alias)} no tiene git.token_ref en el manifiesto")
    repo = ws.path(alias)
    if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isfile(os.path.join(repo, ".git")):
        return rep.add("FAIL", "repo", f"{repo} no es un repositorio git")
    script = os.path.join(HERE, "..", "git-credential-arkana")
    script = os.path.realpath(script)
    wrapper = helper_wrapper(home)
    body = f'#!/usr/bin/env bash\nexec python3 -I "{script}" "$@"\n'
    if dry:
        rep.add("DRY", "wrapper", f"escribiría {os.path.relpath(wrapper, home)}")
        rep.add("DRY", "git-config", f"git -C {alias} config --local credential.helper (asistente de Arkana)")
        return rep
    datafiles.atomic_write(wrapper, body, mode=0o700)
    r = netguard.git(repo, "config", "--local", "credential.helper", f"!{wrapper}")
    if r.returncode != 0:
        return rep.add("FAIL", "git-config", "no se pudo escribir la configuración local del repo")
    rep.add("OK", "wrapper", os.path.relpath(wrapper, home))
    rep.add("OK", "git-config", f"credential.helper configurado en el repo de {manifest.display(alias)} (token: clave {ref})")
    if not get(home, ref):
        rep.add("WARN", "token", f"falta la clave {ref} en .credentials: `credentials.py set {ref}`")
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="credentials.py")
    ap.add_argument("cmd", choices=["keys", "has", "set", "unset", "check", "import-maven", "wire-git"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--server", default="registry")
    ap.add_argument("--prefix", default="REGISTRY")
    a = ap.parse_args(argv)
    home = os.path.realpath(a.home) if a.home else locate.find_home()
    if not home:
        print("FAIL|workspace|no se encontró un workspace de Arkana", file=sys.stderr)
        return 3
    rep = output.Report("arkana-workspace", f"credentials-{a.cmd}", secrets=secrets(home))
    try:
        if a.cmd == "keys":
            for k in sorted(load(home)):
                rep.add("INFO", k, "definida")
        elif a.cmd == "has":
            return 0 if get(home, a.arg or "") else 1
        elif a.cmd == "set":
            if not a.arg:
                print("uso: credentials.py set <CLAVE>   (el valor, por stdin)", file=sys.stderr)
                return 2
            if a.dry_run:
                rep.add("DRY", a.arg, "se guardaría")
            else:
                value = sys.stdin.readline().rstrip("\r\n")
                set_key(home, a.arg, value)
                rep.add("OK", a.arg, "guardada")
        elif a.cmd == "unset":
            hubo = unset_key(home, a.arg or "")
            rep.add("OK" if hubo else "INFO", a.arg or "", "eliminada" if hubo else "no estaba definida")
        elif a.cmd == "check":
            rep = check(home)
        elif a.cmd == "import-maven":
            if a.dry_run:
                rep.add("DRY", "import-maven", f"copiaría usuario y contraseña de {a.server} a {a.prefix}_USER y {a.prefix}_PASSWORD")
            else:
                for k in import_maven(home, a.arg, a.server, a.prefix):
                    rep.add("OK", k, "guardada")
        elif a.cmd == "wire-git":
            rep = wire_git(home, manifest.canon(a.arg or ""), a.dry_run)
    except (ValueError, OSError, KeyError, manifest.ManifestError) as e:
        rep.add("FAIL", a.cmd, str(e))
    except Exception as e:  # el XML mal formado u otros: nunca con el contenido
        rep.add("FAIL", a.cmd, f"{type(e).__name__}")
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
