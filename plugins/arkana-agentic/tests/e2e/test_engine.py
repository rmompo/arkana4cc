import json
import os
import subprocess
import time
import unittest

import lab as L
import state


def log_fake(lab):
    with open(lab.cambios["FAKE_CLAUDE_LOG"], encoding="utf-8") as f:
        return [json.loads(x) for x in f.read().splitlines()]


def pids_de(fichero):
    with open(fichero, encoding="utf-8") as f:
        return [int(x) for x in f.read().split()]


class TestCaminoFeliz(unittest.TestCase):
    def test_flags_del_worker_y_rama_aislada(self):
        with L.Lab() as lab:
            base_develop = lab.head("api", "develop")
            pid = lab.plan()
            l, f, ver = lab.correr(pid)
            self.assertEqual((l.returncode, f.returncode), (0, 0), l.stdout + l.stderr + f.stdout)
            reg = log_fake(lab)[0]
            a = reg["argv"]
            self.assertEqual(reg["cwd"], os.path.realpath(lab.rutas["api"]))
            self.assertEqual(a[a.index("--tools") + 1], "Read,Edit,Write,Glob,Grep")
            self.assertNotIn("Bash", a[a.index("--tools") + 1])
            for flag in ("--restricted", "--no-session-persistence", "--json-schema", "--append-system-prompt-file"):
                self.assertIn(flag, a)
            self.assertEqual(a[a.index("--permission-mode") + 1], "dontAsk")
            self.assertEqual(a[a.index("--permission-prompts") + 1], "none")
            self.assertEqual(a[a.index("--max-turns") + 1], "40")
            i = a.index("--disallowedTools")
            self.assertEqual(a[i + 1:i + 4], ["Agent", "WebSearch", "Skill"])
            ajustes = json.loads(a[a.index("--settings") + 1])["permissions"]
            repo = lab.rutas["api"]
            self.assertIn(f"Edit(/{repo}/**)", ajustes["allow"])
            self.assertTrue(any("/.git-credentials" in d for d in ajustes["deny"]))
            self.assertTrue(any(d.endswith("/.husky/**)") for d in ajustes["deny"]))
            # el worker trabaja en la rama del plan arkana-worker/<plan> (la crea el script, no el worker) y develop no se toca
            self.assertEqual(lab.rama("api"), f"arkana-worker/{pid}")
            self.assertEqual(lab.head("api", "develop"), base_develop)
            self.assertEqual(lab.plan_json(pid)["ramas"]["api"], {"original": "develop", "nombre": f"arkana-worker/{pid}"})
            self.assertNotIn("rama", lab.tarea(pid))
            # el prompt lleva las normas del repo sin la semilla de novedades
            with open(os.path.join(state.plan_dir(pid), "logs", "T001.1.prompt.md"), encoding="utf-8") as fh:
                prompt = fh.read()
            self.assertIn("Norma del repo api", prompt); self.assertNotIn("arkana:messaging", prompt)
            self.assertIn("se verifica automaticamente: v1", prompt)

    def test_completada_con_verificacion_y_contadores(self):
        with L.Lab() as lab:
            pid = lab.plan()
            l, f, ver = lab.correr(pid)
            self.assertEqual(ver["veredicto"], "completada"); self.assertEqual(ver["acciones_permitidas"], ["continue"])
            self.assertEqual(ver["criterios"], [{"id": "C1", "cumplido": True, "origen": "verificado"}])
            self.assertEqual(ver["rutas_cambiadas"], ["src/a.ts"])
            self.assertEqual(lab.tarea(pid)["estado"], "completada")
            self.assertAlmostEqual(lab.plan_json(pid)["contadores"]["gasto_usd"], 0.05, places=3)
            linea = state.load_json(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "linea.json"))
            self.assertEqual(linea["tareas"], {"actual": 1, "hechas": 1, "omitidas": 0, "total": 1})
            self.assertFalse(os.path.exists(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "worker.json")))
            self.assertIn("completada", f.stdout)

    def test_dos_intentos_numerados_y_finish_no_es_repetible(self):
        with L.Lab() as lab:
            pid = lab.plan()
            lab.correr(pid)
            self.assertEqual(lab.finalizar(pid).returncode, 3)    # ya no esta en_curso

    def test_criterio_sin_verificacion_es_autoevaluado(self):
        with L.Lab() as lab:
            pid = lab.plan([{"criterios_aceptacion": [{"id": "C1", "descripcion": "x"}], "verificaciones": []}])
            _, _, ver = lab.correr(pid)
            self.assertEqual(ver["veredicto"], "completada")
            self.assertEqual(ver["criterios"][0]["origen"], "autoevaluado")

    def test_perfil_lectura_solo_lee_y_no_puede_modificar(self):
        with L.Lab() as lab:
            pid = lab.plan([{"perfil": "lectura", "tipo": "investigacion", "rutas_permitidas": [], "verificaciones": [],
                             "criterios_aceptacion": [{"id": "C1", "descripcion": "x"}]}])
            _, _, ver = lab.correr(pid)           # el falso edita: un worker de lectura no debe modificar nada
            a = log_fake(lab)[0]["argv"]
            self.assertEqual(a[a.index("--tools") + 1], "Read,Glob,Grep")
            self.assertEqual((ver["veredicto"], ver["motivo"]), ("rechazada", "perfil_lectura"))


