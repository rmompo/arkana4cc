"""arkana-todo: add/list/done/modify/delete lógico/validate/fix. Hermético: workspace temporal, sin red ni ~/.claude."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
TD = os.path.abspath(os.path.join(AQUI, "..", "scripts", "lib", "todo.py"))
ENV = {k: v for k, v in os.environ.items() if not k.startswith("ARKANA_")}
AYER = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = os.path.realpath(self.tmp.name)
        write(os.path.join(self.h, ".arkana", "arkana.json"), '{"schema_version": 1, "root": ".."}')
        self.store = os.path.join(self.h, ".arkana", "arkana-todo", "todos.json")

    def td(self, *args):
        return subprocess.run([sys.executable, "-I", TD, "--home", self.h, *args], capture_output=True, text=True, env=ENV,
                              stdin=subprocess.DEVNULL, timeout=60)

    def ok(self, *args):
        r = self.td(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def tareas(self):
        return json.loads(read(self.store))["tareas"]


class TestCiclo(Base):
    def test_install_es_idempotente_y_dry_run_no_escribe(self):
        self.ok("install", "--dry-run")
        self.assertFalse(os.path.exists(self.store))
        self.ok("install")
        antes = read(self.store)
        self.assertIn("presente", self.ok("install"))
        self.assertEqual(read(self.store), antes)

    def test_add_list_done_reopen(self):
        self.ok("install")
        self.assertIn("t-001", self.ok("add", "--title", "Rotar claves", "--priority", "high", "--due", "2099-01-01"))
        self.ok("add", "--title", "Limpiar ramas")
        out = self.ok("list")
        self.assertIn("INFO|t-001|[open] Rotar claves · high · vence 2099-01-01", out)
        self.assertIn("t-002", out)
        self.ok("done", "--id", "t-001")
        self.assertNotIn("t-001", self.ok("list"))
        t = self.tareas()[0]
        self.assertEqual((t["estado"], t["cerrada"] != ""), ("done", True))
        self.assertIn("t-001", self.ok("list", "--state", "done"))
        self.assertIn("ya estaba cerrada", self.ok("done", "--id", "t-001"))
        self.ok("done", "--id", "t-001", "--reopen")
        self.assertEqual((self.tareas()[0]["estado"], self.tareas()[0]["cerrada"]), ("open", ""))

    def test_add_funciona_sin_install_previo(self):
        self.ok("add", "--title", "Primera")
        self.assertEqual(self.tareas()[0]["id"], "t-001")

    def test_borrado_logico_y_restauracion(self):
        self.ok("add", "--title", "Borrable")
        self.ok("delete", "--id", "t-001")
        self.assertNotIn("t-001", self.ok("list"))
        self.assertIn("t-001", self.ok("list", "--state", "deleted"))
        self.assertEqual(self.td("done", "--id", "t-001").returncode, 2)               # una borrada no se cierra
        self.ok("modify", "--id", "t-001", "--restore")
        self.assertIn("t-001", self.ok("list"))
        self.assertEqual(self.td("modify", "--id", "t-001", "--restore").returncode, 2)  # ya no está borrada

    def test_los_ids_no_se_reutilizan_tras_borrar(self):
        self.ok("add", "--title", "A"); self.ok("delete", "--id", "t-001"); self.ok("add", "--title", "B")
        self.assertEqual([t["id"] for t in self.tareas()], ["t-001", "t-002"])

    def test_modify_cambia_solo_lo_indicado(self):
        self.ok("add", "--title", "Vieja", "--due", "2099-05-05", "--notes", "n")
        self.ok("modify", "--id", "t-001", "--title", "Nueva", "--priority", "low")
        t = self.tareas()[0]
        self.assertEqual((t["titulo"], t["prioridad"], t["vence"], t["notas"]), ("Nueva", "low", "2099-05-05", "n"))
        self.ok("modify", "--id", "t-001", "--due", "none")
        self.assertEqual(self.tareas()[0]["vence"], "")

    def test_dry_run_no_escribe(self):
        self.ok("add", "--title", "X")
        antes = read(self.store)
        for cmd in (["add", "--title", "Y"], ["done", "--id", "t-001"], ["modify", "--id", "t-001", "--title", "Z"], ["delete", "--id", "t-001"]):
            self.assertIn("DRY|", self.ok(*cmd, "--dry-run"))
        self.assertEqual(read(self.store), antes)

    def test_list_filtra_vencidas_y_ordena(self):
        self.ok("add", "--title", "Futura", "--due", "2099-01-01")
        self.ok("add", "--title", "Vencida", "--due", AYER, "--priority", "high")
        self.ok("add", "--title", "Sin fecha", "--priority", "low")
        out = self.ok("list")
        self.assertLess(out.index("Vencida"), out.index("Futura"))
        self.assertLess(out.index("Futura"), out.index("Sin fecha"))
        self.assertIn("VENCIDA", out)
        solo = self.ok("list", "--overdue")
        self.assertIn("Vencida", solo); self.assertNotIn("Futura", solo)
        self.assertIn("Sin fecha", self.ok("list", "--priority", "low"))

    def test_json(self):
        self.ok("add", "--title", "J")
        d = json.loads(self.ok("list", "--json"))
        self.assertEqual((d["plugin"], d["skill"], d["status"]), ("arkana-todo", "list", "ok"))


class TestValidacion(Base):
    def test_entradas_invalidas(self):
        self.assertEqual(self.td("add", "--title", "  ").returncode, 2)
        self.assertEqual(self.td("add", "--title", "x", "--priority", "urgente").returncode, 2)
        self.assertEqual(self.td("add", "--title", "x", "--due", "2026-13-40").returncode, 2)
        self.assertEqual(self.td("add", "--title", "x", "--due", "mañana").returncode, 2)
        self.assertEqual(self.td("done", "--id", "t-999").returncode, 2)
        self.assertEqual(self.td("list", "--priority", "urgente").returncode, 2)                  # también con el almacén vacío
        self.assertEqual(self.td("modify", "--id", "t-001").returncode, 2)
        self.assertFalse(os.path.exists(self.store))

    def test_componente_se_valida_contra_el_manifiesto(self):
        write(os.path.join(self.h, ".arkana", "core", "workspace.json"),
              json.dumps({"schema": 1, "arkana": {"alias": "ARKANA", "path": "."}, "components": [{"alias": "api", "type": "maven", "path": "back"}]}))
        self.ok("add", "--title", "ok", "--component", "api")
        self.assertEqual(self.td("add", "--title", "mal", "--component", "nadie").returncode, 2)
        self.ok("add", "--title", "todos", "--component", "all")

    def test_sin_workspace_falla_con_codigo_3(self):
        r = subprocess.run([sys.executable, "-I", TD, "--home", os.path.join(self.h, "no-existe"), "list"], capture_output=True, text=True, env=ENV)
        self.assertEqual(r.returncode, 3)

    def test_validate_estados(self):
        self.assertIn("WARN|almacen", self.ok("validate"))                          # sin almacén: aviso, no fallo
        self.ok("add", "--title", "A", "--due", AYER)
        out = self.ok("validate")
        self.assertIn("OK|almacen|1 tareas, 1 abiertas", out); self.assertIn("WARN|vencidas", out)
        d = json.loads(read(self.store)); d["tareas"][0]["estado"] = "raro"; d["tareas"].append(dict(d["tareas"][0], estado="open"))
        write(self.store, json.dumps(d))
        r = self.td("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("estado inválido", r.stdout); self.assertIn("id duplicado", r.stdout)
        write(self.store, "no es json")
        self.assertEqual(self.td("validate").returncode, 1)

    def test_fix_repara_contador_y_campos_sin_perder_tareas(self):
        write(self.store, json.dumps({"version": 1, "next": 1, "tareas": [{"id": "t-005", "titulo": "Vieja"}]}))
        self.assertEqual(self.td("validate").returncode, 1)
        antes = read(self.store)
        self.assertIn("DRY|", self.ok("fix", "--dry-run"))
        self.assertEqual(read(self.store), antes)
        self.ok("fix")
        self.ok("validate")
        d = json.loads(read(self.store))
        self.assertEqual((d["next"], d["tareas"][0]["titulo"], d["tareas"][0]["estado"]), (6, "Vieja", "open"))
        self.assertIn("nada que reparar", self.ok("fix"))


class TestContrato(unittest.TestCase):
    def test_el_contrato_declara_las_skills_que_existen(self):
        raiz = os.path.abspath(os.path.join(AQUI, ".."))
        with open(os.path.join(raiz, "arkana-plugin.json"), encoding="utf-8") as f:
            c = json.load(f)
        self.assertEqual(c["contract"], 1)
        for s in c["provides"]:
            self.assertTrue(os.path.isfile(os.path.join(raiz, "skills", s, "SKILL.md")), s)
        self.assertEqual(c["data"][0]["class"], "data")


if __name__ == "__main__":
    unittest.main()
