"""checks/tools.py y checks/vpn.py (antes arkana-env y arkana-vpn) y component.py: sin red real ni DNS."""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC
import test_layout as TL

sys.path.insert(0, os.path.join(E.SCRIPTS, "lib"))
sys.path.insert(0, os.path.join(E.SCRIPTS, "checks"))
import proc  # noqa: E402
import vpn  # noqa: E402

CK = os.path.join(E.SCRIPTS, "checks")


def run(lab, script, *a):
    return subprocess.run([sys.executable, "-I", os.path.join(CK, script), *a, "--home", lab.arkana], capture_output=True, text=True,
                          env={k: v for k, v in dict(lab.env, HOME=lab.home_dir).items() if k not in ("NVM_DIR", "ARKANA_NODE")}, timeout=60, stdin=subprocess.DEVNULL)


def estados(r):
    return {l.split("|")[1]: l.split("|")[0] for l in r.stdout.splitlines() if l.count("|") >= 2 and l.split("|")[0] in ("OK", "WARN", "FAIL", "INFO")}


class TestProc(unittest.TestCase):
    def test_timeout_mata_tambien_a_los_nietos(self):
        rc, _ = proc.run(["bash", "-c", "sleep 30 & sleep 30; :"], timeout=1)
        self.assertEqual(rc, 124)

    def test_salida_y_codigo(self):
        self.assertEqual(proc.run(["bash", "-c", "echo hola; exit 3"]), (3, "hola"))
        self.assertEqual(proc.run(["no-existe-xyz"])[0], 127)


