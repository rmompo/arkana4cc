"""Registro del proyecto: id inmutable, alias renombrable, resolución en ambos sentidos, baja de piezas y guarda de layout."""
import json
import os
import unittest

import common
from arkana_core import contract, manifest, project

ID_A, ID_B, ID_C = ("11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", "33333333-3333-4333-8333-333333333333")


def registro(lab, layout=3, comps=None):
    comps = comps or [{"id": ID_A, "alias": "arkana"}, {"id": ID_B, "alias": "api"}, {"id": ID_C, "alias": "app"}]
    with open(os.path.join(lab.arkana, project.FILE), "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "layout": layout, "workspace": {"id": ID_A, "name": "lab"}, "components": comps}, f)


class TestRegistry(unittest.TestCase):
    def test_resuelve_alias_o_id_y_muestra_siempre_el_alias(self):
        with common.Lab() as lab:
            registro(lab)
            r = project.Registry.load(lab.arkana)
            self.assertTrue(r.present)
            self.assertEqual((r.id_of("API"), r.id_of(ID_B.upper()), r.id_of("nada")), (ID_B, ID_B, None))
            self.assertEqual((r.alias_of(ID_C), r.alias_of("app"), r.alias_of("nada")), ("app", "app", None))
            self.assertEqual((r.resolve("api"), r.resolve("nada"), r.resolve("all")), (ID_B, "nada", "all"))
            self.assertEqual((r.display(ID_A), r.display(ID_B), r.display("all")), ("ARKANA", "API", "all"))
            self.assertEqual(r.display("44444444-4444-4444-8444-444444444444"), "44444444…")        # id desconocido: acortado

    def test_sin_registro_los_alias_son_la_identidad(self):
        with common.Lab() as lab:
            r = project.Registry.load(lab.arkana)
            self.assertFalse(r.present)
            self.assertEqual((r.resolve("API"), r.display("api"), r.id_of("api")), ("api", "API", None))

    def test_renombrar_cambia_solo_el_alias_y_es_idempotente(self):
        with common.Lab() as lab:
            registro(lab)
            self.assertEqual(project.rename_component(lab.arkana, "api", "backend"), ID_B)
            r = project.Registry.load(lab.arkana)
            self.assertEqual((r.alias_of(ID_B), r.id_of("backend"), r.id_of("api")), ("backend", ID_B, None))
            self.assertEqual(r.display(ID_B), "BACKEND")                                            # lo guardado por id sigue mostrándose bien
            self.assertEqual(project.rename_component(lab.arkana, "api", "backend"), ID_B)           # ya renombrado por otra persona: no falla
            for malo in ("ARKANA", "all", "Mal Nombre", "app"):
                with self.assertRaises(project.ProjectError):
                    project.rename_component(lab.arkana, "backend", malo)

    def test_alta_y_baja_conservan_el_id_para_mostrarlo(self):
        with common.Lab() as lab:
            registro(lab)
            nuevo = project.add_component(lab.arkana, "docs")
            self.assertTrue(project.is_id(nuevo))
            self.assertEqual(project.add_component(lab.arkana, "DOCS"), nuevo)                      # idempotente
            self.assertEqual(project.retire_component(lab.arkana, "app"), ID_C)
            r = project.Registry.load(lab.arkana)
            self.assertIsNone(r.id_of("app"))                                                       # el alias queda libre
            self.assertEqual(r.display(ID_C), "APP (retirado)")
            self.assertNotIn("app", r.aliases())
            self.assertEqual(project.add_component(lab.arkana, "app") != ID_C, True)                # un alias reutilizado es OTRA pieza

    def test_politicas_de_la_instalacion(self):
        with common.Lab() as lab:
            self.assertIs(project.policy(lab.arkana, "versioned_env", False), False)                  # sin registro: el valor por defecto
            registro(lab)
            self.assertIs(project.policy(lab.arkana, "versioned_env", False), False)
            project.set_policy(lab.arkana, "versioned_env", True)
            self.assertIs(project.policy(lab.arkana, "versioned_env"), True)
            self.assertEqual(project.Registry.load(lab.arkana).id_of("api"), ID_B)                     # tocar una política no altera el registro

    def test_guarda_de_layout(self):
        with common.Lab() as lab:
            with self.assertRaises(project.LayoutError) as cm:
                project.require_layout(lab.arkana)
            self.assertIn("/arkana-evolve:apply", str(cm.exception))
            registro(lab, layout=2)
            with self.assertRaises(project.LayoutError):
                project.require_layout(lab.arkana)
            registro(lab, layout=project.LAYOUT_REQUIRED)
            self.assertEqual(project.require_layout(lab.arkana), project.LAYOUT_REQUIRED)


class TestTresNombres(unittest.TestCase):
    """Alias, carpeta real y nombre-módulo: tres formas de referirse a un componente; únicos entre componentes."""

    def lab(self, lab, **mods):
        comps = [{"id": ID_A, "alias": "arkana"}, {"id": ID_B, "alias": "api", **({"module": mods["api"]} if "api" in mods else {})},
                 {"id": ID_C, "alias": "app", **({"module": mods["app"]} if "app" in mods else {})}]
        registro(lab, layout=5, comps=comps)
        return manifest.load(lab.arkana)

    def test_se_resuelve_por_alias_carpeta_o_modulo(self):
        with common.Lab() as lab:
            w = self.lab(lab, api="viso_rest_inquilino")
            self.assertEqual(w.match("api"), ("api", "alias"))
            self.assertEqual(w.match("md-backend"), ("api", "dir"))
            self.assertEqual(w.match("VISO_REST_INQUILINO"), ("api", "mod"))
            self.assertEqual(w.match("nada"), (None, None))
            self.assertEqual([w.key(x) for x in ("api", "md-backend", "viso_rest_inquilino")], ["api"] * 3)
            self.assertEqual(w.path("viso_rest_inquilino"), w.path("api"))
            self.assertTrue(w.has("md-backend"))

    def test_con_prefijo_solo_se_mira_ese_tipo(self):
        with common.Lab() as lab:
            w = self.lab(lab, api="viso_rest_inquilino")
            self.assertEqual((w.key("alias:api"), w.key("dir:md-backend"), w.key("mod:viso_rest_inquilino")), ("api", "api", "api"))
            for malo in ("dir:api", "mod:md-backend", "alias:md-backend", "mod:api"):
                self.assertFalse(w.has(malo), malo)
            self.assertEqual(w.key("dir:api"), "dir:api")                                   # desconocido: no se adivina

    def test_el_modulo_es_opcional_y_por_defecto_no_hay(self):
        with common.Lab() as lab:
            w = self.lab(lab)
            self.assertEqual((w.module("api"), w.folder("api")), ("", "md-backend"))
            self.assertEqual(w.commit_scope("api"), "api")

    def test_nombres_repetidos_se_detectan_sin_distinguir_mayusculas(self):
        with common.Lab() as lab:
            self.assertEqual(self.lab(lab, api="viso").name_conflicts(), [])
            c = self.lab(lab, api="md-mf")                               # el módulo de api es la carpeta de app
            self.assertEqual(len(c.name_conflicts()), 1)
            self.assertIn("md-mf", c.name_conflicts()[0])
            c = self.lab(lab, api="APP".lower())                          # el módulo de api es el alias de app
            self.assertIn("'app'", c.name_conflicts()[0])

    def test_un_componente_puede_repetir_sus_propios_nombres(self):
        with common.Lab() as lab:
            w = self.lab(lab, api="md-backend")                          # módulo == carpeta del mismo componente
            self.assertEqual(w.name_conflicts(), [])

    def test_alta_y_cambio_de_modulo_en_el_registro_compartido(self):
        with common.Lab() as lab:
            registro(lab, layout=5)
            project.set_module(lab.arkana, "api", "Viso_Rest")
            self.assertEqual(project.Registry.load(lab.arkana).module_of("api"), "viso_rest")
            project.set_module(lab.arkana, "api", "")
            self.assertEqual(project.Registry.load(lab.arkana).module_of("api"), "")
            for malo in ("con espacio", "-raro", "a/b", "ñ"):
                with self.assertRaises(project.ProjectError):
                    project.set_module(lab.arkana, "api", malo)
            with self.assertRaises(project.ProjectError):
                project.set_module(lab.arkana, "nadie", "x")
            project.add_component(lab.arkana, "nuevo", module="mod-nuevo")
            self.assertEqual(project.Registry.load(lab.arkana).module_of("nuevo"), "mod-nuevo")

    def test_scope_de_commit_segun_el_formato(self):
        with common.Lab() as lab:
            w = self.lab(lab, api="viso_rest_inquilino")
            w._blocks["api"]["commit_format"] = "ia4d({module})"
            w._blocks["app"]["commit_format"] = "conventional({module})"          # sin módulo: cae al alias
            self.assertEqual((w.commit_scope("api"), w.commit_scope("app")), ("viso_rest_inquilino", "app"))
            w._blocks["api"]["commit_format"] = "ia4d"
            self.assertEqual(w.commit_scope("api"), "api")
            self.assertEqual(manifest.parse_commit_format(None), ("conventional", "alias"))
            self.assertEqual(manifest.parse_commit_format("IA4D({module})"), ("ia4d", "module"))
            self.assertEqual(manifest.parse_commit_format("ia4d({alias})"), ("ia4d", "alias"))
            for malo in ("ia5", "ia4d({x})", "ia4d()", "{module}"):
                with self.assertRaises(ValueError):
                    manifest.parse_commit_format(malo)

    def test_el_manifiesto_sin_registro_sigue_funcionando(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual((w.key("md-backend"), w.module("api"), w.name_conflicts()), ("api", "", []))


class TestWorkspaceConIds(unittest.TestCase):
    def test_el_manifiesto_acepta_ids_en_los_bloques_y_resuelve_por_id(self):
        with common.Lab() as lab:
            m = common.manifiesto()
            m["arkana"]["id"] = ID_A
            m["components"][0]["id"] = ID_B                                                         # app
            lab.escribir(os.path.join("core", "workspace.json"), m)
            ws = manifest.load(lab.arkana)
            self.assertEqual((ws.id_of("app"), ws.alias_of(ID_B), ws.key(ID_B.upper())), (ID_B, "app", "app"))
            self.assertTrue(ws.has(ID_B))
            self.assertEqual(ws.path(ID_B), ws.path("app"))
            self.assertEqual(ws.get(ID_A)["alias"], "ARKANA")
            self.assertIsNone(ws.alias_of("nada"))

    def test_un_id_mal_formado_se_rechaza(self):
        with common.Lab() as lab:
            m = common.manifiesto()
            m["components"][0]["id"] = "no-es-un-uuid"
            lab.escribir(os.path.join("core", "workspace.json"), m)
            with self.assertRaises(manifest.ManifestError):
                manifest.load(lab.arkana)

    def test_el_contrato_admite_el_comando_rename(self):
        c = {"plugin": "arkana-x", "contract": 1, "provides": ["check"], "rename": "python3 scripts/lib/x.py rename"}
        self.assertEqual(contract.validate(c), [])

    def test_el_contrato_admite_el_hook_file_changed(self):
        c = {"plugin": "arkana-x", "contract": 1, "provides": ["check"], "hooks": ["SessionStart", "FileChanged"]}
        self.assertEqual(contract.validate(c), [])


if __name__ == "__main__":
    unittest.main()
