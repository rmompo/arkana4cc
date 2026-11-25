"""Fichero de ignores de arkana-docs/ (.arkanaignore): sintaxis tipo .gitignore, y su efecto en validate (src/ y out/)."""
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts", "lib"))
import ignores  # noqa: E402

import test_knowledge as K  # noqa: E402


def m(*lineas):
    return ignores.Matcher(lineas)


class TestPatrones(unittest.TestCase):
    def test_nombre_sin_barra_casa_en_cualquier_carpeta(self):
        r = m("file.name", "*.py", "file.*")
        for rel in ("file.name", "src/a/file.name", "src/x.py", "src/a/b/c.py", "src/file.txt", "out/file.docx"):
            self.assertTrue(r.ignored(rel), rel)
        for rel in ("src/x.pdf", "src/pyfile", "src/a/file"):
            self.assertFalse(r.ignored(rel), rel)

    def test_carpeta_con_barra_final_solo_casa_carpetas(self):
        r = m("node_modules/")
        self.assertTrue(r.ignored("src/proy/node_modules", is_dir=True))
        self.assertTrue(r.ignored("node_modules", is_dir=True))
        self.assertFalse(r.ignored("src/proy/node_modules", is_dir=False))                # un fichero llamado así no es una carpeta
        self.assertFalse(r.ignored("src/proy/node_modules_viejo", is_dir=True))

    def test_ruta_con_doble_asterisco_desde_arkana_docs(self):
        r = m("src/path/to/folder/**")
        self.assertTrue(r.ignored("src/path/to/folder/a.txt"))
        self.assertTrue(r.ignored("src/path/to/folder/sub/deep/b.bin"))
        self.assertFalse(r.ignored("src/path/to/other/a.txt"))
        self.assertFalse(r.ignored("otro/src/path/to/folder/a.txt"))                       # con barra en medio la ruta está anclada a arkana-docs/

    def test_doble_asterisco_al_principio_y_en_medio(self):
        r = m("**/target/", "a/**/z.txt")
        self.assertTrue(r.ignored("src/x/target", is_dir=True)); self.assertTrue(r.ignored("target", is_dir=True))
        self.assertTrue(r.ignored("a/z.txt")); self.assertTrue(r.ignored("a/b/c/z.txt"))
        self.assertFalse(r.ignored("b/a/z.txt"))

    def test_asterisco_y_interrogante_no_cruzan_carpetas(self):
        r = m("src/*/leeme.txt", "src/dato-?.csv", "src/[ab]x.log")
        self.assertTrue(r.ignored("src/p/leeme.txt")); self.assertFalse(r.ignored("src/p/q/leeme.txt"))
        self.assertTrue(r.ignored("src/dato-1.csv")); self.assertFalse(r.ignored("src/dato-12.csv"))
        self.assertTrue(r.ignored("src/ax.log")); self.assertFalse(r.ignored("src/cx.log"))

    def test_barra_inicial_ancla_y_el_fichero_concreto(self):
        r = m("/fuente/generar.py", "out/informe/fuente/generar.py")
        self.assertTrue(r.ignored("fuente/generar.py")); self.assertFalse(r.ignored("src/fuente/generar.py"))
        self.assertTrue(r.ignored("out/informe/fuente/generar.py"))

    def test_negacion_gana_la_ultima_regla(self):
        r = m("src/ejemplo/**", "!src/ejemplo/guia.pdf")
        self.assertTrue(r.ignored("src/ejemplo/a.py")); self.assertFalse(r.ignored("src/ejemplo/guia.pdf"))
        r = m("!src/ejemplo/guia.pdf", "src/ejemplo/**")
        self.assertTrue(r.ignored("src/ejemplo/guia.pdf"))                                   # el orden importa, como en .gitignore

    def test_comentarios_lineas_en_blanco_y_reglas_rotas(self):
        r = m("# comentario", "", "   ", "*.py   ", "[", "src/[x")
        self.assertEqual(len(r.rules), 3)
        self.assertTrue(r.ignored("a.py")); self.assertFalse(r.ignored("# comentario"))

    def test_sin_reglas_no_ignora_nada(self):
        self.assertFalse(m().ignored("src/a.py")); self.assertFalse(bool(m()))
        self.assertFalse(bool(m("# solo comentarios")))


class TestWalk(K.Base):
    def crear(self, rel, texto="x"):
        K.write(self.path(*rel.split("/")), texto)

    def test_lo_que_cuelga_de_una_carpeta_ignorada_queda_ignorado(self):
        self.crear("arkana-docs/src/proy/node_modules/dep/index.js"); self.crear("arkana-docs/src/proy/doc.pdf")
        K.write(self.path("arkana-docs", ".arkanaignore"), "node_modules/\n")
        res = {rel: ign for _p, rel, ign in ignores.walk(self.h, self.path("arkana-docs", "src"))}
        self.assertTrue(res["src/proy/node_modules/dep/index.js"]); self.assertFalse(res["src/proy/doc.pdf"])