class TestTools(unittest.TestCase):
    def declarar(self, lab, tools=None, **extra):
        p = lab.arkana + "/.arkana/arkana-workspace/tools.json"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        Path(p).write_text(json.dumps(dict({"schema_version": 1, "tools": tools or []}, **extra)))

    def herramienta_falsa(self, lab, nombre="faketool", version="4.5.6"):
        d = os.path.join(lab.root, nombre)
        os.makedirs(os.path.join(d, "bin"))
        with open(os.path.join(d, "bin", nombre), "w") as f:
            f.write(f"#!/bin/sh\necho '{nombre} {version}'\n")
        os.chmod(os.path.join(d, "bin", nombre), 0o755)
        return d

    def configurar_jira(self, lab):
        f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
        d = json.loads(Path(f).read_text())
        d["jira"] = {"url": "https://jira.example", "token_ref": "JIRA_TOKEN"}
        Path(f).write_text(json.dumps(d))

    def test_sin_bloque_jira_no_hay_checks_de_jira(self):
        with TC.CLab() as lab:
            e = estados(run(lab, "tools.py", "--no-network"))
            self.assertEqual([k for k in e if k.startswith("jira")], [])

    def test_entorno_vacio_marca_lo_que_falta_y_no_muestra_secretos(self):
        with TC.CLab() as lab:
            self.configurar_jira(lab)
            os.makedirs(os.path.join(lab.home_dir, ".ia4d"))
            Path(os.path.join(lab.home_dir, ".ia4d", ".env")).write_text("JIRA_HOST=h\nJIRA_API_TOKEN=TOK-S3CRETO\n")
            TC.C.set_key(lab.arkana, "GIT_TOKEN_BE", TC.SECRETO)
            r = run(lab, "tools.py", "--no-network")
            e = estados(r)
            self.assertEqual(e["herramientas"], "INFO")                 # nada declarado: no se exige ninguna herramienta del stack
            self.assertEqual([k for k in e if k.startswith(("nvm", "node-nvmrc", "symlink-", "puerto-", "registro-"))], [])       # no hay nada del stack fijado en el código
            self.assertEqual(e["jira-env"], "OK")
            self.assertEqual(e["cred-host.example"], "OK")              # por token_ref en .credentials
            self.assertNotIn("S3CRETO", r.stdout + r.stderr)

    def test_comprueba_lo_declarado_version_ausente_y_discrepancia(self):
        with TC.CLab() as lab:
            falsa = self.herramienta_falsa(lab)
            self.declarar(lab, [{"tool": "faketool", "version": "4.5", "path": falsa}, {"tool": "otra", "version": "9", "path": self.herramienta_falsa(lab, "otra", "1.2.3")},
                                {"tool": "no-existe-xyz", "version": "1"}])
            e = estados(run(lab, "tools.py", "--no-network"))
            self.assertEqual((e["faketool"], e["otra"], e["no-existe-xyz"]), ("OK", "WARN", "FAIL"))   # 4.5 es prefijo de 4.5.6; 9 ≠ 1.2.3; la tercera no existe
            self.assertNotIn("herramientas", e)

    def test_versiones_de_los_componentes_y_prefijo_de_version(self):
        with TC.CLab() as lab:
            falsa = self.herramienta_falsa(lab, "jq", "1.7.1")
            self.declarar(lab, [{"tool": "jq", "path": falsa, "version": "1.7"}])
            r = run(lab, "tools.py", "--no-network")
            self.assertIn("OK|jq|", r.stdout)

    def test_registros_y_paquetes_declarados(self):
        with TC.CLab() as lab:
            falsa = self.herramienta_falsa(lab)
            self.declarar(lab, [{"tool": "faketool", "version": "4", "path": falsa, "packages": ["@acme/cli@1.0"],
                                 "registries": {"@acme": "https://reg.example/npm/", "@falta": "https://otro.example/", "@dist": "https://a.example/"}}])
            with open(os.path.join(lab.home_dir, ".npmrc"), "w") as f:
                f.write("@acme:registry=https://reg.example/npm\n@dist:registry=https://b.example/\n")
            e = estados(run(lab, "tools.py", "--no-network"))
            self.assertEqual((e["registro-@acme"], e["registro-@falta"], e["registro-@dist"]), ("OK", "FAIL", "WARN"))   # coincide (sin barra final); ausente; otro distinto
            self.assertEqual(e["faketool-paquete-@acme/cli"], "INFO")                                                 # solo se saben comprobar los paquetes globales de node

    def test_urls_y_puertos_solo_los_declarados(self):
        import socket
        with TC.CLab() as lab:
            srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
            ocupado = srv.getsockname()[1]
            try:
                self.declarar(lab, [], ports=[ocupado], urls=["https://no-resuelve.invalid"])
                e = estados(run(lab, "tools.py", "--no-network"))
                self.assertEqual(e[f"puerto-{ocupado}"], "WARN")                                # ocupado
                self.assertNotIn("red-no-resuelve.invalid", e)                                   # --no-network: no se contacta con la URL
            finally:
                srv.close()

    def test_json_y_jira_sin_valores(self):
        with TC.CLab() as lab:
            self.configurar_jira(lab)
            os.makedirs(os.path.join(lab.home_dir, ".ia4d"))
            Path(os.path.join(lab.home_dir, ".ia4d", ".env")).write_text("JIRA_HOST=<tu-host>\nJIRA_API_TOKEN=x\n")
            j = json.loads(run(lab, "tools.py", "--no-network", "--json").stdout)
            self.assertEqual(j["skill"], "check-tools")
            self.assertEqual({i["id"]: i["status"] for i in j["items"]}["jira-env"], "WARN")

    def test_conector_jira_mcp_dependencias_duplicado_y_env_de_proyecto(self):
        with TC.CLab() as lab:
            self.configurar_jira(lab)
            home = lab.home_dir
            jc = os.path.join(home, ".claude", "plugins", "marketplaces", "ia4d-expert-agents-marketplace", "plugins", "ia4d-project-bridge", "mcp", "jira-connector")
            e = estados(run(lab, "tools.py", "--no-network"))
            self.assertEqual(e["jira-mcp"], "FAIL")                                         # plugin ausente
            os.makedirs(jc)
            with open(os.path.join(jc, "index.js"), "w") as f:
                f.write("//")
            e = estados(run(lab, "tools.py", "--no-network"))
            self.assertEqual((e["jira-mcp"], e["jira-mcp-deps"]), ("OK", "FAIL"))             # faltan node_modules
            os.makedirs(os.path.join(jc, "node_modules"))
            with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
                json.dump({"mcpServers": {"jira-connector": {"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/mcp/jira-connector/index.js"]}}}, f)
            e = estados(run(lab, "tools.py", "--no-network"))
            self.assertEqual((e["jira-mcp-deps"], e["jira-mcp-duplicado"]), ("OK", "FAIL"))   # duplicado con ruta sin expandir
            with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
                json.dump({"mcpServers": {"jira-connector": {"command": "node", "args": [os.path.join(jc, "index.js")]}}}, f)
            self.assertEqual(estados(run(lab, "tools.py", "--no-network"))["jira-mcp-duplicado"], "WARN")   # duplicado pero con ruta buena
            with open(os.path.join(home, ".claude", "settings.json"), "w") as f:
                json.dump({}, f)
            self.assertEqual(estados(run(lab, "tools.py", "--no-network"))["jira-mcp-duplicado"], "OK")
            comp = lab.path("api") if hasattr(lab, "path") else os.path.join(lab.ws, "api")
            os.makedirs(comp, exist_ok=True)
            with open(os.path.join(comp, ".env"), "w") as f:
                f.write("JIRA_HOST=x\n")
            self.assertEqual(estados(run(lab, "tools.py", "--no-network"))["jira-env-proyecto"], "WARN")

    def test_sin_workspace_sale_con_3(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(CK, "tools.py"), "--home", "/no/existe"], capture_output=True, text=True, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 3)


