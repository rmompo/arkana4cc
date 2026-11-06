import copy
import unittest
import common
import validate


class TestEsquemas(unittest.TestCase):
    def test_informe_valido(self):
        self.assertEqual(validate.check_schema(common.informe_ok(), common.esquema("informe")), [])

    def test_informe_estado_invalido(self):
        i = common.informe_ok(); i["estado"] = "terminado"
        self.assertTrue(any("terminado" in e for e in validate.check_schema(i, common.esquema("informe"))))

    def test_informe_clave_extra_y_faltante(self):
        i = common.informe_ok(); i["extra"] = 1; del i["resumen"]
        errs = " ".join(validate.check_schema(i, common.esquema("informe")))
        self.assertIn("extra", errs); self.assertIn("resumen", errs)

    def test_informe_resumen_demasiado_largo(self):
        i = common.informe_ok(); i["resumen"] = "x" * 601
        self.assertTrue(validate.check_schema(i, common.esquema("informe")))

    def test_informe_necesita_tipo_enum(self):
        i = common.informe_ok(); i["necesita"] = [{"tipo": "magia", "detalle": "x"}]
        self.assertTrue(validate.check_schema(i, common.esquema("informe")))
        i["necesita"] = [{"tipo": "permiso", "detalle": "x", "comando_sugerido": "npm i"}]
        self.assertEqual(validate.check_schema(i, common.esquema("informe")), [])

    def test_tarea_valida_e_invalida(self):
        self.assertEqual(validate.check_schema(common.tarea_ok(), common.esquema("tarea")), [])
        self.assertTrue(validate.check_schema(common.tarea_ok(tid="T1"), common.esquema("tarea")))
        self.assertEqual(validate.check_schema(common.tarea_ok(repo="otro"), common.esquema("tarea")), [])                  # cualquier alias con formato válido: la existencia la comprueba el plan contra el manifiesto
        self.assertTrue(validate.check_schema(common.tarea_ok(repo="Otro Repo"), common.esquema("tarea")))
        self.assertTrue(validate.check_schema(common.tarea_ok(perfil="ejecucion"), common.esquema("tarea")))
        self.assertTrue(validate.check_schema(common.tarea_ok(instrucciones=[]), common.esquema("tarea")))

    def test_plan_valido_e_invalido(self):
        self.assertEqual(validate.check_schema(common.plan_ok(), common.esquema("plan")), [])
        self.assertTrue(validate.check_schema(common.plan_ok(pid="X1"), common.esquema("plan")))
        self.assertTrue(validate.check_schema(common.plan_ok(estado="volando"), common.esquema("plan")))
        g = {"gate": "G01", "motivo": "permiso", "detalle": "x"}
        self.assertEqual(validate.check_schema(common.plan_ok(gate=g), common.esquema("plan")), [])
        self.assertTrue(validate.check_schema(common.plan_ok(gate={"gate": "G1", "motivo": "raro"}), common.esquema("plan")))

    def test_politica(self):
        import json, os
        pol = common.leer_json(os.path.join(common.PLUGIN, "policy", "politica.default.json"))
        self.assertEqual(validate.check_schema(pol, common.esquema("politica")), [])
        bad = copy.deepcopy(pol); bad["limites"]["max_turns"] = -1
        self.assertTrue(validate.check_schema(bad, common.esquema("politica")))

    def test_bool_no_es_entero(self):
        self.assertTrue(validate.check_schema(True, {"type": "integer"}))
        self.assertFalse(validate.check_schema(3, {"type": "integer"}))


if __name__ == "__main__":
    unittest.main()
