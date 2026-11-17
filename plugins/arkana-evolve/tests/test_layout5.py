"""Migración 0005: solo estampa layout 5 (los campos nuevos del manifiesto son opcionales)."""
import json
import os
import unittest

from test_evolve import Lab


class TestMigracion0005(unittest.TestCase):
    def test_estampa_layout_5_y_no_toca_ningun_dato(self):
        with Lab() as lab:
            lab.run("apply", "--to", "4")
            self.assertEqual(lab.project()["layout"], 4)
            mf = lab.read(".arkana/core/workspace.json")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("0005", r.stdout)
            p = lab.project()
            self.assertEqual(p["layout"], 5)
            self.assertEqual(p["history"][-1]["id"], "0005")
            self.assertEqual(lab.read(".arkana/core/workspace.json"), mf)             # el manifiesto ni se rozó (la 0003 ya le dio los ids antes)

    def test_idempotente_y_dry_run_no_escribe(self):
        with Lab() as lab:
            lab.run("apply", "--to", "4")
            antes = lab.read("arkana-project.json")
            r = lab.run("apply", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("layout 5", r.stdout)
            self.assertEqual(lab.read("arkana-project.json"), antes)
            lab.run("apply")
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertNotIn("WARN|", lab.run("check").stdout)

    def test_no_aplica_con_la_instalacion_sin_registro(self):
        with Lab() as lab:
            self.assertIn("0005", lab.run("check").stdout)


if __name__ == "__main__":
    unittest.main()
