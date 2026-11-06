"""Generador y evaluador semántico de permisos (permissions.py) sobre un workspace de laboratorio."""
import json
import os
import stat
import subprocess
import sys
import unittest

import environment as E
import test_layout as TL

sys.path.insert(0, os.path.join(E.SCRIPTS, "lib"))
import permissions as P  # noqa: E402
from arkana_core import manifest  # noqa: E402
import layout  # noqa: E402


class PLab(TL.Lab):
    def __enter__(self):
        super().__enter__()
        E.seed(self.arkana, self.ws)
        self.w = manifest.load(self.arkana)
        return self

    def put(self, alias, perm, mode=0o600):
        f = P.settings_file(self.w, alias)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        json.dump({"permissions": perm}, open(f, "w"))
        os.chmod(f, mode)


class TestEsperado(unittest.TestCase):
    def test_matriz_del_modelo(self):
        with PLab() as lab:
            m = P.matrix(lab.w)
            self.assertEqual(set(m), set(lab.w.aliases()))
            for a, row in m.items():
                self.assertEqual(row[a], "REW", a)                         # diagonal
                self.assertEqual(row["arkana"], "REW", a)                  # todos REW sobre ARKANA
                self.assertEqual(row[".credentials"], "xxx", a)            # nadie toca las credenciales
                self.assertEqual(row["agentic-state"], "Rxx", a)           # nadie edita el estado de agentic
            self.assertTrue(all(c == "REW" for c in m["arkana"].values() if c != "xxx" and c != "Rxx"))
            self.assertEqual(m["arkana"]["api"], "REW")
            self.assertEqual(m["api"]["docs"], "Rxx")
            self.assertEqual(m["app"]["app-web"], "Rxx")                  # app no edita sus anidados
            self.assertEqual(m["app-web"]["app"], "R··")                  # el contenedor: solo lectura, sin deny que tape lo propio

    def test_solo_arkana_lleva_agentic_y_el_deny_de_claude(self):
        with PLab() as lab:
            a, c = P.expected(lab.w, "arkana"), P.expected(lab.w, "api")
            self.assertEqual(len(a["ask"]), 12)
            self.assertIn("Bash(claude -p *)", a["deny"])
            self.assertNotIn("ask", c)
            self.assertFalse([r for r in c["allow"] + c["deny"] if r.startswith("Bash(")])

    def test_formato_de_ruta_absoluta(self):
        with PLab() as lab:
            self.assertTrue(all(r.startswith(("Read(//", "Edit(//", "Write(//", "Bash(")) for k in P.expected(lab.w, "app").values() for r in k))


class TestEvaluador(unittest.TestCase):
    def test_deny_gana_a_ask_y_ask_a_allow(self):
        r = {"allow": ["Edit(//a/**)"], "ask": ["Edit(//a/b/**)"], "deny": ["Edit(//a/b/c/**)"]}
        self.assertEqual(P.decide(r, "Edit", "/a/x"), "allow")
        self.assertEqual(P.decide(r, "Edit", "/a/b/x"), "ask")
        self.assertEqual(P.decide(r, "Edit", "/a/b/c/x"), "deny")

    def test_edit_cubre_write_pero_no_al_reves(self):
        self.assertEqual(P.decide({"allow": ["Edit(//a/**)"]}, "Write", "/a/x"), "allow")
        self.assertIsNone(P.decide({"allow": ["Write(//a/**)"]}, "Edit", "/a/x"))

    def test_recursiva_o_exacta(self):
        self.assertIsNone(P.decide({"allow": ["Read(//a/f)"]}, "Read", "/a/f/g"))
        self.assertEqual(P.decide({"allow": ["Read(//a/f)"]}, "Read", "/a/f"), "allow")

    def test_sintaxis_de_rutas(self):
        self.assertEqual(P.parse("Read(//x/y/**)")[:3], ("Read", "/x/y", True))
        self.assertEqual(P.parse("Read(~/z/**)")[1], os.path.expanduser("~/z"))
        t, p, rec, legacy = P.parse("Read(/home/x/**)", "/repo")
        self.assertTrue(legacy); self.assertEqual(p, "/repo/home/x")
        self.assertIsNone(P.parse("Bash(ls *)"))

    def test_celdas(self):
        self.assertEqual(P.cell({"allow": ["Read(//a/**)"], "ask": ["Edit(//a/**)"], "deny": ["Write(//a/**)"]}, "/a/x"), "Rex")

    def test_la_matriz_muestra_solo_las_letras_concedidas(self):
        """`Rxx` → `R`, `R··` → `R`, `xxx` → vacío; el modelo interno y el --json conservan las tres posiciones."""
        self.assertEqual([P.shown(c) for c in ("REW", "Rxx", "R··", "xxx", "Rex", "RE·")], ["REW", "R", "R", "", "Re", "RE"])


