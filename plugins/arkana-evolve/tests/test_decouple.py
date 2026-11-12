"""Migración 0002: Arkana deja de escribir en CLAUDE.md / CLAUDE.local.md; las directrices van por hook y las notas locales en ARKANA.local.md."""
import json
import os
import subprocess
import unittest

from test_evolve import Lab, git, GENV  # noqa: F401

BLOQUES = ("<!-- arkana:messaging:start -->\n## Mensajería de Arkana\n- usa check\n<!-- arkana:messaging:end -->\n"
           "<!-- arkana:commits:start -->\n## Convención de commits\n- inglés\n<!-- arkana:commits:end -->\n")


def init_repo(path, files=None, commit=True):
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-q", path], check=True, env=GENV)
    subprocess.run(["git", "-C", path, "config", "core.excludesFile", "/dev/null"], check=True, env=GENV)
    for n, t in (files or {}).items():
        with open(os.path.join(path, n), "w", encoding="utf-8") as f:
            f.write(t)
    if commit and files:
        git(path, "add", "-A")
        git(path, "commit", "-q", "-m", "base")


def leer(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def manifest_con_seed(lab):
    lab.write(".arkana/core/workspace.json", {
        "schema": 1, "workspace": {"name": "demo"}, "arkana": {"alias": "ARKANA", "path": "arkana", "seed_file": "CLAUDE.md"},
        "components": [{"alias": "api", "type": "generic", "path": "api", "seed_file": "CLAUDE.local.md"},
                       {"alias": "app", "type": "generic", "path": "app", "seed_file": "CLAUDE.md"}]})


class TestMigracion0002(unittest.TestCase):
    def montar(self, lab):
        manifest_con_seed(lab)
        lab.write("CLAUDE.md", "# Arkana\n\nReglas propias del gobierno.\n\n" + BLOQUES + "\nFin.\n")
        git(lab.arkana, "add", "-A"); git(lab.arkana, "commit", "-q", "-m", "base")
        ws = os.path.join(lab.root, "ws")
        init_repo(os.path.join(ws, "api"), {"CLAUDE.local.md": "Mis notas locales de api.\n\n" + BLOQUES})
        init_repo(os.path.join(ws, "app"), {"CLAUDE.md": "# app\n\nNorma de la app.\n\n" + BLOQUES})
        return ws

    def test_migra_las_tres_piezas_y_es_idempotente(self):
        with Lab() as lab:
            ws = self.montar(lab)
            self.assertIn("WARN|0002|pendiente", lab.run("check").stdout)
            r = lab.run("apply", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("DRY|0002:api|CLAUDE.local.md → ARKANA.local.md", r.stdout)
            self.assertIn("arkana:messaging", lab.read("CLAUDE.md"))                                      # dry-run no escribe
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            # ARKANA: se quitan los bloques y se conserva lo propio
            ark = lab.read("CLAUDE.md")
            self.assertNotIn("arkana:", ark)
            for x in ("Reglas propias del gobierno.", "Fin."):
                self.assertIn(x, ark)
            # api: CLAUDE.local.md pasa a ARKANA.local.md sin bloques
            self.assertFalse(os.path.exists(os.path.join(ws, "api", "CLAUDE.local.md")))
            self.assertEqual(leer(os.path.join(ws, "api", "ARKANA.local.md")), "Mis notas locales de api.\n")
            # app: CLAUDE.md versionado, sin bloques y con su norma
            app = leer(os.path.join(ws, "app", "CLAUDE.md"))
            self.assertNotIn("arkana:", app)
            self.assertIn("Norma de la app.", app)
            # exclusiones locales (nunca .gitignore) y manifiesto sin seed_file
            for repo in ("api", "app"):
                for pat in (".claude/x", ".claude-session/x", "ARKANA.local.md"):
                    self.assertEqual(subprocess.run(["git", "-C", os.path.join(ws, repo), "check-ignore", "-q", pat]).returncode, 0, (repo, pat))
                self.assertFalse(os.path.exists(os.path.join(ws, repo, ".gitignore")))
            self.assertNotIn("seed_file", lab.read(".arkana/core/workspace.json"))
            # sello del registro compartido y registro con los tres componentes
            p = lab.project()
            self.assertEqual(p["layout"], 3)
            self.assertEqual([c["alias"] for c in p["components"]], ["arkana", "api", "app"])
            self.assertEqual([h["id"] for h in p["history"]], ["0001", "0002", "0003"])
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertNotIn("WARN|", lab.run("check").stdout)

    def test_un_claude_md_versionado_con_cambios_sin_commitear_no_se_toca(self):
        with Lab() as lab:
            ws = self.montar(lab)
            with open(os.path.join(ws, "app", "CLAUDE.md"), "a", encoding="utf-8") as f:
                f.write("edición sin commitear\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("WARN|0002:app|CLAUDE.md tiene cambios sin commitear", r.stdout)
            self.assertIn("arkana:messaging", leer(os.path.join(ws, "app", "CLAUDE.md")))
            self.assertIn("WARN|0002|pendiente", lab.run("check").stdout)                                  # sigue pendiente hasta que se commitee

    def test_cambios_sin_commitear_en_el_claude_md_de_arkana_se_niegan(self):
        with Lab() as lab:
            self.montar(lab)
            lab.write("CLAUDE.md", "# Arkana\n\nsin commitear\n" + BLOQUES)
            r = lab.run("apply")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertIn("cambios sin commitear", r.stdout)

    def test_claude_local_solo_con_bloques_se_borra_y_no_se_pisa_un_arkana_local_existente(self):
        with Lab() as lab:
            ws = self.montar(lab)
            with open(os.path.join(ws, "api", "CLAUDE.local.md"), "w", encoding="utf-8") as f:
                f.write(BLOQUES)
            with open(os.path.join(ws, "app", "CLAUDE.local.md"), "w", encoding="utf-8") as f:
                f.write("Notas viejas de app.\n")
            with open(os.path.join(ws, "app", "ARKANA.local.md"), "w", encoding="utf-8") as f:
                f.write("Notas nuevas de app.\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertFalse(os.path.exists(os.path.join(ws, "api", "CLAUDE.local.md")))
            self.assertFalse(os.path.exists(os.path.join(ws, "api", "ARKANA.local.md")))                   # no había nada propio que conservar
            self.assertIn("WARN|0002:app|existen CLAUDE.local.md y ARKANA.local.md", r.stdout)
            self.assertEqual(leer(os.path.join(ws, "app", "ARKANA.local.md")), "Notas nuevas de app.\n")
            self.assertEqual(leer(os.path.join(ws, "app", "CLAUDE.local.md")), "Notas viejas de app.\n")

    def test_instalacion_ya_al_dia_no_tiene_nada_pendiente_de_0002(self):
        with Lab() as lab:
            lab.write("CLAUDE.md", "# Arkana\n\nSolo lo propio.\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(lab.read("CLAUDE.md"), "# Arkana\n\nSolo lo propio.\n")


if __name__ == "__main__":
    unittest.main()
