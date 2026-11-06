"""Adaptadores por tipo de componente: unión de comandos del plan, rutas protegidas por repo, herramientas y registros declarados en tools.json."""
import json
import os
import tempfile
import unittest

import common  # noqa: F401
import adapters
import matchers
import state


def write(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


class TestAdaptadores(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="adp-")
        self.old = dict(os.environ)
        for k in ("ARKANA_AGENTIC_DIR",):
            os.environ.pop(k, None)
        self.shared = os.path.join(self.d, "shared")
        st = os.path.join(self.shared, ".arkana")
        write(os.path.join(st, "arkana.json"), {"schema_version": 1, "workspace": {"name": "t"}, "root": ".."})
        write(os.path.join(st, "core", "workspace.json"), {"schema": 1, "workspace": {"name": "t"}, "arkana": {"alias": "ARKANA", "path": "shared"},
              "components": [{"alias": "app-web", "type": "node", "path": "wa"}, {"alias": "api", "type": "maven", "path": "be"},
                             {"alias": "docs", "type": "docs", "path": "docs"}]})
        os.environ.update(ARKANA_HOME=self.shared, HOME=os.path.join(self.d, "home"))
        os.makedirs(os.environ["HOME"])

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old)

    def test_tipos_del_manifiesto_y_arkana_generico(self):
        self.assertEqual([adapters.repo_type(r) for r in ("app-web", "api", "docs", "arkana", "shared")], ["node", "maven", "docs", "generic", "generic"])
        self.assertEqual(adapters.repo_type("desconocido"), "generic")                              # un repo que no es del manifiesto no tiene adaptador propio

    def test_la_lista_del_plan_es_la_union_de_los_adaptadores_de_sus_repos(self):
        solo_docs = state.load_allowed_commands(["docs"])
        self.assertEqual(solo_docs, [["git", "diff", "--stat"]])
        self.assertTrue(matchers.is_allowed_command(["mvn", "-B", "test"], state.load_allowed_commands(["api"])))
        self.assertFalse(matchers.is_allowed_command(["npm", "test"], state.load_allowed_commands(["api"])))
        mixto = state.load_allowed_commands(["api", "app-web"])
        for c in (["mvn", "-B", "test"], ["npm", "test"], ["git", "diff", "--stat"]):
            self.assertTrue(matchers.is_allowed_command(c, mixto), c)
        self.assertEqual(len(mixto), len({tuple(c) for c in mixto}))                          # sin duplicados
        self.assertTrue(matchers.is_allowed_command(["npm", "test"], state.load_allowed_commands()))   # sin repos: todos los tipos del manifiesto

    def test_las_rutas_protegidas_son_las_del_adaptador_del_repo(self):
        be, wa = state.load_protected_paths("api")["patrones"], state.load_protected_paths("app-web")["patrones"]
        self.assertTrue(matchers.is_protected_path("pom.xml", be) and matchers.is_protected_path("sub/pom.xml", be))
        self.assertFalse(matchers.is_protected_path("pom.xml", wa))
        self.assertTrue(matchers.is_protected_path("package-lock.json", wa))
        self.assertFalse(matchers.is_protected_path("package-lock.json", be))
        for rid in ("api", "app-web", "docs"):
            self.assertTrue(matchers.is_protected_path("CLAUDE.md", state.load_protected_paths(rid)["patrones"]))     # lo común va en todos
        self.assertIn("scripts", state.load_protected_paths("app-web")["package_json_campos"])
        self.assertEqual(state.load_protected_paths("api")["package_json_campos"], [])

    def test_herramientas_y_path_del_verificador_desde_tools_json(self):
        self.assertEqual(adapters.tools_required(["api"]), ["jdk", "maven"])
        jdk = os.path.join(self.d, "jdk8")
        os.makedirs(os.path.join(jdk, "bin"))
        write(os.path.join(self.shared, ".arkana", "arkana-workspace", "tools.json"), {"schema_version": 1, "tools": [{"tool": "jdk", "version": "8", "path": jdk}, {"tool": "node", "version": "18", "path": "/x"}]})
        self.assertEqual(adapters.tool_bin_dirs(["api"]), [os.path.join(jdk, "bin")])

    def test_registros_y_java_home_salen_de_tools_json(self):
        jdk = os.path.join(self.d, "jdk")
        os.makedirs(os.path.join(jdk, "bin"))
        write(os.path.join(self.shared, ".arkana", "arkana-workspace", "tools.json"), {"schema_version": 1, "tools": [
            {"tool": "jdk", "version": "21", "path": jdk}, {"tool": "node", "version": "20", "registries": {"@acme": "https://reg.example/npm/", "@otro": "https://o.example/"}}]})
        self.assertEqual(adapters.npmrc_lines(), "@acme:registry=https://reg.example/npm/\n@otro:registry=https://o.example/\n")
        self.assertEqual(adapters.tool_home("jdk"), jdk)
        self.assertIsNone(adapters.tool_home("maven"))

    def test_sin_registros_declarados_el_npmrc_va_vacio(self):
        self.assertEqual(adapters.npmrc_lines(), "")

    def test_sin_manifiesto_no_hay_repos_ni_valores_por_defecto(self):
        import repos
        vacio = os.path.join(self.d, "vacio")
        os.makedirs(vacio)
        os.environ["ARKANA_HOME"] = vacio                                                          # una carpeta sin .arkana/core/workspace.json
        with self.assertRaises(repos._manifest.ManifestError):
            repos.repo_path("api")
        with self.assertRaises(repos._manifest.ManifestError):
            repos.repo_ids()


if __name__ == "__main__":
    unittest.main()
