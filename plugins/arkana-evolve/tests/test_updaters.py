"""Actualizadores de máquina (u001: copia de la statusline de usuario). HOME falso; el plugin arkana-statusline real (o uno falso por ARKANA_STATUSLINE_PLUGIN)."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from test_evolve import Lab

REPO_PLUGINS = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
STATUSLINE = os.path.join(REPO_PLUGINS, "arkana-statusline")


def instalar(lab):
    """Instala la copia del despachador en el HOME falso con el propio plugin (como haría la persona usuaria)."""
    r = subprocess.run([sys.executable, "-I", os.path.join(STATUSLINE, "scripts", "lib", "ops.py"), "install"], capture_output=True, text=True, env=lab.env, timeout=60)
    assert r.returncode == 0, r.stdout
    return os.path.join(lab.home, ".claude", "arkana-statusline")


def con_plugin(lab, ruta):
    lab.env = dict(lab.env, ARKANA_STATUSLINE_PLUGIN=ruta)


def plugin_falso(tmp, check_items, fix_items, fix_rc=0):
    d = os.path.join(tmp, "falso", "scripts", "lib")
    os.makedirs(d)
    Path(d, "ops.py").write_text(
        "import json, sys\n"
        f"CHECK = {json.dumps(check_items)}\nFIX = {json.dumps(fix_items)}\n"
        "print(json.dumps({'items': CHECK if sys.argv[1] == 'check' else FIX}))\n"
        f"sys.exit(0 if sys.argv[1] == 'check' else {fix_rc})\n")
    return os.path.join(tmp, "falso")


@unittest.skipUnless(os.path.isfile(os.path.join(STATUSLINE, "scripts", "lib", "ops.py")), "no está el plugin arkana-statusline junto a este")
class TestU001Statusline(unittest.TestCase):
    def test_sin_copia_instalada_no_hay_nada_que_actualizar(self):
        with Lab() as lab:
            con_plugin(lab, STATUSLINE)
            self.assertIn("OK|u001|al día", lab.run("check").stdout)
            r = lab.run("apply").stdout
            self.assertNotIn("u001", r)
            self.assertFalse(os.path.exists(os.path.join(lab.home, ".claude")))              # y no instala nada

    def test_copia_al_dia_no_se_toca(self):
        with Lab() as lab:
            con_plugin(lab, STATUSLINE)
            instalar(lab)
            self.assertIn("OK|u001|al día", lab.run("check").stdout)
            self.assertNotIn("u001", lab.run("apply").stdout)

    def test_check_avisa_y_apply_deja_la_copia_al_dia_y_es_idempotente(self):
        with Lab() as lab:
            con_plugin(lab, STATUSLINE)
            dest = instalar(lab)
            py = os.path.join(dest, "statusline.py")
            Path(py).write_text(Path(py).read_text() + "\n# copia antigua\n")
            c = lab.run("check")
            self.assertEqual(c.returncode, 0, c.stdout)
            self.assertIn("WARN|u001|pendiente (actualizador de máquina)", c.stdout)
            self.assertIn("/arkana-evolve:apply", c.stdout)
            d = lab.run("apply", "--dry-run")
            self.assertIn("DRY|u001|", d.stdout)
            self.assertIn("# copia antigua", Path(py).read_text())                                 # el ensayo no escribe
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("INFO|u001|", r.stdout); self.assertIn("u001:copia", r.stdout)
            self.assertNotIn("# copia antigua", Path(py).read_text())
            self.assertIn("OK|u001|al día", lab.run("check").stdout)
            self.assertNotIn("u001", lab.run("apply").stdout)                                      # idempotente

    def test_la_copia_anterior_al_despachador_tambien_se_actualiza(self):
        with Lab() as lab:
            con_plugin(lab, STATUSLINE)
            dest = instalar(lab)
            os.unlink(os.path.join(dest, "dispatch.py"))                                           # instalada antes del despachador
            self.assertIn("WARN|u001|", lab.run("check").stdout)
            self.assertEqual(lab.run("apply").returncode, 0)
            self.assertTrue(os.path.isfile(os.path.join(dest, "dispatch.py")))

    def test_to_n_no_ejecuta_los_actualizadores(self):
        with Lab() as lab:
            con_plugin(lab, STATUSLINE)
            dest = instalar(lab)
            py = os.path.join(dest, "statusline.py")
            Path(py).write_text("# vieja\n")
            lab.run("apply", "--to", "1")
            self.assertEqual(Path(py).read_text(), "# vieja\n")

    def test_se_ejecuta_tambien_junto_a_migraciones_pendientes(self):
        with Lab() as lab:
            con_plugin(lab, STATUSLINE)
            dest = instalar(lab)
            py = os.path.join(dest, "statusline.py")
            Path(py).write_text("# vieja\n")
            r = lab.run("apply")                                                                   # instalación nueva: hay migraciones pendientes
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("migraciones aplicadas", r.stdout); self.assertIn("INFO|u001|", r.stdout)
            self.assertNotEqual(Path(py).read_text(), "# vieja\n")


class TestU001SinElPlugin(unittest.TestCase):
    def test_sin_el_plugin_arkana_statusline_no_hace_nada_y_no_falla(self):
        with Lab() as lab:
            con_plugin(lab, os.path.join(lab.root, "no-existe"))
            dest = os.path.join(lab.home, ".claude", "arkana-statusline")
            os.makedirs(dest)
            Path(dest, "statusline.sh").write_text("#!/bin/bash\n")                                # una copia antigua, pero no hay plugin con el que compararla
            self.assertIn("OK|u001|al día", lab.run("check").stdout)
            self.assertEqual(lab.run("apply").returncode, 0)

    def test_un_fallo_del_actualizador_se_avisa_sin_deshacer_las_migraciones(self):
        with Lab() as lab:
            falso = plugin_falso(lab.root, [{"id": "copia", "status": "WARN", "detail": "x"}], [{"id": "copia", "status": "FAIL", "detail": "no se pudo escribir"}], fix_rc=1)
            con_plugin(lab, falso)
            dest = os.path.join(lab.home, ".claude", "arkana-statusline")
            os.makedirs(dest)
            Path(dest, "statusline.sh").write_text("#!/bin/bash\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("FAIL|u001:copia|no se pudo escribir", r.stdout)
            self.assertTrue(os.path.isfile(os.path.join(lab.arkana, "arkana-project.json")))      # la migración 0001 sí quedó aplicada

    def test_salida_ilegible_del_plugin_es_un_fallo_claro(self):
        with Lab() as lab:
            d = os.path.join(lab.root, "roto", "scripts", "lib")
            os.makedirs(d)
            Path(d, "ops.py").write_text("import json, sys\nif sys.argv[1] == 'check':\n    print(json.dumps({'items': [{'id': 'copia', 'status': 'WARN'}]}))\nelse:\n    print('no es json')\n")
            con_plugin(lab, os.path.join(lab.root, "roto"))
            dest = os.path.join(lab.home, ".claude", "arkana-statusline")
            os.makedirs(dest)
            Path(dest, "statusline.sh").write_text("#!/bin/bash\n")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("FAIL|u001|", r.stdout)


class TestMotor(unittest.TestCase):
    def test_los_actualizadores_se_cargan_y_cumplen_el_contrato(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "lib"))
        import evolve
        ups = evolve.load_updaters()
        self.assertTrue(ups)
        for u in ups:
            for a in evolve.REQUIRED_UPDATER:
                self.assertTrue(hasattr(u, a), (u.__name__, a))
        self.assertEqual([u.ID for u in ups], sorted(u.ID for u in ups))                             # en orden


if __name__ == "__main__":
    unittest.main()
