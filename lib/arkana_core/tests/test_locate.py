import os
import unittest

import common
from arkana_core import locate


class TestLocate(unittest.TestCase):
    def test_arkana_home_manda(self):
        with common.Lab() as lab:
            os.environ["ARKANA_HOME"] = lab.arkana
            self.assertEqual(locate.find_home(cwd=lab.root), lab.arkana)

    def test_arkana_home_que_no_es_carpeta_se_ignora(self):
        with common.Lab() as lab:
            os.environ["ARKANA_HOME"] = os.path.join(lab.root, "no-existe")
            self.assertEqual(locate.find_home(cwd=lab.arkana), lab.arkana)

    def test_ancestro_del_directorio_actual(self):
        with common.Lab() as lab:
            sub = os.path.join(lab.arkana, "plugins", "x"); os.makedirs(sub)
            self.assertEqual(locate.find_home(cwd=sub), lab.arkana)

    def test_desde_un_componente_hace_falta_el_registro(self):
        with common.Lab() as lab:
            comp = os.path.join(lab.ws, "md-backend")
            self.assertIsNone(locate.find_home(cwd=comp))
            self.assertTrue(lab.registrar())
            self.assertEqual(locate.find_home(cwd=comp), lab.arkana)
            self.assertEqual(locate.find_home(cwd=os.path.join(lab.ws, "md-mf", "src", "wa")), lab.arkana)

    def test_fuera_del_workspace_no_hay_nada(self):
        with common.Lab() as lab:
            lab.registrar()
            self.assertIsNone(locate.find_home(cwd=lab.root))                  # la raíz del lab no es la del workspace
            self.assertIsNone(locate.find_home(cwd=os.path.join(lab.ws + "-otro")))

    def test_registro_con_una_entrada_obsoleta_no_rompe(self):
        with common.Lab() as lab:
            lab.registrar()
            os.rename(os.path.join(lab.arkana, ".arkana", "arkana.json"), os.path.join(lab.arkana, ".arkana", "x"))
            self.assertIsNone(locate.find_home(cwd=os.path.join(lab.ws, "md-backend")))

    def test_registrar_es_idempotente(self):
        with common.Lab() as lab:
            self.assertTrue(lab.registrar())
            self.assertFalse(lab.registrar())
            self.assertEqual(len(locate.read_registry()), 1)

    def test_raiz_del_workspace(self):
        with common.Lab() as lab:
            self.assertEqual(locate.workspace_root(lab.arkana), lab.ws)
            lab.escribir("arkana.json", {"schema_version": 1, "root": lab.root})
            self.assertEqual(locate.workspace_root(lab.arkana), lab.root)

    def test_registro_ilegible_se_trata_como_vacio(self):
        with common.Lab() as lab:
            with open(locate.registry_path(), "w") as f:
                f.write("{no es json")
            self.assertEqual(locate.read_registry(), [])


if __name__ == "__main__":
    unittest.main()
