"""gitinit.py: git init de la carpeta de ARKANA y su identidad a nivel de repo."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
G = os.path.join(HERE, "..", "scripts", "lib", "gitinit.py")
ENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
ENV.pop("GIT_AUTHOR_EMAIL", None); ENV.pop("GIT_COMMITTER_EMAIL", None)


def run(*a):
    return subprocess.run([sys.executable, "-I", G, *a], capture_output=True, text=True, env=ENV, stdin=subprocess.DEVNULL, timeout=60)


def cfg(d, k):
    return subprocess.run(["git", "-C", d, "config", "--local", k], capture_output=True, text=True, env=ENV).stdout.strip()


class TestGitInit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = os.path.join(os.path.realpath(self.tmp.name), "arkana")
        os.makedirs(self.d)

    def test_inicia_el_repo_y_fija_la_identidad_a_nivel_de_repo(self):
        r = run("--home", self.d, "--name", "Ana Pérez", "--email", "ana@example.org")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.d, ".git")))
        self.assertEqual((cfg(self.d, "user.name"), cfg(self.d, "user.email")), ("Ana Pérez", "ana@example.org"))
        head = subprocess.run(["git", "-C", self.d, "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True, env=ENV).stdout.strip()
        self.assertEqual(head, "main")
        self.assertIn("OK|identidad|Ana Pérez <ana@example.org>", r.stdout)

    def test_sin_identidad_no_la_inventa_y_pide_los_datos(self):
        r = run("--home", self.d)
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(self.d, ".git")))                  # el repo sí se inicia
        self.assertIn("faltan user.name y user.email", r.stdout)
        self.assertEqual(cfg(self.d, "user.email"), "")

    def test_dry_run_no_escribe_nada(self):
        r = run("--home", self.d, "--name", "A", "--email", "a@example.org", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(os.listdir(self.d), [])
        self.assertIn("DRY|git|git init", r.stdout)
        self.assertIn("DRY|identidad|A <a@example.org>", r.stdout)                    # el ensayo no deja una línea vacía

    def test_idempotente_y_conserva_la_identidad_existente(self):
        run("--home", self.d, "--name", "Ana", "--email", "ana@example.org")
        r = run("--home", self.d)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("repo existente", r.stdout)
        self.assertEqual(cfg(self.d, "user.name"), "Ana")
        run("--home", self.d, "--email", "otro@example.org")                          # solo cambia lo que se da
        self.assertEqual((cfg(self.d, "user.name"), cfg(self.d, "user.email")), ("Ana", "otro@example.org"))

    def test_valida_nombre_y_correo(self):
        for args in (["--email", "sin-arroba"], ["--email", "a b@c.d"], ["--name", "  "]):
            self.assertEqual(run("--home", self.d, *args).returncode, 1, args)
        self.assertFalse(os.path.isdir(os.path.join(self.d, ".git")))

    def test_rechaza_una_subcarpeta_de_otro_repo(self):
        subprocess.run(["git", "-C", self.d, "init", "-q"], check=True, env=ENV)
        sub = os.path.join(self.d, "dentro")
        os.makedirs(sub)
        r = run("--home", sub, "--name", "A", "--email", "a@example.org")
        self.assertEqual(r.returncode, 1)
        self.assertIn("pertenece al repo", r.stdout)
        self.assertFalse(os.path.isdir(os.path.join(sub, ".git")))

    def test_carpeta_inexistente_y_rama_propia(self):
        self.assertEqual(run("--home", os.path.join(self.d, "no")).returncode, 1)
        run("--home", self.d, "--name", "A", "--email", "a@example.org", "--branch", "develop")
        self.assertEqual(subprocess.run(["git", "-C", self.d, "symbolic-ref", "--short", "HEAD"], capture_output=True, text=True, env=ENV).stdout.strip(), "develop")

    def test_no_toca_la_configuracion_global(self):
        home = os.path.join(self.d, "..", "home")
        os.makedirs(home)
        run("--home", self.d, "--name", "A", "--email", "a@example.org")
        self.assertEqual(os.listdir(home), [])


if __name__ == "__main__":
    unittest.main()
