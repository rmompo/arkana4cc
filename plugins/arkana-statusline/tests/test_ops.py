"""install / check / fix de la statusline con HOME falso: la statusLine ajena solo se sustituye con --replace."""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

import lab as L
from lab import Lab

OPS = os.path.join(L.PLUGIN, "scripts", "lib", "ops.py")


def ops(lab, *a):
    return subprocess.run([sys.executable, "-I", OPS, *a], capture_output=True, text=True, env=lab.env, timeout=60, stdin=subprocess.DEVNULL)


def settings(lab):
    with open(os.path.join(lab.home, ".claude", "settings.json")) as f:
        return json.load(f)


class TestOps(unittest.TestCase):
    def test_install_copia_activa_y_hace_humo_y_es_idempotente(self):
        with Lab() as lab:
            self.assertIn("WARN|instalada", ops(lab, "check").stdout)
            dry = ops(lab, "install", "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.home, ".claude", "arkana-statusline")))
            r = ops(lab, "install")
            self.assertEqual(r.returncode, 0, r.stdout)
            dest = os.path.join(lab.home, ".claude", "arkana-statusline")
            for f in ("statusline.sh", "statusline.py", "arkana_core/manifest.py", "arkana_core/locate.py"):
                self.assertTrue(os.path.isfile(os.path.join(dest, f)), f)
            self.assertNotIn("tests", os.listdir(os.path.join(dest, "arkana_core")))
            s = settings(lab)
            self.assertEqual(s["statusLine"], {"type": "command", "command": "bash ~/.claude/arkana-statusline/statusline.sh"})
            self.assertTrue(s["enabledPlugins"]["arkana-statusline@arkana"])
            self.assertIn("OK|humo", r.stdout)
            c = ops(lab, "check")
            for ok in ("OK|copia", "OK|statusline", "OK|otros-plugins", "OK|humo"):
                self.assertIn(ok, c.stdout)
            self.assertIn("copia al día", ops(lab, "install").stdout)
            # la copia instalada funciona sola, sin el plugin ni el árbol
            out = subprocess.run(["bash", os.path.join(dest, "statusline.sh")], input=json.dumps({"workspace": {"project_dir": lab.path("app")}, "model": {"display_name": "M"}}),
                                 capture_output=True, text=True, env=dict(lab.env, COLUMNS="150"))
            self.assertIn("ARKANA", out.stdout)

    def test_otra_statusline_solo_se_sustituye_con_replace_y_con_copia(self):
        with Lab() as lab:
            sj = os.path.join(lab.home, ".claude", "settings.json")
            with open(sj, "w") as f:
                json.dump({"statusLine": {"type": "command", "command": "bash ~/.claude/statusline-command.sh"}, "enabledPlugins": {"otra-statusline@x": True}, "theme": "dark"}, f)
            r = ops(lab, "install")
            self.assertIn("WARN|statusline", r.stdout)
            self.assertIn("--replace", r.stdout)
            self.assertIn("statusline-command.sh", settings(lab)["statusLine"]["command"])         # no se pisó
            self.assertIn("WARN|otros-plugins", ops(lab, "check").stdout)
            f = ops(lab, "fix")
            self.assertIn("statusline-command.sh", settings(lab)["statusLine"]["command"])         # fix tampoco sustituye la ajena
            r = ops(lab, "install", "--replace")
            self.assertEqual(r.returncode, 0, r.stdout)
            s = settings(lab)
            self.assertIn("arkana-statusline/statusline.sh", s["statusLine"]["command"])
            self.assertEqual(s["theme"], "dark")                                                   # lo demás se conserva
            bak = os.path.join(lab.home, ".claude", "arkana-statusline", "bak")
            self.assertTrue(any(f.startswith("settings.json.") for f in os.listdir(bak)))
            with open(os.path.join(bak, os.listdir(bak)[0])) as fh:
                self.assertIn("statusline-command.sh", fh.read())

    def test_fix_reinstala_lo_desactualizado(self):
        with Lab() as lab:
            ops(lab, "install")
            py = os.path.join(lab.home, ".claude", "arkana-statusline", "statusline.py")
            with open(py, "a") as f:
                f.write("\n# alterado\n")
            self.assertIn("WARN|copia", ops(lab, "check").stdout)
            self.assertEqual(ops(lab, "fix", "--dry-run").returncode, 0)
            self.assertIn("# alterado", Path(py).read_text())
            r = ops(lab, "fix")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("# alterado", Path(py).read_text())
            self.assertIn("OK|copia", ops(lab, "check").stdout)


if __name__ == "__main__":
    unittest.main()
