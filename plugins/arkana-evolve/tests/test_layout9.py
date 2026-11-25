"""Migración 0009: el componente de una tarea de arkana-todo pasa a ser una lista."""
import json
import unittest

from test_evolve import Lab


def todos(lab, tareas):
    lab.write(".arkana/arkana-todo/todos.json", {"version": 1, "next": 9, "tareas": tareas})


def leer(lab):
    return json.loads(lab.read(".arkana/arkana-todo/todos.json"))


def t(i, comp, **kw):
    d = {"id": i, "titulo": "x" + i, "estado": "pending", "prioridad": "medium", "vence": "", "creada": "2026-01-01", "cerrada": "", "notas": "n"}
    if comp is not ...:
        d["componente"] = comp
    d.update(kw)
    return d


class TestMigracion0009(unittest.TestCase):
    def test_pasa_el_texto_a_lista_y_conserva_las_listas_y_el_resto(self):
        with Lab() as lab:
            lab.run("apply", "--to", "8")
            todos(lab, [t("t-001", "api"), t("t-002", "*"), t("t-003", ""), t("t-004", "all"), t("t-005", ["m3wa", "m3mf"]), t("t-006", None), t("t-007", ...)])
            self.assertIn("0009", lab.run("check").stdout)
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            d = leer(lab)
            self.assertEqual([x.get("componente") for x in d["tareas"]], [["api"], ["*"], ["*"], ["*"], ["m3wa", "m3mf"], ["*"], None] if False else
                             [["api"], ["*"], ["*"], ["*"], ["m3wa", "m3mf"], ["*"]] + [d["tareas"][6].get("componente")])
            self.assertNotIn("componente", d["tareas"][6])                                    # una tarea sin campo no se inventa uno: lo repone `fix`
            self.assertEqual((d["next"], d["tareas"][0]["notas"], d["tareas"][0]["titulo"]), (9, "n", "xt-001"))
            self.assertEqual(lab.project()["layout"], 9)

    def test_idempotente_y_dry_run_no_escribe(self):
        with Lab() as lab:
            lab.run("apply", "--to", "8")
            todos(lab, [t("t-001", "api"), t("t-002", ["a", "b"])])
            antes = lab.read(".arkana/arkana-todo/todos.json")
            r = lab.run("apply", "--dry-run")
            self.assertIn("DRY|0009:tareas|1 tareas pasan a componente como lista", r.stdout)
            self.assertEqual(lab.read(".arkana/arkana-todo/todos.json"), antes)
            lab.run("apply")
            despues = lab.read(".arkana/arkana-todo/todos.json")
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertEqual(lab.read(".arkana/arkana-todo/todos.json"), despues)

    def test_sin_tareas_o_ya_en_lista_no_hace_nada_pero_se_estampa(self):
        with Lab() as lab:
            r = lab.run("apply")
            self.assertNotIn("0009:tareas", r.stdout)
            self.assertEqual(lab.project()["layout"], 9)
        with Lab() as lab:
            lab.run("apply", "--to", "8")
            todos(lab, [t("t-001", ["api"])])
            self.assertNotIn("0009:tareas", lab.run("apply").stdout)

    def test_encadena_con_la_0006_en_una_sola_pasada(self):
        with Lab() as lab:
            lab.run("apply", "--to", "5")
            todos(lab, [t("t-001", "all", estado="open", prioridad="normal"), t("t-002", "api")])
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            d = leer(lab)
            self.assertEqual([(x["estado"], x["prioridad"], x["componente"]) for x in d["tareas"]], [("pending", "medium", ["*"]), ("pending", "medium", ["api"])])


if __name__ == "__main__":
    unittest.main()
