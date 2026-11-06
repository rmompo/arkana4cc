"""Contención de red: un comando colgado (o con nietos colgados) no deja esperando, y el DNS caído falla rápido. Sin red real."""
import os
import shutil
import stat
import tempfile
import time
import unittest

import common  # noqa: F401  (prepara sys.path)
from arkana_core import netguard


class TestNetguard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ng-")
        self.old = dict(os.environ)
        os.environ["ARKANA_NET_BREAKER_FILE"] = os.path.join(self.tmp, "breaker.json")

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fake_bin(self, name, body):
        d = os.path.join(self.tmp, "bin"); os.makedirs(d, exist_ok=True)
        f = os.path.join(d, name)
        with open(f, "w") as fh:
            fh.write("#!/bin/sh\n" + body + "\n")
        os.chmod(f, os.stat(f).st_mode | stat.S_IXUSR)
        return d

    def test_mata_el_grupo_aunque_un_nieto_tenga_la_tuberia(self):
        t = time.time()
        p = netguard.run(["sh", "-c", "sleep 30 & sleep 30"], timeout=1)       # el nieto hereda stdout/stderr
        self.assertEqual(p.returncode, netguard.RC_TIMEOUT)
        self.assertLess(time.time() - t, 6)

    def test_comando_inexistente_y_salida_normal(self):
        self.assertEqual(netguard.run(["no-existe-xyz"]).returncode, netguard.RC_NOEXEC)
        p = netguard.run(["sh", "-c", "echo hola; echo err >&2"])
        self.assertEqual((p.returncode, p.stdout.strip(), p.stderr.strip()), (0, "hola", "err"))

    def test_nunca_lee_de_stdin(self):
        self.assertEqual(netguard.run(["sh", "-c", "cat"], timeout=3).returncode, 0)      # stdin = /dev/null: cat termina

    def test_git_de_red_con_dns_colgado_dispara_el_cortacircuitos(self):
        bindir = self.fake_bin("git", "sleep 30")                               # git que se cuelga como con el DNS caído
        os.environ["PATH"] = bindir + os.pathsep + os.environ["PATH"]
        t = time.time()
        p = netguard.git(self.tmp, "fetch", net=True, timeout=1)
        self.assertEqual(p.returncode, netguard.RC_TIMEOUT)
        self.assertTrue(netguard.breaker_open())
        t2 = time.time()
        q = netguard.git(self.tmp, "fetch", net=True, timeout=20)               # ahora falla al instante, sin esperar
        self.assertEqual(q.returncode, netguard.RC_OPEN)
        self.assertIn("VPN", q.stderr)
        self.assertLess(time.time() - t2, 1)
        self.assertLess(t2 - t, 6)

    def test_git_local_no_pasa_por_el_cortacircuitos(self):
        netguard.trip("prueba")
        self.assertNotEqual(netguard.git(self.tmp, "--version").returncode, netguard.RC_OPEN)

    def test_el_cortacircuitos_caduca(self):
        netguard.trip("x", ttl=60)
        self.assertTrue(netguard.breaker_open())
        self.assertFalse(netguard.breaker_open(now=time.time() + 61))
        netguard.reset()
        self.assertFalse(netguard.breaker_open())

    def test_entorno_de_git_sin_preguntas_y_con_limite_de_velocidad(self):
        e = netguard.git_env({})
        self.assertEqual((e["GIT_TERMINAL_PROMPT"], e["GIT_HTTP_LOW_SPEED_LIMIT"], e["GIT_HTTP_LOW_SPEED_TIME"]), ("0", "1000", "15"))

    def test_preflight_dns_caido_falla_en_segundos_y_resuelto_restablece(self):
        bindir = self.fake_bin("getent", "sleep 30")
        os.environ["PATH"] = bindir + os.pathsep + os.environ["PATH"]
        t = time.time()
        ok, det = netguard.preflight("repo.ejemplo.test", timeout=1)
        self.assertFalse(ok)
        self.assertIn("VPN", det)
        self.assertLess(time.time() - t, 6)
        self.assertTrue(netguard.breaker_open())
        self.fake_bin("getent", 'echo "10.0.0.1 $2"')
        ok, _ = netguard.preflight("repo.ejemplo.test", timeout=3)
        self.assertTrue(ok)
        self.assertFalse(netguard.breaker_open())

    def test_host_of(self):
        for u, h in (("https://u:p@repo.x.es/a/b.git", "repo.x.es"), ("git@github.com:o/r.git", "github.com"), ("ssh://h.io/x", "h.io")):
            self.assertEqual(netguard.host_of(u), h)


if __name__ == "__main__":
    unittest.main()
