"""Entrega de mensajes a los workers: qué se entrega, lista congelada al arrancar, registro de la entrega y marca de ejecutado al aceptar."""
from pathlib import Path
import json
import os
import unittest

import lab as L
import state
from test_control import ag, escribir, spec_basico

R1, R2, ONCE, AVISO, OTRO, BAJA = ("N261103-0001-aaaa", "N261103-0002-bbbb", "N261103-0003-cccc", "N261103-0004-dddd", "N261103-0005-eeee", "N261103-0006-ffff")
MSG = "feat(api) validate NIF in a.ts"


def preparar(lab):
    lab.mensaje(R1, tipo="notice", estado=None, repeticion="repeat", vigencia="vigente", asunto="Usa siempre commits en inglés", de="arkana")
    lab.mensaje(R2, tipo="notice", estado=None, repeticion="repeat", vigencia="propuesto", asunto="Norma propuesta sin activar")
    lab.mensaje(ONCE, asunto="Adaptar el cliente al nuevo contrato")
    lab.mensaje(AVISO, tipo="notice", estado=None, asunto="Aviso informativo de una vez")
    lab.mensaje(OTRO, para=["app"], destinatarios=["app"], de="arkana", asunto="Tarea para otro componente")
    lab.mensaje(BAJA, tipo="notice", estado="deleted", repeticion="repeat", vigencia="vigente", asunto="Directriz dada de baja")


def prompt_de(pid, tid="T001", n=1):
    with open(os.path.join(state.plan_dir(pid), "logs", f"{tid}.{n}.prompt.md"), encoding="utf-8") as f:
        return f.read()


