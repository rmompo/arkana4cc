"""Recorre el bucle documentado en templates/orquestador.md usando SOLO agentic.sh y sus contratos JSON
(lo que hara el orquestador), con el claude falso: plan de 3 tareas con reintento, gate de dato, integracion y archivo."""
import json
import os
import unittest

import lab as L
import test_control as C

MSG = "feat(api) validate NIF in a.ts"


class TestFlujoCompleto(unittest.TestCase):
    def test_plan_de_tres_tareas_con_reintento_gate_integracion_y_archivo(self):
        with L.Lab() as lab:
            os.makedirs(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "config"), exist_ok=True)
            with open(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "config", "comandos-permitidos.json"), "w") as f:
                json.dump({"permitidos": [["true"]]}, f)        # lista local aditiva: 'true' hace de verificacion en el laboratorio
            spec = C.spec_basico(3)
            spec["tareas"][1]["depende_de"] = []
            spec["tareas"][2]["depende_de"] = ["T001", "T002"]
            self.assertEqual(C.ag(lab, "plan", "new", C.escribir(lab, "p.json", spec)).returncode, 0)
            self.assertEqual(C.ag(lab, "plan", "approve").returncode, 0)
            self.assertEqual(C.ag(lab, "plan", "start").returncode, 0)
            # modo del worker segun (tarea, intento): T002 falla un criterio y se reintenta; T003 pregunta un dato
            guion = {("T001", 1): "hecha", ("T002", 1): "hecha_sin_cumplir", ("T002", 2): "hecha", ("T003", 1): "bloqueada", ("T003", 2): "hecha"}
            intentos, preguntas, orden = {}, [], []
            for _ in range(40):                                                  # tope de seguridad del bucle
                n = C.js(lab, "next")
                est = n["estado"]
                if est == "terminado":
                    break
                if est == "tarea":
                    t = n["tarea"]
                    intentos[t] = intentos.get(t, 0) + 1
                    orden.append((t, intentos[t]))
                    r = C.ag(lab, "launch", t, env={"FAKE_MODE": guion[(t, intentos[t])]})
                    self.assertEqual(r.returncode, 0, r.stdout)
                    f = json.loads(C.ag(lab, "finish", t, "--json").stdout)
                    self.assertIn("acciones_permitidas", f)
                    if f["veredicto"] == "completada":
                        self.assertEqual(C.ag(lab, "act", "continue", t, "--message", MSG).returncode, 0)
                    elif f["veredicto"] == "rechazada":
                        self.assertIn("retry", f["acciones_permitidas"])
                        fb = C.escribir(lab, "fb.txt", "cumple el criterio C1")
                        self.assertEqual(C.ag(lab, "act", "retry", t, "--feedback-file", fb).returncode, 0)
                    # bloqueada: el script ya abrio el gate; se resuelve en la siguiente vuelta
                elif est == "gate":
                    g = n["gate"]
                    preguntas.append(g["motivo"])
                    self.assertEqual(g["motivo"], "dato")
                    self.assertEqual(C.ag(lab, "approve", g["gate"], "--note", "el NIF tiene 9 caracteres").returncode, 0)
                else:
                    self.fail(f"estado inesperado: {n}")
            self.assertEqual(preguntas, ["dato"])
            self.assertEqual(orden, [("T001", 1), ("T002", 1), ("T002", 2), ("T003", 1), ("T003", 2)])
            self.assertEqual(lab.plan_json(lab_plan(lab))["estado"], "completado")
            self.assertEqual([t["estado"] for t in C.js(lab, "status")["tareas"]], ["completada"] * 3)
            self.assertIn("9 caracteres", " ".join(lab.tarea(lab_plan(lab), "T003")["feedback"]))
            # integrar (merge local, sin push) y archivar
            pid = lab_plan(lab)
            base = lab.head("api", "develop")
            self.assertEqual(C.ag(lab, "integrate", "merge", "--message", "chore(api) integrate NIF validation").returncode, 0)
            self.assertNotEqual(lab.head("api", "develop"), base)
            self.assertEqual(C.ag(lab, "archive").returncode, 0)
            self.assertTrue(os.path.exists(os.path.join(os.environ["ARKANA_AGENTIC_DIR"], "data", "archive", pid, "plan.json")))
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "log", "develop", "--format=%s", "-n", "5"]).stdout.count("feat(api)"), 3)


def lab_plan(lab):
    with open(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "actual")) as f:
        return f.read().strip()


if __name__ == "__main__":
    unittest.main()
