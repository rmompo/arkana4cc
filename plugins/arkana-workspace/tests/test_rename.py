"""component edit --rename: el alias cambia, el id no; manifiesto, local.json, registro y datos locales de los plugins quedan coherentes."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

CLI = os.path.join(E.SCRIPTS, "lib", "components.py")
PLUGINS = os.path.abspath(os.path.join(E.PLUGIN, ".."))
IDS = {a: "%08d-0000-4000-8000-%012d" % (i + 1, i + 1) for i, a in enumerate(["arkana", "app", "api", "app-web", "app-ui", "docs", "specs"])}


def run(lab, *a):
    return subprocess.run([sys.executable, "-I", CLI, *a, "--home", lab.arkana, "--plugins-dir", PLUGINS], capture_output=True, text=True,
                          env=dict(lab.env, ARKANA_HOME=lab.arkana), cwd=lab.ws, stdin=subprocess.DEVNULL, timeout=120)


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def montar(lab, estado_plan="completado"):
    """Registro del proyecto con ids + datos locales que citan `app`."""
    wj(os.path.join(lab.arkana, "arkana-project.json"), {"schema_version": 1, "layout": 3, "workspace": {"id": IDS["arkana"], "name": "t"},
                                                         "components": [{"id": i, "alias": a} for a, i in IDS.items()]})
    st = os.path.join(lab.arkana, ".arkana")
    mid = "N261030-1729-v7fb"
    wj(os.path.join(st, "arkana-messaging/state/messages", mid + ".json"),
       {"id": mid, "asunto": "Aviso para la app", "tipo": "task", "de": "arkana", "para": ["app", "api"], "destinatarios": ["app", "api"], "estado": "open",
        "instrucciones": ["a"], "criterios": ["b"], "confirmaciones": {"app": {"estado": "done"}}, "entregas": {"app": {"n": 1}}, "ejecuciones": {}})
    wj(os.path.join(st, "arkana-messaging/state/read/app.json"), {"schema_version": 2, "ids": {mid: "2026-01-01"}})
    wj(os.path.join(st, "arkana-todo/todos.json"), {"version": 1, "next": 2, "tareas": [{"id": "t-001", "titulo": "x", "estado": "open", "componente": "app"}]})
    wj(os.path.join(st, "arkana-agentic/state/planes/P1/plan.json"), {"id": "P1", "estado": estado_plan, "ramas": {"app": {"nombre": "arkana-worker/P1"}}})
    wj(os.path.join(st, "arkana-agentic/state/planes/P1/tareas/T001.json"), {"id": "T001", "repo": "app"})
    wj(os.path.join(st, "arkana-agentic/data/ledger/sessions/s1.json"), {"session_id": "s1", "component": "app"})
    lp = os.path.join(st, "arkana-workspace", "local.json")
    d = rj(lp) if os.path.isfile(lp) else {"schema_version": 1}
    d.setdefault("git", {})["app"] = {"name": "N", "email": "n@x"}
    d.setdefault("tool_paths", {})["app"] = {"node": "/opt/node"}
    wj(lp, d)
    return st, mid


class TestRenombrar(unittest.TestCase):
    def test_renombra_en_manifiesto_registro_y_datos_locales_sin_cambiar_el_id(self):
        with TC.CLab() as lab:
            st, mid = montar(lab)
            r = run(lab, "edit", "--alias", "app", "--rename", "frontend")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("OK|frontend|alias app → frontend en el manifiesto y en local.json", r.stdout)
            self.assertIn("arkana-messaging:rename|1 mensajes pasan de app a frontend", r.stdout)
            self.assertIn("arkana-todo:rename|1 tareas pasan de app a frontend", r.stdout)
            self.assertIn("arkana-agentic:rename|3 ficheros de la orquestación pasan de app a frontend", r.stdout)
            ws = rj(os.path.join(st, "core", "workspace.json"))
            self.assertEqual([c["alias"] for c in ws["components"]][:2], ["frontend", "api"])
            self.assertEqual(next(c for c in ws["components"] if c["alias"] == "frontend")["id"], IDS["app"])      # el id viaja con el componente
            reg = rj(os.path.join(lab.arkana, "arkana-project.json"))
            self.assertEqual(next(c for c in reg["components"] if c["id"] == IDS["app"])["alias"], "frontend")
            loc = rj(os.path.join(st, "arkana-workspace", "local.json"))
            self.assertIn("frontend", loc["git"]); self.assertNotIn("app", loc["git"]); self.assertIn("frontend", loc["tool_paths"])
            m = rj(os.path.join(st, "arkana-messaging/state/messages", mid + ".json"))
            self.assertEqual((m["para"], m["destinatarios"], list(m["confirmaciones"]), list(m["entregas"])), (["frontend", "api"], ["frontend", "api"], ["frontend"], ["frontend"]))
            self.assertTrue(os.path.isfile(os.path.join(st, "arkana-messaging/state/read/frontend.json")))
            self.assertFalse(os.path.isfile(os.path.join(st, "arkana-messaging/state/read/app.json")))
            self.assertEqual(rj(os.path.join(st, "arkana-todo/todos.json"))["tareas"][0]["componente"], ["frontend"])
            self.assertEqual(rj(os.path.join(st, "arkana-agentic/state/planes/P1/tareas/T001.json"))["repo"], "frontend")
            self.assertEqual(list(rj(os.path.join(st, "arkana-agentic/state/planes/P1/plan.json"))["ramas"]), ["frontend"])
            self.assertEqual(rj(os.path.join(st, "arkana-agentic/data/ledger/sessions/s1.json"))["component"], "frontend")

    def test_dry_run_no_cambia_nada(self):
        with TC.CLab() as lab:
            st, mid = montar(lab)
            antes = open(os.path.join(st, "core", "workspace.json"), encoding="utf-8").read()
            r = run(lab, "edit", "--alias", "app", "--rename", "frontend", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("DRY|", r.stdout)
            self.assertEqual(open(os.path.join(st, "core", "workspace.json"), encoding="utf-8").read(), antes)
            self.assertEqual(rj(os.path.join(st, "arkana-todo/todos.json"))["tareas"][0]["componente"], "app")
            self.assertEqual(next(c for c in rj(os.path.join(lab.arkana, "arkana-project.json"))["components"] if c["id"] == IDS["app"])["alias"], "app")

    def test_un_plan_activo_impide_renombrar_y_no_deja_nada_a_medias(self):
        with TC.CLab() as lab:
            st, mid = montar(lab, estado_plan="en_ejecucion")
            antes = open(os.path.join(st, "core", "workspace.json"), encoding="utf-8").read()
            r = run(lab, "edit", "--alias", "app", "--rename", "frontend")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("no se ha cambiado nada", r.stdout)
            self.assertIn("el plan P1 está en_ejecucion", r.stdout)
            self.assertEqual(open(os.path.join(st, "core", "workspace.json"), encoding="utf-8").read(), antes)
            self.assertEqual(rj(os.path.join(st, "arkana-todo/todos.json"))["tareas"][0]["componente"], "app")
            self.assertEqual(next(c for c in rj(os.path.join(lab.arkana, "arkana-project.json"))["components"] if c["id"] == IDS["app"])["alias"], "app")

    def test_validaciones(self):
        with TC.CLab() as lab:
            montar(lab)
            for args in (["--alias", "arkana", "--rename", "x"], ["--alias", "app", "--rename", "api"], ["--alias", "app", "--rename", "all"],
                         ["--alias", "app", "--rename", "Mal Nombre"]):
                r = run(lab, "edit", *args)
                self.assertEqual(r.returncode, 1, (args, r.stdout))

    def test_seguir_un_renombrado_ya_hecho_en_el_registro_por_otra_persona(self):
        with TC.CLab() as lab:
            st, mid = montar(lab)
            reg = rj(os.path.join(lab.arkana, "arkana-project.json"))
            for c in reg["components"]:
                if c["id"] == IDS["app"]:
                    c["alias"] = "frontend"                                                   # otra persona renombró y empujó
            wj(os.path.join(lab.arkana, "arkana-project.json"), reg)
            r = run(lab, "edit", "--alias", "app", "--rename", "frontend")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(next(c for c in rj(os.path.join(st, "core", "workspace.json"))["components"] if c["alias"] == "frontend")["id"], IDS["app"])
            self.assertEqual(rj(os.path.join(st, "arkana-todo/todos.json"))["tareas"][0]["componente"], ["frontend"])

    def test_alta_con_id_y_baja_conserva_el_id_en_el_registro(self):
        with TC.CLab() as lab:
            montar(lab)
            os.makedirs(os.path.join(lab.ws, "nuevo"), exist_ok=True)
            r = run(lab, "add", "--alias", "nuevo", "--path", os.path.join(lab.ws, "nuevo"))
            self.assertEqual(r.returncode, 0, r.stdout)
            reg = rj(os.path.join(lab.arkana, "arkana-project.json"))
            cid = next(c["id"] for c in reg["components"] if c["alias"] == "nuevo")
            self.assertEqual(next(c for c in rj(os.path.join(lab.arkana, ".arkana", "core", "workspace.json"))["components"] if c["alias"] == "nuevo")["id"], cid)
            r = run(lab, "remove", "--alias", "nuevo", "--yes")
            self.assertEqual(r.returncode, 0, r.stdout)
            reg = rj(os.path.join(lab.arkana, "arkana-project.json"))
            self.assertTrue(next(c for c in reg["components"] if c["id"] == cid).get("retired"))        # el id se conserva, retirado

    def test_sin_registro_renombra_igualmente_sin_ids(self):
        with TC.CLab() as lab:
            r = run(lab, "edit", "--alias", "docs", "--rename", "manuales")
            self.assertEqual(r.returncode, 0, r.stdout)
            ws = rj(os.path.join(lab.arkana, ".arkana", "core", "workspace.json"))
            self.assertIn("manuales", [c["alias"] for c in ws["components"]])
            self.assertNotIn("id", next(c for c in ws["components"] if c["alias"] == "manuales"))


if __name__ == "__main__":
    unittest.main()
