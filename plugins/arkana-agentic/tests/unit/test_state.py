import json
import os
import re
import threading
import time
import unittest
import common
import state
import validate


def montar(pid="P2610301830-abcd", plan_estado="en_ejecucion", estados=("pendiente", "pendiente"), plan_extra=None):
    plan = common.plan_ok(pid, plan_estado, **(plan_extra or {}))
    state.save_json(os.path.join(state.plan_dir(pid), "plan.json"), plan)
    for i, est in enumerate(estados, 1):
        t = common.tarea_ok(f"T{i:03d}", pid, est)
        state.save_json(os.path.join(state.plan_dir(pid), "tareas", f"T{i:03d}.json"), t)
    return pid


class TestIds(unittest.TestCase):
    def test_formato_y_unicidad_del_id_de_plan(self):
        with common.Entorno():
            ids = [state.new_plan_id() for _ in range(500)]
        self.assertEqual(len(set(ids)), 500)
        self.assertTrue(all(re.match(r"^P\d{10}-[a-z]{4}$", i) for i in ids), ids[:3])

    def test_el_id_de_plan_lleva_la_hora_local_en_formato_24h(self):
        with common.Entorno():
            antes = time.strftime("%y%m%d%H%M", time.localtime())
            pid = state.new_plan_id()
            despues = time.strftime("%y%m%d%H%M", time.localtime())
        self.assertIn(pid[1:11], {antes, despues})

    def test_el_id_de_tarea_son_tres_digitos(self):
        t = common.tarea_ok()
        self.assertEqual(t["id"], "T001")
        self.assertEqual(validate.check_schema(t, common.esquema("tarea")), [])
        for malo in ("T01", "T1", "T0001", "t001", "T00a"):
            self.assertTrue(validate.check_schema(dict(t, id=malo), common.esquema("tarea")), malo)
        for malo in ("P261030-1830-m2qa", "P2610301830-ab1d", "P2610301830-abcde", "p2610301830-abcd"):
            self.assertTrue(validate.check_schema(dict(t, plan=malo), common.esquema("tarea")), malo)


class TestJsonAtomico(unittest.TestCase):
    def test_guardar_y_sin_residuos(self):
        with common.Entorno() as d:
            r = os.path.join(d, "x", "a.json")
            state.save_json(r, {"a": "ñ"})
            self.assertEqual(state.load_json(r), {"a": "ñ"})
            self.assertEqual([f for f in os.listdir(os.path.dirname(r)) if f.startswith(".tmp-")], [])

    def test_actualizar_concurrente_no_pierde_escrituras(self):
        with common.Entorno() as d:
            r = os.path.join(d, "c.json"); state.save_json(r, {"n": 0})

            def trabajo():
                for _ in range(20):
                    state.update_json(r, lambda o: o.update(n=o["n"] + 1))
            hilos = [threading.Thread(target=trabajo) for _ in range(6)]
            [h.start() for h in hilos]; [h.join() for h in hilos]
            self.assertEqual(state.load_json(r)["n"], 120)


class TestTransiciones(unittest.TestCase):
    def test_todas_las_ilegales_se_rechazan_y_las_legales_pasan(self):
        for tipo, tabla in (("tarea", state.TASK_TRANSITIONS), ("plan", state.PLAN_TRANSITIONS)):
            for origen in tabla:
                for destino in tabla:
                    obj = {"id": "X", "estado": origen, "historial": []}
                    if destino in tabla[origen]:
                        state.check_transition(obj, tipo, destino)
                        self.assertEqual(obj["estado"], destino)
                        self.assertEqual(obj["historial"][-1]["accion"], f"{origen}->{destino}")
                    else:
                        with self.assertRaises(state.IllegalTransition):
                            state.check_transition(obj, tipo, destino)
                        self.assertEqual(obj["estado"], origen)

    def test_terminales_sin_salida(self):
        for t in ("completada", "fallida_definitiva", "omitida", "cancelada"):
            self.assertEqual(state.TASK_TRANSITIONS[t], set())
        for p in state.TERMINAL_PLAN_STATES:
            self.assertEqual(state.PLAN_TRANSITIONS[p], set())

    def test_estados_de_tablas_y_esquemas_coinciden(self):
        self.assertEqual(set(state.TASK_TRANSITIONS), set(common.esquema("tarea")["properties"]["estado"]["enum"]))
        self.assertEqual(set(state.PLAN_TRANSITIONS), set(common.esquema("plan")["properties"]["estado"]["enum"]))

    def test_transicionar_tarea_registra_y_pinta_linea(self):
        with common.Entorno() as d:
            pid = montar()
            state.transition_task(pid, "T001", "lista")
            state.transition_task(pid, "T001", "en_curso", "script", "lanzado")
            t = state.load_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"))
            self.assertEqual(t["estado"], "en_curso"); self.assertEqual(len(t["historial"]), 2)
            reg = [json.loads(l) for l in common.leer_lineas(os.path.join(state.plan_dir(pid), "registro.jsonl"))]
            self.assertEqual([r["accion"] for r in reg], ["tarea->lista", "tarea->en_curso"])
            linea = state.load_json(os.path.join(d, "state", "run", "linea.json"))
            self.assertEqual(linea["tarea"], "T001")

    def test_transicion_ilegal_no_modifica_el_fichero(self):
        with common.Entorno():
            pid = montar()
            with self.assertRaises(state.IllegalTransition):
                state.transition_task(pid, "T001", "completada")
            t = state.load_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"))
            self.assertEqual(t["estado"], "pendiente"); self.assertEqual(t["historial"], [])


