"""Tres nombres por componente: alias, carpeta real y nombre-módulo (compartido, en arkana-project.json). Referencia por cualquiera, prefijos, unicidad y scope de commits."""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

LIB = os.path.join(E.SCRIPTS, "lib")
sys.path.insert(0, LIB)
from arkana_core import manifest, project  # noqa: E402


def cli(lab, script, *a):
    return subprocess.run([sys.executable, "-I", os.path.join(LIB, script), *a, "--home", lab.arkana], capture_output=True, text=True,
                          env=lab.env, cwd=lab.ws, stdin=subprocess.DEVNULL, timeout=60)


def checks_all(lab, *a):
    return subprocess.run([sys.executable, "-I", os.path.join(E.SCRIPTS, "checks", "all.py"), *a, "--home", lab.arkana], capture_output=True, text=True,
                          env=lab.env, cwd=lab.ws, stdin=subprocess.DEVNULL, timeout=120)


def con_registro(lab):
    """Proyecto migrado: registro compartido y los mismos ids en el manifiesto local."""
    f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
    d = json.loads(Path(f).read_text())
    ids = {}
    for n, b in enumerate([d["arkana"]] + d["components"], 1):
        b["id"] = ids[b.get("alias", "ARKANA").lower()] = "%08d-0000-4000-8000-000000000000" % n
        if b.get("alias") == "api":
            b["path"] = "md-backend"                                                  # carpeta real distinta del alias
    Path(f).write_text(json.dumps(d))
    lf = os.path.join(lab.arkana, ".arkana", "arkana-workspace", "local.json")
    if os.path.isfile(lf):
        loc = json.loads(Path(lf).read_text())
        (loc.get("paths") or {}).pop("api", None)
        Path(lf).write_text(json.dumps(loc))
    Path(lab.arkana, "arkana-project.json").write_text(json.dumps({"schema_version": 1, "layout": 5, "workspace": {"id": "x", "name": "t"},
                                                                   "components": [{"id": i, "alias": a} for a, i in ids.items()]}))


def ws(lab):
    return manifest.load(lab.arkana)


def reg(lab):
    return project.Registry.load(lab.arkana)


def manifiesto(lab):
    return json.loads(Path(lab.arkana, ".arkana", "core", "workspace.json").read_text())


class TestModulo(unittest.TestCase):
    def test_el_modulo_se_guarda_en_el_registro_compartido_y_no_en_el_manifiesto(self):
        with TC.CLab() as lab:
            con_registro(lab)
            antes = manifiesto(lab)
            r = cli(lab, "components.py", "edit", "--alias", "api", "--module", "viso_rest_inquilino")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(reg(lab).module_of("api"), "viso_rest_inquilino")
            self.assertEqual(manifiesto(lab), antes)                                  # el manifiesto local no cambia: ni campo nuevo ni schema
            self.assertEqual(ws(lab).module("api"), "viso_rest_inquilino")
            lst = cli(lab, "components.py", "list").stdout
            self.assertIn("carpeta md-backend · módulo viso_rest_inquilino", lst)
            cli(lab, "components.py", "edit", "--alias", "api", "--module", "")
            self.assertEqual(reg(lab).module_of("api"), "")

    def test_sin_registro_pide_migrar(self):
        with TC.CLab() as lab:
            r = cli(lab, "components.py", "edit", "--alias", "api", "--module", "x")
            self.assertEqual(r.returncode, 1)
            self.assertIn("/arkana-evolve:apply", r.stdout)

    def test_nombre_de_modulo_valido(self):
        with TC.CLab() as lab:
            con_registro(lab)
            for malo in ("Con Espacio", "-raro", "a/b"):
                self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", f"--module={malo}").returncode, 1, malo)

    def test_dry_run_no_escribe(self):
        with TC.CLab() as lab:
            con_registro(lab)
            r = cli(lab, "components.py", "edit", "--alias", "api", "--module", "x", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertEqual(reg(lab).module_of("api"), "")


class TestUnicidad(unittest.TestCase):
    def test_un_modulo_que_repite_alias_o_carpeta_de_otro_componente_se_rechaza_sin_escribir(self):
        with TC.CLab() as lab:
            con_registro(lab)
            antes_m, antes_r = manifiesto(lab), json.loads(Path(lab.arkana, "arkana-project.json").read_text())
            for repetido in ("app", "web", "docs"):
                r = cli(lab, "components.py", "edit", "--alias", "api", "--module", repetido)
                self.assertEqual(r.returncode, 1, repetido)
                self.assertIn("repetiría nombres", r.stdout)
            self.assertEqual((manifiesto(lab), json.loads(Path(lab.arkana, "arkana-project.json").read_text())), (antes_m, antes_r))

    def test_el_modulo_puede_ser_la_carpeta_o_el_alias_del_mismo_componente(self):
        with TC.CLab() as lab:
            con_registro(lab)
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--module", "md-backend").returncode, 0)
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--module", "api").returncode, 0)

    def test_un_alta_cuyo_alias_es_la_carpeta_de_otro_se_rechaza(self):
        with TC.CLab() as lab:
            con_registro(lab)
            os.makedirs(lab.ws + "/otra")
            r = cli(lab, "components.py", "add", "--alias", "md-backend", "--path", lab.ws + "/otra")
            self.assertEqual(r.returncode, 1)
            self.assertIn("repetiría nombres", r.stdout)
            self.assertEqual(len(ws(lab).aliases()), 7)

    def test_un_conflicto_previo_no_bloquea_cambios_ajenos_pero_check_lo_marca(self):
        with TC.CLab() as lab:
            con_registro(lab)
            p = Path(lab.arkana, "arkana-project.json")
            d = json.loads(p.read_text())
            for c in d["components"]:
                if c["alias"] == "api":
                    c["module"] = "app"                                               # alguien lo dejó repetido (p. ej. tras un merge)
            p.write_text(json.dumps(d))
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "docs", "--develop", "dev2").returncode, 0)
            out = checks_all(lab, "--component", "arkana").stdout
            self.assertRegex(out, r"FAIL\|nombres\|el nombre 'app' lo usan varios componentes")

    def test_check_dice_ok_cuando_no_se_repite_nada(self):
        with TC.CLab() as lab:
            con_registro(lab)
            self.assertIn("OK|nombres|", checks_all(lab, "--component", "arkana").stdout)


