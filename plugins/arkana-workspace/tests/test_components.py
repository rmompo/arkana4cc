"""components.py (add/edit/remove/list), config.py (jira/tools), status.py/gitstate.py y checks/all.py."""
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

sys.path.insert(0, os.path.join(E.SCRIPTS, "lib"))
import gitstate  # noqa: E402
from arkana_core import manifest  # noqa: E402

LIB = os.path.join(E.SCRIPTS, "lib")


def cli(lab, script, *a, cwd=None):
    return subprocess.run([sys.executable, "-I", os.path.join(LIB, script), *a, "--home", lab.arkana], capture_output=True, text=True,
                          env=lab.env, cwd=cwd or lab.ws, stdin=subprocess.DEVNULL, timeout=60)


def ws(lab):
    return manifest.load(lab.arkana)


class TestComponents(unittest.TestCase):
    def test_add_guarda_ruta_relativa_y_el_host_del_remoto(self):
        with TC.CLab() as lab:
            os.makedirs(lab.ws + "/nuevo")
            r = cli(lab, "components.py", "add", "--alias", "nuevo", "--path", lab.ws + "/nuevo", "--type", "node", "--remote", "https://git.example/g/n.git",
                    "--token-ref", "GIT_TOKEN_N", "--tool-version", "node=20.1.0", "--git-email", "yo@x.com")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            b = ws(lab).get("nuevo")
            self.assertEqual((b["path"], b["remote_host"], b["git"]["token_ref"], b["tools"]), ("nuevo", "git.example", "GIT_TOKEN_N", [{"tool": "node", "version": "20.1.0"}]))
            loc = json.load(open(lab.arkana + "/.arkana/arkana-workspace/local.json"))
            self.assertEqual(loc["git"]["nuevo"]["email"], "yo@x.com")                 # la identidad va a local.json
            self.assertNotIn("yo@x.com", open(lab.arkana + "/.arkana/core/workspace.json").read())

    def test_rechaza_duplicados_reservados_urls_con_credenciales_y_rutas_repetidas(self):
        with TC.CLab() as lab:
            for args in (["--alias", "app", "--path", "x"], ["--alias", "arkana", "--path", "x"], ["--alias", "shared", "--path", "x"],
                         ["--alias", "n1", "--path", "x", "--remote", "https://u:p@h/g.git"], ["--alias", "n2", "--path", "api"],
                         ["--alias", "Mal Nombre", "--path", "y"], ["--alias", "n3", "--path", "z", "--tool-version", "sinigual"]):
                r = cli(lab, "components.py", "add", *args)
                self.assertEqual(r.returncode, 1, (args, r.stdout))
            self.assertEqual(len(ws(lab).aliases()), 7)

    def test_edit_cambia_solo_lo_indicado_y_deja_copia(self):
        with TC.CLab() as lab:
            antes = ws(lab).get("api")
            r = cli(lab, "components.py", "edit", "--alias", "api", "--develop", "dev2", "--no-vpn")
            self.assertEqual(r.returncode, 0, r.stdout)
            b = ws(lab).get("api")
            self.assertEqual((b["branches"], b["vpn"], b["path"]), ({"main": "main", "develop": "dev2"}, False, antes["path"]))
            self.assertTrue([f for f in os.listdir(lab.arkana + "/.arkana/arkana-workspace/bak") if f.startswith("workspace.json.")])
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "nada", "--develop", "x").returncode, 1)

    def test_statusline_se_fija_y_se_quita_y_no_vale_para_arkana(self):
        with TC.CLab() as lab:
            self.assertNotIn("statusline", ws(lab).get("api"))
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--statusline").returncode, 0)
            self.assertIs(ws(lab).get("api")["statusline"], True)
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--no-statusline").returncode, 0)
            self.assertIs(ws(lab).get("api")["statusline"], False)
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--develop", "dev3").returncode, 0)
            self.assertIs(ws(lab).get("api")["statusline"], False)                                          # lo demás no la toca
            r = cli(lab, "components.py", "edit", "--alias", "arkana", "--statusline")
            self.assertEqual(r.returncode, 1); self.assertIn("no se aplica a ARKANA", r.stdout)

    def test_remove_pide_confirmacion_y_no_borra_la_carpeta(self):
        with TC.CLab() as lab:
            self.assertEqual(cli(lab, "components.py", "remove", "--alias", "specs").returncode, 1)
            self.assertTrue(ws(lab).has("specs"))
            self.assertEqual(cli(lab, "components.py", "remove", "--alias", "specs", "--dry-run").returncode, 0)
            self.assertTrue(ws(lab).has("specs"))
            self.assertEqual(cli(lab, "components.py", "remove", "--alias", "specs", "--yes").returncode, 0)
            self.assertFalse(ws(lab).has("specs")); self.assertTrue(os.path.isdir(lab.ws + "/specs"))

    def test_no_se_crea_repos_conf_y_git_email_domain_va_al_manifiesto(self):
        with TC.CLab() as lab:
            r = cli(lab, "components.py", "edit", "--alias", "api", "--git-email-domain", "@example.org", "--git-email-domain", "ext.example.org")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(ws(lab).get("api")["git"]["email_domains"], ["example.org", "ext.example.org"])      # se guarda sin la @
            self.assertFalse(os.path.exists(lab.arkana + "/.arkana/core/repos.conf"))                      # el modo antiguo ya no existe
            self.assertNotEqual(cli(lab, "components.py", "edit", "--alias", "api", "--git-email-domain", "no valido").returncode, 0)

    def test_arkana_tiene_sus_propias_directrices_de_commit_como_cualquier_componente(self):
        with TC.CLab() as lab:
            r = cli(lab, "components.py", "edit", "--alias", "arkana", "--commit-format", "conventional", "--git-email-domain", "example.org")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            b = ws(lab).get("arkana")
            self.assertEqual((b["commit_format"], b["git"]["email_domains"]), ("conventional", ["example.org"]))
            for opcion in (("--type", "node"), ("--path", "x"), ("--no-vpn",), ("--tool-version", "node=1")):                      # lo que solo es de los componentes se rechaza
                r = cli(lab, "components.py", "edit", "--alias", "arkana", *opcion)
                self.assertEqual(r.returncode, 1, opcion); self.assertIn("no se aplica a ARKANA", r.stdout)

    def test_list_json(self):
        with TC.CLab() as lab:
            j = json.loads(cli(lab, "components.py", "list", "--json").stdout)
            self.assertEqual([i["id"] for i in j["items"]][:3], ["arkana", "app", "api"])


