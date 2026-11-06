"""sync: fetch con contención de red (DNS comprobado, sin VPN no se intenta nada), ⇣ conocido después y nada de pull ni merge."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

sys.path.insert(0, os.path.join(E.SCRIPTS, "lib"))
import gitstate  # noqa: E402
from arkana_core import manifest  # noqa: E402

SYNC = os.path.join(E.SCRIPTS, "lib", "sync.py")


def sync(lab, *a, env=None):
    return subprocess.run([sys.executable, "-I", SYNC, *a, "--home", lab.arkana], capture_output=True, text=True, env=dict(lab.env, **(env or {})),
                          timeout=60, stdin=subprocess.DEVNULL, cwd=lab.ws)


ENV = dict(os.environ, GIT_AUTHOR_NAME="x", GIT_AUTHOR_EMAIL="x@x", GIT_COMMITTER_NAME="x", GIT_COMMITTER_EMAIL="x@x")


def g(path, *a):
    return subprocess.run(["git", "-C", path, *a], check=True, capture_output=True, text=True, env=ENV).stdout


def repo(lab, alias):
    """Carpeta del componente convertida en repositorio git con un commit en `develop`."""
    d = manifest.load(lab.arkana).path(alias)
    os.makedirs(d, exist_ok=True)
    g(d, "init", "-q", "-b", "develop")
    g(d, "commit", "-q", "--allow-empty", "-m", "i")
    return d


class TestSync(unittest.TestCase):
    def test_fetch_local_deja_el_por_bajar_conocido_y_no_integra_nada(self):
        with TC.CLab() as lab:
            d = repo(lab, "app")
            bare = os.path.join(lab.root, "origin.git")
            subprocess.run(["git", "init", "-q", "--bare", "-b", "develop", bare], check=True)
            g(d, "remote", "add", "origin", bare)
            g(d, "push", "-q", "-u", "origin", "develop")
            otro = os.path.join(lab.root, "otro")                                        # otro clon sube un commit
            subprocess.run(["git", "clone", "-q", bare, otro], check=True)
            g(otro, "commit", "-q", "--allow-empty", "-m", "nuevo")
            g(otro, "push", "-q", "origin", "develop")
            self.assertIsNone(gitstate.state(d)["behind"])                               # sin fetch reciente: ⇣?
            antes = g(d, "rev-parse", "HEAD")
            r = sync(lab, "--component", "app")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("OK|app|", r.stdout)
            self.assertIn("⇣1", r.stdout)
            self.assertEqual(gitstate.state(d)["behind"], 1)
            self.assertEqual(g(d, "rev-parse", "HEAD"), antes)                          # no hizo pull ni merge

    def test_sin_dns_no_se_intenta_nada_y_se_avisa(self):
        with TC.CLab() as lab:
            bindir = os.path.join(lab.root, "bin"); os.makedirs(bindir)
            with open(os.path.join(bindir, "getent"), "w") as f:
                f.write("#!/bin/sh\nexit 2\n")
            os.chmod(os.path.join(bindir, "getent"), 0o755)
            marca = os.path.join(lab.root, "fetch-hecho")
            real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
            with open(os.path.join(bindir, "git"), "w") as f:
                f.write(f'#!/bin/sh\ncase "$*" in *fetch*) touch {marca};; esac\nexec {real} "$@"\n')
            os.chmod(os.path.join(bindir, "git"), 0o755)
            d = repo(lab, "api")
            g(d, "remote", "remove", "origin") if "origin" in g(d, "remote") else None
            g(d, "remote", "add", "origin", "https://host.example/r.git")
            r = sync(lab, "--component", "api", env={"PATH": bindir + os.pathsep + os.environ["PATH"], "ARKANA_NET_BREAKER_FILE": os.path.join(lab.root, "br.json")})
            self.assertIn("WARN|api|sin red", r.stdout)
            self.assertIn("VPN", r.stdout)
            self.assertFalse(os.path.exists(marca))                                      # ni un fetch

    def test_no_fetch_sin_remoto_json_y_errores_de_uso(self):
        with TC.CLab() as lab:
            repo(lab, "app")
            d = json.loads(sync(lab, "--no-fetch", "--json", "--component", "app").stdout)
            self.assertEqual((d["skill"], d["items"][0]["component"]), ("sync", "app"))
            r = sync(lab, "--component", "app")                                         # sin remoto: nada que bajar, no es un error
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("OK|app|", r.stdout)
            self.assertEqual(sync(lab, "--component", "nadie").returncode, 3)


if __name__ == "__main__":
    unittest.main()