class TestResultadosDelWorker(unittest.TestCase):
    def caso(self, modo, **kw):
        with L.Lab() as lab:
            pid = lab.plan(**kw.pop("plan_kw", {}))
            l, f, ver = lab.correr(pid, modo=modo, env=kw.get("env"))
            return lab, pid, l, f, ver, lab.tarea(pid)["estado"], lab.plan_json(pid)

    def test_parcial_y_fallida(self):
        _, _, _, _, ver, est, _ = self.caso("parcial")
        self.assertEqual((ver["veredicto"], est), ("parcial", "parcial")); self.assertIn("retry", ver["acciones_permitidas"])
        _, _, _, _, ver, est, _ = self.caso("fallida")
        self.assertEqual((ver["veredicto"], est), ("fallida", "fallida"))

    def test_presupuesto_y_turnos(self):
        _, _, _, _, ver, est, _ = self.caso("presupuesto")
        self.assertEqual((ver["veredicto"], ver["motivo"], est), ("fallida", "coste", "fallida"))
        _, _, _, _, ver, est, _ = self.caso("turnos")
        self.assertEqual((ver["veredicto"], ver["motivo"], est), ("parcial", "turnos", "parcial"))

    def test_informe_invalido_y_sin_json(self):
        _, _, _, _, ver, est, _ = self.caso("invalido")
        self.assertEqual((ver["veredicto"], ver["motivo"]), ("fallida", "informe_invalido"))
        _, _, _, _, ver, est, _ = self.caso("sin_json")
        self.assertEqual((ver["veredicto"], ver["motivo"], est), ("fallida", "informe_invalido", "fallida"))

    def test_bloqueada_abre_gate_y_espera_al_usuario(self):
        lab, pid, l, f, ver, est, plan = self.caso("bloqueada")
        self.assertEqual(f.returncode, 5)
        self.assertEqual((ver["veredicto"], ver["gate"], est), ("bloqueada", "dato", "esperando_usuario"))
        self.assertEqual((plan["estado"], plan["gate"]["motivo"]), ("esperando_usuario", "dato"))
        self.assertEqual(ver["acciones_permitidas"], ["escalate", "skip", "stop"])

    def test_denegaciones_mandan_aunque_diga_hecha(self):
        _, _, _, f, ver, est, plan = self.caso("denegaciones")
        self.assertEqual((f.returncode, ver["veredicto"], ver["gate"], est), (5, "bloqueada", "permiso", "esperando_usuario"))
        self.assertEqual(plan["gate"]["motivo"], "permiso")

    def test_criterio_verificacion_falla(self):
        _, _, _, _, ver, est, _ = self.caso("hecha", plan_kw={"tareas": [{"verificaciones": [{"id": "v1", "comando": ["false"], "timeout_s": 30}]}]})
        self.assertEqual((ver["veredicto"], est, ver["verificaciones"]["v1"]["rc"]), ("rechazada", "rechazada", 1))

    def test_el_worker_reconoce_que_no_cumple(self):
        _, _, _, _, ver, est, _ = self.caso("hecha_sin_cumplir")
        self.assertEqual((ver["veredicto"], ver["criterios"][0]["cumplido"]), ("rechazada", False))

    def test_fuera_de_alcance(self):
        _, _, _, _, ver, est, _ = self.caso("fuera_alcance")
        self.assertEqual((ver["veredicto"], ver["motivo"], ver["fuera_de_alcance"]), ("rechazada", "alcance", ["docs/fuera.md"]))


