"""Cada plugin de Arkana lleva un arkana-plugin.json válido y el marketplace no lista plugins que ya no existen."""
import json
import os
import sys
import unittest

import environment as E

sys.path.insert(0, os.path.join(E.SCRIPTS, "_core"))
from arkana_core import contract  # noqa: E402

PLUGINS = os.path.abspath(os.path.join(E.PLUGIN, ".."))


class TestContratos(unittest.TestCase):
    def test_contratos_validos(self):
        nombres = [d for d in sorted(os.listdir(PLUGINS)) if os.path.isfile(os.path.join(PLUGINS, d, ".claude-plugin", "plugin.json"))]
        self.assertIn("arkana-workspace", nombres)
        for d in nombres:
            self.assertEqual(contract.load(os.path.join(PLUGINS, d))["plugin"], d)

    def test_el_marketplace_solo_lista_plugins_que_existen(self):
        mk = json.load(open(os.path.join(PLUGINS, ".claude-plugin", "marketplace.json")))
        for p in mk["plugins"]:
            self.assertTrue(os.path.isdir(os.path.join(PLUGINS, p["source"])), p["name"])
        self.assertNotIn("arkana-env", [p["name"] for p in mk["plugins"]])

    def test_el_codigo_copiado_del_nucleo_esta_al_dia(self):
        import subprocess
        r = subprocess.run(["bash", os.path.join(PLUGINS, "..", "scripts", "vendor-core.sh"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_la_plantilla_de_claude_md_existe_y_tiene_sus_marcas(self):
        ruta = os.path.join(PLUGINS, "arkana-workspace", "templates", "CLAUDE.modulo.md")
        with open(ruta, encoding="utf-8") as f:
            t = f.read()
        self.assertIn("{{NOMBRE}}", t); self.assertIn("{{DESCRIPCION}}", t)


if __name__ == "__main__":
    unittest.main()
