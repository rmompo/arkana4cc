"""install / check / fix de arkana-messaging: semilla inline, plugin habilitado, latido por sesión; todo con HOME falso."""
import json
import os
import subprocess
import unittest

import lab as L
from lab import Lab


def ops(lab, who, *a, env=None):
    return subprocess.run(["bash", L.CLI, *a], capture_output=True, text=True, env=dict(lab.env, **(env or {})), cwd=lab.cwd(who), timeout=60,
                          stdin=subprocess.DEVNULL)


def prepara(lab):
    for who in ("arkana", "app", "api", "app-web"):
        with open(os.path.join(lab.cwd(who), "CLAUDE.md"), "w") as f:
            f.write(f"# {who}\n\nReglas propias.\n" + ("@.arkana/core/novedades.md\n" if who == "arkana" else ""))


def leer(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class TestOps(unittest.TestCase):
    def test_check_avisa_install_aplica_y_check_queda_en_ok(self):
        with Lab() as lab:
            prepara(lab)
            r = ops(lab, "app", "check")
            self.assertIn("WARN|almacen", r.stdout)
            self.assertIn("WARN|semilla-app", r.stdout)
            self.assertIn("WARN|latido", r.stdout)
            self.assertEqual(ops(lab, "app", "install", "--dry-run").returncode, 0)
            self.assertNotIn("arkana:messaging", leer(os.path.join(lab.cwd("app"), "CLAUDE.md")))                # dry-run no escribe
            r = ops(lab, "app", "install")
            self.assertEqual(r.returncode, 0, r.stdout)
            for who in ("arkana", "app", "api", "app-web"):
                t = leer(os.path.join(lab.cwd(who), "CLAUDE.md"))
                self.assertEqual(t.count("<!-- arkana:messaging:start -->"), 1, who)
                self.assertIn("/arkana-messaging:check", t)
                self.assertIn("Reglas propias.", t)                                                            # lo de fuera no se toca
                self.assertNotIn("\n@", t.split("<!-- arkana:messaging:start -->")[1])                           # el bloque no importa ficheros
            self.assertNotIn("novedades.md", leer(os.path.join(lab.cwd("arkana"), "CLAUDE.md")))               # importación obsoleta fuera
            self.assertTrue(os.path.isdir(lab.store("messages")))
            st = lab.jload(os.path.join(lab.home, ".claude", "settings.json"))
            self.assertTrue(st["enabledPlugins"]["arkana-messaging@arkana"])
            self.assertTrue(os.listdir(os.path.join(lab.arkana, ".arkana", "arkana-messaging", "bak", "arkana")))
            r = ops(lab, "app", "check", "--all")
            self.assertNotIn("WARN|semilla", r.stdout)
            self.assertNotIn("WARN|plugin", r.stdout)
            self.assertIn("WARN|latido", r.stdout)                                                             # aún no han corrido hooks
            self.assertIn("nada que hacer", ops(lab, "app", "fix").stdout)

    def test_latido_de_esta_sesion_y_respaldo(self):
        with Lab() as lab:
            prepara(lab)
            ops(lab, "app", "install")
            sess = os.path.join(lab.store("sessions")); os.makedirs(sess)
            lab.jdump(os.path.join(sess, "otra.json"), {"actor": "app", "event": "stop"})
            self.assertIn("OK|latido|hay un latido reciente", ops(lab, "app", "check").stdout)                 # respaldo
            lab.jdump(os.path.join(sess, "mi-sesion.json"), {"actor": "app"})
            os.utime(os.path.join(sess, "otra.json"), (1, 1))
            self.assertIn("OK|latido|los hooks han corrido en esta sesión", ops(lab, "app", "check", env={"CLAUDE_CODE_SESSION_ID": "mi-sesion"}).stdout)
            self.assertIn("WARN|latido", ops(lab, "api", "check", env={"CLAUDE_CODE_SESSION_ID": "otra-distinta"}).stdout)

    def test_fix_solo_arregla_lo_marcado_y_repone_un_bloque_desactualizado(self):
        with Lab() as lab:
            prepara(lab)
            ops(lab, "app", "install")
            p = os.path.join(lab.cwd("api"), "CLAUDE.md")
            with open(p, "w") as f:
                f.write("# be\n<!-- arkana:messaging:start -->\ncontenido viejo\n<!-- arkana:messaging:end -->\nfin\n")
            self.assertIn("WARN|semilla-api", ops(lab, "app", "check", "--all").stdout)
            r = ops(lab, "app", "fix")
            self.assertEqual(r.returncode, 0, r.stdout)
            t = leer(p)
            self.assertNotIn("contenido viejo", t)
            self.assertIn("arkana:messaging:start", t)
            self.assertIn("fin", t)
            self.assertNotIn("semilla-app", r.stdout)                                                        # lo que estaba bien no se toca

    def test_claude_md_versionado_ausente_no_se_crea(self):
        with Lab() as lab:
            r = ops(lab, "app", "install")
            self.assertIn("WARN|semilla-app", r.stdout)
            self.assertIn("/arkana-workspace:fix", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.cwd("app"), "CLAUDE.md")))

    def test_sin_componente_es_precondicion(self):
        with Lab() as lab:
            self.assertEqual(ops(lab, "fuera", "check").returncode, 3)


if __name__ == "__main__":
    unittest.main()
