"""rename.py: el alias de un componente se reescribe en los datos locales de la orquestación; se niega con un plan activo."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import common  # noqa: F401
import state

SCRIPT = os.path.join(state.PLUGIN, "scripts", "lib", "rename.py")


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class TestRename(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="ren-")
        self.base = os.path.join(self.d, "agentic")
        os.makedirs(self.base)
        self.env = dict(os.environ, ARKANA_AGENTIC_DIR=self.base, ARKANA_HOME=self.d)

    def datos(self, estado="completado"):
        wj(os.path.join(self.base, "state/planes/P1/plan.json"), {"id": "P1", "estado": estado, "ramas": {"app": {"nombre": "x"}}})
        wj(os.path.join(self.base, "state/planes/P1/tareas/T001.json"), {"id": "T001", "repo": "app"})
        wj(os.path.join(self.base, "data/archive/P0/tareas/T001.json"), {"id": "T001", "repo": "app"})
        wj(os.path.join(self.base, "data/ledger/plans/P1.json"), {"id": "P1", "componentes": ["app", "api"]})
        wj(os.path.join(self.base, "data/ledger/sessions/s1.json"), {"session_id": "s1", "component": "app"})

    def run_(self, *a):
        return subprocess.run([sys.executable, "-I", SCRIPT, *a], capture_output=True, text=True, env=self.env, timeout=30)

    def test_reescribe_tareas_ramas_archivo_y_libro(self):
        self.datos()
        r = self.run_("--from", "app", "--to", "frontend", "--dry-run")
        self.assertIn("DRY|rename|5 ficheros", r.stdout)
        self.assertEqual(rj(os.path.join(self.base, "state/planes/P1/tareas/T001.json"))["repo"], "app")        # dry-run no escribe
        r = self.run_("--from", "app", "--to", "frontend")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK|rename|5 ficheros", r.stdout)
        self.assertEqual(rj(os.path.join(self.base, "state/planes/P1/tareas/T001.json"))["repo"], "frontend")
        self.assertEqual(rj(os.path.join(self.base, "data/archive/P0/tareas/T001.json"))["repo"], "frontend")
        self.assertEqual(list(rj(os.path.join(self.base, "state/planes/P1/plan.json"))["ramas"]), ["frontend"])
        self.assertEqual(rj(os.path.join(self.base, "data/ledger/plans/P1.json"))["componentes"], ["frontend", "api"])
        self.assertEqual(rj(os.path.join(self.base, "data/ledger/sessions/s1.json"))["component"], "frontend")
        self.assertIn("0 ficheros", self.run_("--from", "app", "--to", "frontend").stdout)                      # idempotente

    def test_se_niega_con_un_plan_activo_y_no_toca_nada(self):
        self.datos("en_ejecucion")
        r = self.run_("--from", "app", "--to", "frontend")
        self.assertEqual(r.returncode, 1)
        self.assertIn("el plan P1 está en_ejecucion", r.stdout)
        self.assertEqual(rj(os.path.join(self.base, "state/planes/P1/tareas/T001.json"))["repo"], "app")


if __name__ == "__main__":
    unittest.main()
