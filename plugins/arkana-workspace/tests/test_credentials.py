"""Credenciales (.arkana/.credentials), asistente de git y arkana-exec: modo 600, redacción, sin valores en ninguna salida."""
import json
import os
import stat
import subprocess
import sys
import unittest

import environment as E
import test_layout as TL

sys.path.insert(0, os.path.join(E.SCRIPTS, "lib"))
import credentials as C  # noqa: E402
import layout  # noqa: E402
from arkana_core import manifest  # noqa: E402

SECRETO = "tok-S3CRETO-123"
HELPER = os.path.join(E.SCRIPTS, "git-credential-arkana")
EXEC = os.path.join(E.SCRIPTS, "arkana-exec.sh")
CLI = os.path.join(E.SCRIPTS, "lib", "credentials.py")


class CLab(TL.Lab):
    def __enter__(self):
        super().__enter__()
        E.seed(self.arkana, self.ws)
        f = os.path.join(self.arkana, ".arkana", "core", "workspace.json")
        d = json.load(open(f))
        for c in d["components"]:
            if c["alias"] == "api":
                c["git"] = {"token_ref": "GIT_TOKEN_BE", "username": "ci-user"}
                c["remote_host"] = "host.example"
        json.dump(d, open(f, "w"))
        subprocess.run(["git", "-C", self.arkana, "config", "core.excludesFile", "/dev/null"], check=True)
        open(os.path.join(self.arkana, ".gitignore"), "w").write("/.arkana/\n")
        self.env = dict(os.environ, HOME=self.home_dir)
        return self

    def cli(self, *a, entrada=None):
        return subprocess.run([sys.executable, "-I", CLI, *a, "--home", self.arkana], capture_output=True, text=True, input=entrada, env=self.env)


