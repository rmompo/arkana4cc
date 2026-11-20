import json
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
            os.makedirs(os.path.dirname(locate.registry_path()), exist_ok=True)
            with open(locate.registry_path(), "w") as f:
                f.write("{no es json")
            self.assertEqual(locate.read_registry(), [])

    def test_el_registro_vive_en_la_carpeta_de_usuario_de_arkana(self):
        with common.Lab() as lab:
            lab.registrar()
            self.assertEqual(locate.registry_path(), os.path.join(os.path.expanduser("~"), ".arkana", "workspaces.json"))
            self.assertTrue(os.path.isfile(locate.registry_path()))
            self.assertFalse(os.path.exists(locate.legacy_registry_path()))
            self.assertEqual(locate.find_home(cwd=os.path.join(lab.ws, "md-backend")), lab.arkana)

    def test_el_registro_antiguo_se_sigue_leyendo_y_se_migra_al_registrar(self):
        with common.Lab() as lab:
            antiguo = {"workspaces": [{"name": "viejo", "arkana": lab.arkana, "root": lab.ws}]}
            with open(locate.legacy_registry_path(), "w") as f:
                json.dump(antiguo, f)
            self.assertEqual(locate.find_home(cwd=os.path.join(lab.ws, "md-backend")), lab.arkana)      # se lee sin migrar
            self.assertFalse(os.path.exists(locate.registry_path()))
            self.assertTrue(lab.registrar())                                                             # al registrar: mueve y conserva las entradas
            self.assertTrue(os.path.isfile(locate.registry_path()))
            self.assertFalse(os.path.exists(locate.legacy_registry_path()))
            self.assertEqual([w["arkana"] for w in locate.read_registry()], [lab.arkana])

    def test_registrar_sin_nombre_conserva_el_que_ya_tenia_la_entrada(self):
        with common.Lab() as lab:
            lab.registrar()
            self.assertTrue(locate.register(lab.arkana, "mi-proyecto"))                      # con nombre explícito se cambia
            self.assertFalse(locate.register(lab.arkana))                                    # sin nombre: no lo pisa
            self.assertEqual([w["name"] for w in locate.read_registry()], ["mi-proyecto"])

    def test_el_registro_nuevo_manda_sobre_el_antiguo(self):
        with common.Lab() as lab:
            lab.registrar()
            with open(locate.legacy_registry_path(), "w") as f:
                json.dump({"workspaces": [{"name": "x", "arkana": "/otro", "root": "/otro"}]}, f)
            self.assertEqual([w["arkana"] for w in locate.read_registry()], [lab.arkana])


if __name__ == "__main__":
    unittest.main()
