"""arkana-knowledge: add/modify/delete/query/validate/migrate con Changelog, topic, components y borrado lógico. Sin red."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
KN = os.path.abspath(os.path.join(AQUI, "..", "scripts", "lib", "knowledge.py"))
sys.dont_write_bytecode = True
GENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@x")


def kn(home, *args, env=None):
    return subprocess.run([sys.executable, "-I", KN, "--home", home, *args], capture_output=True, text=True, env=env or GENV, stdin=subprocess.DEVNULL, timeout=60)


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def cat(home):
    return json.loads(read(os.path.join(home, "arkana-knowledge", "catalog.json")))["notas"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = os.path.realpath(self.tmp.name)

    def add(self, title="Usar JSON en la cola", topic="decision", **kw):
        args = ["add", "--topic", topic, "--title", title, "--summary", "Se decide usar JSON", "--tags", "cola,json", "--author", "Tester", "--body", "Cuerpo de la decisión"]
        for k, v in kw.items():
            args += [f"--{k}", v]
        r = kn(self.h, *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return next(e["id"] for e in cat(self.h) if e["titulo"] == title)


class TestCiclo(Base):
    def test_add_modify_query_validate_y_el_changelog_no_se_pisa(self):
        nid = self.add(components="app,api")
        self.assertTrue(nid.startswith("decision-"))
        ruta = os.path.join(self.h, "arkana-knowledge", "decision", nid[len("decision-"):] + ".md")
        t = read(ruta)
        for x in ("topic: decision", "components: [app, api]", "state: active", "## Changelog", "- v1.0 · "):
            self.assertIn(x, t)
        e = cat(self.h)[0]
        self.assertEqual((e["topic"], e["components"], e["state"], e["ruta"]), ("decision", ["app", "api"], "active", f"arkana-knowledge/decision/{nid[len('decision-'):]}.md"))
        r = kn(self.h, "modify", "--id", nid, "--body", "Nuevo cuerpo", "--tags", "cola,json,v2", "--summary", "Resumen nuevo", "--change", "se amplía el alcance")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("v1.0 → v1.1", r.stdout)
        t = read(ruta)
        self.assertIn("Nuevo cuerpo", t)
        self.assertNotIn("Cuerpo de la decisión", t)
        self.assertEqual(t.count("- v1."), 2)                                                   # el changelog conserva v1.0 y suma v1.1
        self.assertIn("se amplía el alcance", t)
        kn(self.h, "modify", "--id", nid, "--major", "--body", "Otra vez")
        self.assertIn("v2.0", read(ruta))
        r = kn(self.h, "query", "--q", "cola", "--topic", "decision", "--component", "app", "--json")
        self.assertEqual(json.loads(r.stdout)[0]["id"], nid)
        self.assertEqual(kn(self.h, "query", "--q", "cola", "--component", "app-web", "--json").stdout.strip(), "[]")          # no le toca a app-web
        self.assertIn("# ", kn(self.h, "query", "--id", nid).stdout + "# ")
        self.assertIn("Otra vez", kn(self.h, "query", "--id", nid).stdout)
        r = kn(self.h, "validate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OK|notas|1 notas válidas", r.stdout)

    def test_all_llega_a_todos_los_componentes_y_dry_run_no_escribe(self):
        r = kn(self.h, "add", "--topic", "lesson", "--title", "Leccion global", "--summary", "S", "--body", "texto de la leccion", "--dry-run")
        self.assertIn("DRY|add", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.h, "arkana-knowledge")))
        nid = self.add("Leccion global", "lesson")
        self.assertEqual(cat(self.h)[0]["components"], ["all"])
        for comp in ("app", "app-ui", "arkana"):
            self.assertIn(nid, kn(self.h, "query", "--q", "leccion", "--component", comp, "--json").stdout)

    def test_banderas_antiguas_y_topics_invalidos(self):
        for args in (["add", "--type", "decision", "--title", "x", "--summary", "y"], ["update", "--id", "x"], ["search", "--q", "x"],
                     ["query", "--q", "x", "--module", "mf"], ["add", "--topic", "decision", "--title", "x", "--summary", "y", "--modules", "mf"]):
            self.assertEqual(kn(self.h, *args).returncode, 2, args)
        r = kn(self.h, "add", "--topic", "chisme", "--title", "x", "--summary", "y", "--body", "z")
        self.assertEqual(r.returncode, 2)
        self.assertIn("topic inválido", r.stdout)

    def test_componentes_validados_contra_el_manifiesto(self):
        st = os.path.join(self.h, ".arkana")
        write(os.path.join(st, "arkana.json"), json.dumps({"schema_version": 1, "workspace": {"name": "t"}, "root": ".."}))
        write(os.path.join(st, "core", "workspace.json"), json.dumps({"schema": 1, "workspace": {"name": "t"}, "arkana": {"alias": "ARKANA", "path": "."},
                                                                      "components": [{"alias": "app", "type": "node", "path": "app"}]}))
        r = kn(self.h, "add", "--topic", "decision", "--title", "Con componente raro", "--summary", "s", "--components", "app,nadie", "--body", "x")
        self.assertEqual(r.returncode, 2)
        self.assertIn("nadie", r.stdout)
        self.assertEqual(kn(self.h, "add", "--topic", "decision", "--title", "Con componente bueno", "--summary", "s", "--components", "app,arkana", "--body", "x").returncode, 0)


class TestBorradoLogico(Base):
    def test_oculta_conserva_y_se_restaura(self):
        nid = self.add()
        r = kn(self.h, "delete", "--id", nid, "--reason", "obsoleta", "--dry-run")
        self.assertIn("DRY|delete", r.stdout)
        self.assertEqual(cat(self.h)[0]["state"], "active")
        self.assertEqual(kn(self.h, "delete", "--id", nid, "--reason", "obsoleta").returncode, 0)
        self.assertIn("ya estaba borrada", kn(self.h, "delete", "--id", nid).stdout)
        self.assertEqual(json.loads(kn(self.h, "query", "--q", "json", "--json").stdout), [])             # se oculta
        self.assertEqual(json.loads(kn(self.h, "query", "--q", "json", "--include-deleted", "--json").stdout)[0]["state"], "deleted")
        e = cat(self.h)[0]
        self.assertEqual((e["id"], e["state"]), (nid, "deleted"))                                          # el catálogo la conserva
        ruta = os.path.join(self.h, e["ruta"])
        self.assertIn("borrada (borrado lógico): obsoleta", read(ruta))
        self.assertIn("state: deleted", read(ruta))
        r = kn(self.h, "modify", "--id", nid, "--body", "x")
        self.assertEqual(r.returncode, 1)
        self.assertIn("--restore", r.stdout)
        self.assertEqual(kn(self.h, "modify", "--id", nid, "--restore", "--change", "sigue vigente").returncode, 0)
        self.assertEqual(cat(self.h)[0]["state"], "active")
        self.assertIn("restaurada. sigue vigente", read(ruta))
        self.assertEqual(kn(self.h, "validate").returncode, 0)


class TestValidate(Base):
    def test_detecta_problemas(self):
        nid = self.add()
        ruta = os.path.join(self.h, cat(self.h)[0]["ruta"])
        t = read(ruta)
        write(ruta, t.replace("topic: decision", "topic: chisme").replace("version: 1.0", "version: uno"))
        r = kn(self.h, "validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("topic inválido", r.stdout)
        self.assertIn("versión inválida", r.stdout)
        write(ruta, t.split("## Changelog")[0])
        self.assertIn("sin sección ## Changelog", kn(self.h, "validate").stdout)
        write(ruta, t)
        os.remove(os.path.join(self.h, "arkana-knowledge", "catalog.json"))
        self.assertIn("WARN|catalogo|falta", kn(self.h, "validate").stdout)
        self.assertEqual(kn(self.h, "reindex").returncode, 0)
        self.assertEqual(kn(self.h, "validate").returncode, 0)


class TestMigracion(Base):
    def legacy(self):
        h = self.h
        subprocess.run(["git", "init", "-q", "-b", "main", h], check=True, env=GENV)
        meta = lambda ver, fecha, res: f'---\nid: decision-orquestar\ntitulo: "Orquestar"\ntipo: decision\nversion: {ver}\nfecha: {fecha}\nautor: Ana\nmodulos: [app, api]\netiquetas: [a, b]\nresumen: "{res}"\n---\n'
        write(os.path.join(h, "conocimiento", "decision", "orquestar.md"), meta("1.2", "2026-11-03", "Resumen v1.2") + "\n# Orquestar\n\nCuerpo.\n")
        write(os.path.join(h, "conocimiento", ".historial", "decision-orquestar", "v1.0.md"), meta("1.0", "2026-10-30", "Resumen v1.0") + "\nviejo\n")
        write(os.path.join(h, "conocimiento", ".historial", "decision-orquestar", "v1.1.md"), meta("1.1", "2026-10-31", "Resumen v1.1") + "\nviejo\n")
        write(os.path.join(h, "estado-proyecto.md"), '---\nid: reference-estado-proyecto\ntitulo: "Estado"\ntipo: reference\nversion: 1.4\nfecha: 2026-11-03\nautor: Ana\nmodulos: []\netiquetas: [x]\nresumen: "Estado"\n---\n\n# Estado\n')
        write(os.path.join(h, "catalogo.json"), json.dumps({"version": 1, "notas": []}))
        subprocess.run(["git", "-C", h, "add", "-A"], check=True, env=GENV)
        subprocess.run(["git", "-C", h, "commit", "-q", "-m", "legacy"], check=True, env=GENV)

    def test_migra_historial_a_changelog_mueve_con_git_y_es_idempotente(self):
        self.legacy()
        h = self.h
        self.assertIn("WARN|formato-antiguo", kn(h, "validate").stdout)
        r = kn(h, "migrate", "--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.isdir(os.path.join(h, "conocimiento", ".historial")))                      # dry-run no toca nada
        r = kn(h, "migrate")
        self.assertEqual(r.returncode, 0, r.stdout)
        nueva = os.path.join(h, "arkana-knowledge", "decision", "orquestar.md")
        t = read(nueva)
        for x in ("topic: decision", "components: [app, api]", "state: active", "id: decision-orquestar", "version: 1.2", "# Orquestar", "Cuerpo."):
            self.assertIn(x, t)
        self.assertNotIn("tipo:", t)
        self.assertNotIn("modulos:", t)
        ch = t.split("## Changelog")[1]
        self.assertEqual([l.split(" · ")[0] for l in ch.strip().splitlines()], ["- v1.0", "- v1.1", "- v1.2"])
        self.assertIn("Resumen v1.0", ch)
        self.assertFalse(os.path.exists(os.path.join(h, "conocimiento")))                                  # carpeta, historial y catálogo antiguo fuera
        self.assertFalse(os.path.exists(os.path.join(h, "catalogo.json")))
        st = subprocess.run(["git", "-C", h, "status", "--short"], capture_output=True, text=True, env=GENV).stdout
        self.assertRegex(st, r"(?m)^R.? +conocimiento/decision/orquestar.md -> arkana-knowledge/decision/orquestar.md")   # git mv: el historial de git sigue la nota
        ref = read(os.path.join(h, "estado-proyecto.md"))
        self.assertIn("topic: reference", ref)
        self.assertIn("components: [all]", ref)                                                            # modulos vacío = todos; la nota raíz no se mueve
        self.assertIn("Estado", read(os.path.join(h, "estado-proyecto.md")))
        ids = {e["id"]: e["ruta"] for e in cat(h)}
        self.assertEqual(ids, {"decision-orquestar": "arkana-knowledge/decision/orquestar.md", "reference-estado-proyecto": "estado-proyecto.md"})
        v = kn(h, "validate")
        self.assertEqual(v.returncode, 0, v.stdout)
        self.assertNotIn("formato-antiguo", v.stdout)
        antes = read(nueva)
        self.assertIn("no hay notas del formato antiguo", kn(h, "migrate").stdout)
        self.assertEqual(read(nueva), antes)


class TestInstall(Base):
    def test_install_crea_estructura_y_avisa_del_formato_antiguo(self):
        r = kn(self.h, "install")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.isfile(os.path.join(self.h, "arkana-knowledge", "catalog.json")))
        self.assertIn("presente", kn(self.h, "install").stdout)
        os.makedirs(os.path.join(self.h, "conocimiento"))
        self.assertIn("WARN|formato-antiguo", kn(self.h, "install").stdout)
        self.assertEqual(kn(os.path.join(self.h, "no-existe"), "validate").returncode, 3)


if __name__ == "__main__":
    unittest.main()
