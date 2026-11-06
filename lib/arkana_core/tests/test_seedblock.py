"""Bloques gestionados (arkana:NOMBRE) en CLAUDE.md: crear, añadir, reemplazar, sustituir marcadores antiguos y no tocar lo de fuera."""
import os
import tempfile
import unittest

import common  # noqa: F401
from arkana_core import seedblock as S

OLD = [("<!-- antiguo:novedades:start -->", "<!-- antiguo:novedades:end -->")]


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

    def test_sustituye_marcadores_antiguos(self):
        self.write("antes\n<!-- antiguo:novedades:start -->\n@../x/novedades.md\n<!-- antiguo:novedades:end -->\ndespués\n")
        self.assertEqual(S.state(self.f, "messaging", "b", OLD), "DESACTUALIZADO")
        self.assertEqual(S.apply(self.f, "messaging", "b", OLD), "reemplazado")
        t = self.read()
        self.assertNotIn("antiguo", t)
        self.assertTrue(t.startswith("antes\n"))
        self.assertIn("después", t)

    def test_drop_lines(self):
        self.write("a\n@.arkana/core/novedades.md\nb\n")
        self.assertEqual(S.drop_lines(self.f, {"@.arkana/core/novedades.md"}, dry=True), 1)
        self.assertEqual(self.read(), "a\n@.arkana/core/novedades.md\nb\n")
        self.assertEqual(S.drop_lines(self.f, {"@.arkana/core/novedades.md"}), 1)
        self.assertEqual(self.read(), "a\nb\n")


if __name__ == "__main__":
    unittest.main()
