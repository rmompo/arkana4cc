"""orchestrator.py: las reglas del orquestador se inyectan por hook solo en la sesión de ARKANA, nunca en un componente ni en un worker."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import common  # noqa: F401
import state

HOOK = os.path.join(state.PLUGIN, "scripts", "lib", "orchestrator.py")


def run(cwd, env_extra=None, arkana=None):
    env = dict(os.environ, ARKANA_HOME=arkana or "")
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-I", HOOK, "hook"], input=json.dumps({"cwd": cwd, "source": "startup"}), capture_output=True, text=True,
                          env=env, cwd=cwd, timeout=30)


class TestOrchestratorHook(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="orq-")
        self.arkana = os.path.join(self.d, "arkana")
        self.app = os.path.join(self.d, "app")
        os.makedirs(os.path.join(self.arkana, ".arkana"))
        os.makedirs(os.path.join(self.arkana, "sub"))
        os.makedirs(self.app)

    def test_inyecta_las_reglas_en_arkana_y_en_sus_subcarpetas(self):
        for cwd in (self.arkana, os.path.join(self.arkana, "sub")):
            r = run(cwd, arkana=self.arkana)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "SessionStart")
            self.assertIn("Orquestador (arkana-agentic)", out["additionalContext"])
            self.assertIn("agentic.sh", out["additionalContext"])

    def test_no_inyecta_en_un_componente_ni_en_un_worker_ni_fuera_de_un_workspace(self):
        self.assertEqual(run(self.app, arkana=self.arkana).stdout, "")
        self.assertEqual(run(self.arkana, {"ARKANA_WORKER": "1"}, arkana=self.arkana).stdout, "")
        self.assertEqual(run(self.d, arkana="").stdout, "")

    def test_el_hook_esta_declarado_y_no_escribe_ficheros(self):
        with open(os.path.join(state.PLUGIN, "hooks", "hooks.json"), encoding="utf-8") as f:
            self.assertIn("orchestrator.py", f.read())
        run(self.arkana, arkana=self.arkana)
        self.assertEqual(sorted(os.listdir(self.arkana)), [".arkana", "sub"])


if __name__ == "__main__":
    unittest.main()