class TestEntrega(unittest.TestCase):
    def test_el_prompt_lleva_repeat_vigentes_y_once_accionables_y_la_entrega_queda_anotada(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan()
            l, f, ver = lab.correr(pid)
            self.assertEqual(l.returncode, 0, l.stdout + l.stderr)
            p = prompt_de(pid)
            self.assertIn("## Mensajes para este componente", p)
            self.assertIn("Usa siempre commits en inglés", p)                                   # repeat vigente
            self.assertIn("Adaptar el cliente al nuevo contrato", p)                            # once accionable
            for fuera in ("Norma propuesta sin activar", "Aviso informativo de una vez", "Tarea para otro componente", "Directriz dada de baja"):
                self.assertNotIn(fuera, p)
            self.assertLess(p.index("Usa siempre commits"), p.index("Adaptar el cliente"))      # primero las directrices
            llamadas = lab.llamadas_mensajeria()
            self.assertEqual(sorted(c[2] for c in llamadas if c[1] == "--delivered"), [R1, ONCE])
            self.assertEqual(llamadas[0][3:], ["--for", "api", "--plan", pid, "--task", "T001"])
            ev = [json.loads(x) for x in Path(os.path.join(state.plan_dir(pid), "registro.jsonl")).read_text(encoding="utf-8").splitlines()]
            self.assertEqual(sorted(next(e for e in ev if e["accion"] == "mensajes_entregados")["ids"]), [R1, ONCE])

    def test_la_lista_se_congela_al_arrancar_el_plan(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan()
            lab.mensaje("N261103-0007-gggg", asunto="Llegó después de aprobar el plan")
            lab.correr(pid)
            self.assertNotIn("Llegó después de aprobar", prompt_de(pid))
            self.assertEqual(sorted(state.load_json(os.path.join(state.plan_dir(pid), "mensajes.json"))["T001"]), [R1, ONCE])

    def test_una_baja_posterior_deja_de_entregarse(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan()
            lab.mensaje(R1, tipo="notice", estado="deleted", repeticion="repeat", vigencia="vigente", asunto="Usa siempre commits en inglés", de="arkana")
            lab.correr(pid)
            self.assertNotIn("Usa siempre commits", prompt_de(pid))

    def test_aceptar_la_tarea_marca_ejecutados_una_sola_vez(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan()
            lab.correr(pid)
            r = ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            ejec = [c for c in lab.llamadas_mensajeria() if c[1] == "--executed"]
            self.assertEqual(sorted(c[2] for c in ejec), [R1, ONCE])
            self.assertTrue(lab.tarea(pid)["mensajes_marcados"])
            ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid)                      # idempotente
            self.assertEqual(len([c for c in lab.llamadas_mensajeria() if c[1] == "--executed"]), 2)

    def test_sin_aceptar_no_se_marca_ejecutado(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan()
            lab.correr(pid)
            self.assertEqual([c for c in lab.llamadas_mensajeria() if c[1] == "--executed"], [])

    def test_si_la_mensajeria_falla_el_worker_se_lanza_igual(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan()
            l, f, ver = lab.correr(pid, env={"FAKE_MESSAGING_RC": "1"})
            self.assertEqual(l.returncode, 0, l.stdout + l.stderr)
            self.assertIn("WARN|mensajes", l.stderr)
            self.assertEqual(ver["veredicto"], "completada")

    def test_sin_almacen_de_mensajes_el_prompt_dice_ninguno(self):
        with L.Lab() as lab:
            pid = lab.plan()
            lab.correr(pid)
            self.assertIn("(ninguno)", prompt_de(pid).split("## Mensajes para este componente")[1].split("##")[0])
            self.assertEqual(lab.llamadas_mensajeria(), [])

    def test_plan_show_lista_lo_que_recibira_cada_worker(self):
        with L.Lab() as lab:
            preparar(lab)
            pid = lab.plan(aprobar=False, empezar=False)
            r = ag(lab, "plan", "show", plan=pid)
            self.assertIn("mensajes que recibirá el worker (2)", r.stdout)
            self.assertIn(R1, r.stdout); self.assertIn(ONCE, r.stdout)
            self.assertNotIn(R2, r.stdout)


AV = "N261103-0010-hhhh"          # aviso (notice): por sí solo no se entregaría a ningún worker
PARA_OTRO = "N261103-0011-iiii"   # tarea dirigida a otro componente (app)


def aviso(lab, **campos):
    return lab.mensaje(AV, tipo="notice", estado=None, asunto="Registrar ui en el app-config", cuerpo="Texto del aviso", instrucciones=["1. añade el remote"], **campos)


class TestDesdeMensaje(unittest.TestCase):
    """`--from-message <id>`: se le indica a una tarea un mensaje concreto (launch, act retry, act investigate y plan new)."""

    def lanzar_con(self, lab, pid, *ids):
        args = ["launch", "T001", "--plan", pid]
        for i in ids:
            args += ["--from-message", i]
        return lab.ejecutar("agentic.sh", *args, env={"FAKE_MODE": "hecha"})

    def eventos(self, pid):
        return [json.loads(x) for x in Path(os.path.join(state.plan_dir(pid), "registro.jsonl")).read_text(encoding="utf-8").splitlines()]

    def test_launch_entrega_el_mensaje_indicado_aunque_no_estuviera_en_la_lista_congelada(self):
        with L.Lab() as lab:
            aviso(lab)
            pid = lab.plan()
            self.assertEqual(state.load_json(os.path.join(state.plan_dir(pid), "mensajes.json"))["T001"], [])    # un aviso no se entrega solo
            r = self.lanzar_con(lab, pid, AV)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            p = prompt_de(pid)
            self.assertIn("Registrar ui en el app-config", p)
            self.assertIn(f"Atiende lo que pide el mensaje {AV}", p)                              # el feedback le dice que lo atienda
            self.assertEqual(lab.tarea(pid)["mensajes_extra"], [AV])
            self.assertEqual([c[2] for c in lab.llamadas_mensajeria() if c[1] == "--delivered"], [AV])
            ev = next(e for e in self.eventos(pid) if e["accion"] == "mensaje_indicado")
            self.assertEqual(ev["ids"], [AV])
            lab.finalizar(pid)
            ag(lab, "act", "continue", "T001", "--message", MSG, plan=pid)                        # aceptada: se marca ejecutado
            self.assertEqual([c[2] for c in lab.llamadas_mensajeria() if c[1] == "--executed"], [AV])

    def test_un_mensaje_que_no_va_al_componente_de_la_tarea_no_se_entrega_y_no_se_lanza_nada(self):
        with L.Lab() as lab:
            lab.mensaje(PARA_OTRO, para=["app"], destinatarios=["app"], de="arkana", asunto="Tarea para otro componente")
            pid = lab.plan()
            r = self.lanzar_con(lab, pid, PARA_OTRO)
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertIn("no va dirigido a api", r.stdout + r.stderr)
            self.assertNotIn("mensajes_extra", lab.tarea(pid))
            self.assertEqual(lab.tarea(pid)["intentos"], 0)                                       # ni se lanzó el worker
            r = self.lanzar_con(lab, pid, "N261103-9999-zzzz")                                   # inexistente
            self.assertEqual(r.returncode, 3); self.assertIn("no existe el mensaje", r.stdout + r.stderr)
            lab.mensaje("N261103-0012-jjjj", estado="deleted", asunto="Dado de baja")
            self.assertEqual(self.lanzar_con(lab, pid, "N261103-0012-jjjj").returncode, 3)       # dado de baja

    def test_retry_indica_el_mensaje_al_siguiente_intento(self):
        with L.Lab() as lab:
            aviso(lab)
            pid = lab.plan()
            lab.correr(pid, modo="hecha_sin_cumplir")
            r = ag(lab, "act", "retry", "T001", "--from-message", AV, plan=pid)
            self.assertEqual(r.returncode, 0, r.stdout)
            t = lab.tarea(pid)
            self.assertEqual((t["estado"], t["mensajes_extra"]), ("lista", [AV]))
            self.assertTrue(any(AV in x for x in t["feedback"]))
            lab.lanzar(pid, env={"FAKE_MODE": "hecha"})
            p = prompt_de(pid, n=2)
            self.assertIn("Registrar ui en el app-config", p)
            self.assertIn(f"Atiende lo que pide el mensaje {AV}", p)

    def test_retry_con_un_mensaje_que_no_vale_no_toca_la_tarea(self):
        with L.Lab() as lab:
            lab.mensaje(PARA_OTRO, para=["app"], destinatarios=["app"], de="arkana")
            pid = lab.plan()
            lab.correr(pid, modo="hecha_sin_cumplir")
            antes = lab.tarea(pid)
            sucio = Path(os.path.join(lab.rutas["api"], "src", "a.ts")).read_text()
            r = ag(lab, "act", "retry", "T001", "--from-message", PARA_OTRO, plan=pid)
            self.assertEqual(r.returncode, 3, r.stdout)
            despues = lab.tarea(pid)
            self.assertEqual((despues["estado"], despues.get("feedback")), (antes["estado"], antes.get("feedback")))
            self.assertNotIn("mensajes_extra", despues)
            self.assertEqual(Path(os.path.join(lab.rutas["api"], "src", "a.ts")).read_text(), sucio)   # y no se descartaron los cambios

    def test_otras_acciones_no_admiten_from_message(self):
        with L.Lab() as lab:
            aviso(lab)
            pid = lab.plan()
            r = ag(lab, "act", "skip", "T001", "--from-message", AV, plan=pid)
            self.assertEqual(r.returncode, 2, r.stdout); self.assertIn("solo se admite en 'act retry' y 'act investigate'", r.stdout)

    def test_investigate_toma_asunto_repo_e_instrucciones_del_mensaje(self):
        with L.Lab() as lab:
            lab.mensaje(PARA_OTRO, para=["app"], destinatarios=["app"], de="arkana", asunto="Cómo valida el NIF el front",
                        instrucciones=["1. lee src", "2. resume"], criterios=["Cita ficheros"])
            pid = lab.plan([{}])
            r = ag(lab, "act", "investigate", "--from-message", PARA_OTRO, "--for", "T001", plan=pid)
            self.assertEqual(r.returncode, 5, r.stdout)                                           # gate de plan modificado: el usuario lo aprueba
            n = lab.tarea(pid, "T002")
            self.assertEqual((n["tipo"], n["repo"], n["asunto"], n["instrucciones"]), ("investigacion", "app", "Investigar: Cómo valida el NIF el front", ["1. lee src", "2. resume"]))
            self.assertEqual(n["mensajes_extra"], [PARA_OTRO])
            r = ag(lab, "act", "investigate", "--from-message", PARA_OTRO, "--repo", "api", plan=pid)
            self.assertEqual(r.returncode, 3, r.stdout)                                           # --repo explícito: debe ser destinatario
            self.assertEqual(ag(lab, "act", "investigate", "--from-message", PARA_OTRO, "--from-message", AV, plan=pid).returncode, 2)

    def test_plan_new_con_fichero_entrega_el_mensaje_a_las_tareas_de_sus_destinatarios(self):
        with L.Lab() as lab:
            aviso(lab)
            lab.plan([], aprobar=False, empezar=False)
            spec = spec_basico(2)
            spec["tareas"][1]["repo"] = "app"
            r = ag(lab, "plan", "new", escribir(lab, "p.json", spec), "--from-message", AV)
            self.assertEqual(r.returncode, 0, r.stdout)
            pid = state.read_actual() if hasattr(state, "read_actual") else Path(state.actual_file()).read_text().strip()
            self.assertEqual(lab.tarea(pid, "T001")["mensajes_extra"], [AV])                      # api es destinatario
            self.assertNotIn("mensajes_extra", lab.tarea(pid, "T002"))                           # app no
            self.assertIn(AV, ag(lab, "plan", "show", plan=pid).stdout)                          # `plan show` lo enseña antes de aprobar
            r = ag(lab, "plan", "new", escribir(lab, "q.json", dict(spec_basico(1), tareas=[dict(spec_basico(1)["tareas"][0], repo="app")])), "--from-message", AV)
            self.assertEqual(r.returncode, 2, r.stdout); self.assertIn("no va dirigido al repo de ninguna tarea", r.stdout)

    def test_plan_new_sin_fichero_genera_el_plan_a_partir_del_mensaje(self):
        with L.Lab() as lab:
            aviso(lab, criterios=["Queda el remote"])
            lab.plan([], aprobar=False, empezar=False)
            r = ag(lab, "plan", "new", "--from-message", AV)
            self.assertEqual(r.returncode, 2, r.stdout); self.assertIn("--paths", r.stdout)       # sin rutas no hay plan editable
            r = ag(lab, "plan", "new", "--from-message", AV, "--paths", "src/**")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            pid = Path(state.actual_file()).read_text().strip()
            t = lab.tarea(pid)
            self.assertEqual((t["repo"], t["tipo"], t["instrucciones"], t["rutas_permitidas"], t["mensajes_extra"]), ("api", "tarea", ["1. añade el remote"], ["src/**"], [AV]))
            self.assertEqual(t["criterios_aceptacion"], [{"id": "C1", "descripcion": "Queda el remote"}])
            plan = lab.plan_json(pid)
            self.assertIn(AV, plan["peticion"])
            lab.mensaje("N261103-0013-kkkk", tipo="notice", estado=None, de="arkana", para=["all"], destinatarios=["api", "app", "app-web"], asunto="Para varios")
            r = ag(lab, "plan", "new", "--from-message", "N261103-0013-kkkk", "--paths", "src/**")
            self.assertEqual(r.returncode, 2, r.stdout); self.assertIn("indica --repo", r.stdout)  # va a varios componentes: hay que elegir
            r = ag(lab, "plan", "new", "--from-message", "N261103-0013-kkkk", "--repo", "app", "--paths", "src/**")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(lab.tarea(Path(state.actual_file()).read_text().strip())["repo"], "app")


if __name__ == "__main__":
    unittest.main()
