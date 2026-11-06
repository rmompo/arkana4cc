from pathlib import Path
import json
import os
import unittest

import lab as L
import state

MSG = "feat(api) validate NIF in a.ts"


def ag(lab, *args, plan=None, env=None, timeout=90):
    extra = ["--plan", plan] if plan else []
    return lab.ejecutar("agentic.sh", *args, *extra, env=env, timeout=timeout)


def js(lab, *args, plan=None):
    r = ag(lab, *args, "--json", plan=plan)
    return json.loads(r.stdout)


def escribir(lab, nombre, datos):
    ruta = os.path.join(lab.root, nombre)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(datos if isinstance(datos, str) else json.dumps(datos))
    return ruta


def spec_basico(n=2):
    t = lambda i: {"asunto": f"Tarea {i}", "repo": "api", "tipo": "tarea", "objetivo": "hacer algo",
                   "instrucciones": ["1. editar src/a.ts"], "criterios_aceptacion": [{"id": "C1", "descripcion": "ok", "verificacion": "v1"}],
                   "rutas_permitidas": ["src/**"], "verificaciones": [{"id": "v1", "comando": ["true"], "timeout_s": 30}],
                   "depende_de": [f"T{i - 1:03d}"] if i > 1 else []}
    return {"asunto": "Plan de prueba", "peticion": "haz algo", "tareas": [t(i) for i in range(1, n + 1)]}


class TestPlan(unittest.TestCase):
    def test_ciclo_new_validate_approve_start(self):
        with L.Lab() as lab:
            lab.plan([], aprobar=False, empezar=False)       # crea un plan que no es el actual; el nuevo lo sustituye
            r = ag(lab, "plan", "new", escribir(lab, "p.json", spec_basico(2)))
            self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("creado con 2 tareas", r.stdout)
            with open(os.path.join(os.environ["ARKANA_AGENTIC_DIR"], "state", "actual")) as fh:
                pid = fh.read().strip()
            self.assertEqual(lab.plan_json(pid)["estado"], "borrador")
            self.assertEqual(lab.tarea(pid, "T002")["depende_de"], ["T001"])
            self.assertEqual(lab.plan_json(pid)["autoriza"]["rama"], f"arkana-worker/{pid}")
            self.assertEqual(ag(lab, "plan", "start").returncode, 3)            # sin aprobar no arranca
            self.assertEqual(ag(lab, "plan", "validate").returncode, 0)
            self.assertEqual(ag(lab, "plan", "approve").returncode, 0)
            self.assertEqual(ag(lab, "plan", "approve").returncode, 3)          # ya no es borrador
            self.assertEqual(ag(lab, "plan", "start").returncode, 0)
            self.assertEqual(lab.plan_json(pid)["estado"], "en_ejecucion")
            self.assertIn("T001", ag(lab, "plan", "show").stdout)

    def test_validacion_rechaza_dependencias_ciclos_y_exceso(self):
        with L.Lab() as lab:
            s = spec_basico(2)
            s["tareas"][0]["depende_de"] = ["T002"]                              # ciclo T001 <-> T002
            r = ag(lab, "plan", "new", escribir(lab, "a.json", s))
            self.assertEqual(r.returncode, 1); self.assertIn("ciclo de dependencias", r.stdout)
            s = spec_basico(1); s["tareas"][0]["depende_de"] = ["T009"]
            r = ag(lab, "plan", "new", escribir(lab, "b.json", s))
            self.assertIn("T009, que no existe", r.stdout)
            s = spec_basico(1); s["tareas"][0]["criterios_aceptacion"][0]["verificacion"] = "nada"
            self.assertIn("no esta definida", ag(lab, "plan", "new", escribir(lab, "c.json", s)).stdout)
            s = spec_basico(13)
            self.assertIn("el maximo efectivo es 12", ag(lab, "plan", "new", escribir(lab, "d.json", s)).stdout)
            s = spec_basico(1); s["tareas"][0]["repo"] = "nadie"
            self.assertEqual(ag(lab, "plan", "new", escribir(lab, "e.json", s)).returncode, 1)

    def test_avisa_de_verificaciones_fuera_de_la_lista(self):
        with L.Lab() as lab:
            s = spec_basico(1); s["tareas"][0]["verificaciones"][0]["comando"] = ["rm", "-rf", "x"]
            r = ag(lab, "plan", "new", escribir(lab, "p.json", s))
            self.assertEqual(r.returncode, 0); self.assertIn("abrira un gate", r.stdout)

    def test_aprobado_no_admite_cambios_a_mano(self):
        with L.Lab() as lab:
            pid = lab.plan(empezar=False)
            t = lab.tarea(pid); t["instrucciones"].append("3. borra todo")
            state.save_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"), t)
            self.assertEqual(ag(lab, "plan", "start", plan=pid).returncode, 3)


class TestNext(unittest.TestCase):
    def test_razones(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}], empezar=False)
            self.assertEqual(js(lab, "next", plan=pid)["estado"], "no_iniciado")
            state.start_plan(pid)
            n = js(lab, "next", plan=pid)
            self.assertEqual((n["estado"], n["tarea"]), ("tarea", "T001"))
            lab.correr(pid)
            n = js(lab, "next", plan=pid)                                       # T001 completada (sin commit aun): T002 ya es ejecutable
            self.assertEqual((n["estado"], n["tarea"]), ("tarea", "T002"))

    def test_dependencias_y_terminado(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}])
            lab.correr(pid)
            self.assertEqual(ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid).returncode, 0)
            n = js(lab, "next", plan=pid); self.assertEqual((n["estado"], n["tarea"]), ("tarea", "T002"))
            lab.correr(pid, "T002")
            ag(lab, "act", "continue", "T002", "--message", MSG, plan=pid)
            n = js(lab, "next", plan=pid)
            self.assertEqual((n["estado"], n["detalle"]), ("terminado", "completado"))
            self.assertEqual(lab.plan_json(pid)["estado"], "completado")

    def test_worker_en_curso_y_pausa_suave(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {}])
            pf = os.path.join(lab.root, "pids")
            p = lab.popen_lanzar(pid, "T001", env={"FAKE_MODE": "dormido", "FAKE_SLEEP": "30", "FAKE_PID_FILE": pf})
            try:
                wj = os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "worker.json")
                self.assertTrue(lab.esperar(lambda: os.path.exists(wj) and os.path.exists(pf), 20))
                n = js(lab, "next", plan=pid); self.assertEqual((n["estado"], n["tarea"]), ("worker_en_curso", "T001"))
                self.assertEqual(ag(lab, "next", plan=pid).returncode, 0)             # esperar a un worker vivo no es un fallo
                r = ag(lab, "stop", plan=pid)                                   # suave: solo marca
                self.assertIn("terminara su tarea", r.stdout)
                self.assertTrue(os.path.exists(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "PAUSE")))
                self.assertEqual(ag(lab, "launch", "T002", plan=pid).returncode, 7)   # hay una parada pedida
            finally:
                ag(lab, "stop", "--force", plan=pid)
                p.communicate(timeout=30)

    def test_pausa_cuando_no_hay_worker_y_reanudar(self):
        with L.Lab() as lab:
            pid = lab.plan()
            r = ag(lab, "pause", plan=pid)
            self.assertEqual(lab.plan_json(pid)["estado"], "pausado")
            self.assertEqual(js(lab, "next", plan=pid)["estado"], "pausado")
            self.assertEqual(ag(lab, "launch", "T001", plan=pid).returncode, 3)
            self.assertEqual(ag(lab, "resume", plan=pid).returncode, 0)
            self.assertEqual(js(lab, "next", plan=pid)["estado"], "tarea")

    def test_marca_pause_se_convierte_en_pausa_con_next(self):
        with L.Lab() as lab:
            pid = lab.plan()
            os.makedirs(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run"), exist_ok=True)
            open(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "PAUSE"), "w").close()
            self.assertEqual(js(lab, "next", plan=pid)["estado"], "pausado")
            self.assertEqual(lab.plan_json(pid)["estado"], "pausado")

    def test_limite_de_presupuesto_abre_gate(self):
        with L.Lab() as lab:
            pid = lab.plan()
            state.add_counter(pid, "gasto_usd", 5.0)
            n = js(lab, "next", plan=pid)
            self.assertEqual((n["estado"], n["motivo"]), ("limite", "presupuesto_total"))
            g = lab.plan_json(pid)["gate"]
            self.assertEqual(g["motivo"], "limite"); self.assertEqual(lab.plan_json(pid)["estado"], "esperando_usuario")

    def test_checkpoint_cada_n_tareas(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {}, {}, {}], plan_extra={"politica": {"checkpoint_every": 2}})
            for t in ("T001", "T002"):
                lab.correr(pid, t)
                ag(lab, "act", "continue", t, "--message", MSG, plan=pid)
            n = js(lab, "next", plan=pid)
            self.assertEqual(n["estado"], "gate"); self.assertEqual(n["gate"]["motivo"], "checkpoint")
            gid = n["gate"]["gate"]
            self.assertEqual(ag(lab, "approve", gid, plan=pid).returncode, 0)
            self.assertEqual(js(lab, "next", plan=pid)["tarea"], "T003")

    def test_tarea_pendiente_de_decision_y_fallo_del_plan(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid, modo="hecha_sin_cumplir")
            n = js(lab, "next", plan=pid); self.assertEqual((n["estado"], n["tareas"]), ("decision_pendiente", ["T001"]))
            ag(lab, "act", "skip", "T001", plan=pid)
            self.assertEqual(js(lab, "next", plan=pid)["detalle"], "completado")  # todas omitidas/completadas


