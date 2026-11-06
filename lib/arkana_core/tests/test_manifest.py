import json
import os
import unittest

import common
from arkana_core import manifest


class TestCarga(unittest.TestCase):
    def test_aliases_y_orden(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual(w.aliases(), ["arkana", "app", "api", "app-web", "app-ui", "docs", "specs"])
            self.assertEqual(w.aliases(include_arkana=False)[0], "app")

    def test_rutas_absolutas_bajo_la_raiz(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual(w.root, lab.ws)
            self.assertEqual(w.path("api"), os.path.join(lab.ws, "md-backend"))
            self.assertEqual(w.path("arkana"), os.path.join(lab.ws, "shared"))

    def test_id_historico_shared_es_arkana(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual(w.path("shared"), w.path("arkana"))
            self.assertEqual(manifest.canon("SHARED"), "arkana")
            self.assertEqual(manifest.display("shared"), "ARKANA")
            self.assertEqual(manifest.display("App"), "app")

    def test_alias_sin_distinguir_mayusculas(self):
        with common.Lab() as lab:
            self.assertTrue(manifest.load(lab.arkana).has("API"))
            with self.assertRaises(KeyError):
                manifest.load(lab.arkana).get("no-existe")

    def test_anidamiento_se_deduce_de_las_rutas(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual(sorted(w.nested_in("app")), ["app-ui", "app-web"])
            self.assertEqual(w.nested_in("api"), [])

    def test_pieza_dueña_de_una_ruta_es_la_mas_especifica(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual(w.owner_of(os.path.join(lab.ws, "md-mf", "src", "wa", "x.ts")), "app-web")
            self.assertEqual(w.owner_of(os.path.join(lab.ws, "md-mf", "README.md")), "app")
            self.assertEqual(w.owner_of(os.path.join(lab.arkana, "plugins")), "arkana")
            self.assertIsNone(w.owner_of(lab.root))

    def test_local_json_manda_sobre_el_manifiesto(self):
        with common.Lab() as lab:
            lab.escribir(os.path.join("arkana-workspace", "local.json"), {"paths": {"api": "/otro/sitio", "docs": "~/docs"}})
            w = manifest.load(lab.arkana)
            self.assertEqual(w.path("api"), "/otro/sitio")
            self.assertEqual(w.path("docs"), os.path.expanduser("~/docs"))
            self.assertEqual(w.path("app"), os.path.join(lab.ws, "md-mf"))


class TestValidacion(unittest.TestCase):
    def errores(self, **cambios):
        d = common.manifiesto()
        d.update(cambios)
        return manifest.validate(d)

    def test_el_manifiesto_del_laboratorio_es_valido(self):
        self.assertEqual(self.errores(), [])

    def test_rechaza_rutas_absolutas_y_que_salen_de_la_raiz(self):
        for ruta in ("/abs", "../fuera", "a/../../b", "~/x"):
            e = self.errores(components=[{"alias": "x", "type": "node", "path": ruta}])
            self.assertTrue(any("relativa" in m for m in e), (ruta, e))

    def test_rechaza_alias_repetidos_reservados_y_mal_formados(self):
        base = {"type": "node", "path": "p"}
        e = self.errores(components=[dict(base, alias="a", path="1"), dict(base, alias="a", path="2")])
        self.assertTrue(any("repetido" in m for m in e), e)
        for alias in ("arkana", "all", "shared"):
            self.assertTrue(any("reservado" in m for m in self.errores(components=[dict(base, alias=alias)])), alias)
        self.assertTrue(any("alias" in m for m in self.errores(components=[dict(base, alias="Mal Nombre")])))

    def test_rechaza_rutas_repetidas(self):
        c = [{"alias": "a", "type": "node", "path": "x"}, {"alias": "b", "type": "node", "path": "x/"}]
        self.assertTrue(any("ya la usa" in m for m in self.errores(components=c)))

    def test_el_esquema_rechaza_tipos_desconocidos_y_claves_sobrantes(self):
        self.assertTrue(self.errores(components=[{"alias": "a", "type": "cobol", "path": "p"}]))
        self.assertTrue(self.errores(components=[{"alias": "a", "type": "node", "path": "p", "sobra": 1}]))
        self.assertTrue(self.errores(schema="uno"))

    def test_faltan_campos_obligatorios(self):
        d = common.manifiesto(); del d["arkana"]
        self.assertTrue(manifest.validate(d))


class TestErrores(unittest.TestCase):
    def test_sin_workspace(self):
        with common.Lab() as lab:
            with self.assertRaises(manifest.ManifestError):
                manifest.load(cwd=lab.root)

    def test_json_roto_y_manifiesto_no_valido(self):
        with common.Lab() as lab:
            with open(os.path.join(lab.arkana, ".arkana", "core", "workspace.json"), "w") as f:
                f.write("{roto")
            with self.assertRaisesRegex(manifest.ManifestError, "JSON"):
                manifest.load(lab.arkana)
            lab.escribir(os.path.join("core", "workspace.json"), {"schema": 1, "arkana": {"alias": "A", "path": "/x"}, "components": []})
            with self.assertRaisesRegex(manifest.ManifestError, "no válido"):
                manifest.load(lab.arkana)


if __name__ == "__main__":
    unittest.main()
