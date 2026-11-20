"""arkana-evolve: motor de migraciones y migración 0001. Sin red ni API real; un ARKANA temporal con git y HOME falso."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
CLI = os.path.join(PLUGIN, "scripts", "lib", "evolve.py")
GENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@x",
            GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@x", GIT_TERMINAL_PROMPT="0")
UUID_RX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, env=GENV)


class Lab:
    """root/ws/arkana (repo git con .arkana/{arkana.json, core/workspace.json}) y root/ws/api; HOME falso."""

    def __init__(self, with_git=True):
        self.with_git = with_git

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="evolve-")
        self.root = os.path.realpath(self.tmp.name)
        self.home = os.path.join(self.root, "home")
        self.arkana = os.path.join(self.root, "ws", "arkana")
        os.makedirs(self.home)
        os.makedirs(os.path.join(self.arkana, ".arkana", "core"))
        os.makedirs(os.path.join(self.root, "ws", "api"))
        self.write(".arkana/arkana.json", {"schema_version": 1, "workspace": {"name": "demo"}, "root": ".."})
        self.write(".arkana/core/workspace.json", self.manifest(["api"]))
        if self.with_git:
            git(self.arkana, "init", "-q", "-b", "main")
        self.env = dict(GENV, HOME=self.home, ARKANA_HOME=self.arkana)
        return self

    def __exit__(self, *a):
        self.tmp.cleanup()

    @staticmethod
    def manifest(aliases):
        return {"schema": 1, "workspace": {"name": "demo"}, "arkana": {"alias": "ARKANA", "path": "arkana"},
                "components": [{"alias": a, "type": "generic", "path": a} for a in aliases]}

    def write(self, rel, obj):
        p = os.path.join(self.arkana, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            if isinstance(obj, str):
                f.write(obj)
            else:
                json.dump(obj, f, indent=2)
        return p

    def read(self, rel):
        with open(os.path.join(self.arkana, rel), encoding="utf-8") as f:
            return f.read()

    def project(self):
        return json.loads(self.read("arkana-project.json"))

    def run(self, *args, env=None, cwd=None):
        return subprocess.run([sys.executable, CLI, *args], capture_output=True, text=True, env=env or self.env, cwd=cwd or self.root,
                              stdin=subprocess.DEVNULL, timeout=60)


class TestCheck(unittest.TestCase):
    def test_instalacion_nueva_avisa_de_la_migracion_pendiente_sin_fallar(self):
        with Lab() as lab:
            r = lab.run("check")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("WARN|layout|el repo está en layout 0", r.stdout)
            self.assertIn("WARN|0001|pendiente", r.stdout)

    def test_check_no_admite_dry_run(self):
        with Lab() as lab:
            self.assertEqual(lab.run("check", "--dry-run").returncode, 2)

    def test_repo_por_delante_de_la_instalacion(self):
        with Lab() as lab:
            lab.run("apply")
            p = lab.project()
            p["layout"] = 99
            lab.write("arkana-project.json", p)
            r = lab.run("check")
            self.assertIn("WARN|layout|el repo está en layout 99", r.stdout)
            self.assertIn("actualiza arkana-evolve", r.stdout)

    def test_check_avisa_si_lo_aplicado_se_ha_estropeado(self):
        with Lab() as lab:
            lab.run("apply")
            p = lab.project()
            p["components"].append({"id": p["components"][0]["id"], "alias": "api"})        # UUID repetido
            lab.write("arkana-project.json", p)
            r = lab.run("check")
            self.assertIn("WARN|0001|aplicada, pero", r.stdout)
            self.assertIn("UUID repetidos", r.stdout)

    def test_sin_workspace_sale_con_3(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(GENV, HOME=d)
            env.pop("ARKANA_HOME", None)
            self.assertEqual(lab_run_sin_workspace(env, d), 3)


def lab_run_sin_workspace(env, cwd):
    return subprocess.run([sys.executable, CLI, "check"], capture_output=True, text=True, env=env, cwd=cwd, stdin=subprocess.DEVNULL, timeout=60).returncode


class TestApply0001(unittest.TestCase):
    def test_dry_run_no_escribe_nada(self):
        with Lab() as lab:
            r = lab.run("apply", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("DRY|registro|arkana-project.json se crearía", r.stdout)
            self.assertEqual(sorted(os.listdir(lab.arkana)), [".arkana", ".git"])
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana", "arkana-evolve")))
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana", "arkana-workspace", "bak")))

    def test_apply_crea_el_registro_con_uuid_y_las_carpetas_fijas(self):
        with Lab() as lab:
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            p = lab.project()
            self.assertEqual((p["schema_version"], p["layout"]), (1, 7))                                     # 0001 crea el registro y el motor sube el sello con cada migración
            self.assertTrue(UUID_RX.match(p["workspace"]["id"]))
            self.assertEqual([c["alias"] for c in p["components"]], ["arkana", "api"])
            ids = [c["id"] for c in p["components"]]
            self.assertTrue(all(UUID_RX.match(i) for i in ids) and len(set(ids)) == 2)
            for rel in ("arkana-incoming/.gitkeep", "arkana-incoming/.gitignore", "arkana-knowledge/.gitkeep", "arkana-docs/.gitkeep", "arkana-docs/md/.gitkeep"):
                self.assertTrue(os.path.isfile(os.path.join(lab.arkana, rel)), rel)
            self.assertEqual(lab.read("arkana-incoming/.gitignore"), "*\n!.gitignore\n!.gitkeep\n")
            bak = os.path.join(lab.arkana, ".arkana", "arkana-workspace", "bak")
            copias = [f for f in os.listdir(bak) if f.startswith("evolve-")]
            self.assertEqual(len(copias), 1)
            self.assertEqual(oct(os.stat(os.path.join(bak, copias[0])).st_mode & 0o777), "0o600")
            st = json.loads(lab.read(".arkana/arkana-evolve/state.json"))
            self.assertEqual([e["id"] for e in st["applied"]], ["0001"])

    def test_el_gitignore_interno_deja_versionar_solo_el_gitkeep(self):
        with Lab() as lab:
            lab.run("apply")
            with open(os.path.join(lab.arkana, "arkana-incoming", "informe.pdf"), "wb") as f:
                f.write(b"%PDF-1.4")
            git(lab.arkana, "add", "-A")
            versionados = git(lab.arkana, "ls-files").stdout.split()
            self.assertIn("arkana-incoming/.gitkeep", versionados)
            self.assertIn("arkana-incoming/.gitignore", versionados)
            self.assertNotIn("arkana-incoming/informe.pdf", versionados)
            self.assertEqual(git(lab.arkana, "check-ignore", "-q", "arkana-incoming/informe.pdf").returncode, 0)

    def test_idempotente_y_no_regenera_uuid(self):
        with Lab() as lab:
            lab.run("apply")
            antes = lab.read("arkana-project.json")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0)
            self.assertIn("nada que hacer", r.stdout)
            self.assertEqual(lab.read("arkana-project.json"), antes)
            self.assertIn("OK|0001|aplicada", lab.run("check").stdout)

    def test_no_pisa_lo_que_ya_existe(self):
        with Lab() as lab:
            lab.write("arkana-incoming/nota.txt", "ya había algo")
            lab.write("arkana-docs/.gitkeep", "")
            lab.write("arkana-incoming/.gitignore", "*.tmp\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(lab.read("arkana-incoming/nota.txt"), "ya había algo")
            self.assertEqual(lab.read("arkana-incoming/.gitignore"), "*.tmp\n")
            self.assertIn("WARN|carpetas|arkana-incoming/.gitignore existe con otro contenido", r.stdout)

    def test_segunda_persona_no_regenera_uuid_y_avisa_de_alias_sin_registrar(self):
        with Lab() as lab:
            lab.run("apply")
            antes = lab.project()
            os.remove(os.path.join(lab.arkana, ".arkana", "arkana-evolve", "state.json"))       # un clon: el repo ya trae el registro, el estado local no
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api", "docs"]))               # y su manifiesto local tiene una pieza más
            self.assertIn("WARN|0001|pendiente", lab.run("check").stdout)
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("no se regeneran UUID", r.stdout)
            self.assertIn("alias del manifiesto local que no están en el registro: docs", r.stdout)
            ahora = lab.project()
            self.assertEqual(ahora["components"][:len(antes["components"])], antes["components"])      # los UUID de siempre no cambian
            self.assertEqual([c["alias"] for c in ahora["components"]][-1], "docs")                       # y la 0003 da de alta lo que faltaba
            self.assertIn("OK|0001|aplicada", lab.run("check").stdout)

    def test_to_limita_las_numericas_y_valida_el_argumento(self):
        with Lab() as lab:
            r = lab.run("apply", "--to", "0")
            self.assertIn("nada que hacer", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "arkana-project.json")))
            self.assertEqual(lab.run("apply", "--to", "abc").returncode, 2)
            self.assertEqual(lab.run("apply", "--to", "1").returncode, 0)
            self.assertTrue(os.path.exists(os.path.join(lab.arkana, "arkana-project.json")))

    def test_sin_git_las_migraciones_compartidas_se_niegan(self):
        with Lab(with_git=False) as lab:
            r = lab.run("apply")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertIn("no es un repositorio git", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "arkana-project.json")))

    def test_cambios_sin_commitear_en_lo_que_se_va_a_escribir_se_niegan(self):
        with Lab() as lab:
            lab.write("arkana-docs/.gitkeep", "")
            git(lab.arkana, "add", "-A"); git(lab.arkana, "commit", "-q", "-m", "base")
            lab.write("arkana-docs/.gitkeep", "modificado a mano")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertIn("cambios sin commitear", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "arkana-project.json")))

    def test_json_sigue_el_contrato_de_salida(self):
        with Lab() as lab:
            d = json.loads(lab.run("apply", "--json").stdout)
            self.assertEqual((d["plugin"], d["skill"], d["status"]), ("arkana-evolve", "apply", "ok"))
            self.assertEqual(set(d["summary"]), {"fail", "warn", "ok", "info", "dry"})
            self.assertTrue(all({"id", "status", "detail"} <= set(i) for i in d["items"]))

    def test_nunca_hace_commit_ni_toca_el_home_del_usuario(self):
        with Lab() as lab:
            lab.run("apply")
            self.assertEqual(git(lab.arkana, "rev-list", "--all", "--count").stdout.strip(), "0")
            self.assertEqual(os.listdir(lab.home), [])


class TestMotor(unittest.TestCase):
    MOD = ("ID = {id!r}\nTITLE = 't'\nSCOPE = ('local',)\ndef touches(ctx): return []\ndef detect(ctx): return False\n"
           "def apply(ctx, rep): pass\ndef verify(ctx): return []\n")

    def setUp(self):
        sys.path.insert(0, os.path.join(PLUGIN, "scripts", "lib"))
        sys.path.insert(0, os.path.join(PLUGIN, "scripts", "_core"))
        import evolve
        self.evolve = evolve
        self.d = tempfile.mkdtemp(prefix="evolve-mig-")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def put(self, name, body):
        with open(os.path.join(self.d, name), "w", encoding="utf-8") as f:
            f.write(body)

    def test_las_de_base_van_antes_que_las_numericas_y_estas_en_orden(self):
        self.put("m0010_z.py", self.MOD.format(id="0010"))
        self.put("m0002_y.py", self.MOD.format(id="0002"))
        self.put("b002_b.py", self.MOD.format(id="b002"))
        self.put("b001_a.py", self.MOD.format(id="b001"))
        self.put("notas.txt", "no es una migración")
        orden = [m.ID for m in self.evolve.load_migrations(self.d)]
        self.assertEqual(orden, ["b001", "b002", "0002", "0010"])
        self.assertEqual(self.evolve.latest_layout(self.evolve.load_migrations(self.d)), 10)

    def test_una_migracion_incompleta_se_rechaza(self):
        self.put("m0001_mal.py", "ID = '0001'\nTITLE = 'x'\n")
        with self.assertRaises(self.evolve.EError):
            self.evolve.load_migrations(self.d)

    def test_las_migraciones_reales_declaran_todo_y_sus_ids_son_unicos(self):
        mods = self.evolve.load_migrations()
        ids = [m.ID for m in mods]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("0001", ids)


if __name__ == "__main__":
    unittest.main()
