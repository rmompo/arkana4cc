"""Hook de sesión: BRIEF al usuario (systemMessage) y directrices de la pieza al modelo (additionalContext); solo local; nada en workers ni fuera de un workspace."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

HOOK = os.path.join(E.SCRIPTS, "hooks.py")


def run(lab, cwd, env=None):
    return subprocess.run([sys.executable, "-I", HOOK, "session-status"], input=json.dumps({"cwd": cwd, "source": "startup"}), capture_output=True, text=True,
                          env=dict(lab.env, **(env or {})), cwd=cwd, timeout=30)


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


class TestHookEstado(unittest.TestCase):
    def test_resumen_con_cambios_plan_y_mensajes_sin_inyectar_en_el_contexto(self):
        with TC.CLab() as lab:
            app = os.path.join(lab.ws, "app")
            subprocess.run(["git", "init", "-q", app], check=True)
            with open(os.path.join(app, "nuevo.txt"), "w") as f:
                f.write("x")
            st = os.path.join(lab.arkana, ".arkana")
            os.makedirs(os.path.join(st, "arkana-agentic", "state", "planes", "P1"), exist_ok=True)
            with open(os.path.join(st, "arkana-agentic", "state", "actual"), "w") as f:
                f.write("P1")
            wj(os.path.join(st, "arkana-agentic", "state", "planes", "P1", "plan.json"), {"id": "P1", "estado": "en_ejecucion", "contadores": {"gasto_usd": 0.4}})
            wj(os.path.join(st, "arkana-messaging", "state", "index.json"), {"messages": {
                "N261103-0001-aaaa": {"de": "arkana", "para": ["app"], "tipo": "notice", "estado": None},
                "N261103-0002-bbbb": {"de": "arkana", "para": ["app"], "tipo": "task", "estado": "open"},
                "N261103-0003-cccc": {"de": "arkana", "para": ["app"], "tipo": "notice", "estado": "deleted"},
                "N261103-0004-dddd": {"de": "arkana", "para": ["app"], "tipo": "notice", "estado": None, "repeticion": "repeat", "vigencia": "vigente"},
                "N261103-0005-eeee": {"de": "api", "para": ["app"], "tipo": "notice", "estado": None, "repeticion": "repeat", "vigencia": "propuesto"},
                "N261103-0006-ffff": {"de": "arkana", "para": ["app"], "tipo": "task", "estado": "open", "confirmaciones": {"app": "done"}}}})
            wj(os.path.join(st, "arkana-messaging", "state", "read", "app.json"), {"ids": {"N261103-0001-aaaa": "x"}})
            r = run(lab, app)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(sorted(out), ["hookSpecificOutput", "systemMessage"])      # BRIEF al usuario y directrices al modelo, por canales distintos
            self.assertNotIn("BRIEF", out["hookSpecificOutput"]["additionalContext"])
            m = out["systemMessage"]
            self.assertTrue(m.startswith("****** [ARKANA] BRIEF ******"), m)
            self.assertIn("### GIT (pending):\n", m)
            self.assertRegex(m, r"\d\. app \(\S+\)")
            self.assertIn("### MESSAGING:\n1. app (1 tasks, 1 repeat)", m)
            self.assertIn("plan P1 (en_ejecucion, 0.40 USD)", m)
            self.assertIn("### QUICK START", m)
            usos = [l for l in m.split("### QUICK START\n")[1].splitlines()]
            orden = ["/arkana-workspace:config", "/arkana-workspace:check", "/arkana-workspace:fix", "/arkana-messaging:query --unread",
                     "/arkana-workspace:sync", "/arkana-workspace:status", "/arkana-agentic:status"]
            pos = [next(i for i, l in enumerate(usos) if f"'{c}'" in l) for c in orden]
            self.assertEqual(pos, sorted(pos), usos)                            # config → check → fix, y luego lo del día
            self.assertTrue(m.endswith("\n"), repr(m[-40:]))                    # línea en blanco final
            self.assertNotIn(lab.root, m)

    def test_silencio_sin_nada_que_decir_en_worker_y_fuera_de_workspace(self):
        with TC.CLab() as lab:
            self.assertNotIn("MESSAGING", run(lab, lab.arkana).stdout)
            r = run(lab, os.path.join(lab.ws, "app"), env={"ARKANA_WORKER": "1"})
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            r = run(lab, lab.root, env={"ARKANA_HOME": ""})
            self.assertEqual((r.returncode, r.stdout), (0, ""))

class TestHookDirectrices(unittest.TestCase):
    def ctx(self, r):
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_inyecta_las_directrices_de_la_pieza_del_cwd_sin_ficheros_en_el_repo(self):
        with TC.CLab() as lab:
            app = os.path.join(lab.ws, "app")
            r = run(lab, app)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "SessionStart")
            c = out["additionalContext"]
            self.assertIn("[Arkana] Directrices para app", c)
            self.assertIn("No instales herramientas ni paquetes", c)
            self.assertIn("Conventional Commits con dos puntos", c)                 # formato por defecto
            self.assertIn("chore(app):", c)
            self.assertNotIn("CLAUDE", c)                                           # nada de Claude en lo que ve el repo
            for f in ("CLAUDE.md", "CLAUDE.local.md", "ARKANA.local.md"):          # y el hook no escribe ningún fichero de instrucciones
                self.assertFalse(os.path.exists(os.path.join(app, f)), f)

    def test_cada_pieza_recibe_la_suya_y_arkana_tambien(self):
        with TC.CLab() as lab:
            f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            for c in d["components"]:
                if c["alias"] == "api":
                    c["commit_format"] = "ia4d"
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(d, fh)
            self.assertIn("**IA4D**", self.ctx(run(lab, os.path.join(lab.ws, "api"))))
            self.assertIn("Directrices para ARKANA", self.ctx(run(lab, lab.arkana)))
            sub = os.path.join(lab.ws, "app", "src", "ui")
            os.makedirs(sub, exist_ok=True)
            self.assertIn("Directrices para app-ui", self.ctx(run(lab, sub)))      # la pieza más específica

    def test_las_notas_locales_se_inyectan_con_tope_y_solo_si_existen(self):
        with TC.CLab() as lab:
            app = os.path.join(lab.ws, "app")
            self.assertNotIn("Notas locales", self.ctx(run(lab, app)))
            with open(os.path.join(app, "ARKANA.local.md"), "w", encoding="utf-8") as fh:
                fh.write("Los tests se lanzan con `npm run test:ci`.\n")
            c = self.ctx(run(lab, app))
            self.assertIn("## Notas locales de este repo (ARKANA.local.md)", c)
            self.assertIn("npm run test:ci", c)
            with open(os.path.join(app, "ARKANA.local.md"), "w", encoding="utf-8") as fh:
                fh.write("x" * 20000)
            c = self.ctx(run(lab, app))
            self.assertIn("(notas recortadas)", c)
            self.assertLess(len(c), 12000)

    def test_sin_directrices_en_worker_ni_fuera_de_una_pieza(self):
        with TC.CLab() as lab:
            self.assertEqual(run(lab, os.path.join(lab.ws, "app"), env={"ARKANA_WORKER": "1"}).stdout, "")
            self.assertNotIn("hookSpecificOutput", run(lab, lab.root).stdout)       # cwd fuera de todas las piezas


if __name__ == "__main__":
    unittest.main()
