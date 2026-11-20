"""arkana-note: install/add/list/modify/delete lógico/validate/fix/rename. Hermético: workspace temporal, sin red ni ~/.claude."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
NT = os.path.abspath(os.path.join(AQUI, "..", "scripts", "lib", "note.py"))
ENV = {k: v for k, v in os.environ.items() if not k.startswith("ARKANA_")}


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
        self.store = os.path.join(self.h, ".arkana", "arkana-note", "notes.json")

    def nt(self, *args):
        return subprocess.run([sys.executable, "-I", NT, "--home", self.h, *args], capture_output=True, text=True, env=ENV,
                              stdin=subprocess.DEVNULL, timeout=60)

    def ok(self, *args):
        r = self.nt(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def notas(self):
        return json.loads(read(self.store))["notas"]


class TestCiclo(Base):
    def test_install_es_idempotente_y_dry_run_no_escribe(self):
        self.ok("install", "--dry-run")
        self.assertFalse(os.path.exists(self.store))
        self.ok("install")
        antes = read(self.store)
        self.assertIn("presente", self.ok("install"))
        self.assertEqual(read(self.store), antes)

    def test_add_funciona_sin_install_y_pone_los_valores_por_defecto(self):
        self.assertIn("n-001", self.ok("add", "--title", "Primera"))
        n = self.notas()[0]
        self.assertEqual((n["id"], n["estado"], n["componente"], n["texto"]), ("n-001", "active", "*", ""))

    def test_list_es_una_tabla_con_las_mas_recientes_primero(self):
        self.ok("add", "--title", "Vieja", "--text", "texto uno")
        self.ok("add", "--title", "Nueva con | barra", "--text", "texto dos")
        d = json.loads(read(self.store)); d["notas"][0]["modificada"] = "2000-01-01"; write(self.store, json.dumps(d))
        out = self.ok("list")
        self.assertIn("| identificador | componente | titulo | texto |", out)
        self.assertIn("| n-002 | * | Nueva con \\| barra | texto dos |", out)
        self.assertLess(out.index("n-002"), out.index("n-001"))

    def test_list_con_id_muestra_la_nota_entera_incluso_borrada(self):
        self.ok("add", "--title", "Larga", "--text", "x" * 200)
        self.assertIn("…", self.ok("list"))                                              # en la tabla se acorta
        self.assertIn("x" * 200, self.ok("list", "--id", "n-001"))                        # con --id, entera
        self.ok("delete", "--id", "n-001")
        self.assertIn("removed", self.ok("list", "--id", "n-001"))
        self.assertEqual(self.nt("list", "--id", "n-999").returncode, 2)

    def test_filtros_por_texto_estado_y_sin_notas(self):
        self.assertIn("Sin notas", self.ok("list"))
        self.ok("add", "--title", "Claves", "--text", "rotar tokens"); self.ok("add", "--title", "Otra")
        self.assertIn("n-001", self.ok("list", "--q", "TOKENS")); self.assertNotIn("n-002", self.ok("list", "--q", "tokens"))
        self.ok("delete", "--id", "n-002")
        self.assertNotIn("n-002", self.ok("list")); self.assertIn("n-002", self.ok("list", "--status", "removed"))
        self.assertIn("n-002", self.ok("list", "--status", "all"))
        self.assertEqual(self.nt("list", "--status", "raro").returncode, 2)

    def test_borrado_logico_restauracion_y_ids_no_reutilizados(self):
        self.ok("add", "--title", "Borrable")
        self.ok("delete", "--id", "n-001")
        self.assertEqual(self.nt("modify", "--id", "n-001", "--title", "x").returncode, 2)      # borrada: solo --restore
        self.ok("modify", "--id", "n-001", "--restore")
        self.assertEqual(self.notas()[0]["estado"], "active")
        self.assertEqual(self.nt("modify", "--id", "n-001", "--restore").returncode, 2)
        self.ok("delete", "--id", "n-001"); self.ok("add", "--title", "B")
        self.assertEqual([n["id"] for n in self.notas()], ["n-001", "n-002"])

    def test_modify_cambia_solo_lo_indicado_y_la_fecha(self):
        self.ok("add", "--title", "Vieja", "--text", "t")
        d = json.loads(read(self.store)); d["notas"][0]["modificada"] = "2000-01-01"; write(self.store, json.dumps(d))
        self.ok("modify", "--id", "n-001", "--title", "Nueva")
        n = self.notas()[0]
        self.assertEqual((n["titulo"], n["texto"]), ("Nueva", "t"))
        self.assertNotEqual(n["modificada"], "2000-01-01")
        self.assertEqual(self.nt("modify", "--id", "n-001").returncode, 2)

    def test_dry_run_no_escribe(self):
        self.ok("add", "--title", "X")
        antes = read(self.store)
        for cmd in (["add", "--title", "Y"], ["modify", "--id", "n-001", "--title", "Z"], ["delete", "--id", "n-001"]):
            self.assertIn("DRY|", self.ok(*cmd, "--dry-run"))
        self.assertEqual(read(self.store), antes)

    def test_json_y_entradas_invalidas(self):
        self.ok("add", "--title", "J")
        d = json.loads(self.ok("list", "--json"))
        self.assertEqual((d["plugin"], d["skill"], d["status"]), ("arkana-note", "list", "ok"))
        self.assertEqual(self.nt("add", "--title", "  ").returncode, 2)
        self.assertEqual(self.nt("delete", "--id", "n-404").returncode, 2)

    def test_sin_workspace_falla_con_codigo_3(self):
        r = subprocess.run([sys.executable, "-I", NT, "--home", os.path.join(self.h, "no-existe"), "list"], capture_output=True, text=True, env=ENV)
        self.assertEqual(r.returncode, 3)


class TestComponentes(Base):
    def manifiesto(self):
        write(os.path.join(self.h, ".arkana", "core", "workspace.json"),
              json.dumps({"schema": 1, "arkana": {"alias": "ARKANA", "path": "."},
                          "components": [{"alias": "api", "type": "maven", "path": "back", "id": "11111111-1111-4111-8111-111111111111"},
                                         {"alias": "app", "type": "node", "path": "front"}]}))
        write(os.path.join(self.h, "arkana-project.json"), json.dumps({"schema_version": 1, "layout": 5, "workspace": {"id": "x", "name": "t"},
              "components": [{"id": "11111111-1111-4111-8111-111111111111", "alias": "api", "module": "viso_rest"}]}))

    def test_el_componente_se_valida_y_se_da_por_alias_carpeta_o_modulo(self):
        self.manifiesto()
        for ref in ("api", "API", "back", "viso_rest", "dir:back", "mod:viso_rest"):
            self.ok("add", "--title", f"n {ref}", "--component", ref)
        self.assertEqual({n["componente"] for n in self.notas()}, {"api"})
        self.assertEqual(self.nt("add", "--title", "x", "--component", "nadie").returncode, 2)
        self.assertEqual(self.nt("add", "--title", "x", "--component", "mod:back").returncode, 2)
        self.ok("add", "--title", "todos", "--component", "*")
        self.assertEqual(self.notas()[-1]["componente"], "*")
        self.assertIn("| API |", self.ok("list"))                                          # en MAYÚSCULAS

    def test_filtro_por_componente_incluye_las_de_todos(self):
        self.manifiesto()
        self.ok("add", "--title", "De api", "--component", "api"); self.ok("add", "--title", "De app", "--component", "app"); self.ok("add", "--title", "De todos")
        out = self.ok("list", "--component", "viso_rest")
        self.assertIn("De api", out); self.assertIn("De todos", out); self.assertNotIn("De app", out)

    def test_rename_reescribe_el_componente_y_respeta_dry_run(self):
        self.ok("add", "--title", "Una", "--component", "app"); self.ok("add", "--title", "Otra", "--component", "api")
        antes = read(self.store)
        self.assertIn("DRY|rename|1 notas pasan de app a frontend", self.ok("rename", "--from", "app", "--to", "frontend", "--dry-run"))
        self.assertEqual(read(self.store), antes)
        self.assertIn("OK|rename|1 notas pasan de app a frontend", self.ok("rename", "--from", "APP", "--to", "frontend"))
        self.assertEqual([n["componente"] for n in self.notas()], ["frontend", "api"])
        self.assertIn("0 notas", self.ok("rename", "--from", "app", "--to", "frontend"))


class TestValidacion(Base):
    def test_validate_estados(self):
        self.assertIn("WARN|almacen", self.ok("validate"))
        self.ok("add", "--title", "A")
        self.assertIn("OK|almacen|1 notas, 1 activas", self.ok("validate"))
        d = json.loads(read(self.store)); d["notas"][0]["estado"] = "raro"; d["notas"].append(dict(d["notas"][0], estado="active"))
        write(self.store, json.dumps(d))
        r = self.nt("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("estado inválido", r.stdout); self.assertIn("id duplicado", r.stdout)
        write(self.store, "no es json")
        self.assertEqual(self.nt("validate").returncode, 1)

    def test_fix_repara_contador_y_campos_sin_perder_notas(self):
        write(self.store, json.dumps({"version": 1, "next": 1, "notas": [{"id": "n-005", "titulo": "Vieja"}]}))
        self.assertEqual(self.nt("validate").returncode, 1)
        antes = read(self.store)
        self.assertIn("DRY|", self.ok("fix", "--dry-run")); self.assertEqual(read(self.store), antes)
        self.ok("fix"); self.ok("validate")
        d = json.loads(read(self.store))
        self.assertEqual((d["next"], d["notas"][0]["titulo"], d["notas"][0]["estado"], d["notas"][0]["componente"]), (6, "Vieja", "active", "*"))
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