class TestFichero(unittest.TestCase):
    def test_set_get_modo_600_y_sin_restos(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "GIT_TOKEN_BE", SECRETO)
            f = C.path(lab.arkana)
            self.assertEqual(stat.S_IMODE(os.stat(f).st_mode), 0o600)
            self.assertEqual(C.get(lab.arkana, "GIT_TOKEN_BE"), SECRETO)
            self.assertEqual([x for x in os.listdir(os.path.dirname(f)) if x.startswith(".credentials.")], [])

    def test_valida_nombres_y_valores(self):
        with CLab() as lab:
            for k, v in (("minuscula", "x"), ("1A", "x"), ("A-B", "x"), ("OK", ""), ("OK", "a\nb")):
                with self.assertRaises(ValueError):
                    C.set_key(lab.arkana, k, v)

    def test_el_valor_entra_por_stdin_y_nunca_sale(self):
        with CLab() as lab:
            r = lab.cli("set", "GIT_TOKEN_BE", entrada=SECRETO + "\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            for salida in (r.stdout, r.stderr, lab.cli("keys").stdout, lab.cli("keys", "--json").stdout, lab.cli("check").stdout):
                self.assertNotIn(SECRETO, salida)
            self.assertEqual(lab.cli("has", "GIT_TOKEN_BE").returncode, 0)
            self.assertEqual(lab.cli("has", "NADA").returncode, 1)
            self.assertEqual(lab.cli("unset", "GIT_TOKEN_BE").returncode, 0)
            self.assertEqual(lab.cli("has", "GIT_TOKEN_BE").returncode, 1)

    def test_check_detecta_modo_y_no_ignorado(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "A", "x")
            self.assertEqual(lab.cli("check").returncode, 0, lab.cli("check").stdout)
            os.chmod(C.path(lab.arkana), 0o644)
            self.assertIn("FAIL|credentials-modo", lab.cli("check").stdout)
            open(os.path.join(lab.arkana, ".gitignore"), "w").write("")
            self.assertIn("FAIL|credentials-ignorado", lab.cli("check").stdout)

    def test_import_maven_sin_imprimir_valores(self):
        with CLab() as lab:
            x = lab.fichero_xml = os.path.join(lab.root, "s.xml")
            open(x, "w").write(f'<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"><servers><server><id>registry</id>'
                               f'<username>u-S3CRETO</username><password>{SECRETO}</password></server></servers></settings>')
            r = lab.cli("import-maven", x)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("S3CRETO", r.stdout + r.stderr)
            self.assertEqual(C.get(lab.arkana, "REGISTRY_PASSWORD"), SECRETO)
            self.assertEqual(lab.cli("import-maven", x, "--server", "otro").returncode, 1)

    def test_los_informes_redactan_cualquier_valor_guardado(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "A", SECRETO)
            self.assertNotIn(SECRETO, lab.cli("import-maven", "/no/existe/" + SECRETO).stdout)


class TestGitHelper(unittest.TestCase):
    def helper(self, lab, entrada, op="get", cwd=None):
        return subprocess.run([sys.executable, "-I", HELPER, op], capture_output=True, text=True, input=entrada, cwd=cwd or lab.ws, env=dict(lab.env, ARKANA_HOME=lab.arkana))

    def test_devuelve_usuario_y_token_del_componente_por_host(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "GIT_TOKEN_BE", SECRETO)
            r = self.helper(lab, "protocol=https\nhost=host.example\npath=g/be.git\n\n")
            self.assertEqual(r.stdout, f"username=ci-user\npassword={SECRETO}\n")

    def test_sin_coincidencia_no_imprime_nada(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "GIT_TOKEN_BE", SECRETO)
            self.assertEqual(self.helper(lab, "protocol=https\nhost=otro.example\n\n").stdout, "")
            self.assertEqual(self.helper(lab, "protocol=ssh\nhost=host.example\n\n").stdout, "")
            self.assertEqual(self.helper(lab, "protocol=https\nhost=host.example\n\n", op="store").stdout, "")

    def test_sin_token_en_credentials_no_imprime_nada(self):
        with CLab() as lab:
            self.assertEqual(self.helper(lab, "protocol=https\nhost=host.example\n\n").stdout, "")

    def test_wire_git_configura_solo_el_repo_local(self):
        with CLab() as lab:
            r = lab.cli("wire-git", "api")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            repo = lab.ws + "/api"
            cfg = subprocess.run(["git", "-C", repo, "config", "--local", "credential.helper"], capture_output=True, text=True).stdout.strip()
            self.assertTrue(cfg.startswith("!") and cfg.endswith("git-credential-arkana"))
            self.assertTrue(os.access(cfg[1:], os.X_OK))
            self.assertIn("WARN|token", r.stdout)                               # aún sin token
            self.assertEqual(lab.cli("wire-git", "docs").returncode, 1)         # sin token_ref
            self.assertEqual(lab.cli("wire-git", "api", "--dry-run").returncode, 0)

    def test_git_usa_el_asistente_de_punta_a_punta(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "GIT_TOKEN_BE", SECRETO)
            lab.cli("wire-git", "api")
            repo = lab.ws + "/api"
            r = subprocess.run(["git", "-C", repo, "credential", "fill"], input="protocol=https\nhost=host.example\n\n", capture_output=True, text=True,
                               env=dict(lab.env, ARKANA_HOME=lab.arkana, GIT_TERMINAL_PROMPT="0", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1"))
            self.assertIn(f"password={SECRETO}", r.stdout)


class TestExec(unittest.TestCase):
    def test_inyecta_el_entorno_sin_pisar_lo_existente(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "REGISTRY_USER", "u"); C.set_key(lab.arkana, "OTRA", "v")
            env = dict(lab.env, ARKANA_HOME=lab.arkana, OTRA="ya-definida")
            r = subprocess.run(["bash", EXEC, "--", "bash", "-c", 'echo "$REGISTRY_USER|$OTRA"'], capture_output=True, text=True, env=env)
            self.assertEqual(r.stdout.strip(), "u|ya-definida")
            r = subprocess.run(["bash", EXEC, "--keys", "REGISTRY_USER", "--", "bash", "-c", 'echo "${OTRA:-nada}"'], capture_output=True, text=True, env=dict(lab.env, ARKANA_HOME=lab.arkana))
            self.assertEqual(r.stdout.strip(), "nada")

    def test_valores_con_caracteres_especiales(self):
        with CLab() as lab:
            C.set_key(lab.arkana, "RARA", "a b$(x)'\"`;&")
            r = subprocess.run(["bash", EXEC, "--", "bash", "-c", 'printf %s "$RARA"'], capture_output=True, text=True, env=dict(lab.env, ARKANA_HOME=lab.arkana))
            self.assertEqual(r.stdout, "a b$(x)'\"`;&")

    def test_sin_comando_es_error_de_uso(self):
        self.assertEqual(subprocess.run(["bash", EXEC], capture_output=True, text=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