class TestContencion(unittest.TestCase):
    def test_ruta_protegida_abre_gate_y_no_ejecuta_verificaciones(self):
        with L.Lab() as lab:
            pid = lab.plan([{"verificaciones": [{"id": "v1", "comando": ["touch", lab.marker], "timeout_s": 30}]}])
            l, f, ver = lab.correr(pid, modo="toca_protegido")
            self.assertEqual((f.returncode, ver["veredicto"], ver["gate"]), (5, "bloqueada", "ruta_protegida"))
            self.assertIn(".husky/pre-commit", ver["rutas_protegidas"])
            self.assertFalse(os.path.exists(lab.marker), "no debe ejecutarse ninguna verificacion")
            self.assertEqual((lab.tarea(pid)["estado"], lab.plan_json(pid)["estado"]), ("esperando_usuario", "esperando_usuario"))

    def test_un_fichero_ignorado_por_git_tambien_se_detecta(self):
        with L.Lab() as lab:
            pid = lab.plan()
            git = lab.rutas["api"]
            self.assertEqual(subprocess.run(["git", "-C", git, "check-ignore", ".env"], capture_output=True).returncode, 0)
            _, f, ver = lab.correr(pid, modo="toca_env")
            self.assertEqual((f.returncode, ver["gate"]), (5, "ruta_protegida"))
            self.assertIn(".env", ver["rutas_protegidas"])      # git status no lo mostraria: lo ve el inventario

    def test_package_json_scripts_es_ruta_protegida(self):
        with L.Lab() as lab:
            pid = lab.plan([{"rutas_permitidas": []}])
            _, f, ver = lab.correr(pid, modo="toca_package")
            self.assertEqual((f.returncode, ver["gate"]), (5, "ruta_protegida"))
            self.assertTrue(any("package.json (scripts)" in r for r in ver["rutas_protegidas"]))

    def test_comando_fuera_de_la_lista_cerrada(self):
        with L.Lab() as lab:
            pid = lab.plan([{"verificaciones": [{"id": "v1", "comando": ["ls"], "timeout_s": 30}]}])
            _, f, ver = lab.correr(pid)
            self.assertEqual((f.returncode, ver["gate"], ver["comandos_no_permitidos"]), (5, "herramienta", ["v1"]))

    def test_tocar_otro_repo_es_violacion(self):
        with L.Lab() as lab:
            pid = lab.plan()
            otro = os.path.join(lab.rutas["shared"], "README.md")
            _, f, ver = lab.correr(pid, modo="toca_otro_repo", env={"FAKE_OTHER_FILE": otro})
            self.assertEqual((f.returncode, ver["veredicto"], ver["acciones_permitidas"]), (4, "violacion", ["stop"]))
            self.assertEqual(ver["violaciones"][0]["repo"], "arkana")             # el repo de ARKANA se llama como en el manifiesto
            self.assertEqual(lab.plan_json(pid)["gate"]["motivo"], "violacion")

    def test_cambiar_de_rama_es_violacion(self):
        with L.Lab() as lab:
            pid = lab.plan()
            _, f, ver = lab.correr(pid, modo="cambia_rama")
            self.assertEqual(f.returncode, 4)
            self.assertEqual(ver["violaciones"][0]["tipo"], "rama_cambiada")

    def test_tocar_un_fichero_vigilado_es_violacion(self):
        with L.Lab() as lab:
            pid = lab.plan()
            cred = os.path.join(lab.home, ".git-credentials")
            _, f, ver = lab.correr(pid, modo="toca_otro_repo", env={"FAKE_OTHER_FILE": cred})
            self.assertEqual(f.returncode, 4)
            self.assertEqual(ver["violaciones"][0]["tipo"], "fichero_vigilado")

    def test_el_snapshot_no_guarda_el_contenido_de_los_secretos(self):
        with L.Lab() as lab:
            pid = lab.plan()
            lab.correr(pid)
            with open(os.path.join(state.plan_dir(pid), "snapshots", "T001.1.antes.json"), encoding="utf-8") as f:
                self.assertNotIn("SECRETO", f.read())


