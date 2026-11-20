import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "scripts", "lib")
sys.path.insert(0, LIB)
import pipeline  # noqa: E402


def fake_plugin(parent, name, version="1.0.0"):
    d = os.path.join(parent, name, ".claude-plugin")
    os.makedirs(d)
    with open(os.path.join(d, "plugin.json"), "w") as f:
        json.dump({"name": name, "version": version}, f)
    return os.path.join(parent, name)


class Lab:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = os.path.realpath(self.tmp.name)
        self.siblings = os.path.join(t, "plugins"); os.makedirs(self.siblings)
        self.cache = os.path.join(t, "cache"); os.makedirs(self.cache)
        self.repo = os.path.join(t, "repo"); os.makedirs(self.repo)
        subprocess.run(["git", "-C", self.repo, "init", "-q"], check=True)
        self._env = dict(os.environ); os.environ.pop("ARKANA_HOME", None)
        return self

    def __exit__(self, *a):
        os.environ.clear(); os.environ.update(self._env); self.tmp.cleanup()


def marcar_workspace(repo):
    os.makedirs(os.path.join(repo, ".arkana"))
    with open(os.path.join(repo, ".arkana", "arkana.json"), "w") as f:
        f.write("{}")


def instalar_en_cache(lab, version="1.0.0", names=None):
    for n in names or pipeline.REQUIRED:
        d = os.path.join(lab.cache, n, version, ".claude-plugin"); os.makedirs(d)
        with open(os.path.join(d, "plugin.json"), "w") as f:
            json.dump({"name": n, "version": version}, f)


def instalar_hermanos(lab, names=None):
    for n in names or pipeline.REQUIRED:
        fake_plugin(lab.siblings, n)


class TestPlugins(unittest.TestCase):
    def test_hermanos_tienen_prioridad_sobre_la_cache(self):
        with Lab() as lab:
            instalar_hermanos(lab); instalar_en_cache(lab)
            r = pipeline.plugin_root("arkana-todo", lab.siblings, lab.cache)
            self.assertEqual(r, os.path.join(lab.siblings, "arkana-todo"))

    def test_cache_elige_la_version_mas_reciente_numericamente(self):
        with Lab() as lab:
            for v in ("1.9.0", "1.10.0", "1.2.0"):
                instalar_en_cache(lab, v, ["arkana-todo"])
            r = pipeline.plugin_root("arkana-todo", lab.siblings, lab.cache)
            self.assertTrue(r.endswith(os.path.join("arkana-todo", "1.10.0")))

    def test_plugin_ausente(self):
        with Lab() as lab:
            self.assertIsNone(pipeline.plugin_root("arkana-todo", lab.siblings, lab.cache))

    def test_falta_un_plugin_es_fail_con_la_orden_de_instalacion(self):
        with Lab() as lab:
            instalar_en_cache(lab, names=[n for n in pipeline.REQUIRED if n != "arkana-todo"])
            res = pipeline.plan(lab.repo, lab.repo, lab.siblings, lab.cache)
            self.assertEqual(pipeline.exit_code(res), 1)
            fails = [x for x in res["status"] if x[0] == "FAIL"]
            self.assertEqual(len(fails), 1)
            self.assertIn("/plugin install arkana-todo@arkana", fails[0][2])
            self.assertNotIn("todo", [s["id"] for s in res["steps"]])


class TestHome(unittest.TestCase):
    def test_sin_workspace_usa_la_raiz_git(self):
        with Lab() as lab:
            sub = os.path.join(lab.repo, "a", "b"); os.makedirs(sub)
            home, existe = pipeline.find_home(None, sub)
            self.assertEqual(home, lab.repo); self.assertFalse(existe)

    def test_con_workspace_lo_encuentra_desde_una_subcarpeta(self):
        with Lab() as lab:
            marcar_workspace(lab.repo)
            sub = os.path.join(lab.repo, "x"); os.makedirs(sub)
            self.assertEqual(pipeline.find_home(None, sub), (lab.repo, True))

    def test_env_y_argumento(self):
        with Lab() as lab:
            os.environ["ARKANA_HOME"] = lab.repo
            self.assertEqual(pipeline.find_home(None, "/")[0], lab.repo)
            self.assertEqual(pipeline.find_home(lab.siblings, "/")[0], lab.siblings)

    def test_fuera_de_un_repo_no_hay_home(self):
        with Lab() as lab:
            fuera = os.path.join(lab.siblings)
            res = pipeline.plan(None, fuera, lab.siblings, lab.cache)
            if res["home"] is None:
                self.assertEqual(pipeline.exit_code(res), 1)


