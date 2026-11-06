"""install: carpetas config/state/data, bloque arkana:agentic en el CLAUDE.md de ARKANA, referencia antigua y plugin habilitado (HOME falso)."""
import json
import os
import tempfile
import unittest

import common  # noqa: F401
import install
import state


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="inst-")
        self.shared = os.path.join(self.d, "shared")
        os.makedirs(os.path.join(self.shared, ".arkana"))
        self.old = dict(os.environ)
        os.environ.update(ARKANA_HOME=self.shared, HOME=os.path.join(self.d, "home"), ARKANA_AGENTIC_DIR=os.path.join(self.shared, ".arkana", "arkana-agentic"))
        os.makedirs(os.environ["HOME"])
        self.cm = os.path.join(self.shared, "CLAUDE.md")
        with open(self.cm, "w", encoding="utf-8") as f:
            f.write("# shared\n\n- Orquestación multi-repo (`/arkana-agentic:*`): reglas del orquestador en @orquestacion/ORQUESTADOR.md.\n")

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old)

    def read(self):
        with open(self.cm, encoding="utf-8") as f:
            return f.read()

    def test_install_aplica_todo_y_es_idempotente(self):
        self.assertEqual(install.block_state(), "SIN-BLOQUE")
        dry = install.run(dry=True)
        self.assertTrue(all(s in ("DRY", "OK") for s, _, _ in dry), dry)
        self.assertNotIn("arkana:agentic", self.read())
        self.assertFalse(os.path.isdir(os.path.join(state.base_dir(), "state")))
        items = install.run()
        self.assertFalse([i for i in items if i[0] in ("FAIL", "WARN")], items)
        t = self.read()
        self.assertEqual(t.count("<!-- arkana:agentic:start -->"), 1)
        self.assertIn("Orquestador (arkana-agentic)", t)
        self.assertNotIn("@orquestacion/ORQUESTADOR.md", t)
        self.assertIn("bloque `arkana:agentic`", t)
        for d in ("config", "state", "data"):
            self.assertEqual(oct(os.stat(os.path.join(state.base_dir(), d)).st_mode & 0o777), "0o700")
        with open(os.path.join(os.environ["HOME"], ".claude", "settings.json")) as f:
            self.assertTrue(json.load(f)["enabledPlugins"]["arkana-agentic@arkana"])
        self.assertEqual(install.block_state(), "OK")
        antes = self.read()
        again = install.run()
        self.assertEqual(self.read(), antes)
        self.assertIn(("OK", "bloque", "bloque arkana:agentic igual en CLAUDE.md"), again)

    def test_sin_claude_md_avisa_y_no_lo_crea(self):
        os.remove(self.cm)
        items = install.run(no_settings=True)
        self.assertEqual([i for i in items if i[1] == "bloque"][0][0], "WARN")
        self.assertFalse(os.path.exists(self.cm))


if __name__ == "__main__":
    unittest.main()
