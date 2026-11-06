"""Migración del layout de .arkana/arkana-agentic a config / state / data: copia primero, se niega con un plan activo, idempotente."""
import json
import os
import tarfile
import tempfile
import unittest

import common  # noqa: F401
import migrate


def w(p, obj=None, text=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text if text is not None else json.dumps(obj))


def old_layout(base, estado="completado"):
    w(os.path.join(base, "planes", "P1", "plan.json"), {"id": "P1", "estado": estado})
    w(os.path.join(base, "planes", "P1", "tareas", "T001.json"), {"id": "T001"})
    w(os.path.join(base, "run", "linea.json"), {})
    w(os.path.join(base, "sesiones", "abc"), text="1 0.5\n")
    w(os.path.join(base, "actual"), text="P1")
    w(os.path.join(base, "politica.json"), {"limites": {"total_budget_usd": 8}})


class TestMigrate(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="mig-")
        self.base = os.path.join(self.d, "arkana-agentic")
        self.bak = os.path.join(self.d, "bak")

    def test_mueve_todo_hace_copia_y_es_idempotente(self):
        old_layout(self.base)
        self.assertEqual(len(migrate.pending(self.base)), 5)
        dry = migrate.run(self.base, dry=True)
        self.assertTrue(all(s in ("DRY",) for s, _, _ in dry))
        self.assertTrue(os.path.isdir(os.path.join(self.base, "planes")))                         # dry-run no mueve
        items = migrate.run(self.base, backup_dir=self.bak)
        self.assertFalse([i for i in items if i[0] in ("FAIL", "WARN")], items)
        for rel in ("state/planes/P1/plan.json", "state/planes/P1/tareas/T001.json", "state/run/linea.json", "state/sesiones/abc", "state/actual", "config/politica.json"):
            self.assertTrue(os.path.exists(os.path.join(self.base, rel)), rel)
        for rel in ("planes", "run", "sesiones", "actual", "politica.json"):
            self.assertFalse(os.path.exists(os.path.join(self.base, rel)), rel)
        tgz = [f for f in os.listdir(self.bak) if f.startswith("agentic-layout-")]
        self.assertEqual(len(tgz), 1)
        with tarfile.open(os.path.join(self.bak, tgz[0])) as t:
            self.assertIn("planes/P1/plan.json", t.getnames())
        self.assertEqual(oct(os.stat(self.base + "/state").st_mode & 0o777), "0o700")
        self.assertEqual(migrate.run(self.base, backup_dir=self.bak), [("OK", "layout", "el layout ya es config/state/data")])

    def test_se_niega_con_un_plan_activo_y_no_toca_nada(self):
        old_layout(self.base, estado="en_ejecucion")
        items = migrate.run(self.base, backup_dir=self.bak)
        self.assertEqual(items[0][0], "FAIL")
        self.assertIn("P1", items[0][2])
        self.assertTrue(os.path.isdir(os.path.join(self.base, "planes")))
        self.assertFalse(os.path.exists(self.bak))

    def test_no_pisa_lo_nuevo_y_copia_los_archivados_de_shared(self):
        old_layout(self.base)
        w(os.path.join(self.base, "state", "actual"), text="OTRO")
        arch = os.path.join(self.d, "orquestacion", "archivo", "P0", "plan.json")
        w(arch, {"id": "P0"})
        base = os.path.join(self.d, ".arkana", "arkana-agentic")
        os.makedirs(os.path.dirname(base), exist_ok=True)
        os.rename(self.base, base)
        items = migrate.run(base, backup_dir=self.bak)
        self.assertIn(("WARN", "layout-actual", "existen actual y state/actual: no se pisa; revisa a mano"), items)
        with open(os.path.join(base, "state", "actual")) as f:
            self.assertEqual(f.read(), "OTRO")
        self.assertTrue(os.path.exists(os.path.join(base, "data", "archive", "P0", "plan.json")))
        self.assertTrue(os.path.exists(arch))                                                    # el origen en shared no se borra


if __name__ == "__main__":
    unittest.main()
