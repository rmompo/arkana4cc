"""commits.py: la convención de commits sale del manifiesto (commit_format) como bloque arkana:commits en el CLAUDE.md de cada componente."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

LIB = os.path.join(E.SCRIPTS, "lib")


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
    def test_apply_pone_el_bloque_segun_el_formato_del_manifiesto_y_es_idempotente(self):
        with TC.CLab() as lab:
            set_format(lab, "app-ui", "conventional")
            set_format(lab, "app", "ia4d")                                                       # ia4d es opcional: hay que pedirlo
            self.assertIn("WARN|commits-app", cli(lab, "status").stdout)
            r = cli(lab, "apply", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.ws, "app", "CLAUDE.local.md")))
            with open(os.path.join(lab.arkana, "CLAUDE.md"), "w") as f:
                f.write("# Arkana\n\nReglas propias.\n")
            r = cli(lab, "apply", "--component", "arkana", "--component", "app", "--component", "app-ui")
            self.assertEqual(r.returncode, 0, r.stdout)
            ark = leer(os.path.join(lab.arkana, "CLAUDE.md"))
            self.assertIn("Reglas propias.", ark)
            self.assertIn("<!-- arkana:commits:start -->", ark)
            self.assertIn("Conventional Commits con dos puntos", ark)                                # por defecto: conventional
            self.assertNotIn("**IA4D**", ark)
            mf = leer(os.path.join(lab.ws, "app", "src", "ui", "CLAUDE.local.md"))
            self.assertIn("Conventional Commits con dos puntos", mf)
            self.assertIn("chore(app-ui):", mf)
            self.assertNotIn("**IA4D**", mf)
            app = leer(os.path.join(lab.ws, "app", "CLAUDE.local.md"))
            self.assertIn("**IA4D**", app)
            self.assertIn("Nunca", app)
            self.assertEqual(cli(lab, "status", "--component", "app", "--component", "app-ui").returncode, 0)
            self.assertNotIn("WARN|", cli(lab, "status", "--component", "app", "--component", "app-ui").stdout)
            antes = leer(os.path.join(lab.arkana, "CLAUDE.md"))
            cli(lab, "apply", "--component", "arkana")
            self.assertEqual(leer(os.path.join(lab.arkana, "CLAUDE.md")), antes)                      # idempotente
            set_format(lab, "app-ui", "ia4d")
            self.assertIn("WARN|commits-app-ui", cli(lab, "status", "--component", "app-ui").stdout)   # cambia el manifiesto → desactualizado

    def test_formato_desconocido_falla_y_claude_md_versionado_ausente_no_se_crea(self):
        with TC.CLab() as lab:
            set_format(lab, "docs", "raro")
            r = cli(lab, "apply", "--component", "docs")
            self.assertEqual(r.returncode, 1)
            self.assertIn("commit_format desconocido", r.stdout)
            r = cli(lab, "apply", "--component", "specs")
            self.assertIn("WARN|commits-specs", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.ws, "specs", "CLAUDE.md")))


if __name__ == "__main__":
    unittest.main()
