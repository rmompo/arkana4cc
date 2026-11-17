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

    def test_display_y_canon(self):
        self.assertEqual(manifest.canon(" APP "), "app")
        self.assertEqual(manifest.display("arkana"), "ARKANA")
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
        for alias in ("arkana", "all"):
            self.assertTrue(any("reservado" in m for m in self.errores(components=[dict(base, alias=alias)])), alias)
        self.assertTrue(any("alias" in m for m in self.errores(components=[dict(base, alias="Mal Nombre")])))

    def test_rechaza_rutas_repetidas(self):
        c = [{"alias": "a", "type": "node", "path": "x"}, {"alias": "b", "type": "node", "path": "x/"}]
        self.assertTrue(any("ya la usa" in m for m in self.errores(components=c)))

    def test_el_esquema_rechaza_tipos_desconocidos_y_claves_sobrantes(self):
        self.assertTrue(self.errores(components=[{"alias": "a", "type": "cobol", "path": "p"}]))
        self.assertTrue(self.errores(components=[{"alias": "a", "type": "node", "path": "p", "sobra": 1}]))
        self.assertTrue(self.errores(schema="uno"))

    def test_un_manifiesto_con_seed_file_se_rechaza_y_remite_a_evolve(self):
        with common.Lab() as lab:
            m = common.manifiesto()
            m["components"][0]["seed_file"] = "CLAUDE.local.md"
            lab.escribir(os.path.join("core", "workspace.json"), m)
            with self.assertRaises(manifest.ManifestError) as cm:
                manifest.load(lab.arkana)
            self.assertIn("/arkana-evolve:apply", str(cm.exception))

    def test_faltan_campos_obligatorios(self):
        d = common.manifiesto(); del d["arkana"]
        self.assertTrue(manifest.validate(d))


class TestCamposDeReferencia(unittest.TestCase):
    """mode, ref, watch y checks_skip (esquema 2): resolución única `component_flags`, validación y aviso de esquema desconocido."""

    def comp(self, **kw):
        return dict({"alias": "shell", "type": "node", "path": "mova3-shell"}, **kw)

    def errores(self, **kw):
        d = common.manifiesto(componentes=[("app", "node", "app")])
        d["components"].append(self.comp(**kw))
        return manifest.validate(d)

    def test_sin_campos_nuevos_todo_como_antes(self):
        f = manifest.component_flags({"alias": "a", "type": "node", "path": "p"})
        self.assertEqual(f, {"mode": "work", "ref": "", "statusline": True, "watch": True, "checks_skip": []})
        self.assertFalse(manifest.component_flags({"type": "docs"})["statusline"])               # defecto por tipo, como hasta ahora

    def test_reference_oculta_no_vigila_y_omite_checks_por_defecto(self):
        f = manifest.component_flags({"type": "node", "mode": "reference", "ref": "v6.2.0"})
        self.assertEqual((f["mode"], f["ref"], f["statusline"], f["watch"]), ("reference", "v6.2.0", False, False))
        self.assertEqual(f["checks_skip"], list(manifest.REFERENCE_SKIP))

    def test_lo_explicito_anula_el_defecto_del_modo(self):
        f = manifest.component_flags({"mode": "reference", "statusline": True, "watch": True, "checks_skip": ["commits"]})
        self.assertEqual((f["statusline"], f["watch"], f["checks_skip"]), (True, True, ["commits"]))
        self.assertEqual(manifest.component_flags({"mode": "reference", "checks_skip": []})["checks_skip"], [])    # presente y vacío manda: ejecuta todo

    def test_arkana_nunca_es_reference(self):
        self.assertEqual(manifest.component_flags({"mode": "reference"}, is_arkana=True)["mode"], "work")

    def test_workspace_flags_acepta_alias_o_id(self):
        with common.Lab() as lab:
            m = common.manifiesto()
            m["components"][0].update(mode="reference", ref="v1", id="11111111-1111-4111-8111-111111111111")
            lab.escribir(os.path.join("core", "workspace.json"), m)
            w = manifest.load(lab.arkana)
            self.assertEqual(w.flags("APP")["mode"], "reference")
            self.assertEqual(w.flags("11111111-1111-4111-8111-111111111111")["ref"], "v1")
            self.assertEqual(w.flags("arkana")["mode"], "work")

    def test_validacion_de_los_campos_nuevos(self):
        self.assertEqual(self.errores(mode="reference", ref="v6.2.0", watch=False, checks_skip=["commits", "anidado-*"]), [])
        self.assertTrue(self.errores(mode="cobol"))
        self.assertTrue(self.errores(watch="no"))
        self.assertTrue(any("ref" in e for e in self.errores(ref="v1")))                         # ref sin mode: reference
        self.assertTrue(any("no existen" in e and "gitignore_env" in e for e in self.errores(checks_skip=["gitignore_env"])))   # errata

    def test_arkana_no_admite_mode(self):
        d = common.manifiesto()
        d["arkana"]["mode"] = "reference"
        self.assertTrue(manifest.validate(d))

    def test_esquema_mas_nuevo_dice_actualiza_el_plugin_antes_de_listar_claves(self):
        with common.Lab() as lab:
            m = common.manifiesto()
            m["schema"] = manifest.KNOWN_SCHEMA + 1
            m["components"][0]["campo_futuro"] = True
            lab.escribir(os.path.join("core", "workspace.json"), m)
            with self.assertRaises(manifest.ManifestError) as cm:
                manifest.load(lab.arkana)
            self.assertIn("actualiza el plugin", str(cm.exception))
            self.assertNotIn("clave no permitida", str(cm.exception))

    def test_clave_desconocida_con_esquema_conocido_sugiere_actualizar(self):
        with common.Lab() as lab:
            m = common.manifiesto()
            m["components"][0]["campo_futuro"] = True
            lab.escribir(os.path.join("core", "workspace.json"), m)
            with self.assertRaisesRegex(manifest.ManifestError, "versión más reciente"):
                manifest.load(lab.arkana)


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
