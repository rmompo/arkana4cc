"""Bloques gestionados (arkana:NOMBRE) en CLAUDE.md: crear, añadir, reemplazar y no tocar lo de fuera."""
import os
import tempfile
import unittest

import common  # noqa: F401
from arkana_core import seedblock as S


class TestSeedBlock(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="sb-")
        self.f = os.path.join(self.d, "CLAUDE.md")

    def read(self):
        with open(self.f, encoding="utf-8") as fh:
            return fh.read()

    def write(self, t):
        with open(self.f, "w", encoding="utf-8") as fh:
            fh.write(t)

    def test_ciclo_completo(self):
        self.assertEqual(S.state(self.f, "x", "hola"), "SIN-FICHERO")
        self.assertEqual(S.apply(self.f, "x", "hola", create=False), "falta-fichero")
        self.assertEqual(S.apply(self.f, "x", "hola"), "creado")
        self.assertEqual((S.state(self.f, "x", "hola"), S.apply(self.f, "x", "hola")), ("OK", "igual"))
        self.assertEqual(S.state(self.f, "x", "distinto"), "DESACTUALIZADO")
        self.assertEqual(S.apply(self.f, "x", "distinto", backup_dir=os.path.join(self.d, "bak")), "reemplazado")
        self.assertIn("distinto", self.read())
        self.assertNotIn("hola", self.read())
        self.assertEqual(len(os.listdir(os.path.join(self.d, "bak"))), 1)

    def test_no_toca_lo_de_fuera_y_añade_al_final(self):
        self.write("# Mi repo\n\nReglas propias.\n")
        self.assertEqual(S.state(self.f, "x", "b"), "SIN-BLOQUE")
        self.assertEqual(S.apply(self.f, "x", "b", dry=True), "añadido")
        self.assertEqual(self.read(), "# Mi repo\n\nReglas propias.\n")                       # dry-run no escribe
        S.apply(self.f, "x", "b")
        t = self.read()
        self.assertTrue(t.startswith("# Mi repo\n\nReglas propias.\n"))
        S.apply(self.f, "x", "c")
        self.assertTrue(self.read().startswith("# Mi repo\n\nReglas propias.\n"))
        self.assertEqual(self.read().count("arkana:x:start"), 1)


if __name__ == "__main__":
    unittest.main()