class TestValidateConIgnores(K.Base):
    def crear(self, rel, texto="x"):
        K.write(self.path(*rel.split("/")), texto)

    def validar(self):
        return self.kn("validate").stdout

    def test_sin_fichero_de_ignores_todo_sin_markdown_avisa(self):
        self.crear("arkana-docs/src/script.py"); self.crear("arkana-docs/src/informe.pdf")
        out = self.validar()
        self.assertIn("huerfano|arkana-docs/src/script.py", out); self.assertIn("huerfano|arkana-docs/src/informe.pdf", out)

    def test_un_py_ignorado_no_avisa_y_un_pdf_si(self):
        self.crear("arkana-docs/src/script.py"); self.crear("arkana-docs/src/informe.pdf")
        K.write(self.path("arkana-docs", ".arkanaignore"), "*.py\n")
        out = self.validar()
        self.assertNotIn("script.py", out.replace("INFO|ignorados", ""))                    # solo cuenta en el resumen, sin nombrarlo como huérfano
        self.assertIn("huerfano|arkana-docs/src/informe.pdf está en arkana-docs/src/ sin su Markdown", out)
        self.assertIn("INFO|ignorados|1 ficheros de arkana-docs/src/ ignorados por arkana-docs/.arkanaignore", out)

    def test_carpetas_rutas_y_ficheros_concretos(self):
        for rel in ("src/proy/node_modules/a.js", "src/proy/node_modules/b.js", "src/ejemplo/main.java", "src/ejemplo/sub/Util.java", "src/fuente/generar.sh", "src/real.docx"):
            self.crear("arkana-docs/" + rel)
        K.write(self.path("arkana-docs", ".arkanaignore"), "node_modules/\nsrc/ejemplo/**\nsrc/fuente/*\n")
        out = self.validar()
        huerfanos = [l for l in out.splitlines() if l.startswith("WARN|huerfano|")]
        self.assertEqual(len(huerfanos), 1, out)
        self.assertIn("src/real.docx", huerfanos[0])

    def test_el_puntero_de_git_lfs_sigue_avisando_aunque_este_ignorado(self):
        self.crear("arkana-docs/src/grande.bin", "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 9\n")
        self.crear("arkana-docs/src/real.bin", "version https://git-lfs.github.com/spec/v1\noid sha256:def\nsize 9\n")
        K.write(self.path("arkana-docs", ".arkanaignore"), "grande.bin\n")
        out = self.validar()
        self.assertRegex(out, r"huerfano\|arkana-docs/src/grande\.bin es un puntero de git-lfs \(ignorado en arkana-docs/\.arkanaignore\)")
        self.assertRegex(out, r"huerfano\|arkana-docs/src/real\.bin es un puntero de git-lfs sin su Markdown")

    def test_la_reinclusion_con_negacion_vuelve_a_avisar(self):
        self.crear("arkana-docs/src/ejemplo/a.py"); self.crear("arkana-docs/src/ejemplo/guia.pdf")
        K.write(self.path("arkana-docs", ".arkanaignore"), "src/ejemplo/**\n!src/ejemplo/guia.pdf\n")
        out = self.validar()
        self.assertIn("src/ejemplo/guia.pdf", out); self.assertNotIn("huerfano|arkana-docs/src/ejemplo/a.py", out)

    def test_en_out_un_script_de_apoyo_ignorado_no_es_un_render(self):
        self.crear("arkana-docs/out/Operativa/fuente/generar.py"); self.crear("arkana-docs/out/Operativa/informe.md"); self.crear("arkana-docs/out/Operativa/informe.docx")
        self.crear("arkana-docs/out/Operativa/suelto.pdf")
        antes = self.validar()
        self.assertIn("generar.py es un render sin su fuente generar.md", antes)
        K.write(self.path("arkana-docs", ".arkanaignore"), "out/Operativa/fuente/**\n")
        out = self.validar()
        self.assertNotIn("generar.py es un render", out)
        self.assertIn("suelto.pdf es un render sin su fuente suelto.md", out)               # la regla de duplas sigue para los documentos
        self.assertIn("INFO|ignorados|1 ficheros de arkana-docs/out/ ignorados", out)
        self.assertNotIn("informe.docx es un render", out)

    def test_pista_cuando_hay_muchos_huerfanos_y_no_hay_fichero_de_ignores(self):
        for i in range(55):
            self.crear(f"arkana-docs/src/proy/f{i}.js")
        out = self.validar()
        self.assertIn("hay 55 ficheros sin Markdown", out); self.assertIn(".arkanaignore", out)
        K.write(self.path("arkana-docs", ".arkanaignore"), "*.js\n")
        self.assertNotIn("hay 55 ficheros", self.validar())

    def test_install_crea_la_plantilla_comentada_sin_pisar_y_no_ignora_nada(self):
        ig = self.path("arkana-docs", ".arkanaignore")
        self.assertTrue(os.path.isfile(ig))
        txt = K.read(ig)
        self.assertIn("node_modules/", txt); self.assertFalse(ignores.Matcher(txt.splitlines()))     # solo comentarios: no cambia el comportamiento
        K.write(ig, "*.py\n")
        self.assertEqual(self.kn("install").returncode, 0)
        self.assertEqual(K.read(ig), "*.py\n")


if __name__ == "__main__":
    unittest.main()
