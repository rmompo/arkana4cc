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
            self.assertEqual((r.display(ID_A), r.display(ID_B), r.display("all")), ("ARKANA", "api", "all"))
            self.assertEqual(r.display("44444444-4444-4444-8444-444444444444"), "44444444…")        # id desconocido: acortado

    def test_sin_registro_los_alias_son_la_identidad(self):
        with common.Lab() as lab:
            r = project.Registry.load(lab.arkana)
            self.assertFalse(r.present)
            self.assertEqual((r.resolve("API"), r.display("api"), r.id_of("api")), ("api", "api", None))

    def test_renombrar_cambia_solo_el_alias_y_es_idempotente(self):
        with common.Lab() as lab:
            registro(lab)
            self.assertEqual(project.rename_component(lab.arkana, "api", "backend"), ID_B)
            r = project.Registry.load(lab.arkana)
            self.assertEqual((r.alias_of(ID_B), r.id_of("backend"), r.id_of("api")), ("backend", ID_B, None))
            self.assertEqual(r.display(ID_B), "backend")                                            # lo guardado por id sigue mostrándose bien
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
            self.assertEqual(r.display(ID_C), "app (retirado)")
            self.assertNotIn("app", r.aliases())
            self.assertEqual(project.add_component(lab.arkana, "app") != ID_C, True)                # un alias reutilizado es OTRA pieza

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


if __name__ == "__main__":
    unittest.main()
