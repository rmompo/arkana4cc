"""Laboratorio de pruebas: siete repos git desechables, ~/.claude falso y el claude falso. No toca nada real."""
import json
import os
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(AQUI, "..", ".."))
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(PLUGIN, "scripts", "lib"))
sys.path.insert(0, os.path.join(PLUGIN, "tests", "unit"))
import state  # noqa: E402
import common  # noqa: E402
import inbox  # noqa: E402

SCRIPTS = os.path.join(PLUGIN, "scripts")
FAKE = os.path.join(PLUGIN, "tests", "fake-claude.py")
FAKE_MESSAGING = os.path.join(PLUGIN, "tests", "fake-messaging.py")
CLAVES = ("HOME", "ARKANA_HOME", "ARKANA_AGENTIC_DIR", "ARKANA_AGENTIC_CLAUDE_BIN", "ARKANA_AGENTIC_WATCH_INTERVAL",
          "ARKANA_AGENTIC_KILL_GRACE", "ARKANA_AGENTIC_OWNER_PID", "FAKE_CLAUDE_LOG", "FAKE_EDIT", "ARKANA_PLUGINS_DIR", "ARKANA_MESSAGING_CMD", "FAKE_MESSAGING_LOG", "FAKE_MESSAGING_RC", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")


def sh(cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


class Lab:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="agentic-lab-")
        r = self.root = self.tmp.name
        self.home = os.path.join(r, "home")
        for f, txt in ((".claude/settings.json", "{}"), (".git-credentials", "https://u:SECRETO@h\n"), (".ia4d/.env", "X=1\n"),
                       (".npmrc", "@scope:registry=x\n"), (".gitconfig", "[user]\n")):
            p = os.path.join(self.home, f)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(txt)
        self.rutas = common.make_workspace(r)                           # manifiesto de pruebas en <r>/shared/.arkana (alias neutros)
        for rid in ("shared", "app", "api", "docs", "specs", "app-web", "app-ui"):
            self._repo(rid)
        self.marker = os.path.join(r, "marca-verificacion")
        self.cambios = {"HOME": self.home, "ARKANA_HOME": self.rutas["shared"], "ARKANA_AGENTIC_DIR": os.path.join(r, "agentic"),
                        "ARKANA_AGENTIC_CLAUDE_BIN": FAKE, "ARKANA_AGENTIC_WATCH_INTERVAL": "0.2", "ARKANA_AGENTIC_KILL_GRACE": "1",
                        "ARKANA_AGENTIC_OWNER_PID": "none", "FAKE_CLAUDE_LOG": os.path.join(r, "fake.log"),
                        "ARKANA_PLUGINS_DIR": os.path.join(r, "arkana-data"), "ARKANA_MESSAGING_CMD": f"{sys.executable} {FAKE_MESSAGING}",
                        "FAKE_MESSAGING_LOG": os.path.join(r, "fake-messaging.log"),
                        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
        self.previo = {k: os.environ.get(k) for k in CLAVES}
        os.environ.update(self.cambios)
        self.env = dict(os.environ)
        return self

    def __exit__(self, *a):
        for k, v in self.previo.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def _repo(self, rid):
        d = self.rutas[rid]
        os.makedirs(os.path.join(d, ".husky"), exist_ok=True)
        os.makedirs(os.path.join(d, "src"), exist_ok=True)
        ficheros = {
            "CLAUDE.md": f"# {rid}\n\nNorma del repo {rid}: commits en ingles.\n\n<!-- arkana:messaging:start -->\n@.arkana/core/novedades.md\n<!-- arkana:messaging:end -->\n",
            "package.json": json.dumps({"name": rid, "description": "d", "scripts": {"test": "echo ok"}, "dependencies": {}}),
            "src/a.ts": "export const a = 1;\n", "README.md": "# r\n", ".husky/pre-commit": "#!/bin/sh\nexit 0\n",
            ".gitignore": "/src/*\n" if rid == "app" else ".arkana/\nnode_modules\n.env\n"}
        for n, txt in ficheros.items():
            if rid == "app" and n == "src/a.ts":
                continue   # el src/ de app contiene los repos anidados (esta ignorado)
            with open(os.path.join(d, n), "w", encoding="utf-8") as f:
                f.write(txt)
        if rid == "app":
            os.makedirs(os.path.join(d, "app"), exist_ok=True)
        e = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
        for c in (["init", "-q", "-b", "develop"], ["config", "user.email", "lab@example.com"], ["config", "user.name", "Lab"],
                  ["config", "commit.gpgsign", "false"], ["add", "-A"], ["commit", "-qm", "init"]):
            sh(["git", "-C", d, *c], env=e)

    # ----- planes -----
    def plan(self, tareas=None, plan_extra=None, aprobar=True, empezar=True, comandos_extra=()):
        pid = state.new_plan_id()
        tareas = tareas if tareas is not None else [{}]
        ids = [f"T{i:03d}" for i in range(1, len(tareas) + 1)]
        campos = dict(tareas=ids, politica={}, contadores={}, autoriza={"commits_locales": True})
        campos.update(plan_extra or {})
        plan = common.plan_ok(pid, "borrador", **campos)
        state.save_json(os.path.join(state.plan_dir(pid), "plan.json"), plan)
        especs = []
        for tid, extra in zip(ids, tareas):
            base = common.tarea_ok(tid, pid, "pendiente", repo="api", rutas_permitidas=["src/**"], instrucciones=["1. editar src/a.ts"],
                                   criterios_aceptacion=[{"id": "C1", "descripcion": "se cumple", "verificacion": "v1"}],
                                   verificaciones=[{"id": "v1", "comando": ["true"], "timeout_s": 30}])
            base.update(extra)
            especs.append(base)
            state.save_json(os.path.join(state.plan_dir(pid), "tareas", f"{tid}.json"), base)
        state.save_json(os.path.join(os.environ["ARKANA_AGENTIC_DIR"], "config", "comandos-permitidos.json"),
                           {"permitidos": [["true"], ["false"], ["touch", self.marker]] + [list(c) for c in comandos_extra]})
        if aprobar:
            state.approve_plan(pid)
        if empezar:
            state.start_plan(pid)
            inbox.freeze(pid, especs)                                       # como `plan start`: congela los mensajes de cada tarea
        return pid

    def mensaje(self, mid, **campos):
        """Escribe un mensaje en el almacén falso de mensajería (clase data) y lo devuelve."""
        m = {"id": mid, "asunto": f"Mensaje {mid}", "tipo": "task", "de": "app", "para": ["api"], "destinatarios": ["api"], "prioridad": "normal",
             "estado": "open", "repeticion": "once", "instrucciones": ["a"], "criterios": ["b"], "fecha": "2026-11-03T10:00:00Z", "updated": "2026-11-03T10:00:00Z"}
        m.update(campos)
        state.save_json(os.path.join(os.environ["ARKANA_PLUGINS_DIR"], "arkana-messaging", "state", "messages", mid + ".json"), m)
        return m

    def llamadas_mensajeria(self):
        f = self.cambios["FAKE_MESSAGING_LOG"]
        if not os.path.exists(f):
            return []
        with open(f, encoding="utf-8") as fh:
            return [json.loads(x)["argv"] for x in fh.read().splitlines()]

    # ----- ejecucion -----
    def ejecutar(self, script, *args, env=None, timeout=90):
        e = dict(self.env, **(env or {}))
        return subprocess.run(["bash", os.path.join(SCRIPTS, script), *args], capture_output=True, text=True, env=e, timeout=timeout,
                              cwd=self.root)                       # nunca desde el directorio de las pruebas: el claude falso edita en su cwd

    def lanzar(self, pid, tid="T001", env=None, timeout=90):
        return self.ejecutar("launch-worker.sh", pid, tid, env=env, timeout=timeout)

    def finalizar(self, pid, tid="T001"):
        return self.ejecutar("verify-task.sh", pid, tid)

    def popen_lanzar(self, pid, tid="T001", env=None):
        e = dict(self.env, **(env or {}))
        return subprocess.Popen(["bash", os.path.join(SCRIPTS, "launch-worker.sh"), pid, tid], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=e)

    def correr(self, pid, tid="T001", modo="hecha", env=None):
        """lanzar + finalizar con un modo del claude falso. Devuelve (launch, finish, resultado de verificacion)."""
        e = dict({"FAKE_MODE": modo}, **(env or {}))
        l = self.lanzar(pid, tid, env=e)
        f = self.finalizar(pid, tid)
        ver = None
        n = self.tarea(pid, tid)["intentos"]
        ruta = os.path.join(state.plan_dir(pid), "verificacion", f"{tid}.{n}.json")
        if os.path.exists(ruta):
            ver = state.load_json(ruta)
        return l, f, ver

    # ----- consultas -----
    def tarea(self, pid, tid="T001"):
        return state.load_json(os.path.join(state.plan_dir(pid), "tareas", f"{tid}.json"))

    def plan_json(self, pid):
        return state.load_json(os.path.join(state.plan_dir(pid), "plan.json"))

    def rama(self, rid):
        return sh(["git", "-C", self.rutas[rid], "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

    def head(self, rid, ref="HEAD"):
        return sh(["git", "-C", self.rutas[rid], "rev-parse", ref]).stdout.strip()

    def esperar(self, cond, timeout=15, paso=0.05):
        fin = time.time() + timeout
        while time.time() < fin:
            if cond():
                return True
            time.sleep(paso)
        return False

    def vivo(self, pid):
        import launch
        return launch.pid_alive(pid)