class TestAct(unittest.TestCase):
    def test_continuar_hace_commit_local_validado_en_la_rama(self):
        with L.Lab() as lab:
            base = lab.head("api", "develop")
            pid = lab.plan()
            lab.correr(pid)
            r = ag(lab, "act", "continue", "T001", plan=pid)
            self.assertEqual(r.returncode, 2, r.stdout); self.assertIn("--message", r.stdout)
            r = ag(lab, "act", "continue", "T001", "--message", "Added the thing.", plan=pid)
            self.assertEqual(r.returncode, 1, r.stdout)                         # formato invalido
            r = ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            t = lab.tarea(pid)
            self.assertEqual(t["commit"], lab.head("api"))
            self.assertNotEqual(t["commit"], base)
            self.assertEqual(lab.head("api", "develop"), base)             # develop intacto
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "log", "-1", "--format=%s"]).stdout.strip(), MSG)
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"]).stdout.strip(), "")
            self.assertIn("ya hecho", ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid).stdout)

    def test_continuar_exige_tarea_completada(self):
        with L.Lab() as lab:
            pid = lab.plan()
            self.assertEqual(ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid).returncode, 3)

    def test_reintentar_descarta_cambios_aplica_limites_y_causa_repetida(self):
        with L.Lab() as lab:
            ag(lab, "policy", "set", "max_attempts_per_task", "3")        # un plan solo puede bajar los limites: se sube en la politica local
            pid = lab.plan([{}], plan_extra={"politica": {"max_attempts_per_task": 3}})
            a_txt = os.path.join(lab.rutas["api"], "src", "a.ts")
            lab.correr(pid, modo="hecha_sin_cumplir")
            sucio = Path(a_txt).read_text()
            r = ag(lab, "act", "retry", "T001", "--feedback-file", escribir(lab, "fb.txt", "arregla el criterio C1"), plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotEqual(Path(a_txt).read_text(), sucio)                      # cambios descartados
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"]).stdout.strip(), "")
            t = lab.tarea(pid)
            self.assertEqual((t["estado"], t["feedback"]), ("lista", ["arregla el criterio C1"]))
            lab.correr(pid, modo="hecha_sin_cumplir")                           # misma causa: ya no se reintenta
            r = ag(lab, "act", "retry", "T001", plan=pid)
            self.assertEqual(r.returncode, 6, r.stdout); self.assertIn("misma causa", r.stdout)

    def test_reintentar_respeta_el_maximo_de_intentos(self):
        with L.Lab() as lab:
            pid = lab.plan([{}], plan_extra={"politica": {"max_attempts_per_task": 1}})
            lab.correr(pid, modo="hecha_sin_cumplir")
            r = ag(lab, "act", "retry", "T001", plan=pid)
            self.assertEqual(r.returncode, 6); self.assertIn("ya uso sus 1 intentos", r.stdout)

    def test_accion_no_permitida_tras_el_resultado(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid, modo="toca_otro_repo", env={"FAKE_OTHER_FILE": os.path.join(lab.rutas["shared"], "README.md")})
            r = ag(lab, "act", "retry", "T001", plan=pid)
            self.assertEqual(r.returncode, 3, r.stdout)

    def test_omitir_y_detener(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {}])
            self.assertEqual(ag(lab, "act", "skip", "T002", plan=pid).returncode, 0)
            self.assertEqual(lab.tarea(pid, "T002")["estado"], "omitida")
            self.assertEqual(ag(lab, "act", "stop", plan=pid).returncode, 0)
            self.assertEqual(lab.plan_json(pid)["estado"], "detenido")

    def test_escalar_abre_gate_y_la_respuesta_llega_como_feedback(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid, modo="hecha_sin_cumplir")
            r = ag(lab, "act", "escalate", "T001", "--reason", "no avanza", "--detail", "que formato de NIF usamos", plan=pid)
            self.assertEqual(r.returncode, 5, r.stdout)
            p = lab.plan_json(pid)
            self.assertEqual((p["estado"], p["gate"]["motivo"], p["gate"]["tarea"]), ("esperando_usuario", "decision", "T001"))
            self.assertEqual(js(lab, "next", plan=pid)["estado"], "gate")
            r = ag(lab, "approve", p["gate"]["gate"], "--note", "usa el formato DNI/NIE", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            t = lab.tarea(pid)
            self.assertEqual(t["estado"], "lista"); self.assertIn("usa el formato DNI/NIE", t["feedback"][-1])
            self.assertEqual(lab.plan_json(pid)["estado"], "en_ejecucion")

    def test_dividir_reemplaza_la_tarea_y_pide_aprobar_el_plan_modificado(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}])
            lab.correr(pid, modo="parcial")
            nuevas = [{"asunto": "Parte A", "repo": "api", "tipo": "tarea", "objetivo": "parte a", "instrucciones": ["1. a"],
                       "criterios_aceptacion": [{"id": "C1", "descripcion": "ok"}], "rutas_permitidas": ["src/**"]},
                      {"asunto": "Parte B", "repo": "api", "tipo": "tarea", "objetivo": "parte b", "instrucciones": ["1. b"],
                       "criterios_aceptacion": [{"id": "C1", "descripcion": "ok"}], "rutas_permitidas": ["src/**"]}]
            r = ag(lab, "act", "split", "T001", "--tasks-file", escribir(lab, "n.json", nuevas), plan=pid)
            self.assertEqual(r.returncode, 5, r.stdout)
            self.assertEqual(lab.tarea(pid, "T001")["estado"], "omitida")
            self.assertEqual(lab.tarea(pid, "T003")["depende_de"], [])
            self.assertEqual(lab.tarea(pid, "T004")["depende_de"], ["T003"])
            self.assertEqual(lab.tarea(pid, "T002")["depende_de"], ["T004"])      # la dependiente espera al ultimo
            p = lab.plan_json(pid)
            self.assertEqual((p["gate"]["motivo"], p["contadores"]["cambios_plan"]), ("plan_modificado", 1))
            self.assertFalse(state.plan_approval_ok(pid))                       # no se ejecuta sin reaprobar
            self.assertEqual(ag(lab, "approve", p["gate"]["gate"], plan=pid).returncode, 0)
            self.assertTrue(state.plan_approval_ok(pid))
            self.assertEqual(js(lab, "next", plan=pid)["tarea"], "T003")

    def test_limite_de_cambios_de_plan(self):
        with L.Lab() as lab:
            pid = lab.plan([{}], plan_extra={"politica": {"max_plan_changes": 0}})
            r = ag(lab, "act", "investigate", "--repo", "app", "--subject", "mirar", "--instructions-file", escribir(lab, "i.txt", "1. lee"), plan=pid)
            self.assertEqual(r.returncode, 6, r.stdout)

    def test_investigar_crea_tarea_de_lectura_con_gate(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            r = ag(lab, "act", "investigate", "--repo", "app", "--subject", "Como valida el NIF el front", "--for", "T001",
                   "--instructions-file", escribir(lab, "i.txt", "1. lee src\n2. resume"), plan=pid)
            self.assertEqual(r.returncode, 5, r.stdout)
            n = lab.tarea(pid, "T002")
            self.assertEqual((n["tipo"], n["perfil"], n["repo"], n["instrucciones"]), ("investigacion", "lectura", "app", ["1. lee src", "2. resume"]))
            self.assertEqual(lab.tarea(pid, "T001")["depende_de"], ["T002"])
            self.assertEqual(lab.plan_json(pid)["gate"]["motivo"], "plan_modificado")

    def test_investigar_preautorizado_no_abre_gate(self):
        with L.Lab() as lab:
            pid = lab.plan([{}], plan_extra={"autoriza": {"commits_locales": True, "investigate_without_gate": True}})
            r = ag(lab, "act", "investigate", "--repo", "app", "--subject", "mirar", "--instructions-file", escribir(lab, "i.txt", "1. lee"), plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIsNone(lab.plan_json(pid)["gate"]); self.assertTrue(state.plan_approval_ok(pid))


class TestGates(unittest.TestCase):
    def test_ruta_protegida_se_autoriza_y_se_reverifica(self):
        with L.Lab() as lab:
            pid = lab.plan([{"rutas_permitidas": ["src/**", ".husky/**"]}])
            l, f, ver = lab.correr(pid, modo="toca_protegido")
            p = lab.plan_json(pid)
            self.assertEqual((f.returncode, p["gate"]["motivo"], p["gate"]["reanuda"]), (5, "ruta_protegida", "reverify"), f.stdout)
            self.assertFalse(os.path.exists(lab.marker))
            r = ag(lab, "approve", p["gate"]["gate"], plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(lab.tarea(pid)["estado"], "verificando")
            f = ag(lab, "finish", "T001", plan=pid)
            self.assertEqual(f.returncode, 0, f.stdout); self.assertEqual(lab.tarea(pid)["estado"], "completada")

    def test_rechazar_gate_omite_la_tarea(self):
        with L.Lab() as lab:
            pid = lab.plan([{"rutas_permitidas": ["src/**", ".husky/**"]}])
            lab.correr(pid, modo="toca_protegido")
            gid = lab.plan_json(pid)["gate"]["gate"]
            r = ag(lab, "reject", gid, plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(lab.tarea(pid)["estado"], "omitida")
            self.assertIsNone(lab.plan_json(pid)["gate"])
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"]).stdout.strip(), "")

    def test_violacion_solo_admite_detener(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid, modo="toca_otro_repo", env={"FAKE_OTHER_FILE": os.path.join(lab.rutas["shared"], "README.md")})
            gid = lab.plan_json(pid)["gate"]["gate"]
            r = ag(lab, "approve", gid, plan=pid)
            self.assertEqual(r.returncode, 3, r.stdout); self.assertIn("reject --stop", r.stdout)
            self.assertEqual(ag(lab, "reject", gid, "--stop", plan=pid).returncode, 0)
            self.assertEqual(lab.plan_json(pid)["estado"], "detenido")

    def test_gate_inexistente_o_distinto(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            self.assertEqual(ag(lab, "approve", "G99", plan=pid).returncode, 3)

    def test_worker_bloqueado_por_dato_reintenta_con_la_respuesta(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid, modo="bloqueada")
            p = lab.plan_json(pid)
            self.assertEqual((p["gate"]["motivo"], p["gate"]["reanuda"]), ("dato", "retry"))
            ag(lab, "approve", p["gate"]["gate"], "--note", "el NIF tiene 9 caracteres", plan=pid)
            t = lab.tarea(pid)
            self.assertEqual(t["estado"], "lista"); self.assertIn("9 caracteres", t["feedback"][-1])


class TestParada(unittest.TestCase):
    def test_stop_force_con_el_lanzador_vivo(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            pf = os.path.join(lab.root, "pids")
            p = lab.popen_lanzar(pid, env={"FAKE_MODE": "dormido", "FAKE_SLEEP": "30", "FAKE_PID_FILE": pf})
            wj = os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "worker.json")
            self.assertTrue(lab.esperar(lambda: os.path.exists(wj) and os.path.exists(pf), 20))
            r = ag(lab, "stop", "--force", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            p.communicate(timeout=30)
            self.assertEqual(lab.tarea(pid)["estado"], "cancelada"); self.assertEqual(lab.plan_json(pid)["estado"], "detenido")
            pids = [int(x) for x in Path(pf).read_text().split()]
            self.assertTrue(lab.esperar(lambda: not any(lab.vivo(x) for x in pids), 10))

    def test_stop_force_con_el_lanzador_muerto(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            pf = os.path.join(lab.root, "pids")
            p = lab.popen_lanzar(pid, env={"FAKE_MODE": "dormido", "FAKE_SLEEP": "30", "FAKE_PID_FILE": pf})
            run = os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run")
            self.assertTrue(lab.esperar(lambda: os.path.exists(os.path.join(run, "worker.json")) and os.path.exists(pf), 20))
            w = state.load_json(os.path.join(run, "worker.json"))
            pids = [int(x) for x in Path(pf).read_text().split()]
            wd = os.path.join(run, "watchdog.pid")
            import signal
            if os.path.exists(wd):
                try:
                    os.kill(int(Path(wd).read_text().strip()), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass
            p.kill(); p.communicate(timeout=30)                                 # cae el lanzador; el worker sigue
            self.assertTrue(lab.vivo(pids[0]))
            r = ag(lab, "stop", "--force", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(lab.esperar(lambda: not any(lab.vivo(x) for x in pids), 10))
            self.assertEqual(lab.tarea(pid)["estado"], "cancelada"); self.assertEqual(lab.plan_json(pid)["estado"], "detenido")
            self.assertFalse(os.path.exists(os.path.join(run, "worker.json")))
            self.assertEqual(w["plan"], pid)

    def test_stop_force_sin_worker(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            r = ag(lab, "stop", "--force", plan=pid)
            self.assertIn("no habia ningun worker", r.stdout)
            self.assertEqual(lab.plan_json(pid)["estado"], "detenido")


class TestRecover(unittest.TestCase):
    def preparar(self, lab):
        pid = lab.plan([{}])
        state.transition_task(pid, "T001", "lista")
        state.transition_task(pid, "T001", "en_curso")
        return pid

    def test_marca_interrumpida_y_propone(self):
        with L.Lab() as lab:
            pid = self.preparar(lab)
            r = ag(lab, "fix", plan=pid)
            self.assertEqual(r.returncode, 5, r.stdout); self.assertIn("T001 interrumpida", r.stdout)
            self.assertEqual(lab.tarea(pid)["estado"], "interrumpida")
            self.assertEqual(js(lab, "next", plan=pid)["estado"], "decision_pendiente")

    def test_reintentar_y_descartar(self):
        with L.Lab() as lab:
            pid = self.preparar(lab)
            ag(lab, "fix", plan=pid)
            self.assertEqual(ag(lab, "fix", "--task", "T001", plan=pid).returncode, 2)
            self.assertEqual(ag(lab, "fix", "--task", "T001", "--action", "retry", plan=pid).returncode, 0)
            self.assertEqual(lab.tarea(pid)["estado"], "lista")
        with L.Lab() as lab:
            pid = self.preparar(lab)
            ag(lab, "fix", plan=pid)
            self.assertEqual(ag(lab, "fix", "--task", "T001", "--action", "discard", plan=pid).returncode, 0)
            self.assertEqual(lab.tarea(pid)["estado"], "cancelada")

    def test_sin_nada_que_recuperar(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            self.assertIn("no hay tareas interrumpidas", ag(lab, "fix", plan=pid).stdout)


class TestPoliticaYEstado(unittest.TestCase):
    def test_policy_show_set_y_techos(self):
        with L.Lab() as lab:
            r = ag(lab, "policy", "set", "max_turns", "50")
            self.assertEqual(r.returncode, 0, r.stdout)
            filas = {f["clave"]: f for f in json.loads(ag(lab, "policy", "show", "--json").stdout)}
            self.assertEqual((filas["max_turns"]["valor"], filas["max_turns"]["nivel"]), (50, "local"))
            self.assertEqual(ag(lab, "policy", "set", "max_turns", "500").returncode, 6)     # supera el techo
            self.assertEqual(ag(lab, "policy", "set", "max_turns", "-1").returncode, 2)
            self.assertEqual(ag(lab, "policy", "set", "inventada", "1").returncode, 2)
            self.assertEqual(ag(lab, "policy", "set", "max_turns", "500", "--ceiling").returncode, 0)
            self.assertEqual(ag(lab, "policy", "set", "max_turns", "500").returncode, 0)
            self.assertEqual(oct(os.stat(lab.cambios["ARKANA_AGENTIC_DIR"]).st_mode & 0o777), "0o700")

    def test_status_humano_y_json(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}])
            lab.correr(pid)
            h = ag(lab, "status", plan=pid).stdout
            for t in (pid, "T001", "T002", "Gasto 0,", "Gate abierto: ninguno", "estado: en_ejecucion"):
                self.assertIn(t, h)
            d = js(lab, "status", plan=pid)
            self.assertEqual([t["estado"] for t in d["tareas"]], ["completada", "pendiente"])
            self.assertEqual(d["tareas"][0]["max_attempts"], 2)

    def test_log_muestra_resultado_y_verificacion(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid, modo="hecha_sin_cumplir")
            o = ag(lab, "log", "T001", plan=pid).stdout
            self.assertIn("Verificacion: rechazada", o); self.assertIn("Worker: exit 0", o)
            self.assertIn("todavia no", ag(lab, "log", "T001", plan=lab.plan([{}])).stdout)

    def test_sin_plan_actual(self):
        with L.Lab() as lab:
            self.assertIn("Sin plan actual", ag(lab, "status").stdout)
            self.assertEqual(ag(lab, "next").returncode, 3)

    def test_check_rapido(self):
        with L.Lab() as lab:
            d = json.loads(ag(lab, "check", "--json", env={"ARKANA_AGENTIC_CLAUDE_BIN": "claude"}).stdout)
            ids = {x["id"]: x["estado"] for x in d}
            for i in ("claude-version", "claude-flags", "utilidades", "runtime-700", "politica-valida", "worker-huerfano", "permisos-arkana", "instrucciones", "layout"):
                self.assertIn(i, ids)
            self.assertEqual(ids["utilidades"], "OK"); self.assertEqual(ids["politica-valida"], "OK")
            self.assertEqual(ids["claude-flags"], "OK")


class TestContratoDeRepos(unittest.TestCase):
    """El esquema ya no enumera los repos: la existencia de cada repo la comprueba el plan contra el manifiesto."""

    def test_plan_new_rechaza_un_repo_que_no_esta_en_el_manifiesto(self):
        with L.Lab() as lab:
            lab.plan([], aprobar=False, empezar=False)
            spec = spec_basico(1)
            spec["tareas"][0]["repo"] = "no-existe"
            r = ag(lab, "plan", "new", escribir(lab, "p.json", spec))
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("repo desconocido no-existe", r.stdout)
            spec["tareas"][0]["repo"] = "Mal_Formato"
            self.assertEqual(ag(lab, "plan", "new", escribir(lab, "q.json", spec)).returncode, 1)         # y el formato lo sigue exigiendo el esquema


class TestAdaptadoresComoLoVeElVerificador(unittest.TestCase):
    """El verificador no hereda el PATH del shell: `check` debe avisar si una herramienta del adaptador solo está en el PATH del usuario."""

    def estados(self, lab, encontrados=()):
        import doctor
        os.environ["ARKANA_AGENTIC_CLAUDE_BIN"] = "claude"
        real = doctor.shutil.which
        doctor.shutil.which = lambda cmd, path=None: (f"/usr/bin/{cmd}" if cmd in encontrados else None)
        try:
            return {i: (e, d) for e, i, d in doctor.checks(False)}
        finally:
            doctor.shutil.which = real

    def test_una_herramienta_solo_en_el_path_del_usuario_no_cuenta(self):
        with L.Lab() as lab:
            e, d = self.estados(lab)["adaptadores"]
            self.assertEqual(e, "WARN")
            self.assertIn("el verificador no encuentra", d)
            self.assertIn("node", d)

    def test_cuenta_si_esta_en_el_path_del_verificador_o_declarada_con_su_carpeta_bin(self):
        with L.Lab() as lab:
            self.assertEqual(self.estados(lab, encontrados=("node", "npm", "ng"))["adaptadores"][0], "OK")      # en /usr/bin
        with L.Lab() as lab:
            node = os.path.join(lab.root, "node-instalado")
            os.makedirs(os.path.join(node, "bin"))
            tj = os.path.join(os.environ["ARKANA_PLUGINS_DIR"], "arkana-workspace", "tools.json")
            os.makedirs(os.path.dirname(tj))
            Path(tj).write_text(json.dumps({"schema_version": 1, "tools": [{"tool": "node", "version": "18", "path": node}]}))
            self.assertEqual(self.estados(lab)["adaptadores"][0], "OK")                                          # declarada con ruta (npm va con node)


class TestRedCaida(unittest.TestCase):
    """agentic solo edita y hace commits locales (sin fetch ni push): sin VPN es un aviso, no una parada; `check --need-network` lo vuelve a exigir."""

    def con_red_caida(self, ok=False):
        import repos
        orig = (repos.net_hosts, repos.net_preflight)
        repos.net_hosts = lambda: ["gitlab.ejemplo"]
        repos.net_preflight = lambda: (ok, "hosts de los remotos resuelven" if ok else "gitlab.ejemplo no resuelve (sin respuesta): ¿VPN caída?")

        def restaurar():
            repos.net_hosts, repos.net_preflight = orig
        return restaurar

    def test_check_red_vpn_es_warn_y_con_need_network_es_fail(self):
        import doctor
        with L.Lab() as lab:
            os.environ["ARKANA_AGENTIC_CLAUDE_BIN"] = "claude"                                   # el simulado edita un fichero en su cwd ante cualquier llamada (--version incluida)
            os.environ["FAKE_EDIT"] = os.path.join(lab.root, "descarte.txt")                     # que no sea src/a.ts del propio repo de pruebas (lo restaura Lab al salir)
            restaurar = self.con_red_caida()
            try:
                est = {i: (e, d) for e, i, d in doctor.checks(False)}
                self.assertEqual(est["red-vpn"][0], "WARN")
                self.assertIn("No bloquea", est["red-vpn"][1])
                self.assertEqual({i: e for e, i, d in doctor.checks(False, necesita_red=True)}["red-vpn"], "FAIL")
            finally:
                restaurar()
            restaurar = self.con_red_caida(ok=True)
            try:
                self.assertEqual({i: e for e, i, d in doctor.checks(False)}["red-vpn"], "OK")
                self.assertEqual({i: e for e, i, d in doctor.checks(False, necesita_red=True)}["red-vpn"], "OK")
            finally:
                restaurar()

    def test_la_salida_de_check_marca_red_vpn_como_warn_y_con_need_network_como_fail(self):
        import doctor
        import argparse
        import contextlib
        import io
        with L.Lab():
            os.environ["ARKANA_AGENTIC_CLAUDE_BIN"] = "claude"
            restaurar = self.con_red_caida()
            try:
                for necesita, esperado in ((False, "WARN|red-vpn|"), (True, "FAIL|red-vpn|")):
                    out = io.StringIO()
                    with contextlib.redirect_stdout(out):
                        doctor.main(argparse.Namespace(deep=False, json=False, necesita_red=necesita))
                    self.assertIn(esperado, out.getvalue())
                    self.assertEqual(("FAIL|red-vpn|" in out.getvalue()), necesita)
            finally:
                restaurar()

    def test_launch_con_la_red_caida_avisa_y_lanza_el_worker(self):
        import contextlib
        import io
        import launch
        with L.Lab() as lab:
            pid = lab.plan()
            restaurar = self.con_red_caida()
            os.environ["FAKE_MODE"] = "hecha"
            cwd = os.getcwd()
            os.chdir(lab.root)                                                                   # el worker simulado escribe relativo a su cwd: que sea el temporal, no el árbol del plugin
            try:
                err = io.StringIO()
                with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                    rc = launch.main(["launch", pid, "T001"])
            finally:
                os.chdir(cwd)
                restaurar()
                os.environ.pop("FAKE_MODE", None)
            self.assertEqual(rc, 0, err.getvalue())
            self.assertIn("WARN|red|", err.getvalue())
            self.assertIn("el worker se lanza igual", err.getvalue())
            self.assertEqual(lab.tarea(pid)["intentos"], 1)                                      # sí se lanzó

class TestCamposDeEjecucion(unittest.TestCase):
    """Los campos que el motor escribe en las tareas (commit, autorizado) tienen que pasar la validacion del esquema al cambiar el plan."""

    def test_dividir_e_investigar_con_tareas_ya_commiteadas_y_autorizadas(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}])
            lab.correr(pid, "T001")
            self.assertEqual(ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid).returncode, 0)     # T001 con commit
            t = lab.tarea(pid, "T001")
            self.assertTrue(t["commit"])
            t["autorizado"] = {"rutas_protegidas": [".husky/pre-commit"], "verificaciones": ["v1"]}             # y con una autorizacion previa
            state.save_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"), t)
            r = ag(lab, "act", "investigate", "--repo", "app", "--subject", "mirar algo", "--instructions-file", escribir(lab, "i.txt", "1. lee"), plan=pid)
            self.assertEqual(r.returncode, 5, r.stdout)                                                         # gate de plan modificado, no un error de esquema
            self.assertNotIn("clave no permitida", r.stdout)


class TestRamaPorPlan(unittest.TestCase):
    """Todo el trabajo de un plan en un repo va en UNA rama, arkana-worker/<plan>, que crea el script de lanzamiento; la decision final es por repo."""

    def ramas(self, lab, rid="api"):
        return L.sh(["git", "-C", lab.rutas[rid], "branch", "--list", "arkana-worker/*", "--format=%(refname:short)"], env=lab.env).stdout.split()

    def contar(self, lab, rid, rango):
        return int(L.sh(["git", "-C", lab.rutas[rid], "rev-list", "--count", rango], env=lab.env).stdout.strip())

    def asuntos(self, lab, rid, rango):
        return L.sh(["git", "-C", lab.rutas[rid], "log", "--reverse", "--format=%s", rango], env=lab.env).stdout.splitlines()

    def aceptar(self, lab, pid, tid, **env):
        lab.correr(pid, tid, env=env or None)
        self.assertEqual(ag(lab, "act", "continue", tid, "--message", MSG, plan=pid).returncode, 0)

    def dos_tareas(self, lab):
        pid = lab.plan([{}, {"depende_de": ["T001"]}])
        for t in ("T001", "T002"):
            self.aceptar(lab, pid, t)
        return pid

    def dos_repos(self, lab):
        """T001 y T003 en api, T002 en app (el orden lo elige el orquestador, aqui intercalado)."""
        pid = lab.plan([{}, {"repo": "app", "rutas_permitidas": ["README.md"]}, {"depende_de": ["T001"]}])
        self.aceptar(lab, pid, "T001")
        self.aceptar(lab, pid, "T002", FAKE_EDIT="README.md")
        self.aceptar(lab, pid, "T003")
        return pid

    def test_todas_las_tareas_de_un_repo_van_en_una_sola_rama_del_plan(self):
        with L.Lab() as lab:
            base = lab.head("api", "develop")
            pid = self.dos_tareas(lab)
            self.assertEqual(self.ramas(lab), [f"arkana-worker/{pid}"])
            self.assertEqual(lab.plan_json(pid)["ramas"]["api"], {"original": "develop", "nombre": f"arkana-worker/{pid}"})
            self.assertNotIn("rama", lab.tarea(pid, "T001")); self.assertNotIn("rama", lab.tarea(pid, "T002"))
            self.assertEqual(self.asuntos(lab, "api", "develop..HEAD"), [MSG, MSG])              # un commit por tarea aceptada
            self.assertEqual(lab.rama("api"), f"arkana-worker/{pid}")
            self.assertEqual(lab.head("api", "develop"), base)                                     # develop no se toca
            self.assertEqual(lab.tarea(pid, "T002")["commit"], lab.head("api"))

    def test_el_nombre_de_la_rama_va_en_el_prompt_del_worker_solo_como_informacion(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid)
            with open(os.path.join(state.plan_dir(pid), "logs", "T001.1.prompt.md"), encoding="utf-8") as f:
                prompt = f.read()
            self.assertIn(f"`arkana-worker/{pid}`", prompt); self.assertIn("no tienes git", prompt)

    def test_dos_repos_cada_uno_su_rama_con_el_mismo_nombre(self):
        with L.Lab() as lab:
            pid = self.dos_repos(lab)
            self.assertEqual((self.ramas(lab, "api"), self.ramas(lab, "app")), ([f"arkana-worker/{pid}"], [f"arkana-worker/{pid}"]))
            self.assertEqual((self.contar(lab, "api", "develop..HEAD"), self.contar(lab, "app", "develop..HEAD")), (2, 1))
            self.assertEqual(set(lab.plan_json(pid)["ramas"]), {"api", "app"})
            self.assertEqual((lab.rama("api"), lab.rama("app")), (f"arkana-worker/{pid}", f"arkana-worker/{pid}"))

    def test_un_repo_fuera_de_la_rama_vuelve_a_ella_antes_de_lanzar(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}])
            self.aceptar(lab, pid, "T001")
            L.sh(["git", "-C", lab.rutas["api"], "switch", "-q", "develop"], env=lab.env)        # alguien lo dejo en develop
            self.aceptar(lab, pid, "T002")
            self.assertEqual(lab.rama("api"), f"arkana-worker/{pid}")
            self.assertEqual(self.contar(lab, "api", "develop..HEAD"), 2)                          # y T002 parte del trabajo aceptado de T001

    def test_un_reintento_vuelve_al_ultimo_commit_aceptado_y_no_crea_ramas(self):
        with L.Lab() as lab:
            ag(lab, "policy", "set", "max_attempts_per_task", "3")
            pid = lab.plan([{}, {"depende_de": ["T001"]}], plan_extra={"politica": {"max_attempts_per_task": 3}})
            self.aceptar(lab, pid, "T001")
            aceptado = lab.head("api")
            lab.correr(pid, "T002", modo="hecha_sin_cumplir")
            self.assertNotEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"], env=lab.env).stdout.strip(), "")   # trabajo sin aceptar
            self.assertEqual(ag(lab, "act", "retry", "T002", plan=pid).returncode, 0)
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"], env=lab.env).stdout.strip(), "")        # descartado
            self.assertEqual(lab.head("api"), aceptado)                                                                            # lo aceptado se conserva
            lab.correr(pid, "T002", modo="hecha")
            self.assertEqual(self.ramas(lab), [f"arkana-worker/{pid}"]); self.assertEqual(lab.tarea(pid, "T002")["intentos"], 2)

    def test_dos_planes_en_el_mismo_repo_no_chocan(self):
        with L.Lab() as lab:
            base = lab.head("api", "develop")
            pid1 = lab.plan([{}])
            self.aceptar(lab, pid1, "T001")
            ag(lab, "integrate", "keep", plan=pid1)                                                   # deja arkana-worker/<plan1>
            pid2 = lab.plan([{}])
            self.aceptar(lab, pid2, "T001")
            self.assertEqual(sorted(self.ramas(lab)), sorted([f"arkana-worker/{pid1}", f"arkana-worker/{pid2}"]))
            self.assertEqual(lab.plan_json(pid2)["ramas"]["api"]["original"], "develop")          # el plan nuevo parte de develop, no del anterior
            self.assertEqual(self.contar(lab, "api", "develop..HEAD"), 1)
            self.assertEqual(ag(lab, "integrate", "discard", plan=pid2).returncode, 0)
            self.assertEqual(self.ramas(lab), [f"arkana-worker/{pid1}"])                                         # el descarte de un plan no toca la rama del otro
            self.assertEqual(lab.head("api", "develop"), base)

    def test_review_resume_cada_repo_sin_cambiar_nada(self):
        with L.Lab() as lab:
            pid = self.dos_repos(lab)
            h = {r: lab.head(r) for r in ("api", "app")}
            r = ag(lab, "integrate", "review", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            for texto in (f"api: rama arkana-worker/{pid} (original develop) · decision: pendiente", f"app: rama arkana-worker/{pid}", "T001 ", "T003 ", "T002 ", MSG,
                          "src/a.ts", "README.md", "gasto del plan"):
                self.assertIn(texto, r.stdout)
            self.assertEqual({r: lab.head(r) for r in ("api", "app")}, h)
            self.assertEqual((lab.rama("api"), lab.rama("app")), (f"arkana-worker/{pid}", f"arkana-worker/{pid}"))
            regs = [json.loads(l) for l in Path(os.path.join(state.plan_dir(pid), "registro.jsonl")).read_text(encoding="utf-8").splitlines()]
            self.assertEqual([x["quien"] for x in regs if x["accion"] == "review"], ["orchestrator"])                 # la revision deja traza

    def test_review_avisa_de_dependencias_entre_repos(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"repo": "app", "depende_de": ["T001"]}])
            self.aceptar(lab, pid, "T001")
            r = ag(lab, "integrate", "review", plan=pid)
            self.assertIn("api, app", r.stdout)

    def test_cada_repo_se_decide_por_separado(self):
        with L.Lab() as lab:
            base = {r: lab.head(r, "develop") for r in ("api", "app")}
            pid = self.dos_repos(lab)
            r = ag(lab, "integrate", "merge", "--repo", "api", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual((lab.rama("api"), self.ramas(lab, "api")), ("develop", []))     # el merge integra la rama entera y la borra
            self.assertEqual(self.asuntos(lab, "api", f"{base['api']}..develop").count(MSG), 2)
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "log", "-1", "--format=%s"], env=lab.env).stdout.strip(), f"chore(api) merge arkana-worker/{pid}")
            self.assertEqual(lab.rama("app"), f"arkana-worker/{pid}")                                           # el otro repo sigue como estaba
            self.assertEqual(lab.plan_json(pid)["ramas"]["api"]["decision"], "merge")
            regs = [json.loads(l) for l in Path(os.path.join(state.plan_dir(pid), "registro.jsonl")).read_text(encoding="utf-8").splitlines()]
            fusion = [r for r in regs if r["accion"] == "integrate" and "api: merge" in r["motivo"]]
            self.assertEqual(len(fusion), 1); self.assertEqual(fusion[0]["sha"], lab.head("api", "develop"))        # el registro lleva el sha del merge
            r = ag(lab, "integrate", "keep", plan=pid)                                                # sin --repo: solo los que aun no tienen decision
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual((lab.rama("app"), self.ramas(lab, "app")), ("develop", [f"arkana-worker/{pid}"]))
            self.assertEqual(lab.head("app", "develop"), base["app"])
            self.assertEqual(lab.plan_json(pid)["ramas"]["app"]["decision"], "keep")
            self.assertIn("ya tienen decision", ag(lab, "integrate", "merge", plan=pid).stdout)
            r = ag(lab, "integrate", "discard", "--repo", "app", plan=pid)                           # cambiar una decision es explicito
            self.assertEqual(r.returncode, 0, r.stdout); self.assertEqual(self.ramas(lab, "app"), [])
            self.assertEqual(lab.plan_json(pid)["ramas"]["app"]["decision"], "discard")

    def test_merge_con_mensaje_propio(self):
        with L.Lab() as lab:
            base = lab.head("api", "develop")
            pid = self.dos_tareas(lab)
            r = ag(lab, "integrate", "merge", "--message", "chore(api) integrate both tasks", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            log = self.asuntos(lab, "api", f"{base}..develop")
            self.assertEqual(log.count(MSG), 2); self.assertEqual(log.count("chore(api) integrate both tasks"), 1)

    def test_up_to_integra_solo_hasta_una_tarea_y_conserva_la_rama(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}, {"depende_de": ["T002"]}])
            for t in ("T001", "T002", "T003"):
                self.aceptar(lab, pid, t)
            c2, c3 = lab.tarea(pid, "T002")["commit"], lab.tarea(pid, "T003")["commit"]
            r = ag(lab, "integrate", "merge", "--repo", "api", "--up-to", "T002", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            ancestro = lambda a, b: L.sh(["git", "-C", lab.rutas["api"], "merge-base", "--is-ancestor", a, b], env=lab.env).returncode == 0
            self.assertTrue(ancestro(c2, "develop")); self.assertFalse(ancestro(c3, "develop"))
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "log", "-1", "--format=%s"], env=lab.env).stdout.strip(), f"chore(api) merge arkana-worker/{pid} up to T002")
            self.assertEqual(self.ramas(lab), [f"arkana-worker/{pid}"]); self.assertEqual(lab.rama("api"), "develop")      # la rama se conserva con T003
            d = lab.plan_json(pid)["ramas"]["api"]
            self.assertEqual((d["decision"], d["integrado_hasta"]), ("merge", "T002"))
            r = ag(lab, "integrate", "merge", "--repo", "api", plan=pid)                          # el resto, cuando se quiera
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(ancestro(c3, "develop")); self.assertEqual(self.ramas(lab), [])

    def test_up_to_exige_merge_repo_y_una_tarea_del_repo_con_commit(self):
        with L.Lab() as lab:
            pid = self.dos_repos(lab)
            self.assertEqual(ag(lab, "integrate", "merge", "--up-to", "T001", plan=pid).returncode, 2)                        # sin --repo
            self.assertEqual(ag(lab, "integrate", "keep", "--repo", "api", "--up-to", "T001", plan=pid).returncode, 2)    # no es merge
            r = ag(lab, "integrate", "merge", "--repo", "api", "--up-to", "T002", plan=pid)                              # T002 es de app
            self.assertEqual(r.returncode, 2, r.stdout); self.assertEqual(lab.rama("api"), f"arkana-worker/{pid}")
            self.assertEqual(ag(lab, "integrate", "merge", "--repo", "app-web", plan=pid).returncode, 2)                     # sin rama en ese repo

    def test_keep_deja_la_rama_y_discard_la_borra(self):
        with L.Lab() as lab:
            base = lab.head("api", "develop")
            pid = self.dos_tareas(lab)
            self.assertEqual(ag(lab, "integrate", "keep", plan=pid).returncode, 0)
            self.assertEqual((lab.rama("api"), self.ramas(lab)), ("develop", [f"arkana-worker/{pid}"]))
            self.assertEqual(lab.head("api", "develop"), base)
            self.assertEqual(ag(lab, "integrate", "discard", "--repo", "api", plan=pid).returncode, 0)
            self.assertEqual(self.ramas(lab), []); self.assertEqual(lab.head("api", "develop"), base)


