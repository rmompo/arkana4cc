"""Migración 0010: plantilla arkana-docs/.arkanaignore para las instalaciones que ya existían."""
import os
import unittest

from test_evolve import Lab, git


def existe(lab, rel):
    return os.path.exists(os.path.join(lab.arkana, rel))


class TestMigracion0010(unittest.TestCase):
    def test_crea_la_plantilla_comentada_en_una_instalacion_existente(self):
        with Lab() as lab:
            lab.run("apply", "--to", "9")
            os.remove(os.path.join(lab.arkana, "arkana-docs", ".arkanaignore")) if existe(lab, "arkana-docs/.arkanaignore") else None
            self.assertIn("0010", lab.run("check").stdout)
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("0010:plantilla", r.stdout)
            txt = lab.read("arkana-docs/.arkanaignore")
            self.assertIn("node_modules/", txt)
            self.assertFalse([l for l in txt.splitlines() if l.strip() and not l.lstrip().startswith("#")])     # solo comentarios: no ignora nada
            self.assertEqual(lab.project()["layout"], 10)

    def test_no_pisa_uno_existente_y_es_idempotente(self):
        with Lab() as lab:
            lab.run("apply", "--to", "9")
            lab.write("arkana-docs/.arkanaignore", "*.py\n")
            lab.run("apply")
            self.assertEqual(lab.read("arkana-docs/.arkanaignore"), "*.py\n")
            self.assertIn("nada que hacer", lab.run("apply").stdout)

    def test_dry_run_no_escribe(self):
        with Lab() as lab:
            lab.run("apply", "--to", "9")
            if existe(lab, "arkana-docs/.arkanaignore"):
                os.remove(os.path.join(lab.arkana, "arkana-docs", ".arkanaignore"))
            r = lab.run("apply", "--dry-run")
            self.assertIn("DRY|0010:plantilla|arkana-docs/.arkanaignore se crearía", r.stdout)
            self.assertFalse(existe(lab, "arkana-docs/.arkanaignore"))

    def test_una_instalacion_nueva_la_recibe_con_un_solo_apply(self):
        with Lab() as lab:
            self.assertEqual(lab.run("apply").returncode, 0)
            self.assertTrue(existe(lab, "arkana-docs/.arkanaignore"))
            for d in ("src", "md", "out"):
                self.assertTrue(existe(lab, f"arkana-docs/{d}/.gitkeep"), d)

    def test_con_el_fichero_versionado_y_modificado_sin_commitear_no_se_toca(self):
        with Lab() as lab:
            lab.run("apply", "--to", "9")
            lab.write("arkana-docs/.arkanaignore", "a\n"); git(lab.arkana, "add", "-A", "-f"); git(lab.arkana, "commit", "-q", "-m", "chore(root) base")
            lab.write("arkana-docs/.arkanaignore", "a\nb\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)                                   # existe: no es pendiente, así que no hay precondición que fallar
            self.assertEqual(lab.read("arkana-docs/.arkanaignore"), "a\nb\n")


if __name__ == "__main__":
    unittest.main()
