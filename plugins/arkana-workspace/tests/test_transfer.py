"""export / import (ZIP con manifiesto y hashes) y handover: sin secretos, sin rutas absolutas, validación total antes de escribir."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

import environment as E
import test_credentials as TC

LIB = os.path.join(E.SCRIPTS, "lib")
SECRETO = TC.SECRETO


def cli(lab, script, *a, plugins=None):
    env = dict(lab.env, **({"ARKANA_PLUGINS_DIR": plugins} if plugins else {}))
    return subprocess.run([sys.executable, "-I", os.path.join(LIB, script), *a], capture_output=True, text=True, env=env,
                          cwd=lab.ws, stdin=subprocess.DEVNULL, timeout=60)


def make_plugins(tmp):
    """Un plugin de pruebas que declara datos de clase data (mensajes) y local, además de los reales."""
    d = os.path.join(tmp, "plugins", "arkana-fake")
    os.makedirs(os.path.join(d, ".claude-plugin"))
    with open(os.path.join(d, ".claude-plugin", "plugin.json"), "w") as f:
        json.dump({"name": "arkana-fake", "version": "1.0.0"}, f)
    with open(os.path.join(d, "arkana-plugin.json"), "w") as f:
        json.dump({"plugin": "arkana-fake", "contract": 1, "provides": ["x"], "data": [
        {"path": "arkana-fake/state/messages/", "class": "data", "description": "m"},
        {"path": "arkana-fake/local.txt", "class": "local", "description": "l"},
        {"path": "arkana-fake/config/", "class": "config", "description": "c"}]}, f)
    return os.path.join(tmp, "plugins")


def put(lab, rel, text):
    p = os.path.join(lab.arkana, ".arkana", rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def read(lab, rel):
    p = os.path.join(lab.arkana, ".arkana", rel)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return f.read()


def evil_zip(path, entries, manifest_files=None, schema=1, symlink=None):
    """ZIP con las entradas dadas; el manifiesto se calcula con los hashes reales salvo que se pase manifest_files."""
    files = manifest_files if manifest_files is not None else [
        {"path": n[6:], "class": "config", "plugin": "x", "size": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in entries.items() if n.startswith("files/")]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("arkana-export.json", json.dumps({"schema_version": schema, "files": files}))
        for n, b in entries.items():
            z.writestr(n, b)
        if symlink:
            zi = zipfile.ZipInfo(symlink)
            zi.external_attr = 0o120777 << 16
            z.writestr(zi, "/etc/passwd")
    return path


class TestExport(unittest.TestCase):
    def test_exporta_config_sin_credenciales_ni_rutas_locales(self):
        with TC.CLab() as lab, tempfile.TemporaryDirectory() as t:
            from_cred = os.path.join(lab.arkana, ".arkana", ".credentials")
            Path(from_cred).write_text(f"GIT_TOKEN_BE={SECRETO}\n"); os.chmod(from_cred, 0o600)
            put(lab, "arkana-workspace/tools.json", json.dumps({"schema_version": 1, "tools": [{"tool": "node", "version": "20.1.0", "path": "/home/yo/.nvm/node"}]}))
            put(lab, "arkana-workspace/local.json", '{"git": {"x": {"email": "yo@x.com"}}}')
            out = os.path.join(t, "ws.zip")
            r = cli(lab, "transfer.py", "export", "--out", out, "--home", lab.arkana)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            z = zipfile.ZipFile(out)
            names = z.namelist()
            self.assertIn("arkana-export.json", names)
            self.assertIn("files/core/workspace.json", names)
            self.assertFalse([n for n in names if "credentials" in n or "local.json" in n])
            blob = b"".join(z.read(n) for n in names)
            for prohibido in (SECRETO.encode(), b"/home/yo", b"yo@x.com"):
                self.assertNotIn(prohibido, blob)
            man = json.loads(z.read("arkana-export.json"))
            self.assertEqual(man["schema_version"], 1)
            self.assertIn("arkana-workspace", man["plugins"])
            for f in man["files"]:
                self.assertEqual(hashlib.sha256(z.read("files/" + f["path"])).hexdigest(), f["sha256"])
                self.assertFalse(os.path.isabs(f["path"]))
            self.assertEqual(json.loads(z.read("files/arkana-workspace/tools.json"))["tools"], [{"tool": "node", "version": "20.1.0"}])
            self.assertNotEqual(cli(lab, "transfer.py", "export", "--out", out, "--home", lab.arkana).returncode, 0)       # no sobrescribe sin --force
            self.assertEqual(cli(lab, "transfer.py", "export", "--out", out, "--force", "--home", lab.arkana).returncode, 0)

    def test_include_data_y_dry_run(self):
        with TC.CLab() as lab, tempfile.TemporaryDirectory() as t:
            pl = make_plugins(t)
            put(lab, "arkana-fake/state/messages/M1.json", '{"id": "M1"}')
            put(lab, "arkana-fake/local.txt", "local")
            a = os.path.join(t, "a.zip")
            b = os.path.join(t, "b.zip")
            self.assertEqual(cli(lab, "transfer.py", "export", "--out", a, "--home", lab.arkana, plugins=pl).returncode, 0)
            self.assertEqual(cli(lab, "transfer.py", "export", "--out", b, "--include-data", "--home", lab.arkana, plugins=pl).returncode, 0)
            self.assertNotIn("files/arkana-fake/state/messages/M1.json", zipfile.ZipFile(a).namelist())
            self.assertIn("files/arkana-fake/state/messages/M1.json", zipfile.ZipFile(b).namelist())
            self.assertNotIn("files/arkana-fake/local.txt", zipfile.ZipFile(b).namelist())
            c = os.path.join(t, "c.zip")
            r = cli(lab, "transfer.py", "export", "--out", c, "--dry-run", "--home", lab.arkana)
            self.assertEqual(r.returncode, 0)
            self.assertFalse(os.path.exists(c))


class TestImport(unittest.TestCase):
    def rechaza(self, lab, z, texto=""):
        antes = read(lab, "core/workspace.json")
        r = cli(lab, "transfer.py", "import", z, "--home", lab.arkana)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("no se ha escrito nada", r.stdout)
        self.assertIn(texto, r.stdout)
        self.assertEqual(read(lab, "core/workspace.json"), antes)
        self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana", "pwned")))

    def test_rechaza_zip_slip_rutas_absolutas_enlaces_hashes_y_destinos_desconocidos(self):
        with TC.CLab() as lab, tempfile.TemporaryDirectory() as t:
            good = b'{"x": 1}'
            ws = read(lab, "core/workspace.json").encode()
            casos = [
                ("slip", dict(entries={"files/../pwned": good}), "ruta no válida"),
                ("abs", dict(entries={"files//etc/pwned": good}), "ruta no válida"),
                ("barra", dict(entries={"files/a\\b": good}), "ruta no válida"),
                ("cred", dict(entries={"files/.credentials": good}), "credenciales"),
                ("cred2", dict(entries={"files/core/.credentials": good}), "credenciales"),
                ("fuera", dict(entries={"otra/cosa": good}), "fuera de files"),
                ("desconocido", dict(entries={"files/pwned": good}), "ningún plugin"),
                ("local", dict(entries={"files/arkana-workspace/local.json": good}), "no se importa"),
                ("esquema", dict(entries={"files/core/workspace.json": ws}, schema=9), "esquema"),
                ("symlink", dict(entries={}, symlink="files/core/workspace.json"), "enlace"),
                ("hash", dict(entries={"files/core/workspace.json": ws + b" "},
                              manifest_files=[{"path": "core/workspace.json", "size": len(ws) + 1, "sha256": "0" * 64}]), "alterado"),
                ("extra", dict(entries={"files/core/workspace.json": ws, "files/core/otro.json": good},
                               manifest_files=[{"path": "core/workspace.json", "size": len(ws), "sha256": hashlib.sha256(ws).hexdigest()}]), "fuera del manifiesto"),
                ("invalido", dict(entries={"files/core/workspace.json": b'{"schema": 1}'}), "manifiesto no válido"),
            ]
            for nombre, kw, texto in casos:
                with self.subTest(nombre):
                    self.rechaza(lab, evil_zip(os.path.join(t, nombre + ".zip"), **kw), texto)
            self.rechaza(lab, os.path.join(t, "no-existe.zip"), "ZIP")

    def test_ida_y_vuelta_entre_dos_workspaces(self):
        with TC.CLab() as a, tempfile.TemporaryDirectory() as t:
            put(a, "arkana-workspace/tools.json", json.dumps({"schema_version": 1, "tools": [{"tool": "node", "version": "20.1.0", "path": "/a/node"}]}))
            z = os.path.join(t, "w.zip")
            self.assertEqual(cli(a, "transfer.py", "export", "--out", z, "--home", a.arkana).returncode, 0)
            with TC.CLab() as b:
                put(b, "arkana-workspace/tools.json", json.dumps({"schema_version": 1, "tools": [{"tool": "node", "version": "18.0.0", "path": "/b/node"}]}))
                r = cli(b, "transfer.py", "import", z, "--on-conflict", "replace", "--home", b.arkana)
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertEqual(read(b, "core/workspace.json"), read(a, "core/workspace.json"))
                tools = json.loads(read(b, "arkana-workspace/tools.json"))["tools"]
                self.assertEqual(tools, [{"tool": "node", "version": "20.1.0", "path": "/b/node"}])          # la ruta local se conserva
                bak = os.path.join(b.arkana, ".arkana", "arkana-workspace", "bak")
                self.assertTrue(any(f.endswith("tools.json") for _d, _s, fs in os.walk(bak) for f in fs))     # copia de lo reemplazado
                self.assertIn("igual", r.stdout)                                                                # core/workspace.json idéntico
                self.assertNotIn(SECRETO, r.stdout)

    def test_conflictos_keep_replace_ask_y_dry_run(self):
        with TC.CLab() as a, tempfile.TemporaryDirectory() as t:
            put(a, "arkana-fake/config/c.json", '{"v": "zip"}')
            pl = make_plugins(t)
            z = os.path.join(t, "w.zip")
            self.assertEqual(cli(a, "transfer.py", "export", "--out", z, "--home", a.arkana, plugins=pl).returncode, 0)
            put(a, "arkana-fake/config/c.json", '{"v": "local"}')
            r = cli(a, "transfer.py", "import", z, "--dry-run", "--on-conflict", "replace", "--home", a.arkana, plugins=pl)
            self.assertEqual((r.returncode, read(a, "arkana-fake/config/c.json")), (0, '{"v": "local"}'))
            cli(a, "transfer.py", "import", z, "--home", a.arkana, plugins=pl)                                  # keep por defecto
            self.assertEqual(read(a, "arkana-fake/config/c.json"), '{"v": "local"}')
            r = cli(a, "transfer.py", "import", z, "--on-conflict", "ask", "--home", a.arkana, plugins=pl)
            self.assertIn("WARN|import:arkana-fake/config/c.json|conflicto", r.stdout)
            self.assertEqual(read(a, "arkana-fake/config/c.json"), '{"v": "local"}')
            cli(a, "transfer.py", "import", z, "--on-conflict", "replace", "--home", a.arkana, plugins=pl)
            self.assertEqual(read(a, "arkana-fake/config/c.json"), '{"v": "zip"}')

    def test_registros_de_datos_la_marca_de_borrado_y_lo_mas_reciente_mandan(self):
        with TC.CLab() as a, tempfile.TemporaryDirectory() as t:
            pl = make_plugins(t)
            m = "arkana-fake/state/messages/"
            for n, obj in (("viv", {"id": "viv", "updated": "2026-01-02"}), ("bor", {"id": "bor", "state": "deleted"}),
                           ("nue", {"id": "nue", "updated": "2026-05-01", "v": "zip"}), ("vie", {"id": "vie", "updated": "2026-01-01", "v": "zip"})):
                put(a, m + n + ".json", json.dumps(obj))
            z = os.path.join(t, "w.zip")
            self.assertEqual(cli(a, "transfer.py", "export", "--out", z, "--include-data", "--home", a.arkana, plugins=pl).returncode, 0)
            put(a, m + "viv.json", json.dumps({"id": "viv", "state": "deleted"}))                              # local: borrado; ZIP: vivo
            put(a, m + "bor.json", json.dumps({"id": "bor", "updated": "2026-09-09"}))                         # local: vivo; ZIP: borrado
            put(a, m + "nue.json", json.dumps({"id": "nue", "updated": "2026-01-01", "v": "local"}))           # ZIP más reciente
            put(a, m + "vie.json", json.dumps({"id": "vie", "updated": "2026-05-01", "v": "local"}))           # local más reciente
            r = cli(a, "transfer.py", "import", z, "--home", a.arkana, plugins=pl)
            self.assertEqual(r.returncode, 0, r.stdout)
            g = lambda n: json.loads(read(a, m + n + ".json"))
            self.assertEqual(g("viv")["state"], "deleted")      # la marca de borrado local gana
            self.assertEqual(g("bor")["state"], "deleted")      # la del ZIP gana
            self.assertEqual(g("nue")["v"], "zip")
            self.assertEqual(g("vie")["v"], "local")


class TestHandover(unittest.TestCase):
    def test_sin_secretos_ni_rutas_absolutas(self):
        with TC.CLab() as lab, tempfile.TemporaryDirectory() as t:
            cred = os.path.join(lab.arkana, ".arkana", ".credentials")
            Path(cred).write_text(f"GIT_TOKEN_BE={SECRETO}\n"); os.chmod(cred, 0o600)
            for fmt in ("md", "json"):
                r = cli(lab, "handover.py", "--format", fmt, "--home", lab.arkana)
                self.assertEqual(r.returncode, 0, r.stderr)
                for prohibido in (SECRETO, lab.root, lab.home_dir, "ci-user@"):
                    self.assertNotIn(prohibido, r.stdout, fmt)
                self.assertIn("api", r.stdout)
            out = os.path.join(t, "h.md")
            r = cli(lab, "handover.py", "--out", out, "--home", lab.arkana)
            self.assertEqual(r.returncode, 0)
            with open(out) as f:
                self.assertIn("# Traspaso del workspace", f.read())
            h = json.loads(cli(lab, "handover.py", "--format", "json", "--home", lab.arkana).stdout)
            self.assertEqual(h["credentials"]["refs"], ["GIT_TOKEN_BE"])
            self.assertEqual(h["credentials"]["missing"], [])


if __name__ == "__main__":
    unittest.main()
