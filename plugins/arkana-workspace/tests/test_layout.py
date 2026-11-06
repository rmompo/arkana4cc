"""Disposición de `.arkana/` (layout.py init): manifiesto inicial con ARKANA, idempotencia, dry-run, precondiciones y secretos."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

import environment as E

sys.path.insert(0, os.path.join(E.SCRIPTS, "lib"))
import layout  # noqa: E402
from arkana_core import locate, manifest  # noqa: E402


def sh(*a, cwd=None):
    subprocess.run(a, cwd=cwd, check=True, capture_output=True, env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


class Lab:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="layout-")
        self.root = os.path.realpath(self.tmp.name)
        self.ws = os.path.join(self.root, "ws")
        self.home_dir = os.path.join(self.root, "home")
        self.arkana = os.path.join(self.ws, "shared")
        os.makedirs(self.home_dir)
        os.makedirs(os.path.join(self.arkana, "plugins"))
        os.makedirs(os.path.join(self.arkana, ".arkana", "core"))
        for alias, _t, carpeta, _s in E.SEED_COMPONENTS:
            os.makedirs(os.path.join(self.ws, carpeta), exist_ok=True)
        self._env = dict(os.environ)
        os.environ.pop("ARKANA_HOME", None)
        os.environ["HOME"] = self.home_dir
        sh("git", "init", "-q", self.arkana)
        sh("git", "remote", "add", "origin", "https://usuario:S3CRETO@host.example/g/shared.git", cwd=self.arkana)
        sh("git", "init", "-q", os.path.join(self.ws, "api"))
        sh("git", "remote", "add", "origin", "https://host.example/g/be.git", cwd=os.path.join(self.ws, "api"))
        return self

    def __exit__(self, *a):
        os.environ.clear(); os.environ.update(self._env)
        self.tmp.cleanup()

    def estado(self, *rel):
        return os.path.join(self.arkana, ".arkana", *rel)


class TestInit(unittest.TestCase):
    def test_crea_manifiesto_solo_con_arkana_local_tools_y_registro(self):
        with Lab() as lab:
            rep = layout.init(lab.arkana, lab.ws)
            self.assertEqual(rep.count("FAIL"), 0, rep.text())
            w = manifest.load(lab.arkana)
            self.assertEqual(w.aliases(), ["arkana"])                               # sin componentes: se dan de alta con components.py add
            self.assertEqual(w.path("arkana"), lab.arkana)
            self.assertEqual(locate.find_home(cwd=lab.arkana), lab.arkana)
            for f in ("arkana.json", "core/workspace.json", "arkana-workspace/local.json", "arkana-workspace/tools.json"):
                self.assertTrue(os.path.isfile(lab.estado(*f.split("/"))), f)
            self.assertFalse(os.path.exists(lab.estado("core", "repos.conf")))     # no hay ficheros del modo antiguo

    def test_seed_de_pruebas_da_de_alta_los_componentes_con_su_remoto(self):
        with Lab() as lab:
            rep = E.seed(lab.arkana, lab.ws)
            self.assertEqual(rep.count("FAIL"), 0, rep.text())
            w = manifest.load(lab.arkana)
            self.assertEqual(w.aliases(), ["arkana", "app", "api", "app-web", "app-ui", "docs", "specs"])
            self.assertEqual(w.path("api"), os.path.join(lab.ws, "api"))
            self.assertEqual(w.path("app-web"), os.path.join(lab.ws, "app/src/web"))
            self.assertEqual(w.get("api")["remote"], "https://host.example/g/be.git")
            self.assertEqual(w.get("api")["remote_host"], "host.example")
            self.assertEqual(locate.find_home(cwd=os.path.join(lab.ws, "api")), lab.arkana)

    def test_las_urls_del_manifiesto_no_llevan_credenciales(self):
        with Lab() as lab:
            layout.init(lab.arkana, lab.ws)
            for f in ("core/workspace.json", "arkana-workspace/local.json"):
                self.assertNotIn("S3CRETO", Path(lab.estado(*f.split("/"))).read_text())
            self.assertEqual(manifest.load(lab.arkana).get("arkana")["remote"], "https://host.example/g/shared.git")

    def test_idempotente_y_no_pisa(self):
        with Lab() as lab:
            layout.init(lab.arkana, lab.ws)
            ws = lab.estado("core", "workspace.json")
            d = json.loads(Path(ws).read_text()); d["workspace"]["name"] = "editado"; Path(ws).write_text(json.dumps(d))
            rep = layout.init(lab.arkana, lab.ws)
            self.assertIn("ya está inicializado", rep.text())
            self.assertEqual(json.loads(Path(ws).read_text())["workspace"]["name"], "editado")
            self.assertEqual(len(locate.read_registry()), 1)

    def test_dry_run_no_escribe_nada(self):
        with Lab() as lab:
            antes = sorted(os.listdir(lab.estado()))
            rep = layout.init(lab.arkana, lab.ws, dry=True)
            self.assertGreaterEqual(rep.count("DRY"), 5)
            self.assertEqual(sorted(os.listdir(lab.estado())), antes)
            self.assertFalse(os.path.exists(locate.registry_path()))

    def test_copia_de_seguridad_antes_de_cambiar(self):
        with Lab() as lab:
            layout.init(lab.arkana, lab.ws)
            bak = os.listdir(lab.estado("arkana-workspace", "bak"))
            self.assertEqual(len(bak), 1); self.assertTrue(bak[0].startswith("layout-"))

    def test_se_niega_con_un_plan_activo(self):
        with Lab() as lab:
            d = lab.estado("arkana-agentic"); os.makedirs(os.path.join(d, "planes", "P1"))
            Path(os.path.join(d, "actual")).write_text("P1")
            Path(os.path.join(d, "planes", "P1", "plan.json")).write_text(json.dumps({"estado": "ejecutando"}))
            rep = layout.init(lab.arkana, lab.ws)
            self.assertEqual(rep.exit_code(), 1); self.assertIn("plan activo", rep.text())
            self.assertFalse(os.path.exists(lab.estado("arkana.json")))
            Path(os.path.join(d, "planes", "P1", "plan.json")).write_text(json.dumps({"estado": "completado"}))
            self.assertEqual(layout.init(lab.arkana, lab.ws).exit_code(), 0)

    def test_se_niega_si_no_es_arkana(self):
        with Lab() as lab:
            os.rmdir(os.path.join(lab.arkana, "plugins"))
            self.assertEqual(layout.init(lab.arkana, lab.ws).exit_code(), 1)

    def test_ya_no_existe_el_modo_antiguo(self):
        self.assertFalse(hasattr(layout, "migrate") or hasattr(layout, "KNOWN") or hasattr(layout, "read_conf"))

    def test_cli_json(self):
        with Lab() as lab:
            r = subprocess.run([sys.executable, "-I", os.path.join(E.SCRIPTS, "lib", "layout.py"), "init", "--dry-run", "--json",
                                "--home", lab.arkana, "--base", lab.ws], capture_output=True, text=True, env=dict(os.environ, HOME=lab.home_dir))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["skill"], "layout-init")


if __name__ == "__main__":
    unittest.main()
