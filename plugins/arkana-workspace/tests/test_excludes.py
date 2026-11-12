"""excludes.py: lo que Arkana y el editor crean en un repo de trabajo se excluye en `.git/info/exclude`, nunca en `.gitignore`."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

CLI = os.path.join(E.SCRIPTS, "lib", "excludes.py")


def cli(lab, *a):
    return subprocess.run([sys.executable, "-I", CLI, *a, "--home", lab.arkana], capture_output=True, text=True, env=lab.env, cwd=lab.ws,
                          stdin=subprocess.DEVNULL, timeout=60)


def init(path):
    subprocess.run(["git", "init", "-q", path], check=True)
    subprocess.run(["git", "-C", path, "config", "core.excludesFile", "/dev/null"], check=True)     # que el global del usuario no tape nada


def leer(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class TestExcludes(unittest.TestCase):
    def test_apply_escribe_en_info_exclude_y_no_toca_el_gitignore(self):
        with TC.CLab() as lab:
            app = os.path.join(lab.ws, "app")
            init(app)
            self.assertIn("WARN|excludes-app|sin ignorar: .claude/, .claude-session/, ARKANA.local.md", cli(lab, "status", "--component", "app").stdout)
            r = cli(lab, "apply", "--component", "app", "--dry-run")
            self.assertIn("DRY|excludes-app|.claude/: se añadiría", r.stdout)
            self.assertNotIn(".claude", leer(os.path.join(app, ".git", "info", "exclude")) if os.path.exists(os.path.join(app, ".git", "info", "exclude")) else "")
            r = cli(lab, "apply", "--component", "app")
            self.assertEqual(r.returncode, 0, r.stdout)
            ex = leer(os.path.join(app, ".git", "info", "exclude"))
            for pat in (".claude/", ".claude-session/", "ARKANA.local.md"):
                self.assertIn(pat, ex)
            self.assertFalse(os.path.exists(os.path.join(app, ".gitignore")))                      # el .gitignore del repo no se toca ni se crea
            for pat in (".claude/x", ".claude-session/x", "ARKANA.local.md"):
                self.assertEqual(subprocess.run(["git", "-C", app, "check-ignore", "-q", pat]).returncode, 0, pat)
            self.assertIn("nada que añadir", cli(lab, "apply", "--component", "app").stdout)         # idempotente
            self.assertEqual(ex, leer(os.path.join(app, ".git", "info", "exclude")))

    def test_solo_anade_lo_que_no_cubre_ya_otra_via(self):
        with TC.CLab() as lab:
            api = os.path.join(lab.ws, "api")
            init(api)
            with open(os.path.join(api, ".gitignore"), "w") as f:
                f.write(".claude/\n")
            r = cli(lab, "apply", "--component", "api")
            self.assertNotIn(".claude/: añadido", r.stdout)
            self.assertIn(".claude-session/: añadido", r.stdout)
            self.assertEqual(leer(os.path.join(api, ".gitignore")), ".claude/\n")

    def test_una_carpeta_que_no_es_repo_avisa(self):
        with TC.CLab() as lab:
            r = cli(lab, "status", "--component", "docs")
            self.assertIn("WARN|excludes-docs|no es un repositorio git", r.stdout)
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
