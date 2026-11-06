"""Laboratorio de los tests de mensajería: un workspace temporal (ARKANA + app + api + app-web anidado) con HOME falso. Sin red."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
CLI = os.path.join(PLUGIN, "scripts", "messaging.sh")
COMPONENTES = [("app", "node", "md-mf"), ("api", "maven", "md-backend"), ("app-web", "node", "md-mf/src/wa")]


class Lab:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="msg-lab-")
        self.root = os.path.realpath(self.tmp.name)
        self.ws = os.path.join(self.root, "ws")
        self.arkana = os.path.join(self.ws, "shared")
        self.home = os.path.join(self.root, "home")
        os.makedirs(self.home)
        st = os.path.join(self.arkana, ".arkana")
        os.makedirs(os.path.join(st, "core"))
        self._w(os.path.join(st, "arkana.json"), {"schema_version": 1, "workspace": {"name": "lab"}, "root": ".."})
        self._w(os.path.join(st, "core", "workspace.json"), {
            "schema": 1, "workspace": {"name": "lab"},
            "arkana": {"alias": "ARKANA", "path": "shared", "branches": {"main": "main", "develop": "develop"}},
            "components": [{"alias": a, "type": t, "path": p} for a, t, p in COMPONENTES]})
        for _, _, p in COMPONENTES:
            os.makedirs(os.path.join(self.ws, p), exist_ok=True)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("ARKANA_")}
        self.env.update(HOME=self.home, ARKANA_HOME=self.arkana, ARKANA_NET_BREAKER_FILE=os.path.join(self.root, "breaker.json"),
                        GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
        return self

    def __exit__(self, *a):
        self.tmp.cleanup()

    @staticmethod
    def _w(p, obj):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)

    def cwd(self, who):
        return {"arkana": self.arkana, "app": os.path.join(self.ws, "md-mf"), "api": os.path.join(self.ws, "md-backend"),
                "app-web": os.path.join(self.ws, "md-mf", "src", "wa"), "fuera": self.root}[who]

    def run(self, who, *args, timeout=60):
        return subprocess.run(["bash", CLI, *args], capture_output=True, text=True, env=self.env, cwd=self.cwd(who), timeout=timeout, stdin=subprocess.DEVNULL)

    def popen(self, who, *args):
        return subprocess.Popen(["bash", CLI, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=self.env, cwd=self.cwd(who))

    def put(self, who, tipo="notice", asunto="Algo ha cambiado en el endpoint", to="all", extra=()):
        r = self.run(who, "put", "--type", tipo, "--subject", asunto, "--to", to, *extra, "--json")
        assert r.returncode == 0, r.stdout + r.stderr
        det = json.loads(r.stdout)["items"][0]["detail"]
        return det.split()[0]

    def get(self, who, *args):
        r = self.run(who, "get", *args, "--json")
        assert r.returncode == 0, r.stdout + r.stderr
        return json.loads(r.stdout)

    def store(self, rel=""):
        return os.path.join(self.arkana, ".arkana", "arkana-messaging", "state", rel)

    def msg(self, nid):
        return self.jload(self.store(f"messages/{nid}.json"))

    @staticmethod
    def jload(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def jdump(path, obj):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)

    def file(self, name, text):
        p = os.path.join(self.root, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p