class TestConfig(unittest.TestCase):
    def test_jira_y_tools(self):
        with TC.CLab() as lab:
            self.assertEqual(cli(lab, "config.py", "jira", "--url", "https://jira.example", "--token-ref", "JIRA_TOKEN").returncode, 0)
            self.assertEqual(ws(lab).data["jira"], {"url": "https://jira.example", "token_ref": "JIRA_TOKEN"})
            self.assertEqual(cli(lab, "config.py", "tools", "--tool", "jdk", "--version", "1.8", "--path", "/opt/jdk").returncode, 0)
            cli(lab, "config.py", "tools", "--tool", "jdk", "--version", "1.8.1")                 # reemplaza, no duplica
            t = json.load(open(lab.arkana + "/.arkana/arkana-workspace/tools.json"))["tools"]
            self.assertEqual([x["version"] for x in t if x["tool"] == "jdk"], ["1.8.1"])
            self.assertEqual(cli(lab, "config.py", "tools", "--tool", "x").returncode, 1)         # sin versión

    def test_tools_guarda_paquetes_registros_urls_y_puertos_y_conserva_lo_que_no_se_repite(self):
        with TC.CLab() as lab:
            r = cli(lab, "config.py", "tools", "--tool", "node", "--version", "20.1.0", "--path", "/opt/node", "--package", "@acme/cli@1.2.3",
                    "--registry", "@acme=https://reg.example/npm/", "--check-url", "https://api.example", "--port", "8080", "--port", "3000")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            cli(lab, "config.py", "tools", "--tool", "node", "--version", "20.2.0", "--package", "otro")           # cambia la versión, conserva el resto y suma el paquete
            d = json.load(open(lab.arkana + "/.arkana/arkana-workspace/tools.json"))
            n = next(x for x in d["tools"] if x["tool"] == "node")
            self.assertEqual((n["version"], n["path"], n["packages"], n["registries"]), ("20.2.0", "/opt/node", ["@acme/cli@1.2.3", "otro"], {"@acme": "https://reg.example/npm/"}))
            self.assertEqual((d["urls"], d["ports"]), (["https://api.example"], [3000, 8080]))
            self.assertNotEqual(cli(lab, "config.py", "tools", "--package", "x").returncode, 0)                    # --package necesita --tool


