"""Cobertura de arkana-evolve: nada de lo que cambia el layout se queda sin migración, el sello coincide con la última migración y toda instalación antigua llega al layout actual.
Son las comprobaciones que impiden que una versión nueva de Arkana deje atrás a las instalaciones que ya existen."""
import json
import os
import re
import sys
import unittest

from test_evolve import Lab, PLUGIN, git

sys.path.insert(0, os.path.join(PLUGIN, "scripts", "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "scripts", "_core"))
import evolve  # noqa: E402
from arkana_core import project  # noqa: E402

RAIZ = os.path.abspath(os.path.join(PLUGIN, "..", ".."))


class TestSelloYMigraciones(unittest.TestCase):
    def setUp(self):
        self.mods = evolve.load_migrations()
        self.numericas = [m for m in self.mods if not evolve.is_baseline(m)]

    def test_el_layout_que_conoce_el_nucleo_es_el_de_la_ultima_migracion(self):
        """Si se añade una migración sin subir LAYOUT_KNOWN, las instalaciones recién migradas avisarían de «actualiza el plugin» a quien ya está al día (y al revés)."""
        self.assertEqual(project.LAYOUT_KNOWN, evolve.latest_layout(self.mods))

    def test_los_ids_son_consecutivos_y_cada_migracion_declara_su_layout(self):
        ids = [int(m.ID) for m in self.numericas]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        for m in self.numericas:
            if hasattr(m, "LAYOUT"):
                self.assertEqual(m.LAYOUT, int(m.ID), m.ID)

    def test_cada_migracion_tiene_ambito_valido_y_titulo(self):
        for m in self.mods:
            self.assertTrue(set(m.SCOPE) <= {"shared", "local"} and m.SCOPE, m.ID)
            self.assertTrue(m.TITLE.strip(), m.ID)

    def test_el_readme_documenta_todas_las_migraciones(self):
        with open(os.path.join(PLUGIN, "README.md"), encoding="utf-8") as f:
            readme = f.read()
        for m in self.mods:
            self.assertRegex(readme, r"\| `%s` \|" % re.escape(str(m.ID)), f"falta la fila de {m.ID} en el README")

    def test_el_nucleo_de_cada_plugin_conoce_el_mismo_layout(self):
        """Cada plugin lleva su copia del núcleo: ninguna puede quedarse con un LAYOUT_KNOWN anterior (avisaría de actualizar a quien ya está al día)."""
        vistos = {}
        base = os.path.join(RAIZ, "plugins")
        for p in sorted(os.listdir(base)):
            f = os.path.join(base, p, "scripts", "_core", "arkana_core", "project.py")
            if os.path.isfile(f):
                m = re.search(r"^LAYOUT_KNOWN = (\d+)", open(f, encoding="utf-8").read(), re.M)
                vistos[p] = int(m.group(1))
        self.assertTrue(vistos)
        self.assertEqual(set(vistos.values()), {evolve.latest_layout(self.mods)}, vistos)


class TestEscalera(unittest.TestCase):
    """Una instalación detenida en cualquier punto (cada migración numérica) llega al layout actual con un solo `apply`, sin pérdida de datos y de forma idempotente."""

    def datos_antiguos(self, lab):
        lab.write(".arkana/arkana-todo/todos.json", {"version": 1, "next": 3, "tareas": [
            {"id": "t-001", "titulo": "A", "estado": "open", "prioridad": "normal", "vence": "", "componente": "all", "creada": "2026-01-01", "cerrada": "", "notas": "n"},
            {"id": "t-002", "titulo": "B", "estado": "deleted", "prioridad": "high", "vence": "", "componente": "api", "creada": "2026-01-01", "cerrada": "", "notas": ""}]})
        for rel, txt in (("arkana-docs/manual.pdf", "pdf"), ("arkana-docs/cliente/a.md", "a"), ("arkana-docs/md/manual.pdf.md", "# m")):
            p = os.path.join(lab.arkana, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write(txt)

    def comprobar_al_dia(self, lab):
        self.assertEqual(lab.project()["layout"], project.LAYOUT_KNOWN)
        self.assertEqual([h["id"] for h in lab.project()["history"]], ["%04d" % i for i in range(1, project.LAYOUT_KNOWN + 1)])
        tareas = json.loads(lab.read(".arkana/arkana-todo/todos.json"))["tareas"]
        self.assertEqual([(t["estado"], t["prioridad"], t["componente"]) for t in tareas], [("pending", "medium", ["*"]), ("removed", "high", ["api"])])
        self.assertEqual(tareas[0]["notas"], "n")
        for rel in ("arkana-docs/src/manual.pdf", "arkana-docs/src/cliente/a.md", "arkana-docs/md/manual.pdf.md", "arkana-docs/out/.gitkeep"):
            self.assertTrue(os.path.exists(os.path.join(lab.arkana, rel)), rel)
        self.assertFalse(os.path.exists(os.path.join(lab.arkana, "arkana-docs", "manual.pdf")))
        self.assertEqual(lab.read(".gitignore").count("/.arkana/"), 1)

    def test_desde_cualquier_punto_se_llega_al_layout_actual(self):
        for parada in range(0, project.LAYOUT_KNOWN):
            with self.subTest(parada=parada):
                with Lab() as lab:
                    if parada:
                        r = lab.run("apply", "--to", str(parada))
                        self.assertEqual(r.returncode, 0, r.stdout)
                    self.datos_antiguos(lab)
                    git(lab.arkana, "add", "-A", "-f"); git(lab.arkana, "commit", "-q", "-m", "chore(root) base")
                    r = lab.run("apply")
                    self.assertEqual(r.returncode, 0, (parada, r.stdout))
                    self.comprobar_al_dia(lab)
                    self.assertIn("nada que hacer", lab.run("apply").stdout)
                    self.assertNotRegex(lab.run("check").stdout, r"(?m)^(FAIL|WARN)\|")

    def test_check_de_una_instalacion_antigua_lista_exactamente_lo_pendiente(self):
        with Lab() as lab:
            lab.run("apply", "--to", "5")
            self.datos_antiguos(lab)
            salida = lab.run("check").stdout
            pendientes = re.findall(r"WARN\|(\d{4})\|pendiente", salida)
            self.assertEqual(pendientes, ["0006", "0007", "0008", "0009"])


if __name__ == "__main__":
    unittest.main()
