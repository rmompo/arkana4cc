"""commits.py: la convención de commits sale del manifiesto (commit_format) y se inyecta en la sesión; no se escribe ningún fichero en los repos."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

LIB = os.path.join(E.SCRIPTS, "lib")
sys.path.insert(0, LIB)


def cli(lab, *a):
    return subprocess.run([sys.executable, "-I", os.path.join(LIB, "commits.py"), *a, "--home", lab.arkana], capture_output=True, text=True,
                          env=lab.env, cwd=lab.ws, stdin=subprocess.DEVNULL, timeout=60)


def leer(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def set_format(lab, alias, fmt):
    f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
    d = json.loads(leer(f))
    for c in d["components"]:
        if c["alias"] == alias:
            c["commit_format"] = fmt
    with open(f, "w", encoding="utf-8") as fh:
        json.dump(d, fh)


class TestCommits(unittest.TestCase):
    def test_show_da_la_convencion_segun_el_formato_del_manifiesto(self):
        with TC.CLab() as lab:
            set_format(lab, "app", "ia4d")                                                       # ia4d es opcional: hay que pedirlo
            r = cli(lab, "show", "--component", "arkana", "--component", "app", "--component", "app-ui")
            self.assertEqual(r.returncode, 0, r.stdout)
            ark, app, ui = r.stdout.split("### ")[1:]
            self.assertIn("Conventional Commits con dos puntos", ark)                            # por defecto: conventional
            self.assertNotIn("**IA4D**", ark)
            self.assertIn("**IA4D**", app)
            self.assertIn("Nunca", app)
            self.assertIn("chore(app-ui):", ui)

    def test_status_valida_el_formato_y_no_escribe_nada(self):
        with TC.CLab() as lab:
            r = cli(lab, "status", "--component", "app", "--component", "arkana")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("OK|commits-app|formato conventional", r.stdout)
            for rel in ("app/CLAUDE.md", "app/CLAUDE.local.md", "shared/CLAUDE.md"):
                self.assertFalse(os.path.exists(os.path.join(lab.ws, rel)), rel)

    def test_formato_desconocido_falla(self):
        with TC.CLab() as lab:
            set_format(lab, "docs", "raro")
            r = cli(lab, "status", "--component", "docs")
            self.assertEqual(r.returncode, 1)
            self.assertIn("commit_format desconocido", r.stdout)
            self.assertIn("FAIL:", cli(lab, "show", "--component", "docs").stdout)

    def test_apply_ya_no_existe(self):
        with TC.CLab() as lab:
            self.assertEqual(cli(lab, "apply").returncode, 2)


if __name__ == "__main__":
    unittest.main()