class TestRutaProtegidaDenegada(unittest.TestCase):
    """Hallazgo del piloto 3: los ajustes del worker deniegan CLAUDE.md, asi que el worker no podia tocarlo y el gate 'autorizar y reintentar' no
    servia de nada (el segundo intento fallaba igual). Ahora una denegacion sobre una ruta protegida abre un gate `ruta_protegida` y, si es
    autorizable (CLAUDE.md), aprobarlo levanta SOLO esa denegacion en el siguiente intento."""

    def ajustes(self, lab, n):
        with open(lab.cambios["FAKE_CLAUDE_LOG"], encoding="utf-8") as f:
            a = [json.loads(x) for x in f.read().splitlines()][n]["argv"]
        return json.loads(a[a.index("--settings") + 1])["permissions"]

    def plan_claude_md(self, lab):
        return lab.plan([{"rutas_permitidas": ["CLAUDE.md"]}])

    def test_denegacion_de_claude_md_abre_un_gate_ruta_protegida_autorizable(self):
        with L.Lab() as lab:
            pid = self.plan_claude_md(lab)
            l, f, ver = lab.correr(pid, modo="deniega_claude_md")
            self.assertEqual((f.returncode, ver["veredicto"], ver["gate"], ver["autorizable"]), (5, "bloqueada", "ruta_protegida", True))
            g = lab.plan_json(pid)["gate"]
            self.assertEqual((g["motivo"], g["reanuda"], g["rutas"]), ("ruta_protegida", "retry", ["CLAUDE.md"]))
            self.assertIn("CLAUDE.md", g["detalle"]); self.assertIn("Piloto: vi", g["detalle"])               # dice que ruta y que queria escribir
            self.assertIn("autorizar esa edicion y reintentar", g["opciones"])
            self.assertTrue(any(d.endswith("/CLAUDE.md)") for d in self.ajustes(lab, 0)["deny"]))              # el primer intento la tenia denegada

    def test_aprobar_autoriza_solo_esa_ruta_y_el_segundo_intento_funciona(self):
        with L.Lab() as lab:
            pid = self.plan_claude_md(lab)
            ag(lab, "policy", "set", "max_attempts_per_task", "2")
            lab.correr(pid, modo="deniega_claude_md")
            gid = lab.plan_json(pid)["gate"]["gate"]
            r = ag(lab, "approve", gid, "--note", "solo la vineta indicada", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            t = lab.tarea(pid)
            self.assertEqual((t["estado"], t["autorizado"]["rutas_protegidas"]), ("lista", ["CLAUDE.md"]))
            self.assertIn("solo la vineta indicada", " ".join(t["feedback"]))
            l, f, ver = lab.correr(pid, modo="edita_claude_md")
            self.assertEqual((l.returncode, f.returncode, ver["veredicto"]), (0, 0, "completada"), l.stdout + f.stdout)
            with open(os.path.join(lab.rutas["api"], "CLAUDE.md"), encoding="utf-8") as fh:
                self.assertIn("- Piloto: vi", fh.read())
            deny = self.ajustes(lab, 1)["deny"]
            repo = lab.rutas["api"]
            self.assertFalse(any(d.endswith("/CLAUDE.md)") for d in deny), deny)                              # levantada solo para esta tarea...
            for sigue in (".git/**", ".husky/**", ".claude/**", ".env*"):
                self.assertTrue(any(d.endswith(f"/{sigue})") and d.startswith("Edit(") for d in deny), (sigue, deny))   # ...y el resto sigue denegado
            self.assertTrue(any(d.endswith("/CLAUDE.local.md)") for d in deny))

    def test_las_rutas_que_no_se_pueden_autorizar_solo_admiten_omitir_o_detener(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            l, f, ver = lab.correr(pid, modo="deniega_husky")
            self.assertEqual((f.returncode, ver["gate"], ver["autorizable"]), (5, "ruta_protegida", False))
            g = lab.plan_json(pid)["gate"]
            self.assertEqual((g["reanuda"], g.get("rutas")), ("none", None))
            self.assertNotIn("autorizar", " ".join(g["opciones"]))
            r = ag(lab, "approve", g["gate"], plan=pid)
            self.assertEqual(r.returncode, 3, r.stdout)                                                        # no se puede aprobar
            self.assertEqual(ag(lab, "reject", g["gate"], plan=pid).returncode, 0)                            # pero si omitir la tarea
            self.assertEqual(lab.tarea(pid)["estado"], "omitida")

    def test_un_permiso_generico_ya_no_ofrece_autorizar(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            l, f, ver = lab.correr(pid, modo="denegaciones")
            g = lab.plan_json(pid)["gate"]
            self.assertEqual((f.returncode, g["motivo"]), (5, "permiso"))
            self.assertNotIn("rutas", g)
            self.assertNotIn("autorizar", " ".join(g["opciones"]))                                             # aprobar no cambia los permisos del worker
            self.assertIn("sus permisos no cambian", " ".join(g["opciones"]))


class TestTotals(unittest.TestCase):
    """`totals` es solo consulta: suma el gasto de todos los planes (en curso y archivados) y de todas las sesiones que anoto la statusline."""

    def test_suma_planes_archivados_y_sesiones_sin_contar_dos_veces(self):
        with L.Lab() as lab:
            p1 = lab.plan([{}], plan_extra={"contadores": {"gasto_usd": 0.25}})
            lab.plan([{}], plan_extra={"contadores": {"gasto_usd": 0.75}})
            arch = os.path.join(os.environ["ARKANA_AGENTIC_DIR"], "data", "archive")
            for pid, gasto in ((p1, 0.25), ("P2610010101-zzzz", 0.5)):                                   # uno ya esta en planes/ (no se cuenta dos veces) y otro solo archivado
                os.makedirs(os.path.join(arch, pid))
                state.save_json(os.path.join(arch, pid, "plan.json"), {"id": pid, "estado": "completado", "asunto": "archivado", "contadores": {"gasto_usd": gasto}})
            ses = os.path.join(os.environ["ARKANA_AGENTIC_DIR"], "state", "sesiones")
            os.makedirs(ses)
            for sid, coste in (("s1", "1.5"), ("s2", "2.0")):
                with open(os.path.join(ses, sid), "w") as f:
                    f.write(f"1793444251 {coste}\n")
            with open(os.path.join(ses, "rota"), "w") as f:
                f.write("basura")                                                                       # un fichero ilegible se ignora
            d = js(lab, "totals")
            self.assertEqual((d["planes"]["cantidad"], d["planes"]["total_usd"]), (3, 1.5))
            self.assertEqual((d["sesiones"]["cantidad"], d["sesiones"]["total_usd"]), (2, 3.5))
            h = ag(lab, "totals")
            self.assertEqual(h.returncode, 0, h.stdout + h.stderr)
            self.assertIn("Planes:   3 \u00b7 1,50 USD", h.stdout); self.assertIn("Sesiones: 2 \u00b7 3,50 USD", h.stdout)

    def test_sin_nada_que_sumar_da_cero_y_no_escribe(self):
        with L.Lab() as lab:
            d = js(lab, "totals")
            self.assertEqual((d["planes"]["total_usd"], d["sesiones"]["total_usd"]), (0, 0))


class TestFixSinPlanActual(unittest.TestCase):
    def test_fix_con_carpeta_de_planes_pero_sin_plan_actual_no_falla_y_limpia_el_worker_obsoleto(self):
        with L.Lab() as lab:
            base = lab.cambios["ARKANA_AGENTIC_DIR"]
            os.makedirs(os.path.join(base, "state", "planes"), exist_ok=True)
            wj = os.path.join(base, "state", "run", "worker.json")
            os.makedirs(os.path.dirname(wj), exist_ok=True)
            with open(wj, "w") as f:
                json.dump({"plan": "P0", "tarea": "T001", "pid": 999999}, f)
            r = ag(lab, "fix")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("no hay plan actual", r.stdout)
            self.assertFalse(os.path.exists(wj))


class TestDoctorPermisos(unittest.TestCase):
    """permisos-arkana no se conforma con que haya reglas de agentic.sh: exige el 'ask' de cada decision humana."""

    def doctor(self, lab, ask):
        os.makedirs(os.path.join(lab.rutas["shared"], ".claude"), exist_ok=True)
        cmd = "bash /x/plugins/arkana-agentic/scripts/agentic.sh"
        perm = {"allow": [f"Bash({cmd} *)"], "deny": ["Bash(claude -p *)"], "ask": [f"Bash({cmd} {h}*)" for h in ask]}
        with open(os.path.join(lab.rutas["shared"], ".claude", "settings.local.json"), "w") as f:
            json.dump({"permissions": perm}, f)
        d = json.loads(ag(lab, "check", "--json").stdout)
        return next(x for x in d if x["id"] == "permisos-arkana")

    def test_completas_obsoletas_y_ausentes(self):
        todas = ["plan approve", "approve", "reject", "policy set", "integrate merge", "integrate discard"]
        with L.Lab() as lab:
            self.assertEqual(self.doctor(lab, todas)["estado"], "OK")
            r = self.doctor(lab, ["plan approve", "approve", "reject", "policy set", "integrar merge", "integrar descartar"])   # reglas con los verbos antiguos
            self.assertEqual(r["estado"], "WARN"); self.assertIn("integrate merge", r["detalle"]); self.assertIn("SIN pedir confirmacion", r["detalle"])
            r = self.doctor(lab, [])
            self.assertEqual(r["estado"], "WARN"); self.assertIn("approve", r["detalle"])


class TestArchivoEIntegracion(unittest.TestCase):
    def completar(self, lab):
        pid = lab.plan([{}])
        lab.correr(pid)
        ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid)
        js(lab, "next", plan=pid)
        return pid

    def test_archivar_solo_planes_terminados(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            self.assertEqual(ag(lab, "archive", plan=pid).returncode, 3)
            pid = self.completar(lab)
            r = ag(lab, "archive", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            d = os.path.join(os.environ["ARKANA_AGENTIC_DIR"], "data", "archive", pid)
            self.assertTrue(os.path.exists(os.path.join(d, "plan.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "tareas", "T001.json")))
            self.assertFalse(os.path.exists(os.path.join(d, "snapshots"))); self.assertFalse(os.path.exists(os.path.join(d, "logs")))
            self.assertEqual(ag(lab, "archive", plan=pid).returncode, 3)

    def test_integrar_merge_local_sin_push(self):
        with L.Lab() as lab:
            pid = self.completar(lab)
            base = lab.head("api", "develop")
            r = ag(lab, "integrate", "merge", "--message", "chore(api) integrate NIF validation", plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(lab.rama("api"), "develop")
            self.assertNotEqual(lab.head("api", "develop"), base)
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "rev-list", "--parents", "-n1", "develop"]).stdout.split().__len__(), 3)   # merge commit
            self.assertNotEqual(L.sh(["git", "-C", lab.rutas["api"], "branch", "--list", f"arkana-worker/{pid}"]).stdout.strip(), "x")
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "branch", "--list", f"arkana-worker/{pid}"]).stdout.strip(), "")

    def test_integrar_dejar_y_descartar(self):
        with L.Lab() as lab:
            pid = self.completar(lab)
            base = lab.head("api", "develop")
            ag(lab, "integrate", "keep", plan=pid)
            self.assertEqual((lab.rama("api"), lab.head("api", "develop")), ("develop", base))
            self.assertNotEqual(L.sh(["git", "-C", lab.rutas["api"], "branch", "--list", f"arkana-worker/{pid}"]).stdout.strip(), "")
            ag(lab, "integrate", "discard", plan=pid)                               # sin --repo no cambia una decision ya tomada
            self.assertNotEqual(L.sh(["git", "-C", lab.rutas["api"], "branch", "--list", f"arkana-worker/{pid}"]).stdout.strip(), "")
            ag(lab, "integrate", "discard", "--repo", "api", plan=pid)
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "branch", "--list", f"arkana-worker/{pid}"]).stdout.strip(), "")
            self.assertEqual(lab.head("api", "develop"), base)

    def test_integrar_se_niega_con_cambios_sin_commitear(self):
        with L.Lab() as lab:
            pid = self.completar(lab)
            with open(os.path.join(lab.rutas["api"], "README.md"), "a") as f:
                f.write("sucio\n")
            self.assertEqual(ag(lab, "integrate", "merge", plan=pid).returncode, 3)



