"""Laboratorio de los tests del núcleo: un workspace temporal con HOME falso. No toca nada real."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", ".."))          # shared/lib: contiene el paquete arkana_core
CORE_SH = os.path.abspath(os.path.join(HERE, "..", "arkana-core.sh"))
sys.path.insert(0, LIB)
sys.dont_write_bytecode = True

COMPONENTES = [  # alias, tipo, ruta relativa a la raíz
    ("app", "node", "md-mf"), ("api", "maven", "md-backend"),
    ("app-web", "node", "md-mf/src/wa"), ("app-ui", "node", "md-mf/src/mf"),
    ("docs", "docs", "md-docs"), ("specs", "docs", "md-specs"),
]


def manifiesto(componentes=COMPONENTES, **extra):
    d = {"schema": 1, "workspace": {"name": "lab"},
         "arkana": {"alias": "ARKANA", "path": "shared", "branches": {"main": "main", "develop": "develop"}},
         "components": [{"alias": a, "type": t, "path": p} for a, t, p in componentes]}
    d.update(extra)
    return d


class Lab:
    """root/shared/.arkana/{arkana.json, core/workspace.json} y las carpetas de los componentes; HOME falso."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="arkana-core-")
        self.root = os.path.realpath(self.tmp.name)
        self.home_dir = os.path.join(self.root, "home")          # HOME falso
        self.arkana = os.path.join(self.root, "ws", "shared")
        self.ws = os.path.join(self.root, "ws")
        os.makedirs(self.home_dir)
        os.makedirs(os.path.join(self.arkana, ".arkana", "core"))
        self.escribir("arkana.json", {"schema_version": 1, "workspace": {"name": "lab"}, "root": ".."})
        self.escribir(os.path.join("core", "workspace.json"), manifiesto())
        for _, _, p in COMPONENTES:
            os.makedirs(os.path.join(self.ws, p), exist_ok=True)
        self._env = dict(os.environ)
        for k in ("ARKANA_HOME",):
            os.environ.pop(k, None)
        os.environ["HOME"] = self.home_dir
        self.env = dict(os.environ)
        return self

    def __exit__(self, *a):
        os.environ.clear(); os.environ.update(self._env)
        self.tmp.cleanup()

    def escribir(self, rel, obj):
        p = os.path.join(self.arkana, ".arkana", rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
        return p

    def registrar(self):
        from arkana_core import locate
        return locate.register(self.arkana, "lab")

    def bash(self, codigo, cwd=None, env=None):
        r = subprocess.run(["bash", "-c", f'source "{CORE_SH}"; {codigo}'], capture_output=True, text=True, cwd=cwd or self.ws, env=env or self.env)
        return r.returncode, r.stdout.strip()
