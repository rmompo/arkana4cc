"""install / check / fix de arkana-messaging: almacén, plugin habilitado y latido por sesión; todo con HOME falso y sin escribir nada en los repos."""
import os
import subprocess
import unittest

import lab as L
from lab import Lab


def ops(lab, who, *a, env=None):
    return subprocess.run(["bash", L.CLI, *a], capture_output=True, text=True, env=dict(lab.env, **(env or {})), cwd=lab.cwd(who), timeout=60,
                          stdin=subprocess.DEVNULL)


def instrucciones(lab):
    """Ficheros de instrucciones que habría en las carpetas de las piezas."""
    return [f for who in ("arkana", "app", "api", "app-web") for f in ("CLAUDE.md", "CLAUDE.local.md", "ARKANA.local.md")
            if os.path.exists(os.path.join(lab.cwd(who), f))]


class TestOps(unittest.TestCase):
    def test_check_avisa_install_aplica_y_no_escribe_nada_en_los_repos(self):
        with Lab() as lab:
            r = ops(lab, "app", "check")
            self.assertIn("WARN|almacen", r.stdout)
            self.assertIn("WARN|latido", r.stdout)
            self.assertNotIn("semilla", r.stdout)                                                               # ya no hay semillas en ficheros
            self.assertEqual(ops(lab, "app", "install", "--dry-run").returncode, 0)
            self.assertFalse(os.path.isdir(lab.store("messages")))                                              # dry-run no escribe
            r = ops(lab, "app", "install")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(os.path.isdir(lab.store("messages")))
            st = lab.jload(os.path.join(lab.home, ".claude", "settings.json"))
            self.assertTrue(st["enabledPlugins"]["arkana-messaging@arkana"])
            self.assertEqual(instrucciones(lab), [])                                                            # ni CLAUDE.md ni ARKANA.local.md: nada en los repos
            r = ops(lab, "app", "check", "--all")
            self.assertNotIn("WARN|plugin", r.stdout)
            self.assertIn("WARN|latido", r.stdout)                                                             # aún no han corrido hooks
            r = ops(lab, "app", "fix").stdout
            self.assertIn("WARN|latido", r)                                                                    # fix no arregla el latido, pero lo sigue avisando
            self.assertIn("sin arreglo automático", r)
            self.assertNotIn("nada que hacer", r)

    def test_latido_de_esta_sesion_y_respaldo(self):
        with Lab() as lab:
            ops(lab, "app", "install")
            sess = os.path.join(lab.store("sessions")); os.makedirs(sess)
            lab.jdump(os.path.join(sess, "otra.json"), {"actor": "app", "event": "stop"})
            self.assertIn("OK|latido|hay un latido reciente", ops(lab, "app", "check").stdout)                 # respaldo
            lab.jdump(os.path.join(sess, "mi-sesion.json"), {"actor": "app"})
            os.utime(os.path.join(sess, "otra.json"), (1, 1))
            self.assertIn("OK|latido|los hooks han corrido en esta sesión", ops(lab, "app", "check", env={"CLAUDE_CODE_SESSION_ID": "mi-sesion"}).stdout)
            self.assertIn("WARN|latido", ops(lab, "api", "check", env={"CLAUDE_CODE_SESSION_ID": "otra-distinta"}).stdout)

    def test_fix_repone_el_almacen_y_solo_eso(self):
        with Lab() as lab:
            ops(lab, "app", "install")
            import shutil
            shutil.rmtree(lab.store("messages"))
            self.assertIn("WARN|almacen", ops(lab, "app", "check").stdout)
            r = ops(lab, "app", "fix")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("OK|almacen|almacén creado", r.stdout)
            self.assertTrue(os.path.isdir(lab.store("messages")))
            self.assertNotIn("plugin|", r.stdout)                                                           # el plugin ya estaba habilitado: fix no lo toca

    def test_sin_componente_es_precondicion(self):
        with Lab() as lab:
            self.assertEqual(ops(lab, "fuera", "check").returncode, 3)


if __name__ == "__main__":
    unittest.main()