class TestVpn(unittest.TestCase):
    def test_clasificacion_de_errores(self):
        for texto, cls in (("fatal: Could not resolve host: x", "red"), ("remote: HTTP Basic: Access denied", "cred"),
                           ("error: 403 forbidden", "perm"), ("fatal: repository 'x' not found", "noexiste"), ("otra cosa", "otro")):
            self.assertEqual(vpn.classify(texto), cls, texto)

    def test_host_y_url_limpia(self):
        self.assertEqual(vpn.host_of("https://u:p@h.example:8443/g/r.git"), "h.example")
        self.assertEqual(vpn.host_of("git@h.example:g/r.git"), "h.example")
        self.assertEqual(vpn.clean_url("https://u:S3CRETO@h/g"), "https://h/g")
        self.assertEqual(vpn.host_of("/tmp/local/origin.git"), "")

    def test_remoto_local_lectura_y_escritura_y_remoto_con_host_omitido(self):
        with TC.CLab() as lab:
            bare = os.path.join(lab.root, "origin.git")
            subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
            repo = lab.ws + "/api"
            env = dict(os.environ, GIT_AUTHOR_NAME="x", GIT_AUTHOR_EMAIL="x@x", GIT_COMMITTER_NAME="x", GIT_COMMITTER_EMAIL="x@x")
            subprocess.run(["git", "-C", repo, "remote", "set-url", "origin", bare], check=True)
            subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "i"], check=True, env=env)
            r = run(lab, "vpn.py", "--component", "api", "--no-network")
            self.assertIn("lectura OK · escritura OK", r.stdout)
            self.assertIn("WARN|repo-api|", r.stdout); self.assertIn("no existe en el remoto", r.stdout)       # el remoto está vacío: aún no hay rama
            self.assertNotIn("S3CRETO", r.stdout)
            r = run(lab, "vpn.py", "--component", "arkana", "--no-network")           # remoto con host: no se contacta
            self.assertIn("INFO|repo-arkana|", r.stdout); self.assertIn("omitido", r.stdout)


class TestComponent(unittest.TestCase):
    def test_componente_sin_git_y_permisos_faltantes(self):
        with TC.CLab() as lab:
            r = run(lab, "component.py", "--component", "docs", "--no-network")
            e = estados(r)
            self.assertEqual(e["permisos"], "FAIL"); self.assertEqual(e["claude-md"], "FAIL"); self.assertEqual(e["git-repo"], "WARN")
            self.assertEqual(r.returncode, 1)

    def test_se_deduce_del_directorio_actual(self):
        with TC.CLab() as lab:
            r = subprocess.run([sys.executable, "-I", os.path.join(CK, "component.py"), "--home", lab.arkana, "--no-network"], capture_output=True, text=True,
                               cwd=lab.ws + "/api", env=lab.env, stdin=subprocess.DEVNULL)
            self.assertIn("api", r.stdout.splitlines()[0])
            r = subprocess.run([sys.executable, "-I", os.path.join(CK, "component.py"), "--home", lab.arkana], capture_output=True, text=True, cwd="/", env=lab.env, stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 3)


if __name__ == "__main__":
    unittest.main()