class TestDiffYApply(unittest.TestCase):
    def test_sin_fichero_falta(self):
        with PLab() as lab:
            self.assertEqual(P.diff(lab.w, "api")[0][0], "missing")

    def test_apply_deja_conforme_e_idempotente_con_modo_600(self):
        with PLab() as lab:
            for a in lab.w.aliases():
                P.apply(lab.w, a)
                self.assertEqual(P.diff(lab.w, a), [], a)
                self.assertEqual(stat.S_IMODE(os.stat(P.settings_file(lab.w, a)).st_mode), 0o600)
                self.assertEqual(P.apply(lab.w, a)[0], [], a)

    def test_apply_conserva_reglas_ajenas_y_hace_copia(self):
        with PLab() as lab:
            lab.put("api", {"allow": ["Bash(ls *)"], "ask": ["Bash(rm *)"]})
            f = P.settings_file(lab.w, "api")
            d = json.load(open(f)); d["otra"] = 1; json.dump(d, open(f, "w"))
            P.apply(lab.w, "api")
            d = json.load(open(f))
            self.assertIn("Bash(ls *)", d["permissions"]["allow"]); self.assertIn("Bash(rm *)", d["permissions"]["ask"]); self.assertEqual(d["otra"], 1)
            self.assertTrue(os.listdir(os.path.join(lab.w.state, "arkana-workspace", "bak")))

    def test_dry_run_no_escribe(self):
        with PLab() as lab:
            ch, f = P.apply(lab.w, "docs", dry=True)
            self.assertTrue(ch); self.assertFalse(os.path.exists(f))

    def test_clasifica_las_desviaciones(self):
        with PLab() as lab:
            P.apply(lab.w, "api")
            f = P.settings_file(lab.w, "api")
            d = json.load(open(f)); perm = d["permissions"]
            perm["allow"] = [r for r in perm["allow"] if not r.startswith("Write(") or "backend" not in r]
            perm["deny"] = [r for r in perm["deny"] if "docs" not in r]
            perm["allow"] += perm["allow"][:1] + [P.fmt("Edit", lab.w.path("docs"))]          # duplicada y de más
            perm["deny"].append("Write(//x/**)")
            json.dump(d, open(f, "w")); os.chmod(f, 0o644)
            kinds = {k for k, _ in P.diff(lab.w, "api")}
            self.assertTrue({"duplicate", "obsolete", "mode", "stronger"} <= kinds, kinds)

    def test_regla_legacy_con_una_barra(self):
        with PLab() as lab:
            home = lab.w.path("api")
            lab.put("api", {"allow": [f"Read({lab.w.path('docs')}/**)"], "deny": []})
            self.assertIn("legacy", {k for k, _ in P.diff(lab.w, "api")})
            P.apply(lab.w, "api")
            self.assertNotIn("legacy", {k for k, _ in P.diff(lab.w, "api")})

    def test_prune_quita_lo_que_da_de_mas(self):
        with PLab() as lab:
            P.apply(lab.w, "api")
            f = P.settings_file(lab.w, "api")
            d = json.load(open(f)); d["permissions"]["deny"] = [r for r in d["permissions"]["deny"] if "docs" not in r]
            d["permissions"]["allow"].append(P.fmt("Edit", lab.w.path("docs"))); json.dump(d, open(f, "w"))
            self.assertIn("stronger", {k for k, _ in P.diff(lab.w, "api")})
            P.apply(lab.w, "api", prune=True)
            self.assertEqual(P.diff(lab.w, "api"), [])

    def test_las_credenciales_quedan_denegadas_tras_apply(self):
        with PLab() as lab:
            P.apply(lab.w, "arkana")
            r = P.effective(lab.w, "arkana")[0]
            cred = os.path.join(lab.w.state, ".credentials")
            self.assertEqual([P.decide(r, t, cred) for t in P.TOOLS], ["deny"] * 3)


class TestCli(unittest.TestCase):
    def run_cli(self, lab, *a):
        return subprocess.run([sys.executable, "-I", os.path.join(E.SCRIPTS, "lib", "permissions.py"), *a, "--home", lab.arkana],
                              capture_output=True, text=True, env=dict(os.environ, HOME=lab.home_dir))

    def test_matriz_md_y_json_y_estado(self):
        with PLab() as lab:
            r = self.run_cli(lab, "matrix", "--format", "md")
            self.assertIn("| ARKANA |", r.stdout); self.assertIn("`R`", r.stdout); self.assertNotIn("Rxx", r.stdout); self.assertNotIn("·", r.stdout)
            self.assertEqual(json.loads(self.run_cli(lab, "matrix", "--json").stdout)["api"]["api"], "REW")
            self.assertEqual(self.run_cli(lab, "status").returncode, 1)          # nada aplicado aún
            self.assertEqual(self.run_cli(lab, "apply", "--json").returncode, 0)
            self.assertEqual(self.run_cli(lab, "status").returncode, 0)
            self.assertEqual(self.run_cli(lab, "matrix", "--component", "nada").returncode, 3)


if __name__ == "__main__":
    unittest.main()
