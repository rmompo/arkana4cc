"""Laboratorio de los tests de la statusline: workspace temporal con HOME falso y repos git reales (locales, sin red)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, ".."))
SL = os.path.join(PLUGIN, "statusline")
sys.path.insert(0, SL)
sys.dont_write_bytecode = True
GITENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@x", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@x")
COMPONENTES = [("app", "node", "md-mf"), ("api", "maven", "md-backend"), ("app-web", "node", "md-mf/src/wa"), ("docs", "docs", "md-docs")]


def git(path, *a, env=None):
    r = subprocess.run(["git", "-C", path, *a], capture_output=True, text=True, env=env or GITENV)
    assert r.returncode == 0, (a, r.stderr)
    return r.stdout.strip()


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


class Lab:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sl-lab-")
        self.root = os.path.realpath(self.tmp.name)
        self.ws = os.path.join(self.root, "ws")
        self.arkana = os.path.join(self.ws, "shared")
        self.home = os.path.join(self.root, "home")
        os.makedirs(os.path.join(self.home, ".claude"))
        st = os.path.join(self.arkana, ".arkana")
        wj(os.path.join(st, "arkana.json"), {"schema_version": 1, "workspace": {"name": "lab"}, "root": ".."})
        wj(os.path.join(st, "core", "workspace.json"), {
            "schema": 1, "workspace": {"name": "lab"}, "arkana": {"alias": "ARKANA", "path": "shared"},
            "components": [dict({"alias": a, "type": t, "path": p}, **({"remote_host": "x.invalid"} if a == "api" else {})) for a, t, p in COMPONENTES]})
        for p in ["shared"] + [x[2] for x in COMPONENTES]:
            d = os.path.join(self.ws, p)
            os.makedirs(d, exist_ok=True)
            subprocess.run(["git", "init", "-q", "-b", "develop", d], check=True, env=GITENV)
            git(d, "commit", "-q", "--allow-empty", "-m", "init")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("ARKANA_", "COLUMNS"))}
        self.env.update(HOME=self.home, ARKANA_HOME=self.arkana, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
        return self

    def __exit__(self, *a):
        self.tmp.cleanup()

    def path(self, alias):
        return {"arkana": self.arkana, **{a: os.path.join(self.ws, p) for a, _, p in COMPONENTES}}[alias]

    def run(self, cwd_alias, extra=None, columns=120, env=None):
        inp = {"workspace": {"project_dir": self.path(cwd_alias)}, "model": {"display_name": "Sonnet 5.5"}, "effort": {"level": "medium"},
               "context_window": {"used_percentage": 61}, "rate_limits": {"five_hour": {"used_percentage": 0}, "seven_day": {"used_percentage": 19}},
               "cost": {"total_cost_usd": 0.0}, "session_id": "sess-1"}
        inp.update(extra or {})
        r = subprocess.run(["bash", os.path.join(SL, "statusline.sh")], input=json.dumps(inp), capture_output=True, text=True,
                           env=dict(self.env, COLUMNS=str(columns), **(env or {})), cwd=self.root, timeout=30)
        return r
