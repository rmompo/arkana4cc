"""Migraciones 0006 (modelo de estados de arkana-todo) y 0007 (/.arkana/ en el .gitignore de ARKANA)."""
import json
import os
import unittest

from test_evolve import Lab, git

ANTIGUAS = [
    {"id": "t-001", "titulo": "A", "estado": "open", "prioridad": "normal", "vence": "", "componente": "", "creada": "2026-01-01", "cerrada": "", "notas": ""},
    {"id": "t-002", "titulo": "B", "estado": "deleted", "prioridad": "high", "vence": "", "componente": "all", "creada": "2026-01-01", "cerrada": "", "notas": ""},
    {"id": "t-003", "titulo": "C", "estado": "done", "prioridad": "low", "vence": "", "componente": "api", "creada": "2026-01-01", "cerrada": "2026-01-02", "notas": "n"},
]


def todos(lab, tareas):
    lab.write(".arkana/arkana-todo/todos.json", {"version": 1, "next": 4, "tareas": tareas})


def leer(lab):
    return json.loads(lab.read(".arkana/arkana-todo/todos.json"))


class TestMigracion0006(unittest.TestCase):
    def test_pasa_las_tareas_al_modelo_nuevo_sin_tocar_lo_demas(self):
        with Lab() as lab:
            lab.run("apply", "--to", "5")
            todos(lab, json.loads(json.dumps(ANTIGUAS)))
            self.assertIn("pendiente", lab.run("check").stdout)
            r = lab.run("apply", "--to", "6")
            self.assertEqual(r.returncode, 0, r.stdout)
            d = leer(lab)
            self.assertEqual([(t["estado"], t["prioridad"], t["componente"]) for t in d["tareas"]],
                             [("pending", "medium", "*"), ("removed", "high", "*"), ("done", "low", "api")])
            self.assertEqual((d["next"], d["tareas"][2]["notas"], d["tareas"][2]["cerrada"]), (4, "n", "2026-01-02"))     # el resto, intacto
            self.assertEqual(lab.project()["layout"], 6)

    def test_idempotente_y_dry_run_no_escribe(self):
        with Lab() as lab:
            lab.run("apply", "--to", "5")
            todos(lab, json.loads(json.dumps(ANTIGUAS)))
            antes = lab.read(".arkana/arkana-todo/todos.json")
            r = lab.run("apply", "--dry-run")
            self.assertIn("2 tareas pasan al modelo nuevo", r.stdout)
            self.assertEqual(lab.read(".arkana/arkana-todo/todos.json"), antes)
            lab.run("apply")
            despues = lab.read(".arkana/arkana-todo/todos.json")
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertEqual(lab.read(".arkana/arkana-todo/todos.json"), despues)

    def test_sin_tareas_o_ya_migradas_no_hace_nada_pero_se_estampa(self):
        with Lab() as lab:
            r = lab.run("apply")                                                          # sin todos.json
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("0006:tareas", r.stdout)
            self.assertEqual(lab.project()["layout"], 10)
        with Lab() as lab:
            lab.run("apply", "--to", "5")
            todos(lab, [{"id": "t-001", "titulo": "A", "estado": "pending", "prioridad": "medium", "componente": "*"}])
            self.assertNotIn("0006:tareas", lab.run("apply").stdout)


class TestMigracion0007(unittest.TestCase):
    def test_añade_el_ignore_y_es_idempotente(self):
        with Lab() as lab:
            lab.run("apply", "--to", "6")
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".gitignore")))
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("0007:gitignore", r.stdout)
            self.assertEqual(lab.read(".gitignore"), "/.arkana/\n")
            self.assertEqual(lab.project()["layout"], 10)
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertEqual(lab.read(".gitignore").count("/.arkana/"), 1)

    def test_respeta_un_gitignore_existente(self):
        with Lab() as lab:
            lab.run("apply", "--to", "6")
            lab.write(".gitignore", "node_modules/")                                        # sin salto de línea final
            git(lab.arkana, "add", ".gitignore"); git(lab.arkana, "commit", "-q", "-m", "ignore")
            lab.run("apply")
            self.assertEqual(lab.read(".gitignore"), "node_modules/\n/.arkana/\n")

    def test_ya_ignorado_por_otra_via_no_hace_nada(self):
        with Lab() as lab:
            lab.run("apply", "--to", "6")
            with open(os.path.join(lab.arkana, ".git", "info", "exclude"), "a", encoding="utf-8") as f:
                f.write(".arkana/\n")
            r = lab.run("apply")
            self.assertNotIn("0007:gitignore", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".gitignore")))

    def test_avisa_si_arkana_ya_estaba_versionado(self):
        with Lab() as lab:
            lab.run("apply", "--to", "6")
            git(lab.arkana, "add", "-A", "-f"); git(lab.arkana, "commit", "-q", "-m", "con .arkana")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("WARN|0007:versionado", r.stdout)
            self.assertIn("git rm -r --cached .arkana", r.stdout)

    def test_con_el_gitignore_con_cambios_sin_commitear_no_se_pisa(self):
        with Lab() as lab:
            lab.run("apply", "--to", "6")
            lab.write(".gitignore", "a\n"); git(lab.arkana, "add", ".gitignore"); git(lab.arkana, "commit", "-q", "-m", "x")
            lab.write(".gitignore", "a\nb\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertEqual(lab.read(".gitignore"), "a\nb\n")


class TestRegistroDeUsuario(unittest.TestCase):
    def test_mueve_el_registro_antiguo_a_la_carpeta_arkana_del_usuario(self):
        with Lab() as lab:
            viejo = os.path.join(lab.home, ".arkana-workspaces.json")
            with open(viejo, "w") as f:
                json.dump({"workspaces": [{"name": "otro", "arkana": "/x/arkana", "root": "/x"}]}, f)
            r = lab.run("apply", "--dry-run")
            self.assertIn("DRY|registro-usuario|", r.stdout)
            self.assertTrue(os.path.isfile(viejo))                                            # el ensayo no mueve nada
            self.assertIn("OK|registro-usuario|", lab.run("apply").stdout)
            nuevo = os.path.join(lab.home, ".arkana", "workspaces.json")
            self.assertFalse(os.path.exists(viejo))
            with open(nuevo) as f:
                nombres = sorted(w["name"] for w in json.load(f)["workspaces"])
            self.assertIn("otro", nombres)                                                    # conserva las entradas de otros workspaces
            self.assertNotIn("registro-usuario", lab.run("apply").stdout)                     # idempotente

    def test_sin_registro_antiguo_no_toca_nada(self):
        with Lab() as lab:
            self.assertNotIn("registro-usuario", lab.run("apply").stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.home, ".arkana")))


if __name__ == "__main__":
    unittest.main()