class TestOrden(unittest.TestCase):
    def test_siguiente_respeta_dependencias(self):
        ts = [common.tarea_ok("T001", estado="completada"), common.tarea_ok("T002", estado="pendiente", depende_de=["T001"]),
              common.tarea_ok("T003", estado="pendiente", depende_de=["T002"])]
        self.assertEqual(state.next_task(ts)["id"], "T002")
        ts[0]["estado"] = "pendiente"
        self.assertEqual(state.next_task(ts)["id"], "T001")
        ts[0]["estado"] = "fallida_definitiva"
        self.assertIsNone(state.next_task(ts))


class TestLimites(unittest.TestCase):
    def pol(self):
        return {"limites": {"max_turns": 40, "budget_usd": 0.75, "max_attempts_per_task": 2},
                "techos": {"max_turns": 80, "budget_usd": 3.0, "max_attempts_per_task": 3}}

    def test_gana_el_mas_restrictivo(self):
        e = state.effective_limits(self.pol(), {"budget_usd": 2.0}, {"budget_usd": 0.5, "max_turns": 10})
        self.assertEqual((e["budget_usd"], e["max_turns"]), (0.5, 10))

    def test_la_tarea_no_supera_la_politica(self):
        e = state.effective_limits(self.pol(), None, {"budget_usd": 2.0, "max_turns": 500})
        self.assertEqual((e["budget_usd"], e["max_turns"]), (0.75, 40))

    def test_alias_de_intentos(self):
        e = state.effective_limits(self.pol(), None, {"max_attempts": 1})
        self.assertEqual(e["max_attempts_per_task"], 1)

    def test_techo_local_se_puede_subir_con_politica_local(self):
        with common.Entorno() as d:
            self.assertEqual(state.load_policy()["techos"]["total_budget_usd"], 25.0)
            state.save_json(os.path.join(d, "config", "politica.json"), {"limites": {"total_budget_usd": 8.0}, "techos": {"total_budget_usd": 10.0}})
            p = state.load_policy()
            self.assertEqual((p["limites"]["total_budget_usd"], p["techos"]["total_budget_usd"]), (8.0, 10.0))
            e = state.effective_limits(p, {"total_budget_usd": 50})
            self.assertEqual(e["total_budget_usd"], 8.0)

    def test_politica_por_defecto_cumple_su_esquema_y_techos(self):
        import validate
        p = state.load_policy()
        self.assertEqual(validate.check_schema(p, common.esquema("politica")), [])
        for k, v in p["limites"].items():
            self.assertLessEqual(v, p["techos"][k], k)


class TestLinea(unittest.TestCase):
    def test_contenido_y_recorte(self):
        with common.Entorno() as d:
            pid = montar(estados=("completada", "en_curso"))
            state.save_json(os.path.join(d, "state", "run", "worker.json"), {"pid": 4242, "inicio": "2026-10-30T18:31:10Z"})
            l = state.render_status_line(pid)
            self.assertEqual((l["tarea"], l["repo"], l["worker_pid"]), ("T002", "app", 4242))
            self.assertEqual(l["tareas"], {"actual": 2, "hechas": 1, "omitidas": 0, "total": 2})     # actual = posicion de la tarea en curso en el plan
            self.assertEqual(l["gasto_usd"], 1.42)
            self.assertLessEqual(len(l["asunto_corto"]), 40); self.assertTrue(l["asunto_corto"].endswith("…"))

    def test_el_contador_sin_tarea_en_curso_es_el_de_resueltas(self):
        with common.Entorno():
            pid = montar(plan_estado="pausado", estados=("completada", "pendiente"))
            self.assertEqual(state.render_status_line(pid)["tareas"], {"actual": 1, "hechas": 1, "omitidas": 0, "total": 2})

    def test_las_omitidas_se_cuentan_y_cuentan_como_resueltas(self):
        with common.Entorno():
            pid = montar(plan_estado="completado", estados=("completada", "omitida"))
            self.assertEqual(state.render_status_line(pid)["tareas"], {"actual": 2, "hechas": 1, "omitidas": 1, "total": 2})

    def test_estados_con_gate_e_interrumpida(self):
        with common.Entorno():
            pid = montar(plan_estado="esperando_usuario", estados=("esperando_usuario", "pendiente"),
                         plan_extra={"gate": {"gate": "G01", "motivo": "permiso"}})
            l = state.render_status_line(pid)
            self.assertEqual((l["estado"], l["gate"], l["tarea"]), ("esperando_usuario", "permiso", "T001"))

    def test_plan_terminado_conserva_la_linea_con_su_estado_y_no_existente_la_borra(self):
        with common.Entorno() as d:
            pid = montar()
            state.render_status_line(pid)
            ruta = os.path.join(d, "state", "run", "linea.json")
            self.assertTrue(os.path.exists(ruta))
            state.transition_plan(pid, "completado")
            l = state.load_json(ruta)                                     # se conserva para que la statusline muestre «ok» un rato
            self.assertEqual((l["estado"], l["tarea"], l["repo"], l["worker_pid"]), ("completado", None, None, None))
            self.assertEqual(l["tareas"]["total"], 2); self.assertIn("ts", l); self.assertEqual(l["gasto_usd"], 1.42)
            self.assertIsNone(state.render_status_line("P0000000000-zzzz"))      # un plan que no existe la borra
            self.assertFalse(os.path.exists(ruta))

    def test_detenido_y_fallido_tambien_se_conservan(self):
        for destino, origen in (("detenido", "en_ejecucion"), ("fallido", "en_ejecucion")):
            with common.Entorno() as d:
                pid = montar(plan_estado=origen)
                state.transition_plan(pid, destino)
                self.assertEqual(state.load_json(os.path.join(d, "state", "run", "linea.json"))["estado"], destino)

    def test_borrador_y_aprobado_no_pintan(self):
        with common.Entorno() as d:
            for est in ("borrador", "aprobado"):
                pid = montar(plan_estado=est)
                self.assertIsNone(state.render_status_line(pid))
            self.assertFalse(os.path.exists(os.path.join(d, "state", "run", "linea.json")))