class TestGitState(unittest.TestCase):
    def mk(self, lab):
        d = lab.ws + "/gs"; os.makedirs(d)
        env = dict(os.environ, GIT_AUTHOR_NAME="x", GIT_AUTHOR_EMAIL="x@x", GIT_COMMITTER_NAME="x", GIT_COMMITTER_EMAIL="x@x")
        g = lambda *a: subprocess.run(["git", "-C", d, *a], check=True, capture_output=True, env=env)
        g("init", "-q", "-b", "develop"); g("commit", "-q", "--allow-empty", "-m", "i")
        return d, g

    def test_limpio_y_sin_remoto_no_pinta_flechas(self):
        with TC.CLab() as lab:
            d, _ = self.mk(lab)
            s = gitstate.state(d)
            self.assertTrue(s["clean"]); self.assertFalse(s["has_remote"])
            self.assertEqual(gitstate.badge(s), " develop ✓ ")

    def test_contadores_locales(self):
        with TC.CLab() as lab:
            d, g = self.mk(lab)
            open(d + "/a", "w").write("1"); open(d + "/b", "w").write("1"); g("add", "a"); g("add", "b"); g("commit", "-q", "-m", "x")
            open(d + "/a", "w").write("2"); open(d + "/c", "w").write("1"); open(d + "/b", "w").write("2"); g("add", "b")
            s = gitstate.state(d)
            self.assertEqual((s["untracked"], s["staged"], s["modified"]), (1, 1, 1))
            self.assertEqual(gitstate.badge(s), " develop ◌1 ✚1 ●1 ")

    def test_remoto_ahead_y_behind_desconocido_o_fresco(self):
        with TC.CLab() as lab:
            d, g = self.mk(lab)
            bare = lab.root + "/o.git"
            subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
            g("remote", "add", "origin", bare); g("push", "-q", "-u", "origin", "develop")
            g("commit", "-q", "--allow-empty", "-m", "otro")
            s = gitstate.state(d)
            self.assertEqual(s["ahead"], 1); self.assertTrue(s["has_remote"])
            os.utime(d + "/.git/FETCH_HEAD") if os.path.exists(d + "/.git/FETCH_HEAD") else open(d + "/.git/FETCH_HEAD", "w").close()
            self.assertEqual(gitstate.state(d)["behind"], 0)                                  # fetch reciente: se sabe
            old = os.stat(d + "/.git/FETCH_HEAD").st_mtime - 3600
            os.utime(d + "/.git/FETCH_HEAD", (old, old))
            s = gitstate.state(d)
            self.assertIsNone(s["behind"]); self.assertEqual(gitstate.badge(s), " develop ⇡1 ⇣? ")

    def test_status_cli(self):
        with TC.CLab() as lab:
            r = cli(lab, "status.py", "--component", "api", "--json")
            j = json.loads(r.stdout)
            self.assertEqual(j["items"][0]["git"]["branch"] in ("master", "main", "develop"), True)
            self.assertEqual(cli(lab, "status.py", "--component", "nada").returncode, 3)


class TestAll(unittest.TestCase):
    def test_agrega_componentes_herramientas_credenciales_y_plugins(self):
        with TC.CLab() as lab:
            plug = lab.root + "/plugins/arkana-demo"; os.makedirs(plug)
            json.dump({"plugin": "arkana-demo", "contract": 1, "provides": ["check"], "check": "echo 'FAIL|algo|roto'; echo 'OK|otro|bien'"}, open(plug + "/arkana-plugin.json", "w"))
            r = subprocess.run([sys.executable, "-I", os.path.join(E.SCRIPTS, "checks", "all.py"), "--home", lab.arkana, "--plugins-dir", lab.root + "/plugins", "--component", "docs"],
                               capture_output=True, text=True, env={k: v for k, v in lab.env.items() if k != "NVM_DIR"}, stdin=subprocess.DEVNULL, timeout=90)
            self.assertIn("docs:permisos", r.stdout); self.assertNotIn("tools:jira", r.stdout)               # Jira es opcional: sin bloque `jira` no se comprueba
            self.assertIn("FAIL|arkana-demo:algo|roto", r.stdout); self.assertIn("OK|arkana-demo:otro|bien", r.stdout)
            self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