class TestPrecondiciones(unittest.TestCase):
    def test_plan_no_en_ejecucion(self):
        with L.Lab() as lab:
            r = lab.lanzar(lab.plan(empezar=False))
            self.assertEqual(r.returncode, 3); self.assertIn("en_ejecucion", r.stdout)

    def test_plan_sin_aprobar(self):
        with L.Lab() as lab:
            pid = lab.plan(aprobar=False, empezar=False)
            state.transition_plan(pid, "aprobado"); state.start_plan(pid)
            r = lab.lanzar(pid)
            self.assertEqual(r.returncode, 3); self.assertIn("aprobado", r.stdout)

    def test_plan_alterado_tras_aprobar(self):
        with L.Lab() as lab:
            pid = lab.plan()
            state.update_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"), lambda o: o.update(instrucciones=["borra todo"]))
            r = lab.lanzar(pid)
            self.assertEqual(r.returncode, 3); self.assertIn("no coincide", r.stdout)
            self.assertFalse(os.path.exists(lab.cambios["FAKE_CLAUDE_LOG"]), "no debe llegar a lanzarse el worker")

    def test_repo_con_cambios_sin_commitear(self):
        with L.Lab() as lab:
            pid = lab.plan()
            with open(os.path.join(lab.rutas["api"], "suelto.txt"), "w", encoding="utf-8") as f:
                f.write("x")
            r = lab.lanzar(pid)
            self.assertEqual(r.returncode, 3); self.assertIn("sin commitear", r.stdout)

    def test_tarea_con_dependencia_sin_completar(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"depende_de": ["T001"]}])
            r = lab.lanzar(pid, "T002")
            self.assertEqual(r.returncode, 3); self.assertIn("dependencias", r.stdout)

    def test_limites_de_intentos_y_de_presupuesto(self):
        with L.Lab() as lab:
            pid = lab.plan()
            state.update_json(os.path.join(state.plan_dir(pid), "tareas", "T001.json"), lambda o: o.update(intentos=2))
            r = lab.lanzar(pid)
            self.assertEqual(r.returncode, 6); self.assertIn("intentos", r.stdout)
        with L.Lab() as lab:
            pid = lab.plan()
            state.add_counter(pid, "gasto_usd", 5.0)
            r = lab.lanzar(pid)
            self.assertEqual(r.returncode, 6); self.assertIn("presupuesto", r.stdout)

    def test_parada_y_pausa_impiden_lanzar(self):
        for marca in ("STOP", "PAUSE", "STOP-FORCE"):
            with L.Lab() as lab:
                pid = lab.plan()
                run = os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run")
                os.makedirs(run, exist_ok=True)
                open(os.path.join(run, marca), "w").close()
                self.assertEqual(lab.lanzar(pid).returncode, 7, marca)