if __name__ == "__main__":
    unittest.main()


class TestAprobacionYGates(unittest.TestCase):
    def test_hash_cubre_el_contenido_aprobado_y_no_el_estado(self):
        with common.Entorno():
            pid = montar(plan_estado="borrador")
            h0 = state.approve_plan(pid)
            self.assertTrue(state.plan_approval_ok(pid))
            # el estado, los intentos, el feedback y el historial NO cambian el hash
            state.update_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"),
                             lambda o: o.update(estado="lista", intentos=1, feedback=["x"]))
            self.assertEqual(state.approval_hash(pid), h0)
            self.assertTrue(state.plan_approval_ok(pid))

    def test_alterar_instrucciones_invalida_la_aprobacion(self):
        with common.Entorno():
            pid = montar(plan_estado="borrador"); state.approve_plan(pid)
            state.update_json(os.path.join(state.plan_dir(pid), "tareas", "T002.json"),
                             lambda o: o.update(instrucciones=["borra todo"]))
            self.assertFalse(state.plan_approval_ok(pid))

    def test_sin_aprobar_no_es_ok(self):
        with common.Entorno():
            self.assertFalse(state.plan_approval_ok(montar(plan_estado="borrador")))

    def test_iniciar_y_contadores(self):
        with common.Entorno():
            pid = montar(plan_estado="borrador"); state.approve_plan(pid); state.start_plan(pid)
            p = state.load_json(os.path.join(state.plan_dir(pid), "plan.json"))
            self.assertEqual(p["estado"], "en_ejecucion"); self.assertGreater(p["contadores"]["inicio_ts"], 1e9)
            self.assertEqual(state.add_counter(pid, "tareas_lanzadas"), 1)
            self.assertEqual(state.add_counter(pid, "tareas_lanzadas"), 2)
            self.assertAlmostEqual(state.add_counter(pid, "gasto_usd", 0.05) - 1.4234, 0.05, places=4)

    def test_gate_para_el_plan_y_se_cierra(self):
        with common.Entorno() as d:
            pid = montar()
            g = state.open_gate(pid, "permiso", "necesita npm install", ["autorizar", "omitir"])
            p = state.load_json(os.path.join(state.plan_dir(pid), "plan.json"))
            self.assertEqual((p["estado"], p["gate"]["motivo"]), ("esperando_usuario", "permiso"))
            self.assertEqual(state.load_json(os.path.join(d, "state", "run", "linea.json"))["gate"], "permiso")
            import validate
            self.assertEqual(validate.check_schema(p, common.esquema("plan")), [])
            state.close_gate(pid, "user", "autorizado")
            p = state.load_json(os.path.join(state.plan_dir(pid), "plan.json"))
            self.assertEqual((p["estado"], p["gate"]), ("en_ejecucion", None))

    def test_comandos_permitidos_se_amplian_solo_desde_la_politica_local(self):
        with common.Entorno() as d:
            self.assertNotIn(["true"], state.load_allowed_commands())
            state.save_json(os.path.join(d, "config", "comandos-permitidos.json"), {"permitidos": [["true"]]})
            self.assertIn(["true"], state.load_allowed_commands()); self.assertIn(["npm", "test"], state.load_allowed_commands())
