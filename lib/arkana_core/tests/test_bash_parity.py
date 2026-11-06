"""arkana-core.sh y arkana_core (Python) deben resolver igual: hooks y statusline usan bash, el resto Python."""
import os
import unittest

import common
from arkana_core import locate, manifest


class TestParidad(unittest.TestCase):
    def test_home_por_ancestro_por_variable_y_por_registro(self):
        with common.Lab() as lab:
            sub = os.path.join(lab.arkana, "plugins"); os.makedirs(sub)
            self.assertEqual(lab.bash("ac_home", cwd=sub), (0, lab.arkana))
            self.assertEqual(lab.bash("ac_home", cwd=os.path.join(lab.ws, "md-backend"))[0], 1)       # sin registro
            lab.registrar()
            comp = os.path.join(lab.ws, "md-mf", "src", "wa")
            self.assertEqual(lab.bash("ac_home", cwd=comp), (0, lab.arkana))
            self.assertEqual(locate.find_home(cwd=comp), lab.arkana)
            env = dict(lab.env, ARKANA_HOME=lab.arkana)
            self.assertEqual(lab.bash("ac_home", cwd=lab.root, env=env), (0, lab.arkana))
            self.assertEqual(lab.bash("ac_home", cwd=lab.root)[0], 1)

    def test_aliases_y_rutas_coinciden(self):
        with common.Lab() as lab:
            w = manifest.load(lab.arkana)
            self.assertEqual(lab.bash(f'ac_aliases "{lab.arkana}"')[1].split(), w.aliases())
            for a in w.aliases() + ["shared", "APP"]:
                rc, out = lab.bash(f'ac_path "{lab.arkana}" "{a}"')
                self.assertEqual((rc, out), (0, w.path(a)), a)

    def test_override_local(self):
        with common.Lab() as lab:
            lab.escribir(os.path.join("arkana-workspace", "local.json"), {"paths": {"api": "/otro/sitio", "docs": "~/d"}})
            w = manifest.load(lab.arkana)
            for a in ("api", "docs", "app"):
                self.assertEqual(lab.bash(f'ac_path "{lab.arkana}" {a}')[1], w.path(a), a)

    def test_campos_y_alias_desconocido(self):
        with common.Lab() as lab:
            self.assertEqual(lab.bash(f'ac_field "{lab.arkana}" api type')[1], "maven")
            self.assertEqual(lab.bash(f'ac_field "{lab.arkana}" arkana alias')[1], "ARKANA")
            self.assertEqual(lab.bash(f'ac_path "{lab.arkana}" nada')[0], 1)
            self.assertEqual(lab.bash("ac_canon Shared")[1], "arkana")

    def test_emit(self):
        with common.Lab() as lab:
            self.assertEqual(lab.bash('ac_emit OK id "con detalle"')[1], "OK|id|con detalle")


if __name__ == "__main__":
    unittest.main()
