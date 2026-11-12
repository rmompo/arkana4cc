"""Migración 0004: notas con UUID, componentes por id del registro, notas sueltas a arkana-knowledge/ y sin catálogo versionado."""
import json
import os
import re
import subprocess
import unittest

from test_evolve import Lab, UUID_RX, git


def nota(id_, topic="decision", comps="[api]", extra=""):
    return (f'---\nid: {id_}\ntitulo: "Titulo {id_}"\ntopic: {topic}\nversion: 1.2\nfecha: 2026-01-01\nautor: yo\ncomponents: {comps}\netiquetas: [a]\n'
            f'resumen: "r"\nstate: active\n---\n\n# Cuerpo {id_}\n\n## Changelog\n\n- v1.0 · 2026-01-01 · yo — creada\n- v1.2 · 2026-01-01 · yo — ajuste\n')


def meta(txt):
    m = re.match(r"---\n(.*?)\n---\n", txt, re.S)
    return dict(l.split(": ", 1) for l in m.group(1).split("\n"))


class TestMigracion0004(unittest.TestCase):
    def migrar(self, lab, commit=True):
        """Instalación ya en layout 3 con notas del formato post-b003."""
        lab.write("arkana-knowledge/decision/usar-json.md", nota("decision-usar-json"))
        lab.write("arkana-knowledge/lesson/cuidado.md", nota("lesson-cuidado", "lesson", "[all]"))
        lab.write("arkana-knowledge/catalog.json", {"notas": []})
        lab.write("referencia-suelta.md", nota("api-guia", "reference", "[api, arkana]"))
        if commit:
            git(lab.arkana, "add", "-A")
            git(lab.arkana, "commit", "-q", "-m", "base")
        return lab.run("apply")

    def test_ids_uuid_slug_componentes_y_catalogo(self):
        with Lab() as lab:
            r = self.migrar(lab)
            self.assertEqual(r.returncode, 0, r.stdout)
            reg = lab.project()
            ids = {c["alias"]: c["id"] for c in reg["components"]}
            m = meta(lab.read("arkana-knowledge/decision/usar-json.md"))
            self.assertRegex(m["id"], UUID_RX)
            self.assertEqual((m["slug"], m["version"], m["fuentes"]), ("usar-json", "1.2", "[]"))
            self.assertEqual(m["components"], f"[{ids['api']}]")
            self.assertIn("- v1.2 ", lab.read("arkana-knowledge/decision/usar-json.md"))
            self.assertEqual(meta(lab.read("arkana-knowledge/lesson/cuidado.md"))["components"], "[all]")
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "arkana-knowledge", "catalog.json")))
            self.assertEqual(reg["layout"], 4)
            self.assertEqual(reg["history"][-1]["id"], "0004")

    def test_nota_suelta_se_mueve_con_git_mv(self):
        with Lab() as lab:
            self.migrar(lab)
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "referencia-suelta.md")))
            m = meta(lab.read("arkana-knowledge/reference/api-guia.md"))
            self.assertEqual(m["slug"], "api-guia")
            st = subprocess.run(["git", "-C", lab.arkana, "status", "--porcelain"], capture_output=True, text=True).stdout
            self.assertRegex(st, r"R[ M] .*referencia-suelta\.md -> arkana-knowledge/reference/api-guia\.md")

    def test_idempotente_y_no_toca_uuid_existentes(self):
        with Lab() as lab:
            self.migrar(lab)
            uid = meta(lab.read("arkana-knowledge/decision/usar-json.md"))["id"]
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertEqual(meta(lab.read("arkana-knowledge/decision/usar-json.md"))["id"], uid)
            self.assertNotIn("WARN|", lab.run("check").stdout)

    def test_alias_fuera_del_registro_se_deja_y_avisa(self):
        with Lab() as lab:
            lab.write("arkana-knowledge/decision/x.md", nota("decision-x", comps="[fantasma]"))
            git(lab.arkana, "add", "-A")
            git(lab.arkana, "commit", "-q", "-m", "base")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("'fantasma' no está en el registro", r.stdout)
            self.assertEqual(meta(lab.read("arkana-knowledge/decision/x.md"))["components"], "[fantasma]")

    def test_dry_run_no_escribe(self):
        with Lab() as lab:
            lab.write("arkana-knowledge/decision/x.md", nota("decision-x"))
            git(lab.arkana, "add", "-A")
            git(lab.arkana, "commit", "-q", "-m", "base")
            antes = lab.read("arkana-knowledge/decision/x.md")
            r = lab.run("apply", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("decision-x →", r.stdout)
            self.assertEqual(lab.read("arkana-knowledge/decision/x.md"), antes)

    def test_destino_ocupado_deja_la_nota_donde_estaba(self):
        with Lab() as lab:
            lab.write("arkana-knowledge/reference/g.md", nota("reference-g", "reference"))
            lab.write("g-copia.md", nota("g", "reference"))
            git(lab.arkana, "add", "-A")
            git(lab.arkana, "commit", "-q", "-m", "base")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("ya existe arkana-knowledge/reference/g.md", r.stdout)
            self.assertTrue(os.path.isfile(os.path.join(lab.arkana, "g-copia.md")))


if __name__ == "__main__":
    unittest.main()
