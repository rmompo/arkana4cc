"""install: carpetas config/state/data y plugin habilitado (HOME falso); no escribe nada en los repos."""
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

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old)

    def repo_files(self):
        return sorted(f for f in os.listdir(self.shared) if f != ".arkana")

    def test_install_aplica_todo_es_idempotente_y_no_escribe_en_el_repo(self):
        dry = install.run(dry=True)
        self.assertTrue(all(s in ("DRY", "OK") for s, _, _ in dry), dry)
        self.assertFalse(os.path.isdir(os.path.join(state.base_dir(), "state")))
        items = install.run()
        self.assertFalse([i for i in items if i[0] in ("FAIL", "WARN")], items)
        for d in ("config", "state", "data"):
            self.assertEqual(oct(os.stat(os.path.join(state.base_dir(), d)).st_mode & 0o777), "0o700")
        with open(os.path.join(os.environ["HOME"], ".claude", "settings.json")) as f:
            self.assertTrue(json.load(f)["enabledPlugins"]["arkana-agentic@arkana"])
        self.assertEqual(self.repo_files(), [])                                       # ni CLAUDE.md ni ARKANA.local.md: nada en el repo
        again = install.run()
        self.assertIn(("OK", "carpetas", "config, state y data presentes"), again)
        self.assertIn(("OK", "plugin", "arkana-agentic@arkana habilitado"), again)
        self.assertEqual(self.repo_files(), [])


if __name__ == "__main__":
    unittest.main()
