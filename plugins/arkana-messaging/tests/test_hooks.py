"""Hooks de mensajería (SessionStart, UserPromptSubmit, Stop): solo lectura local, leído/no leído, un solo bloqueo y latido."""
import json
import os
import stat
import subprocess
import sys
import unittest

import lab as L
from lab import Lab

HOOKS = os.path.join(L.PLUGIN, "scripts", "hooks.py")


def hook(lab, who, name, ev=None, env=None):
    payload = dict({"session_id": "s1", "cwd": lab.cwd(who)}, **(ev or {}))
    r = subprocess.run([sys.executable, "-I", HOOKS, name], input=json.dumps(payload), capture_output=True, text=True,
                       env=dict(lab.env, **(env or {})), cwd=lab.cwd(who), timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else None


def ctxt(out):
    return out.get("hookSpecificOutput", {}).get("additionalContext", "") if out else ""


class TestHooks(unittest.TestCase):
    def test_session_start_inyecta_lo_nuevo_lo_marca_leido_y_recuerda_lo_abierto(self):
        with Lab() as lab:
            ins, cri = lab.file("i.txt", "Cambia el cliente\n"), lab.file("c.txt", "Compila\n")
            t = lab.put("arkana", "task", "Adaptar el cliente al nuevo contrato", "api", ("--instructions-file", ins, "--criteria-file", cri))
            n = lab.put("app", "notice", "Aviso informativo para el backend", "api")
            out = hook(lab, "api", "session-start", {"source": "startup"})
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
            txt = ctxt(out)
            for x in (t, n, "Cambia el cliente", "Compila", "Propón al usuario"):
                self.assertIn(x, txt)
            self.assertIn(t, lab.jload(lab.store("read/api.json"))["ids"])
            # segunda sesión (p. ej. /compact): ya leído → solo el recordatorio de lo abierto (la tarea), sin el aviso
            txt2 = ctxt(hook(lab, "api", "session-start", {"source": "compact"}))
            self.assertIn("Siguen abiertos", txt2)
            self.assertIn(t, txt2)
            self.assertNotIn(n, txt2)
            self.assertNotIn("Cambia el cliente", txt2)                                         # ni el texto completo
            self.assertIsNone(hook(lab, "app-web", "session-start"))                            # a app-web no le toca nada

    def test_systemmessage_informa_de_pendientes_leidos_en_el_turno_y_tareas_hechas(self):
        with Lab() as lab:
            ins, cri = lab.file("i.txt", "x\n"), lab.file("c.txt", "y\n")
            t = lab.put("arkana", "task", "Adaptar el cliente al nuevo contrato", "api", ("--instructions-file", ins, "--criteria-file", cri))
            lab.put("app", "notice", "Aviso informativo para el backend", "api")
            m1 = hook(lab, "api", "session-start", {"source": "clear"})["systemMessage"]
            self.assertTrue(m1.startswith("[ARKANA messaging] api:"))
            for x in ("2 sin leer", "2 leídos en el último turno", "tareas para ti: 1 abiertas · 0 hechas"):
                self.assertIn(x, m1)
            m2 = hook(lab, "api", "session-start", {"source": "compact"})["systemMessage"]
            for x in ("0 sin leer", "0 leídos en el último turno", "1 abiertas"):
                self.assertIn(x, m2)
            self.assertIsNone(hook(lab, "api", "prompt-submit"))                            # nada nuevo: no repite la línea
            lab.put("api", "task", "Revisar el contrato", "app", ("--instructions-file", ins, "--criteria-file", cri))
            lab.run("api", "put", "--done", t, "--result", "hecho")
            m3 = hook(lab, "api", "prompt-submit")["systemMessage"]                         # cambió el estado: informa
            for x in ("0 abiertas · 1 hechas", "tareas pedidas por ti: 0 hechas de 1"):
                self.assertIn(x, m3)
            self.assertIsNone(hook(lab, "app-web", "session-start"))                            # sin mensajes, sin línea
            self.assertNotIn("systemMessage", hook(lab, "api", "session-start", {"source": "resume"}) or {})   # en startup/resume lo cuenta el BRIEF de workspace

    def test_directrices_vigentes_se_recuerdan_y_las_propuestas_no(self):
        with Lab() as lab:
            vig = lab.put("arkana", "notice", "Usa siempre commits en inglés", "api", ("--repeat",))
            pro = lab.put("app", "notice", "Norma propuesta que aún no rige", "api", ("--repeat",))
            txt = ctxt(hook(lab, "api", "session-start", {"source": "clear"}))
            self.assertIn(vig, txt)
            self.assertNotIn(pro, txt)                                                          # propuesta: no se inyecta ni se recuerda
            txt2 = ctxt(hook(lab, "api", "session-start", {"source": "compact"}))
            self.assertIn("Directrices vigentes", txt2)                                         # ya leída: se recuerda cada sesión
            self.assertIn(vig, txt2)
            lab.run("arkana", "put", "--activate", pro)
            self.assertIn(pro, ctxt(hook(lab, "api", "prompt-submit")))                     # al activarla pasa a ser nueva
            self.assertIn("directrices vigentes para ti: 2", hook(lab, "api", "session-start", {"source": "clear"})["systemMessage"])

    def test_prompt_submit_solo_inyecta_lo_nuevo(self):
        with Lab() as lab:
            self.assertIsNone(hook(lab, "app", "prompt-submit", {"prompt": "hola"}))
            n = lab.put("api", "notice", "Primer aviso para app", "app")
            out = hook(lab, "app", "prompt-submit")
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            self.assertIn(n, ctxt(out))
            self.assertIsNone(hook(lab, "app", "prompt-submit"))                               # ya leído
            n2 = lab.put("api", "notice", "Segundo aviso para app", "app")
            txt = ctxt(hook(lab, "app", "prompt-submit"))
            self.assertIn(n2, txt)
            self.assertNotIn(n, txt)
            self.assertIsNone(hook(lab, "api", "prompt-submit"))                            # lo que escribe uno no se le inyecta a él

    def test_mensaje_largo_se_da_como_asunto_e_id_y_get_lo_marca_leido(self):
        with Lab() as lab:
            largo = lab.file("b.txt", "x" * 3000)
            n = lab.put("api", "notice", "Un aviso larguísimo", "app", ("--body-file", largo))
            txt = ctxt(hook(lab, "app", "prompt-submit"))
            self.assertIn(f"get --detail {n}", txt)
            self.assertNotIn("x" * 100, txt)
            self.assertIn(n, ctxt(hook(lab, "app", "prompt-submit")))                          # sigue sin leer: se repite
            self.assertEqual(lab.run("app", "get", "--detail", n).returncode, 0)
            o = hook(lab, "app", "prompt-submit")                                              # recuperado con get: leído, sin inyectar nada
            self.assertEqual(ctxt(o), "")
            self.assertIn("1 leídos en el último turno", o["systemMessage"])

    def test_stop_bloquea_una_vez_solo_ante_alta_prioridad_tarea_o_pregunta(self):
        with Lab() as lab:
            lab.put("api", "notice", "Aviso normal para app", "app")
            self.assertIsNone(hook(lab, "app", "stop"))                                        # un aviso normal no bloquea
            ins, cri = lab.file("i.txt", "a\n"), lab.file("c.txt", "b\n")
            t = lab.put("arkana", "task", "Tarea urgente para app", "app", ("--instructions-file", ins, "--criteria-file", cri, "--priority", "high"))
            self.assertIsNone(hook(lab, "app", "stop", {"stop_hook_active": True}))           # nunca si ya se bloqueó en este turno
            out = hook(lab, "app", "stop")
            self.assertEqual(out["decision"], "block")
            self.assertIn(t, out["reason"])
            self.assertIn("/arkana-messaging:get --pending", out["reason"])
            self.assertIsNone(hook(lab, "app", "stop"))                                        # una sola vez por mensaje y sesión
            q = lab.put("arkana", "question", "¿Qué endpoint usa el cliente hoy?", "app")
            self.assertEqual(hook(lab, "app", "stop")["decision"], "block")                    # mensaje nuevo: puede bloquear otra vez
            self.assertIn(q, lab.jload(lab.store("sessions/s1.json"))["reminded"])

    def test_latido_por_ejecucion(self):
        with Lab() as lab:
            hook(lab, "app", "prompt-submit", {"session_id": "abc-123"})
            hb = lab.jload(lab.store("sessions/abc-123.json"))
            self.assertEqual((hb["actor"], hb["event"]), ("app", "prompt-submit"))
            self.assertTrue(hb["ts"].endswith("Z"))

    def test_silencio_en_worker_fuera_de_componente_y_con_entrada_basura(self):
        with Lab() as lab:
            lab.put("api", "notice", "Aviso para app que no debe verse", "app")
            self.assertIsNone(hook(lab, "app", "session-start", env={"ARKANA_WORKER": "1"}))
            self.assertIsNone(hook(lab, "fuera", "session-start"))
            r = subprocess.run([sys.executable, "-I", HOOKS, "prompt-submit"], input="{no json", capture_output=True, text=True, env=lab.env, cwd=lab.cwd("app"))
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            self.assertFalse(os.path.exists(lab.store("sessions/s1.json")))                    # el worker no deja ni latido

    def test_nunca_usa_git(self):
        with Lab() as lab:
            bindir = os.path.join(lab.root, "bin"); os.makedirs(bindir)
            marca = os.path.join(lab.root, "git-usado")
            with open(os.path.join(bindir, "git"), "w") as f:
                f.write(f"#!/bin/sh\ntouch {marca}\nsleep 30\n")
            os.chmod(os.path.join(bindir, "git"), 0o755)
            lab.put("api", "notice", "Aviso para app sin git", "app")
            env = {"PATH": bindir + os.pathsep + os.environ["PATH"]}
            for ev in ("session-start", "prompt-submit", "stop"):
                hook(lab, "app", ev, env=env)
            self.assertFalse(os.path.exists(marca))


if __name__ == "__main__":
    unittest.main()