class TestProcesos(unittest.TestCase):
    def esperar_worker(self, lab, pidfile):
        wj = os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "worker.json")
        self.assertTrue(lab.esperar(lambda: os.path.exists(wj) and os.path.exists(pidfile), 20), "el worker no arranco")
        return wj

    def muertos(self, lab, pidfile):
        pids = pids_de(pidfile)
        self.assertTrue(lab.esperar(lambda: not any(lab.vivo(p) for p in pids), 10), f"siguen vivos: {[p for p in pids if lab.vivo(p)]}")

    def test_solo_un_worker_vivo_a_la_vez(self):
        with L.Lab() as lab:
            pid = lab.plan([{}, {"repo": "shared"}])
            pf = os.path.join(lab.root, "pids")
            p = lab.popen_lanzar(pid, "T001", env={"FAKE_MODE": "dormido", "FAKE_SLEEP": "30", "FAKE_PID_FILE": pf})
            try:
                self.esperar_worker(lab, pf)
                r = lab.lanzar(pid, "T002")
                self.assertEqual(r.returncode, 3); self.assertIn("ya hay un worker vivo", r.stdout)
                self.assertEqual(lab.tarea(pid, "T002")["estado"], "pendiente")
            finally:
                open(os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run", "STOP-FORCE"), "w").close()
                p.communicate(timeout=30)

    def test_stop_force_mata_todo_el_grupo_y_cancela(self):
        with L.Lab() as lab:
            pid = lab.plan()
            pf = os.path.join(lab.root, "pids")
            p = lab.popen_lanzar(pid, env={"FAKE_MODE": "dormido", "FAKE_SLEEP": "30", "FAKE_PID_FILE": pf})
            self.esperar_worker(lab, pf)
            run = os.path.join(lab.cambios["ARKANA_AGENTIC_DIR"], "state", "run")
            self.assertIsNotNone(state.load_json(os.path.join(run, "linea.json"))["worker_pid"])
            open(os.path.join(run, "STOP-FORCE"), "w").close()
            out, err = p.communicate(timeout=30)
            self.assertEqual(p.returncode, 7, out + err)
            self.assertEqual(lab.tarea(pid)["estado"], "cancelada")
            self.muertos(lab, pf)
            for f in ("worker.json", "STOP-FORCE", "killed.json"):
                self.assertFalse(os.path.exists(os.path.join(run, f)), f)

    def test_dead_man_switch_si_muere_el_dueno(self):
        with L.Lab() as lab:
            pid = lab.plan()
            pf = os.path.join(lab.root, "pids")
            dueno = subprocess.Popen(["sleep", "120"])
            try:
                p = lab.popen_lanzar(pid, env={"FAKE_MODE": "dormido", "FAKE_SLEEP": "30", "FAKE_PID_FILE": pf,
                                               "ARKANA_AGENTIC_OWNER_PID": str(dueno.pid)})
                self.esperar_worker(lab, pf)
                dueno.kill(); dueno.wait()
                out, err = p.communicate(timeout=30)
                self.assertEqual(p.returncode, 0, out + err); self.assertIn("dueno_muerto", out)
                self.assertEqual(lab.tarea(pid)["estado"], "interrumpida")
                self.muertos(lab, pf)
            finally:
                dueno.kill() if dueno.poll() is None else None

    def test_tiempo_maximo_de_la_tarea(self):
        with L.Lab() as lab:
            pid = lab.plan([{"limites": {"timeout_s": 2}}])
            l, f, ver = lab.correr(pid, modo="dormido", env={"FAKE_SLEEP": "30"})
            self.assertEqual(l.returncode, 0, l.stdout + l.stderr)
            self.assertEqual((ver["veredicto"], ver["motivo"]), ("fallida", "tiempo"))
            raw = state.load_json(os.path.join(state.plan_dir(pid), "informes", "T001.1.raw.json"))
            self.assertEqual(raw["exit_code"], 124)

    def test_un_hijo_no_queda_vivo_tras_terminar_normalmente(self):
        with L.Lab() as lab:
            pid = lab.plan()
            l, f, ver = lab.correr(pid)
            self.assertEqual(ver["veredicto"], "completada")
            # ningun proceso de ESTE laboratorio (su ruta aparece en los argumentos del worker) sigue vivo
            self.assertTrue(lab.esperar(lambda: subprocess.run(["pgrep", "-f", lab.root], capture_output=True).returncode == 1, 5),
                            "quedan procesos del laboratorio")


if __name__ == "__main__":
    unittest.main()
