"""refresh: fetch con contención de red (DNS comprobado, sin VPN no se intenta nada) y ⇣ conocido después."""
import json
import os
import stat
import subprocess
import sys
import unittest

import lab as L
from lab import Lab

REFRESH = os.path.join(L.PLUGIN, "scripts", "lib", "refresh.py")


def refresh(lab, *a, env=None):
    return subprocess.run([sys.executable, "-I", REFRESH, *a, "--home", lab.arkana], capture_output=True, text=True, env=dict(lab.env, **(env or {})), timeout=60,
                          stdin=subprocess.DEVNULL, cwd=lab.root)


class TestRefresh(unittest.TestCase):
    def test_fetch_local_deja_el_pull_conocido(self):
        with Lab() as lab:
            d = lab.path("app")
            bare = os.path.join(lab.root, "origin.git")
            subprocess.run(["git", "init", "-q", "--bare", "-b", "develop", bare], check=True)
            L.git(d, "remote", "add", "origin", bare)
            L.git(d, "push", "-q", "-u", "origin", "develop")
            import statusline as S
            self.assertIsNone(S.git_state(d)["behind"])
            r = refresh(lab, "--component", "app")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("OK|app|develop ◌1", r.stdout)                              # ◌1: el repo anidado de app-web
            self.assertEqual(S.git_state(d)["behind"], 0)

    def test_sin_dns_no_se_intenta_nada_y_se_avisa(self):
        with Lab() as lab:
            bindir = os.path.join(lab.root, "bin"); os.makedirs(bindir)
            with open(os.path.join(bindir, "getent"), "w") as f:
                f.write("#!/bin/sh\nexit 2\n")
            os.chmod(os.path.join(bindir, "getent"), 0o755)
            marca = os.path.join(lab.root, "fetch-hecho")
            real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
            with open(os.path.join(bindir, "git"), "w") as f:
                f.write(f'#!/bin/sh\ncase "$*" in *fetch*) touch {marca};; esac\nexec {real} "$@"\n')
            os.chmod(os.path.join(bindir, "git"), 0o755)
            L.git(lab.path("api"), "remote", "add", "origin", "https://x.invalid/r.git")
            r = refresh(lab, "--component", "api", env={"PATH": bindir + os.pathsep + os.environ["PATH"], "ARKANA_NET_BREAKER_FILE": os.path.join(lab.root, "br.json")})
            self.assertIn("WARN|api|sin red", r.stdout)
            self.assertIn("VPN", r.stdout)
            self.assertFalse(os.path.exists(marca))                                              # ni un fetch

    def test_no_fetch_solo_repinta_y_errores_de_uso(self):
        with Lab() as lab:
            r = refresh(lab, "--no-fetch", "--json")
            d = json.loads(r.stdout)
            self.assertEqual(d["skill"], "refresh")
            self.assertEqual(len(d["items"]), 5)
            self.assertEqual(refresh(lab, "--component", "nadie").returncode, 3)


if __name__ == "__main__":
    unittest.main()
