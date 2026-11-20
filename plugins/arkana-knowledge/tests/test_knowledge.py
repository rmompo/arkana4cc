"""arkana-knowledge: notas con UUID, documentos con Markdown, ingesta, validación e índice local. Sin red."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
KN = os.path.abspath(os.path.join(AQUI, "..", "scripts", "lib", "knowledge.py"))
HOOKS = os.path.abspath(os.path.join(AQUI, "..", "scripts", "hooks.py"))
sys.dont_write_bytecode = True
ENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
ENV.pop("ARKANA_HOME", None)
ENV["ARKANA_STABLE_SECONDS"] = "0"
UUID_RX = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
APP_ID = "11111111-1111-4111-8111-111111111111"


def run(args, env=None, stdin=""):
    return subprocess.run(args, capture_output=True, text=True, env=env or ENV, input=stdin, timeout=60)


def write(p, text, mode="w"):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        f.write(text)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = os.path.realpath(self.tmp.name)
        write(os.path.join(self.h, ".arkana", "arkana.json"), '{"schema_version": 1}')
        self.kn("install")

    def kn(self, *args):
        return run([sys.executable, "-I", KN, "--home", self.h, *args])

    def path(self, *p):
        return os.path.join(self.h, *p)

    def add(self, title="Usar JSON en la cola", topic="decision", **kw):
        a = ["add", "--topic", topic, "--title", title, "--summary", kw.pop("summary", "resumen de prueba")]
        for k, v in kw.items():
            a += ["--" + k.replace("_", "-"), v]
        return self.kn(*a)

    def registry(self, comps):
        write(self.path("arkana-project.json"), json.dumps({"schema_version": 1, "layout": 3, "workspace": {"id": "22222222-2222-4222-8222-222222222222", "name": "w"},
                                                            "components": [{"id": i, "alias": a} for a, i in comps]}))


class Notas(Base):
    def test_install_crea_carpetas_fijas(self):
        for d in ("arkana-incoming", "arkana-knowledge", "arkana-docs", os.path.join("arkana-docs", "src"), os.path.join("arkana-docs", "md"), os.path.join("arkana-docs", "out")):
            self.assertTrue(os.path.isfile(self.path(d, ".gitkeep")), d)
        self.assertIn("!.gitkeep", read(self.path("arkana-incoming", ".gitignore")))
        self.assertEqual(self.kn("install").returncode, 0)

    def test_add_uuid_methodology_y_changelog(self):
        r = self.add(topic="methodology", tags="pr,review")
        self.assertEqual(r.returncode, 0, r.stdout)
        txt = read(self.path("arkana-knowledge", "methodology", "usar-json-en-la-cola.md"))
        self.assertRegex(txt, r"id: " + UUID_RX)
        self.assertIn("## Changelog", txt)
        self.assertIn("- v1.0 ", txt)
        self.assertEqual(self.kn("validate").returncode, 0)

    def test_add_duplicado_y_topic_invalido(self):
        self.assertEqual(self.add().returncode, 0)
        self.assertEqual(self.add().returncode, 1)
        self.assertEqual(self.add(topic="otro").returncode, 2)

    def test_modify_versiona_y_no_pisa_changelog(self):
        self.add()
        r = self.kn("modify", "--id", "usar-json-en-la-cola", "--body", "# nuevo", "--change", "cambio uno")
        self.assertEqual(r.returncode, 0, r.stdout)
        r = self.kn("modify", "--id", "usar-json-en-la-cola", "--major", "--change", "cambio dos")
        txt = read(self.path("arkana-knowledge", "decision", "usar-json-en-la-cola.md"))
        self.assertIn("version: 2.0", txt)
        for v in ("v1.0", "v1.1", "v2.0"):
            self.assertIn(f"- {v} ", txt)
        self.assertEqual(self.kn("validate").returncode, 0)

    def test_delete_logico_oculta_y_restore(self):
        self.add()
        self.assertEqual(self.kn("delete", "--id", "usar-json-en-la-cola", "--reason", "obsoleta").returncode, 0)
        self.assertIn("sin resultados", self.kn("query", "--q", "json").stdout)
        self.assertIn("usar-json", self.kn("query", "--q", "json", "--include-deleted").stdout.replace("-", "-"))
        self.assertEqual(self.kn("modify", "--id", "usar-json-en-la-cola", "--body", "x").returncode, 1)
        self.assertEqual(self.kn("modify", "--id", "usar-json-en-la-cola", "--restore").returncode, 0)
        self.assertIn("json", self.kn("query", "--q", "json").stdout.lower())

    def test_componentes_se_guardan_por_id_y_se_muestran_alias(self):
        self.registry([("arkana", "33333333-3333-4333-8333-333333333333"), ("app", APP_ID)])
        self.assertEqual(self.add(components="app").returncode, 0)
        self.assertIn(APP_ID, read(self.path("arkana-knowledge", "decision", "usar-json-en-la-cola.md")))
        out = json.loads(self.kn("query", "--q", "json", "--json", "--component", "app").stdout)
        self.assertEqual(out[0]["components"], ["APP"])
        self.assertEqual(self.add("Otra", components="inventado").returncode, 2)
        # renombrar el alias no toca la nota
        self.registry([("arkana", "33333333-3333-4333-8333-333333333333"), ("front", APP_ID)])
        out = json.loads(self.kn("query", "--q", "json", "--json", "--component", "front").stdout)
        self.assertEqual(out[0]["components"], ["FRONT"])
        self.assertEqual(self.kn("validate").returncode, 0)

    def test_validate_detecta_problemas(self):
        self.add()
        p = self.path("arkana-knowledge", "decision", "usar-json-en-la-cola.md")
        write(p, read(p).replace("topic: decision", "topic: raro"))
        r = self.kn("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("topic inválido", r.stdout)

    def test_catalogo_antiguo_avisa(self):
        write(self.path("arkana-knowledge", "catalog.json"), "{}")
        self.assertIn("catálogo antiguo", self.kn("validate").stdout)

    def test_indice_local_se_reconstruye(self):
        self.add()
        idx = self.path(".arkana", "arkana-knowledge", "index.json")
        self.assertTrue(os.path.isfile(idx) or self.kn("reindex").returncode == 0)
        self.kn("query", "--q", "json")
        self.assertTrue(os.path.isfile(idx))
        self.add("Segunda nota sobre colas", summary="otra cosa")
        self.assertIn("segunda", self.kn("query", "--q", "segunda").stdout.lower())


class Documentos(Base):
    def incoming(self, name, content="# Manual\ntexto del manual de pruebas\n"):
        p = self.path("arkana-incoming", name)
        write(p, content)
        return os.path.join("arkana-incoming", name)

    def ingest(self, f, *extra):
        return self.kn("ingest", "add", "--file", f, "--title", "Manual", "--summary", "manual de pruebas", *extra)

    def test_ingest_md_mueve_original_y_crea_md(self):
        f = self.incoming("manual.md")
        r = self.ingest(f)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.isfile(self.path("arkana-docs", "src", "manual.md")))
        self.assertTrue(os.path.isfile(self.path("arkana-docs", "md", "manual.md.md")))
        self.assertFalse(os.path.exists(self.path("arkana-docs", "manual.md")))                       # ya no cuelga de arkana-docs/
        self.assertFalse(os.path.exists(self.path(f)))
        self.assertEqual(self.kn("validate").returncode, 0)
        self.assertIn("doc", self.kn("query", "--q", "manual", "--kind", "document").stdout)

    def test_ingest_dest_dir_refleja_arbol(self):
        r = self.ingest(self.incoming("a.md"), "--dest-dir", "cliente/specs")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertTrue(os.path.isfile(self.path("arkana-docs", "src", "cliente", "specs", "a.md")))
        self.assertTrue(os.path.isfile(self.path("arkana-docs", "md", "cliente", "specs", "a.md.md")))

    def test_duplicado_por_sha256(self):
        self.assertEqual(self.ingest(self.incoming("a.md")).returncode, 0)
        r = self.ingest(self.incoming("b.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("uplicad", r.stdout)

    def test_symlink_rechazado(self):
        real = self.path("fuera.md")
        write(real, "x")
        os.symlink(real, self.path("arkana-incoming", "enlace.md"))
        r = self.ingest(os.path.join("arkana-incoming", "enlace.md"))
        self.assertNotEqual(r.returncode, 0)

    def test_sha_alterado_y_huerfano(self):
        self.ingest(self.incoming("a.md"))
        os.chmod(self.path("arkana-docs", "src", "a.md"), 0o644)                                       # el original es de solo lectura: para alterarlo hay que forzarlo
        write(self.path("arkana-docs", "src", "a.md"), "cambiado")
        write(self.path("arkana-docs", "src", "suelto.pdf"), "x")
        r = self.kn("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("sha256", r.stdout)
        self.assertIn("suelto.pdf", r.stdout)

    def test_puntero_lfs_avisa(self):
        self.ingest(self.incoming("a.md"))
        os.chmod(self.path("arkana-docs", "src", "a.md"), 0o644)
        write(self.path("arkana-docs", "src", "a.md"), "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 3\n")
        self.assertIn("git-lfs", self.kn("validate").stdout)

    def test_puntero_lfs_huerfano_se_nombra_como_tal(self):
        write(self.path("arkana-docs", "src", "grande.bin"), "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 9\n")
        write(self.path("arkana-docs", "src", "suelto.pdf"), "x")
        out = self.kn("validate").stdout
        self.assertRegex(out, r"huerfano\|arkana-docs/src/grande\.bin es un puntero de git-lfs")
        self.assertRegex(out, r"huerfano\|arkana-docs/src/suelto\.pdf está en arkana-docs/src/ sin su Markdown")

    def test_el_original_queda_de_solo_lectura(self):
        self.assertEqual(self.ingest(self.incoming("a.md")).returncode, 0)
        modo = stat.S_IMODE(os.stat(self.path("arkana-docs", "src", "a.md")).st_mode)
        self.assertEqual(modo & 0o222, 0, oct(modo))                                                  # nadie puede escribir
        if os.geteuid() != 0:                                                                     # root salta los permisos: allí la garantía real es el sha256 de validate
            with self.assertRaises(PermissionError):
                write(self.path("arkana-docs", "src", "a.md"), "x")

    def test_con_keep_source_la_copia_tambien_es_de_solo_lectura(self):
        f = self.incoming("k.md")
        self.assertEqual(self.ingest(f, "--keep-source").returncode, 0)
        self.assertTrue(os.path.exists(self.path(f)))
        self.assertEqual(os.stat(self.path("arkana-docs", "src", "k.md")).st_mode & 0o222, 0)

    def test_un_original_suelto_en_arkana_docs_es_del_layout_anterior(self):
        write(self.path("arkana-docs", "viejo.pdf"), "x")
        out = self.kn("validate").stdout
        self.assertRegex(out, r"WARN\|suelto\|arkana-docs/viejo\.pdf está fuera de src/, md/ y out/")
        self.assertIn("/arkana-evolve:apply", out)

    def test_out_es_libre_y_validate_no_lo_toca(self):
        write(self.path("arkana-docs", "out", "informes", "resumen.md"), "# elaborado")
        r = self.kn("validate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("resumen.md", r.stdout)
        self.assertNotIn("huerfano", r.stdout)

    def test_out_son_duplas_markdown_fuente_y_render(self):
        write(self.path("arkana-docs", "out", "informe-x.md"), "# informe")
        write(self.path("arkana-docs", "out", "informe-x.docx"), "PK")
        write(self.path("arkana-docs", "out", "informe-x.pdf"), "%PDF")                              # varios renders de la misma fuente
        write(self.path("arkana-docs", "out", "solo-md.md"), "# solo markdown")                      # entregable en Markdown: sin render, válido
        r = self.kn("validate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("WARN|out", r.stdout)
        self.assertIn("INFO|out|2 documentos elaborados (fuente .md) y 2 renders", r.stdout)

    def test_un_render_sin_su_markdown_fuente_avisa(self):
        write(self.path("arkana-docs", "out", "huerfano.docx"), "PK")
        write(self.path("arkana-docs", "out", "sub", "otro.md"), "# otro")
        write(self.path("arkana-docs", "out", "sub", "otro.pptx"), "PK")                             # este sí tiene fuente
        write(self.path("arkana-docs", "out", "sub", "falta.pdf"), "%PDF")
        out = self.kn("validate").stdout
        self.assertRegex(out, r"WARN\|out\|arkana-docs/out/huerfano\.docx es un render sin su fuente huerfano\.md")
        self.assertRegex(out, r"WARN\|out\|arkana-docs/out/sub/falta\.pdf es un render sin su fuente falta\.md")
        self.assertNotIn("otro.pptx es un render", out)

    def test_la_fuente_debe_estar_en_la_misma_carpeta(self):
        write(self.path("arkana-docs", "out", "a", "x.md"), "# x")
        write(self.path("arkana-docs", "out", "b", "x.docx"), "PK")
        self.assertIn("b/x.docx es un render sin su fuente x.md", self.kn("validate").stdout)

    def test_reconvert_lee_el_original_de_src(self):
        self.assertEqual(self.ingest(self.incoming("a.md")).returncode, 0)
        did = json.loads(self.kn("query", "--q", "manual", "--kind", "document", "--json").stdout)[0]["id"]
        self.assertEqual(self.kn("ingest", "reconvert", "--id", did).returncode, 0)

    def test_modelo_sin_herramienta(self):
        write(self.path("md.txt"), "# Resumen del modelo\n")
        f = self.incoming("escaneado.pdf", "%PDF-1.4 sin texto")
        r = self.ingest(f, "--md-file", self.path("md.txt"), "--conversion", "modelo", "--coverage", "parcial")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("modelo", self.kn("validate").stdout)

    def test_scan_lista_pendientes(self):
        self.incoming("a.md")
        r = self.kn("ingest", "scan", "--json")
        self.assertEqual(r.returncode, 0)
        self.assertEqual([x["ruta"] for x in json.loads(r.stdout)["ficheros"]], [os.path.join("arkana-incoming", "a.md")])

    def test_fuentes_enlazan_nota_con_documento(self):
        r = self.ingest(self.incoming("a.md"))
        import re
        did = re.search(UUID_RX, r.stdout).group(0)
        self.assertEqual(self.add(sources=did).returncode, 0)
        self.assertEqual(self.kn("validate").returncode, 0)
        self.assertEqual(self.add("Otra", sources="no-existe").returncode, 2)


class Hooks(Base):
    def hook(self, cmd, ev=None):
        env = dict(ENV, ARKANA_HOME=self.h)
        return run([sys.executable, "-I", HOOKS, cmd], env=env, stdin=json.dumps(dict({"session_id": "s1", "cwd": self.h}, **(ev or {}))))

    def test_session_start_vigila_incoming(self):
        out = json.loads(self.hook("session-start").stdout)["hookSpecificOutput"]
        self.assertEqual(out["watchPaths"], [self.path("arkana-incoming")])
        self.assertNotIn("additionalContext", out)

    def test_prompt_avisa_una_vez(self):
        self.hook("session-start")
        write(self.path("arkana-incoming", "n.pdf"), "x")
        self.hook("file-changed", {"file_path": self.path("arkana-incoming", "n.pdf"), "event": "add"})
        self.assertTrue(os.path.isfile(self.path(".arkana", "arkana-knowledge", "pending.json")))
        o = self.hook("prompt-submit").stdout
        self.assertIn("arkana-incoming", o)
        self.assertEqual(self.hook("prompt-submit").stdout, "")

    def test_silencio_en_worker_o_fuera(self):
        env = dict(ENV, ARKANA_HOME=self.h, ARKANA_WORKER="1")
        self.assertEqual(run([sys.executable, "-I", HOOKS, "session-start"], env=env, stdin="{}").stdout, "")
        env = dict(ENV, ARKANA_HOME="/nonexistent")
        self.assertEqual(run([sys.executable, "-I", HOOKS, "session-start"], env=env, stdin='{"cwd": "/tmp"}').stdout, "")


if __name__ == "__main__":
    unittest.main()
