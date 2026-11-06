import os
import tempfile
import unittest

import common
import commitmsg


class TestCommitMsg(unittest.TestCase):
    """El formato de commit y los dominios de correo salen del manifiesto del workspace de pruebas (common.make_workspace)."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previo = os.environ.get("ARKANA_HOME")
        common.make_workspace(self.tmp.name)
        os.environ["ARKANA_HOME"] = os.path.join(self.tmp.name, "shared")

    def tearDown(self):
        if self.previo is None:
            os.environ.pop("ARKANA_HOME", None)
        else:
            os.environ["ARKANA_HOME"] = self.previo
        self.tmp.cleanup()

    def test_conventional_por_defecto_e_ia4d_opcional(self):
        for repo in ("docs", "specs"):                                                         # sin commit_format
            self.assertEqual(commitmsg.format_of(repo), "conv", repo)
            self.assertEqual(commitmsg.check_message(repo, "docs(docs): add guides"), [], repo)
            self.assertTrue(commitmsg.check_message(repo, "docs(docs) add guides"), repo)

    def test_ia4d_cuando_el_componente_lo_pide(self):
        for repo in ("shared", "app", "api", "app-web"):
            self.assertEqual(commitmsg.check_message(repo, "docs(shared) add workstation setup guides"), [], repo)
            self.assertTrue(commitmsg.check_message(repo, "docs(shared): add guides"), repo)

    def test_conventional_exige_dos_puntos(self):
        self.assertEqual(commitmsg.check_message("app-ui", "chore(app-ui): ignore local Claude files"), [])
        self.assertTrue(commitmsg.check_message("app-ui", "chore(app-ui) ignore local Claude files"))
        self.assertTrue(commitmsg.check_message("app-ui", "cosa(app-ui): tipo invalido"))

    def test_longitud_punto_y_coautor(self):
        self.assertTrue(commitmsg.check_message("shared", "docs(shared) " + "x" * 70))
        self.assertTrue(commitmsg.check_message("shared", "docs(shared) termina en punto."))
        self.assertTrue(commitmsg.check_message("shared", "docs(shared) ok\n\nCo-Authored-By: X <x@y>"))
        self.assertEqual(commitmsg.check_message("shared", "docs(shared) ok\n\ncuerpo largo sin problema"), [])

    def test_autor_con_dominio_exigido_solo_donde_el_componente_lo_declara(self):
        self.assertEqual(commitmsg.check_message("app-web", "chore(app-web) x", "u@example.org"), [])
        self.assertEqual(commitmsg.check_message("app-ui", "chore(app-ui): x", "u@ext.example.org"), [])
        self.assertTrue(commitmsg.check_message("app-web", "chore(app-web) x", "u@otro.com"))
        self.assertIn("@example.org", commitmsg.check_message("app-web", "chore(app-web) x", "u@otro.com")[0])
        self.assertEqual(commitmsg.check_message("shared", "docs(shared) x", "u@otro.com"), [])           # sin email_domains: sin regla
        self.assertEqual(commitmsg.check_message("api", "chore(api) x", "u@otro.com"), [])

    def test_formato_del_componente_segun_el_manifiesto(self):
        self.assertEqual((commitmsg.format_of("api"), commitmsg.format_of("app-ui"), commitmsg.format_of("nadie")), ("ia4d", "conv", None))

    def test_arkana_tiene_su_propio_formato_y_dominios_igual_que_un_componente(self):
        import json
        p = os.path.join(self.tmp.name, "shared", ".arkana", "core", "workspace.json")
        d = json.load(open(p))
        d["arkana"].update(commit_format="conventional", git={"email_domains": ["example.org"]})
        json.dump(d, open(p, "w"))
        for alias in ("arkana", "shared"):                                                    # `shared` es el id histórico de ARKANA
            self.assertEqual(commitmsg.format_of(alias), "conv", alias)
            self.assertEqual(commitmsg.check_message(alias, "docs(arkana): x", "u@example.org"), [], alias)
            self.assertTrue(commitmsg.check_message(alias, "docs(arkana) x"), alias)                                   # sin dos puntos: no vale
            self.assertTrue(commitmsg.check_message(alias, "docs(arkana): x", "u@otro.com"), alias)                    # dominio no permitido

    def test_repo_desconocido(self):
        self.assertTrue(commitmsg.check_message("otro", "docs(x) y"))


if __name__ == "__main__":
    unittest.main()
