"""paths.py: ubicación de los metadatos (.arkana de la carpeta de ARKANA) y compatibilidad con ~/.claude."""
from pathlib import Path
import os
import tempfile
import unittest

import common  # noqa: F401  (pone scripts/lib en sys.path)
import launch
import paths


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "home")
        self.shared = os.path.join(self.tmp.name, "shared")
        os.makedirs(os.path.join(self.home, ".claude")); os.makedirs(self.shared)
        self._env = dict(os.environ)
        for k in ("ARKANA_HOME", "ARKANA_PLUGINS_DIR", "ARKANA_SHARED", "ARKANA_BASE", "ARKANA_AGENTIC_DIR"):
            os.environ.pop(k, None)
        os.environ["HOME"] = self.home
        os.environ["ARKANA_SHARED"] = self.shared

    def tearDown(self):
        os.environ.clear(); os.environ.update(self._env); self.tmp.cleanup()


class TestNombreDeCarpeta(Base):
    """La carpeta de ARKANA se reconoce por su contenido, no por su nombre; `arkana` y `shared` valen como hermana de un repo git."""
    def _crear(self, nombre):
        d = os.path.join(self.tmp.name, nombre)
        os.makedirs(os.path.join(d, "plugins")); os.makedirs(os.path.join(d, ".arkana"))
        Path(os.path.join(d, ".arkana", "arkana.json")).write_text("{}")
        return os.path.realpath(d)

    def _aislado(self, cwd):
        for k in ("ARKANA_HOME", "ARKANA_SHARED"):
            os.environ.pop(k, None)
        import importlib.util
        import subprocess
        subprocess.run(["git", "init", "-q", cwd], check=True)
        spec = importlib.util.spec_from_file_location("paths_aislado", os.path.join(os.path.dirname(paths.__file__), "paths.py"))
        aislado = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(aislado)
        aislado.__file__ = os.path.join(self.tmp.name, "fuera", "paths.py")        # sin ancestro que sea ARKANA
        return aislado

    def test_hermana_arkana(self):
        d = self._crear("arkana"); repo = os.path.join(self.tmp.name, "api"); os.makedirs(repo)
        self.assertEqual(self._aislado(repo).arkana_dir(cwd=repo), d)

    def test_hermana_shared_nombre_heredado(self):
        d = self._crear("shared"); repo = os.path.join(self.tmp.name, "api"); os.makedirs(repo)
        self.assertEqual(self._aislado(repo).arkana_dir(cwd=repo), d)

    def test_shared_dir_sigue_existiendo_como_alias(self):
        self.assertIs(paths.shared_dir, paths.arkana_dir)


class TestRutas(Base):
    def test_carpeta_por_defecto_en_la_de_arkana(self):
        self.assertEqual(paths.plugins_dir(), os.path.join(os.path.realpath(self.shared), ".arkana"))

    def test_arkana_plugins_dir_manda(self):
        os.environ["ARKANA_PLUGINS_DIR"] = "/tmp/x"
        self.assertEqual(paths.plugins_dir(), "/tmp/x")
        self.assertEqual(paths.item("core/workspace.json"), "/tmp/x/core/workspace.json")

    def test_sin_nada_se_usa_la_carpeta_nueva(self):
        self.assertEqual(paths.item("arkana-agentic"), os.path.join(paths.plugins_dir(), "arkana-agentic"))

    def test_item_cuelga_siempre_de_la_carpeta_arkana(self):
        self.assertEqual(paths.item("core/workspace.json"), os.path.join(paths.plugins_dir(), "core", "workspace.json"))


class TestManifiesto(Base):
    def escribir_manifiesto(self, ws):
        import json
        st = os.path.join(self.shared, ".arkana")
        os.makedirs(os.path.join(st, "core"))
        Path(os.path.join(st, "arkana.json")).write_text(json.dumps({"schema_version": 1, "root": ".."}))
        Path(os.path.join(st, "core", "workspace.json")).write_text(json.dumps({"schema": 1, "arkana": {"alias": "ARKANA", "path": "shared"},
                   "components": [{"alias": "api", "type": "maven", "path": "back"}, {"alias": "docs", "type": "docs", "path": "d"}]}))

    def test_arkana_home_manda_sobre_arkana_shared(self):
        otra = os.path.join(self.tmp.name, "otra"); os.makedirs(otra)
        os.environ["ARKANA_HOME"] = otra
        # (el tearDown de Base restaura el entorno completo, incluido el ARKANA_HOME por defecto de common.py)
        self.assertEqual(paths.shared_dir(), os.path.realpath(otra))

    def test_los_repos_salen_del_manifiesto_cuando_existe(self):
        import repos
        self.escribir_manifiesto(self.tmp.name)
        raiz = os.path.dirname(self.shared)
        self.assertEqual(repos.repo_path("api"), os.path.join(raiz, "back"))
        self.assertEqual(repos.repo_path("docs"), os.path.join(raiz, "d"))

    def test_sin_manifiesto_los_repos_fallan_con_un_error_claro(self):
        import repos
        with self.assertRaises(repos._manifest.ManifestError):
            repos._workspace()
        self.assertFalse(hasattr(repos, "REPO_IDS"))                       # no queda ninguna lista de repos en el código
        self.assertFalse(hasattr(repos, "DEFAULT_PATHS"))

    def test_sin_workspace_localizable_no_hay_ruta_por_defecto(self):
        for k in ("ARKANA_HOME", "ARKANA_SHARED", "ARKANA_BASE"):
            os.environ.pop(k, None)
        fake = os.path.join(self.tmp.name, "plugin-instalado", "scripts", "lib", "paths.py")   # un plugin instalado fuera de un repo de Arkana
        os.makedirs(os.path.dirname(fake))
        import importlib.util
        spec = importlib.util.spec_from_file_location("paths_aislado", os.path.join(os.path.dirname(paths.__file__), "paths.py"))
        aislado = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(aislado)
        aislado.__file__ = fake
        with self.assertRaises(aislado.NoWorkspace):
            aislado.shared_dir(cwd=self.tmp.name)


class TestIntegracion(Base):
    def test_el_estado_de_agentic_usa_la_carpeta_nueva(self):
        import state
        self.assertEqual(state.base_dir(), os.path.join(paths.plugins_dir(), "arkana-agentic"))
        os.environ["ARKANA_AGENTIC_DIR"] = "/tmp/otro"
        self.assertEqual(state.base_dir(), "/tmp/otro")

    def test_el_worker_no_puede_leer_ni_editar_los_metadatos(self):
        meta = paths.plugins_dir().lstrip("/")
        deny = launch.worker_settings("home/x/repo", "edicion", [])["permissions"]["deny"]
        self.assertIn(f"Read(/{meta}/**)", deny)
        self.assertIn(f"Edit(/{meta}/**)", deny)
        self.assertIn(f"Read(/{meta}/.credentials)", deny); self.assertIn(f"Edit(/{meta}/.credentials)", deny)

    def test_el_worker_no_ejecuta_hooks_de_usuario(self):
        for perfil in ("edicion", "lectura"):
            self.assertIs(launch.worker_settings("home/x/repo", perfil, [])["disableAllHooks"], True)


if __name__ == "__main__":
    unittest.main()