class TestPasos(unittest.TestCase):
    def plan(self, lab):
        instalar_en_cache(lab)
        return pipeline.plan(lab.repo, lab.repo, lab.siblings, lab.cache)

    def test_orden_de_los_pasos(self):
        with Lab() as lab:
            ids = [s["id"] for s in self.plan(lab)["steps"]]
            self.assertEqual(ids, ["layout", "evolve", "statusline", "messaging", "agentic", "knowledge", "todo",
                                   "permisos", "credenciales", "herramientas", "verificacion"])

    def test_ensayo_solo_en_los_pasos_que_escriben(self):
        with Lab() as lab:
            for s in self.plan(lab)["steps"]:
                if s["id"] in ("credenciales", "herramientas", "verificacion"):
                    self.assertNotIn("--dry-run", s["dry"]); self.assertEqual(s["dry"], s["apply"])
                else:
                    self.assertTrue(s["dry"].endswith("--dry-run")); self.assertNotIn("--dry-run", s["apply"])

    def test_ordenes_con_rutas_absolutas_y_arkana_home(self):
        with Lab() as lab:
            res = self.plan(lab)
            for s in res["steps"]:
                self.assertIn(f"ARKANA_HOME={lab.repo}", s["apply"])
                self.assertIn(os.path.join(lab.cache, s["plugin"]), s["apply"])

    def test_ruta_con_espacios_se_entrecomilla(self):
        with Lab() as lab:
            instalar_en_cache(lab)
            raro = os.path.join(lab.siblings, "mi repo"); os.makedirs(raro)
            subprocess.run(["git", "-C", raro, "init", "-q"], check=True)
            res = pipeline.plan(raro, raro, lab.siblings, lab.cache)
            self.assertIn(f"'{raro}'", res["steps"][0]["apply"])

    def test_nuevo_o_existente(self):
        with Lab() as lab:
            res = self.plan(lab)
            self.assertTrue(res["new_workspace"]); self.assertIn(("INFO", "home"), [tuple(x[:2]) for x in res["status"]])
            marcar_workspace(lab.repo)
            res = pipeline.plan(lab.repo, lab.repo, lab.siblings, lab.cache)
            self.assertFalse(res["new_workspace"]); self.assertEqual(pipeline.exit_code(res), 0)

    def test_no_escribe_nada(self):
        with Lab() as lab:
            self.plan(lab)
            self.assertEqual(sorted(os.listdir(lab.repo)), [".git"])


class TestCli(unittest.TestCase):
    def test_json_y_salida_de_texto(self):
        with Lab() as lab:
            env = dict(os.environ, HOME=lab.tmp.name, ARKANA_HOME=lab.repo)
            r = subprocess.run([sys.executable, "-I", os.path.join(LIB, "pipeline.py"), "plan", "--json"],
                               capture_output=True, text=True, env=env, cwd=lab.repo)
            data = json.loads(r.stdout)
            self.assertEqual(r.returncode, 0)  # los plugins hermanos del repo están presentes
            self.assertEqual(data["home"], lab.repo)
            r = subprocess.run([sys.executable, "-I", os.path.join(LIB, "pipeline.py"), "plan"], capture_output=True, text=True, env=env, cwd=lab.repo)
            self.assertTrue(all(l.split("|")[0] in ("OK", "INFO", "WARN", "FAIL", "PASO") for l in r.stdout.splitlines()))


if __name__ == "__main__":
    unittest.main()
