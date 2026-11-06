"""launch.SEED_BLOCK: el worker no recibe la semilla de mensajería del CLAUDE.md (marcador actual y anterior)."""
import unittest

import common  # noqa: F401  (pone scripts/lib en sys.path)
import launch

NORMA = "# repo\n\nNorma del repo: commits en ingles.\n"


class TestSeedBlock(unittest.TestCase):
    def recorta(self, texto):
        return launch.SEED_BLOCK.sub("", texto).strip()

    def test_quita_el_marcador_actual(self):
        t = NORMA + "\n<!-- arkana:messaging:start -->\n@algo/novedades.md\n<!-- arkana:messaging:end -->\n"
        self.assertEqual(self.recorta(t), NORMA.strip())

    def test_respeta_el_resto_del_contenido(self):
        t = "antes\n<!-- arkana:messaging:start -->\nx\n<!-- arkana:messaging:end -->\ndespues\n"
        self.assertEqual(self.recorta(t), "antes\n\ndespues")

    def test_sin_semilla_no_cambia_nada(self):
        self.assertEqual(self.recorta(NORMA), NORMA.strip())


if __name__ == "__main__":
    unittest.main()