class TestLeccionesDelPiloto(unittest.TestCase):
    """Defectos que encontro el piloto real (fase 8): planes sin commits, instrucciones que piden ejecutar y verificaciones vacias."""

    def test_sin_commits_locales_varias_ediciones_en_un_repo_se_rechaza(self):
        with L.Lab() as lab:
            s = spec_basico(2)
            s["autoriza"] = {"commits_locales": False}
            r = ag(lab, "plan", "new", escribir(lab, "p.json", s))
            self.assertEqual(r.returncode, 1, r.stdout); self.assertIn("commits_locales es false", r.stdout); self.assertIn("2 tareas de edicion", r.stdout)

    def test_sin_commits_locales_una_edicion_avisa(self):
        with L.Lab() as lab:
            s = spec_basico(1)
            s["autoriza"] = {"commits_locales": False}
            r = ag(lab, "plan", "new", escribir(lab, "p.json", s))
            self.assertEqual(r.returncode, 0, r.stdout); self.assertIn("SIN commitear", r.stdout)
            s2 = spec_basico(1)                                                       # con commits (por defecto) no hay aviso
            self.assertNotIn("SIN commitear", ag(lab, "plan", "new", escribir(lab, "q.json", s2)).stdout)

    def test_avisa_si_se_pide_al_worker_ejecutar_comandos(self):
        with L.Lab() as lab:
            for texto, avisa in (("4. Ejecuta la verificacion v1 (git diff --stat) y comprueba el resultado.", True), ("Ejecuta npm test antes de terminar.", True),
                                 ("Corre los tests con npm.", True), ("Edita src/a.ts y lee el resultado.", False)):
                s = spec_basico(1)
                s["tareas"][0]["instrucciones"] = ["1. editar src/a.ts", texto]
                out = ag(lab, "plan", "new", escribir(lab, "p.json", s)).stdout
                self.assertEqual("no tiene shell" in out, avisa, (texto, out))

    def test_git_diff_stat_no_cuenta_como_verificacion_de_un_criterio(self):
        with L.Lab() as lab:
            s = spec_basico(1)
            s["tareas"][0]["verificaciones"] = [{"id": "v1", "comando": ["git", "diff", "--stat"], "timeout_s": 30}]
            out = ag(lab, "plan", "new", escribir(lab, "p.json", s)).stdout
            self.assertIn("no comprueba nada", out); self.assertIn("autoevaluado", out)
            pid = lab.plan([{"verificaciones": [{"id": "v1", "comando": ["git", "diff", "--stat"], "timeout_s": 30}]}])
            l, f, ver = lab.correr(pid)
            self.assertEqual(ver["veredicto"], "completada", f.stdout)
            self.assertEqual(ver["criterios"], [{"id": "C1", "cumplido": True, "origen": "autoevaluado"}])       # antes salia «verificado»
        with L.Lab() as lab:                                                           # y si el worker admite que no lo cumple, ya no hay un 'verificado' que lo tape
            pid = lab.plan([{"verificaciones": [{"id": "v1", "comando": ["git", "diff", "--stat"], "timeout_s": 30}]}])
            l, f, ver = lab.correr(pid, modo="hecha_sin_cumplir")
            self.assertEqual(ver["veredicto"], "rechazada")

    def test_continuar_sin_commit_deja_rastro_en_el_registro(self):
        with L.Lab() as lab:
            pid = lab.plan([{}], plan_extra={"autoriza": {"commits_locales": False}})
            lab.correr(pid)
            self.assertEqual(ag(lab, "act", "continue", "T001", plan=pid).returncode, 0)
            with open(os.path.join(state.plan_dir(pid), "registro.jsonl")) as f:
                regs = [json.loads(l) for l in f]
            dec = [r for r in regs if r["accion"] == "continue"]
            self.assertEqual(len(dec), 1); self.assertEqual((dec[0]["tarea"], dec[0]["quien"]), ("T001", "orchestrator"))
            self.assertIn("no autoriza commits", dec[0]["motivo"])

    def test_plan_sin_commits_no_deja_atascado_al_usuario(self):
        """Reproduce el piloto: la tarea edita, no hay commit, el repo queda sucio en la rama del plan."""
        with L.Lab() as lab:
            base = lab.head("api", "develop")
            pid = lab.plan([{}], plan_extra={"autoriza": {"commits_locales": False}})
            lab.correr(pid)
            ag(lab, "act", "continue", "T001", plan=pid)
            self.assertEqual(js(lab, "next", plan=pid)["detalle"], "completado")
            self.assertEqual(lab.rama("api"), f"arkana-worker/{pid}")
            self.assertNotEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"], env=lab.env).stdout.strip(), "")   # sucio
            r = ag(lab, "integrate", "merge", plan=pid)                                # integrar y dejar siguen negandose, con un mensaje util
            self.assertEqual(r.returncode, 3, r.stdout); self.assertIn("sin commitear en la rama", r.stdout); self.assertIn("integrate discard", r.stdout)
            self.assertEqual(ag(lab, "integrate", "keep", plan=pid).returncode, 3)
            self.assertEqual(lab.rama("api"), f"arkana-worker/{pid}")              # no se movio nada
            r = ag(lab, "integrate", "discard", plan=pid)                            # descartar si funciona: es el propio trabajo del plan
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(lab.rama("api"), "develop"); self.assertEqual(lab.head("api", "develop"), base)
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "status", "--porcelain"], env=lab.env).stdout.strip(), "")
            self.assertEqual(L.sh(["git", "-C", lab.rutas["api"], "branch", "--list", f"arkana-worker/{pid}"], env=lab.env).stdout.strip(), "")

    def test_descartar_no_toca_un_repo_sucio_que_no_esta_en_la_rama_del_pipeline(self):
        with L.Lab() as lab:
            pid = lab.plan([{}])
            lab.correr(pid)
            ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid)
            L.sh(["git", "-C", lab.rutas["api"], "switch", "-q", "develop"], env=lab.env)
            with open(os.path.join(lab.rutas["api"], "README.md"), "a") as f:
                f.write("trabajo del usuario sin commitear\n")
            r = ag(lab, "integrate", "discard", plan=pid)
            self.assertEqual(r.returncode, 3, r.stdout)                              # el trabajo del usuario en develop no se descarta
            self.assertIn("trabajo del usuario", Path(os.path.join(lab.rutas["api"], "README.md")).read_text())


if __name__ == "__main__":
    unittest.main()
