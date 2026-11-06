"""inbox: qué mensajes se entregan a un componente y cómo se rinden en el prompt."""
import os
import tempfile
import unittest

import common  # noqa: F401  (prepara sys.path)
import inbox


def m(**c):
    base = {"id": "N261103-0001-aaaa", "asunto": "Algo que hacer", "tipo": "task", "de": "app", "para": ["api"], "destinatarios": ["api"],
            "estado": "open", "repeticion": "once"}
    base.update(c)
    return base


class TestAplica(unittest.TestCase):
    def test_once_solo_accionables_abiertos_sin_confirmar_ni_ejecutar(self):
        self.assertTrue(inbox.applies(m(), "api"))
        self.assertTrue(inbox.applies(m(tipo="question"), "api"))
        self.assertFalse(inbox.applies(m(tipo="notice", estado=None), "api"))                       # los avisos once no se entregan
        self.assertFalse(inbox.applies(m(estado="done"), "api"))
        self.assertFalse(inbox.applies(m(confirmaciones={"api": {"estado": "done"}}), "api"))
        self.assertFalse(inbox.applies(m(ejecuciones={"api": {"n": 1}}), "api"))               # ya ejecutado para ese componente
        self.assertFalse(inbox.applies(m(), "app"))                                                    # el remitente no se lo entrega a sí mismo
        self.assertFalse(inbox.applies(m(), "app-web"))

    def test_repeat_vigente_aunque_este_ejecutado_pero_no_propuesto_ni_oculto(self):
        r = m(tipo="notice", estado=None, repeticion="repeat", vigencia="vigente", ejecuciones={"api": {"n": 3}})
        self.assertTrue(inbox.applies(r, "api"))                                                    # ejecutado ≥1 vez no lo saca
        self.assertFalse(inbox.applies(dict(r, vigencia="propuesto"), "api"))
        self.assertFalse(inbox.applies(dict(r, estado="deleted"), "api"))
        self.assertFalse(inbox.applies(dict(r, estado="reconciled"), "api"))

    def test_repeat_a_all_llega_a_cualquier_componente_menos_al_remitente(self):
        r = m(tipo="notice", estado=None, repeticion="repeat", vigencia="vigente", para=["all"], destinatarios=["arkana"])
        self.assertTrue(inbox.applies(r, "app-ui"))
        self.assertFalse(inbox.applies(r, "app"))

    def test_mensaje_antiguo_sin_destinatarios_usa_para(self):
        self.assertTrue(inbox.applies({k: v for k, v in m().items() if k != "destinatarios"}, "api"))

    def test_select_ordena_repeat_primero_y_canoniza_el_alias(self):
        a = m(id="N261103-0001-zzzz")
        r = m(id="N261103-0010-yyyy", tipo="notice", estado=None, repeticion="repeat", vigencia="vigente")
        self.assertEqual([x["id"] for x in inbox.select("api", {a["id"]: a, r["id"]: r})], [r["id"], a["id"]])      # repeat primero
        pa = m(id="N261103-0011-xxxx", para=["arkana"], destinatarios=["arkana"], de="app")
        self.assertEqual([x["id"] for x in inbox.select("shared", {pa["id"]: pa})], [pa["id"]])                          # shared == arkana


class TestRender(unittest.TestCase):
    def test_vacio_y_topes(self):
        self.assertEqual(inbox.render([]), "(ninguno)")
        largo = m(cuerpo="x" * 3000)
        t = inbox.render([largo])
        self.assertIn("demasiado largo", t)
        self.assertNotIn("x" * 100, t)
        muchos = [m(id=f"N261103-{i:04d}-aaaa", cuerpo="y" * 1000) for i in range(1, 12)]
        self.assertLessEqual(len(inbox.render(muchos)), inbox.MAX_CHARS + 11 * 300)                     # tras el tope total, solo asunto + id

    def test_almacen_ausente_es_lista_vacia(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["ARKANA_PLUGINS_DIR"] = d
            try:
                self.assertEqual(inbox.load_all(), {})
                self.assertEqual(inbox.select("api"), [])
            finally:
                os.environ.pop("ARKANA_PLUGINS_DIR", None)


class TestIndicadosAMano(unittest.TestCase):
    """`--from-message`: mensajes elegidos para una tarea (mensajes_extra)."""
    def test_check_for_exige_que_exista_no_este_de_baja_y_vaya_al_componente(self):
        msgs = {"N261103-0001-aaaa": m(), "N261103-0002-bbbb": m(id="N261103-0002-bbbb", estado="deleted"), "N261103-0003-cccc": m(id="N261103-0003-cccc", para=["app"], destinatarios=["app"])}
        self.assertIsNone(inbox.check_for("N261103-0001-aaaa", "api", msgs)[1])
        for mid, texto in (("N261103-9999-zzzz", "no existe"), ("N261103-0002-bbbb", "deleted"), ("N261103-0003-cccc", "no va dirigido a api")):
            mm, err = inbox.check_for(mid, "api", msgs)
            self.assertIsNone(mm); self.assertIn(texto, err)
        self.assertIn("no va dirigido", inbox.check_for("N261103-0001-aaaa", "app", msgs)[1])         # el remitente tampoco es destinatario

    def test_un_aviso_indicado_a_mano_se_entrega_aunque_applies_diga_que_no(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["ARKANA_PLUGINS_DIR"] = d
            try:
                aviso = m(tipo="notice", estado=None)
                os.makedirs(os.path.join(d, "arkana-messaging", "state", "messages"))
                import json
                with open(os.path.join(d, "arkana-messaging", "state", "messages", aviso["id"] + ".json"), "w") as f:
                    json.dump(aviso, f)
                self.assertFalse(inbox.applies(aviso, "api"))
                t = {"id": "T001", "repo": "api", "mensajes_extra": [aviso["id"]]}
                self.assertEqual([x["id"] for x in inbox.for_task("P1", t)], [aviso["id"]])
                self.assertEqual(inbox.ids_for("P1", t), [aviso["id"]])
                self.assertEqual(inbox.listing("P1", t)[0]["id"], aviso["id"])                                  # `plan show` también lo enseña
            finally:
                os.environ.pop("ARKANA_PLUGINS_DIR", None)

    def test_textos_para_copiar_a_una_tarea(self):
        self.assertEqual(inbox.instruction_lines(m(instrucciones=["1. a", " ", "2. b"])), ["1. a", "2. b"])
        self.assertEqual(inbox.instruction_lines(m(cuerpo="primera\n\nsegunda")), ["primera", "segunda"])      # sin instrucciones: el cuerpo
        self.assertEqual(inbox.instruction_lines(m()), ["Algo que hacer"])                                      # sin nada: el asunto
        self.assertEqual(len(inbox.instruction_lines(m(instrucciones=[f"{i}" for i in range(1, 100)]))), 40)    # tope
        self.assertEqual(inbox.criteria_of(m(criterios=["x", "y"])), [{"id": "C1", "descripcion": "x"}, {"id": "C2", "descripcion": "y"}])
        self.assertIn("N261103-0001-aaaa", inbox.criteria_of(m())[0]["descripcion"])                           # genérico
        self.assertIn("N261103-0001-aaaa", inbox.pointer(m()))
        self.assertIn("Mensajes para este componente", inbox.pointer(m()))


if __name__ == "__main__":
    unittest.main()
