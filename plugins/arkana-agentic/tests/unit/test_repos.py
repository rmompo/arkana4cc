"""repos: los repos salen del manifiesto, la rama de un plan es arkana-worker/<plan> y las ramas m3a/ de planes anteriores se siguen reconociendo."""
import os
import tempfile
import unittest

import common
import repos


class TestRepos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previo = os.environ.get("ARKANA_HOME")
        self.rutas = common.make_workspace(self.tmp.name)
        os.environ["ARKANA_HOME"] = self.rutas["arkana"]

    def tearDown(self):
        if self.previo is None:
            os.environ.pop("ARKANA_HOME", None)
        else:
            os.environ["ARKANA_HOME"] = self.previo
        self.tmp.cleanup()

    def test_los_repos_y_sus_rutas_salen_del_manifiesto(self):
        self.assertEqual(repos.repo_ids(), ["arkana", "app", "api", "app-web", "app-ui", "docs", "specs"])
        self.assertEqual(repos.repo_path("app-web"), self.rutas["app-web"])
        self.assertEqual(repos.all_repos(), {k: v for k, v in self.rutas.items() if k != "shared"})
        self.assertTrue(repos.repo_known("shared") and repos.repo_known("API"))               # `shared` es el id histórico de ARKANA; no distingue mayúsculas
        self.assertFalse(repos.repo_known("otro"))
        with self.assertRaises(KeyError):
            repos.repo_path("otro")

    def test_la_rama_de_un_plan_usa_el_prefijo_nuevo_y_reconoce_el_anterior(self):
        self.assertEqual(repos.plan_branch("P2611041200-abcd"), "arkana-worker/P2611041200-abcd")
        for rama in ("arkana-worker/P1", "m3a/P1"):                                          # m3a/ lo usaron los planes anteriores
            self.assertTrue(repos.is_plan_branch(rama), rama)
        for rama in ("develop", "main", "feature/x", "arkana/P1", "m3a", "", None):
            self.assertFalse(repos.is_plan_branch(rama), rama)


    def test_launch_y_verify_sin_workspace_dan_un_error_limpio_no_un_traceback(self):
        import contextlib
        import io
        import launch
        import paths
        import verify
        originales = (launch._main, verify.finish)

        def sin_workspace(*a, **k):
            raise paths.NoWorkspace("no se encuentra el workspace de Arkana")
        launch._main, verify.finish = sin_workspace, sin_workspace
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                self.assertEqual(launch.main(["launch", "P1", "T001"]), 3)
                self.assertEqual(verify.main(["finish", "P1", "T001"]), 3)
        finally:
            launch._main, verify.finish = originales
        self.assertEqual(out.getvalue().count("workspace de Arkana"), 4)           # mensaje propio + el de la excepción, en cada uno
        vacio = os.path.join(self.tmp.name, "vacio")                               # y con una carpeta sin manifiesto de verdad
        os.makedirs(vacio)
        os.environ["ARKANA_HOME"] = vacio
        with self.assertRaises(repos._manifest.ManifestError):
            repos.repo_ids()


if __name__ == "__main__":
    unittest.main()
