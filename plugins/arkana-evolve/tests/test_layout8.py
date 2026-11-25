"""Migración 0008: arkana-docs/ en src/ (originales, solo lectura), md/ y out/."""
import json
import os
import stat
import unittest

from test_evolve import Lab, git


def tocar(lab, rel, texto="x"):
    p = os.path.join(lab.arkana, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(texto)


def existe(lab, rel):
    return os.path.exists(os.path.join(lab.arkana, rel))


def modo(lab, rel):
    return stat.S_IMODE(os.stat(os.path.join(lab.arkana, rel)).st_mode)


class TestMigracion0008(unittest.TestCase):
    def preparar(self, lab):
        lab.run("apply", "--to", "7")                                              # layout 7: los originales aún cuelgan de arkana-docs/
        tocar(lab, "arkana-docs/manual.pdf", "pdf")
        tocar(lab, "arkana-docs/cliente/specs/a.md", "a")
        tocar(lab, "arkana-docs/md/manual.pdf.md", "# manual")
        tocar(lab, "arkana-docs/md/cliente/specs/a.md.md", "# a")

    def test_mueve_los_originales_a_src_y_respeta_md(self):
        with Lab() as lab:
            self.preparar(lab)
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("0008:mover", r.stdout)
            self.assertTrue(existe(lab, "arkana-docs/src/manual.pdf"))
            self.assertTrue(existe(lab, "arkana-docs/src/cliente/specs/a.md"))
            self.assertFalse(existe(lab, "arkana-docs/manual.pdf"))
            self.assertFalse(existe(lab, "arkana-docs/cliente"))
            self.assertTrue(existe(lab, "arkana-docs/md/manual.pdf.md"))                      # el Markdown no se toca
            self.assertTrue(existe(lab, "arkana-docs/md/cliente/specs/a.md.md"))
            self.assertTrue(existe(lab, "arkana-docs/out/.gitkeep"))
            self.assertTrue(existe(lab, "arkana-docs/src/.gitkeep") or os.listdir(os.path.join(lab.arkana, "arkana-docs", "src")))
            self.assertEqual(lab.project()["layout"], 9)

    def test_los_originales_quedan_de_solo_lectura(self):
        with Lab() as lab:
            self.preparar(lab)
            lab.run("apply")
            for rel in ("arkana-docs/src/manual.pdf", "arkana-docs/src/cliente/specs/a.md"):
                self.assertEqual(modo(lab, rel) & 0o222, 0, rel)

    def test_usa_git_mv_si_estan_versionados_y_conserva_el_historial(self):
        with Lab() as lab:
            self.preparar(lab)
            git(lab.arkana, "add", "-A", "-f"); git(lab.arkana, "commit", "-q", "-m", "docs")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            estado = git(lab.arkana, "status", "--porcelain").stdout
            self.assertRegex(estado, r"R\s+arkana-docs/manual\.pdf -> arkana-docs/src/manual\.pdf")      # renombrado, no borrado+alta

    def test_idempotente_y_dry_run_no_escribe(self):
        with Lab() as lab:
            self.preparar(lab)
            r = lab.run("apply", "--dry-run")
            self.assertIn("DRY|0008:mover|arkana-docs/manual.pdf → arkana-docs/src/manual.pdf", r.stdout)
            self.assertTrue(existe(lab, "arkana-docs/manual.pdf"))
            self.assertFalse(existe(lab, "arkana-docs/src/manual.pdf"))                         # el ensayo no mueve nada
            lab.run("apply")
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertNotIn("WARN|", lab.run("check").stdout)

    def test_un_destino_ocupado_se_avisa_y_no_se_pisa(self):
        with Lab() as lab:
            self.preparar(lab)
            tocar(lab, "arkana-docs/src/manual.pdf", "OTRO")
            r = lab.run("apply")
            self.assertIn("WARN|0008:manual.pdf", r.stdout)
            self.assertEqual(open(os.path.join(lab.arkana, "arkana-docs", "src", "manual.pdf")).read(), "OTRO")
            self.assertEqual(open(os.path.join(lab.arkana, "arkana-docs", "manual.pdf")).read(), "pdf")      # el original sigue donde estaba
            self.assertNotEqual(r.returncode, 0)                                                              # verify: queda algo fuera de src/

    def test_avisa_si_gitattributes_fija_lfs_en_la_ruta_antigua(self):
        with Lab() as lab:
            self.preparar(lab)
            tocar(lab, ".gitattributes", "arkana-docs/**/*.pdf filter=lfs diff=lfs merge=lfs -text\n*.png filter=lfs -text\n")
            r = lab.run("apply")
            self.assertIn("WARN|0008:gitattributes", r.stdout)
            self.assertIn("arkana-docs/src/**/*.pdf", r.stdout)
            self.assertIn("arkana-docs/**/*.pdf", open(os.path.join(lab.arkana, ".gitattributes")).read())    # no lo reescribe

    def test_con_un_original_versionado_con_cambios_sin_commitear_no_se_toca(self):
        with Lab() as lab:
            self.preparar(lab)
            git(lab.arkana, "add", "-A", "-f"); git(lab.arkana, "commit", "-q", "-m", "docs")
            tocar(lab, "arkana-docs/manual.pdf", "cambiado")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertTrue(existe(lab, "arkana-docs/manual.pdf"))

    def test_sin_arkana_docs_no_hace_nada(self):
        with Lab() as lab:
            r = lab.run("apply")                                                        # la 0001 crea arkana-docs/ y la 0008 lo completa
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(existe(lab, "arkana-docs/out/.gitkeep"))
            self.assertTrue(existe(lab, "arkana-docs/src/.gitkeep"))
            self.assertTrue(existe(lab, "arkana-docs/md/.gitkeep"))


if __name__ == "__main__":
    unittest.main()