class TestReferenciaPorCualquierNombre(unittest.TestCase):
    def lab(self, lab):
        con_registro(lab)
        cli(lab, "components.py", "edit", "--alias", "api", "--module", "viso_rest_inquilino")

    def test_edit_acepta_carpeta_modulo_y_prefijos(self):
        with TC.CLab() as lab:
            self.lab(lab)
            for ref, dev in (("api", "d1"), ("API", "d2"), ("md-backend", "d3"), ("viso_rest_inquilino", "d4"), ("dir:md-backend", "d5"),
                             ("mod:viso_rest_inquilino", "d6"), ("alias:api", "d7")):
                r = cli(lab, "components.py", "edit", "--alias", ref, "--develop", dev)
                self.assertEqual(r.returncode, 0, (ref, r.stdout))
                self.assertEqual(ws(lab).get("api")["branches"]["develop"], dev, ref)

    def test_un_prefijo_de_otro_tipo_no_adivina(self):
        with TC.CLab() as lab:
            self.lab(lab)
            for mal in ("dir:api", "mod:md-backend", "alias:md-backend", "mod:api"):
                self.assertEqual(cli(lab, "components.py", "edit", "--alias", mal, "--develop", "x").returncode, 1, mal)

    def test_las_opciones_component_de_los_comandos_aceptan_cualquier_nombre(self):
        with TC.CLab() as lab:
            self.lab(lab)
            for nombre in ("viso_rest_inquilino", "md-backend", "mod:viso_rest_inquilino"):
                r = cli(lab, "status.py", "--component", nombre)
                self.assertIn("|api|", r.stdout, (nombre, r.stdout))
                r = cli(lab, "commits.py", "show", "--component", nombre)
                self.assertEqual(r.returncode, 0, (nombre, r.stdout))
            self.assertEqual(cli(lab, "commits.py", "show", "--component", "nadie").returncode, 3)


class TestScopeDeCommits(unittest.TestCase):
    def test_con_module_en_el_formato_el_scope_es_el_modulo(self):
        with TC.CLab() as lab:
            con_registro(lab)
            cli(lab, "components.py", "edit", "--alias", "api", "--module", "viso_rest_inquilino")
            self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--commit-format", "conventional({module})").returncode, 0)
            self.assertIn("chore(viso_rest_inquilino): ignore", cli(lab, "commits.py", "show", "--component", "api").stdout)
            cli(lab, "components.py", "edit", "--alias", "api", "--commit-format", "ia4d({module})")
            out = cli(lab, "commits.py", "show", "--component", "api").stdout
            self.assertIn("docs(viso_rest_inquilino) link", out); self.assertIn("**IA4D**", out)
            self.assertIn("scope viso_rest_inquilino", cli(lab, "commits.py", "status", "--component", "api").stdout)

    def test_sin_modulo_cae_al_alias_y_avisa(self):
        with TC.CLab() as lab:
            con_registro(lab)
            cli(lab, "components.py", "edit", "--alias", "api", "--commit-format", "ia4d({module})")
            self.assertIn("docs(api) link", cli(lab, "commits.py", "show", "--component", "api").stdout)
            self.assertRegex(cli(lab, "commits.py", "status", "--component", "api").stdout, r"WARN\|commits-api\|.*no tiene módulo")

    def test_por_defecto_y_con_alias_explicito_el_scope_es_el_alias(self):
        with TC.CLab() as lab:
            con_registro(lab)
            cli(lab, "components.py", "edit", "--alias", "api", "--module", "viso_rest_inquilino")
            self.assertIn("chore(api): ignore", cli(lab, "commits.py", "show", "--component", "api").stdout)
            cli(lab, "components.py", "edit", "--alias", "api", "--commit-format", "conventional({alias})")
            self.assertIn("chore(api): ignore", cli(lab, "commits.py", "show", "--component", "api").stdout)

    def test_un_formato_desconocido_se_rechaza(self):
        with TC.CLab() as lab:
            for mal in ("ia5", "ia4d({x})", "{module}"):
                self.assertEqual(cli(lab, "components.py", "edit", "--alias", "api", "--commit-format", mal).returncode, 1, mal)


class TestAliasEnMayusculas(unittest.TestCase):
    def test_los_alias_se_muestran_en_mayusculas_y_se_guardan_en_minusculas(self):
        with TC.CLab() as lab:
            out = cli(lab, "status.py").stdout
            self.assertIn("ARKANA", out)
            self.assertNotRegex(out, r"\|\w*\|app ")
            self.assertEqual(manifest.display("api"), "API")
            self.assertEqual(ws(lab).aliases()[:3], ["arkana", "app", "api"])


if __name__ == "__main__":
    unittest.main()
