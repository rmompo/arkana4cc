"""El pipeline de /arkana:install deja TODO el andamiaje de Arkana en su repo: carpetas finales con .gitkeep (para que git las versione) y arkana-incoming/ con su .gitignore.
Integración con los plugins reales de este repo (git, layout, evolve y knowledge) en una carpeta y un HOME temporales."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts", "lib"))
import pipeline  # noqa: E402

CARPETAS_FINALES = ["arkana-incoming", "arkana-knowledge", "arkana-docs/src", "arkana-docs/md", "arkana-docs/out"]
PASOS = ("git", "layout", "evolve", "knowledge")


class TestAndamiaje(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        t = os.path.realpath(self.tmp.name)
        self.home, self.repo = os.path.join(t, "home"), os.path.join(t, "ws", "arkana")
        os.makedirs(self.home); os.makedirs(self.repo)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("ARKANA_")}
        self.env.update(HOME=self.home, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")

    def instalar(self):
        old = dict(os.environ)
        os.environ.update(HOME=self.home)
        try:
            plan = pipeline.plan(self.repo, self.repo)
        finally:
            os.environ.clear(); os.environ.update(old)
        self.assertEqual(pipeline.exit_code(plan), 0, plan["status"])
        for st in plan["steps"]:
            if st["id"] in PASOS:
                extra = " --name Ana --email ana@example.org" if st["id"] == "git" else ""
                r = subprocess.run(["bash", "-c", st["apply"] + extra], capture_output=True, text=True, env=self.env, cwd=self.repo, stdin=subprocess.DEVNULL, timeout=120)
                self.assertEqual(r.returncode, 0, (st["id"], r.stdout, r.stderr))

    def git(self, *a):
        return subprocess.run(["git", "-C", self.repo, *a], capture_output=True, text=True, env=self.env).stdout

    def test_cada_carpeta_final_lleva_su_gitkeep_y_git_las_versionaria(self):
        self.instalar()
        versionables = self.git("add", "-A", "-n").splitlines()
        for d in CARPETAS_FINALES:
            self.assertTrue(os.path.isfile(os.path.join(self.repo, d, ".gitkeep")), d)
            self.assertTrue(any(f"{d}/.gitkeep" in l for l in versionables), f"git no versionaría {d}/")

    def test_arkana_incoming_ignora_su_contenido_salvo_gitignore_y_gitkeep(self):
        self.instalar()
        with open(os.path.join(self.repo, "arkana-incoming", ".gitignore"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "*\n!.gitignore\n!.gitkeep\n")
        with open(os.path.join(self.repo, "arkana-incoming", "informe.pdf"), "w") as f:
            f.write("x")
        versionables = self.git("add", "-A", "-n")
        self.assertIn("arkana-incoming/.gitignore", versionables); self.assertIn("arkana-incoming/.gitkeep", versionables)
        self.assertNotIn("informe.pdf", versionables)

    def test_solo_las_carpetas_finales_llevan_gitkeep_y_lo_local_no_se_versiona(self):
        self.instalar()
        self.assertFalse(os.path.exists(os.path.join(self.repo, "arkana-docs", ".gitkeep")))          # arkana-docs/ solo agrupa
        versionables = self.git("add", "-A", "-n")
        self.assertNotIn(".arkana/", versionables)                                                      # el estado local y .credentials nunca
        self.assertIn(".gitignore", versionables); self.assertIn("arkana-project.json", versionables)

    def test_repetir_la_instalacion_no_cambia_nada(self):
        self.instalar()
        antes = self.git("status", "--porcelain", "-uall")
        self.instalar()
        self.assertEqual(self.git("status", "--porcelain", "-uall"), antes)

    def test_el_diagnostico_de_conocimiento_no_echa_en_falta_ninguna_carpeta(self):
        self.instalar()
        plan = pipeline.plan(self.repo, self.repo)
        k = next(s for s in plan["steps"] if s["id"] == "knowledge")["apply"].replace(" install", " validate")
        r = subprocess.run(["bash", "-c", k], capture_output=True, text=True, env=self.env, cwd=self.repo, stdin=subprocess.DEVNULL, timeout=60)
        self.assertNotIn("WARN|carpeta", r.stdout, r.stdout)


if __name__ == "__main__":
    unittest.main()
