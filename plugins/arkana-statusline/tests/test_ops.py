"""install / check / fix / choose / uninstall del despachador con HOME falso: la statusLine ajena solo se sustituye con --replace y pasa a ser un proveedor."""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

import lab as L
from lab import Lab

OPS = os.path.join(L.PLUGIN, "scripts", "lib", "ops.py")


def ops(lab, *a):
    return subprocess.run([sys.executable, "-I", OPS, *a], capture_output=True, text=True, env=lab.env, timeout=60, stdin=subprocess.DEVNULL)


def settings(lab):
    with open(os.path.join(lab.home, ".claude", "settings.json")) as f:
        return json.load(f)


def prefs(lab):
    p = os.path.join(lab.home, ".arkana", "statusline.json")
    return json.loads(Path(p).read_text()) if os.path.isfile(p) else {}


HOOK = os.path.join(L.PLUGIN, "scripts", "hook.py")


def hook(lab, cwd, env=None):
    return subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": cwd}), capture_output=True, text=True, env=env or lab.env, timeout=30)


class TestOps(unittest.TestCase):
    def test_install_copia_activa_y_hace_humo_y_es_idempotente(self):
        with Lab() as lab:
            self.assertIn("WARN|instalada", ops(lab, "check").stdout)
            dry = ops(lab, "install", "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stdout)
            self.assertFalse(os.path.exists(os.path.join(lab.home, ".claude", "arkana-statusline")))
            r = ops(lab, "install")
            self.assertEqual(r.returncode, 0, r.stdout)
            dest = os.path.join(lab.home, ".claude", "arkana-statusline")
            for f in ("statusline.sh", "dispatch.py", "statusline.py", "arkana_core/manifest.py", "arkana_core/locate.py"):
                self.assertTrue(os.path.isfile(os.path.join(dest, f)), f)
            self.assertNotIn("tests", os.listdir(os.path.join(dest, "arkana_core")))
            s = settings(lab)
            self.assertEqual(s["statusLine"], {"type": "command", "command": "bash ~/.claude/arkana-statusline/statusline.sh"})
            self.assertTrue(s["enabledPlugins"]["arkana-statusline@arkana"])
            self.assertIn("OK|humo", r.stdout)
            c = ops(lab, "check")
            for ok in ("OK|copia", "OK|statusline", "OK|otros-plugins", "OK|humo"):
                self.assertIn(ok, c.stdout)
            self.assertIn("INFO|proveedores|ninguno", c.stdout)
            self.assertIn("copia al día", ops(lab, "install").stdout)
            # la copia instalada funciona sola, sin el plugin ni el árbol: en la carpeta de ARKANA se ve la de Arkana
            out = subprocess.run(["bash", os.path.join(dest, "statusline.sh")], input=json.dumps({"workspace": {"project_dir": lab.path("arkana")}, "model": {"display_name": "M"}}),
                                 capture_output=True, text=True, env=dict(lab.env, COLUMNS="150"))
            self.assertIn("ARKANA", out.stdout)

    def test_con_arkana_instalada_gobierna_ella_y_la_statusline_ajena_pasa_a_ser_un_proveedor(self):
        with Lab() as lab:
            sj = os.path.join(lab.home, ".claude", "settings.json")
            with open(sj, "w") as f:
                json.dump({"statusLine": {"type": "command", "command": "bash ~/.claude/statusline-command.sh"}, "enabledPlugins": {"otra-statusline@x": True}, "theme": "dark"}, f)
            f = ops(lab, "fix")                                                                    # sin instalación previa de Arkana, fix no toma el hueco
            self.assertIn("WARN|statusline", f.stdout)
            self.assertIn("statusline-command.sh", settings(lab)["statusLine"]["command"])
            self.assertEqual(prefs(lab), {})
            self.assertIn("WARN|statusline", ops(lab, "check").stdout)
            self.assertIn("INFO|otros-plugins", ops(lab, "check").stdout)
            r = ops(lab, "install")                                                                # install SÍ: con Arkana instalada, Arkana gobierna (sin --replace)
            self.assertEqual(r.returncode, 0, r.stdout)
            s = settings(lab)
            self.assertIn("arkana-statusline/statusline.sh", s["statusLine"]["command"])
            self.assertEqual(s["theme"], "dark")                                                   # lo demás se conserva
            self.assertEqual(prefs(lab)["providers"], [{"id": "plugin4cc", "command": "bash ~/.claude/statusline-command.sh", "priority": 20}])
            bak = os.path.join(lab.home, ".claude", "arkana-statusline", "bak")
            self.assertTrue(any(f.startswith("settings.json.") for f in os.listdir(bak)))
            with open(os.path.join(bak, os.listdir(bak)[0])) as fh:
                self.assertIn("statusline-command.sh", fh.read())
            self.assertIn("plugin4cc (prioridad 20)", ops(lab, "check").stdout)
            self.assertEqual(ops(lab, "install", "--replace").returncode, 0)                       # --replace se acepta por compatibilidad

    def test_una_statusline_propia_pasa_a_ser_un_proveedor_con_id_por_comando(self):
        with Lab() as lab:
            with open(os.path.join(lab.home, ".claude", "settings.json"), "w") as f:
                json.dump({"statusLine": {"type": "command", "command": "bash ~/mi-barra.sh"}}, f)
            self.assertEqual(ops(lab, "install").returncode, 0)
            prov = prefs(lab)["providers"]
            self.assertEqual(len(prov), 1)
            self.assertTrue(prov[0]["id"].startswith("other-")); self.assertEqual((prov[0]["command"], prov[0]["priority"]), ("bash ~/mi-barra.sh", 30))

    def test_fix_reinstala_lo_desactualizado(self):
        with Lab() as lab:
            ops(lab, "install")
            py = os.path.join(lab.home, ".claude", "arkana-statusline", "statusline.py")
            with open(py, "a") as f:
                f.write("\n# alterado\n")
            self.assertIn("WARN|copia", ops(lab, "check").stdout)
            self.assertEqual(ops(lab, "fix", "--dry-run").returncode, 0)
            self.assertIn("# alterado", Path(py).read_text())
            r = ops(lab, "fix")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn("# alterado", Path(py).read_text())
            self.assertIn("OK|copia", ops(lab, "check").stdout)

    def test_choose_guarda_la_eleccion_por_componente_y_la_valida(self):
        with Lab() as lab:
            r = ops(lab, "choose", "--component", "app", "--use", "arkana")
            self.assertEqual(r.returncode, 0, r.stdout)
            clave = f"{lab.arkana}|app"
            self.assertEqual(prefs(lab)["components"], {clave: "arkana"})
            self.assertEqual(oct(os.stat(os.path.join(lab.home, ".arkana", "statusline.json")).st_mode & 0o777), "0o600")
            self.assertIn("app: arkana", ops(lab, "check").stdout)
            self.assertIn("DRY|", ops(lab, "choose", "--component", "api", "--use", "other", "--dry-run").stdout)
            self.assertNotIn(f"{lab.arkana}|api", prefs(lab)["components"])
            ops(lab, "choose", "--component", "app", "--use", "other")
            self.assertEqual(prefs(lab)["components"][clave], "other")
            ops(lab, "choose", "--component", "app", "--use", "ask")                                # vuelve a preguntar: se borra la elección
            self.assertNotIn(clave, prefs(lab)["components"])
            self.assertEqual(ops(lab, "choose", "--component", "arkana", "--use", "arkana").returncode, 2)   # ARKANA siempre usa la suya
            self.assertEqual(ops(lab, "choose", "--component", "nadie", "--use", "arkana").returncode, 2)
            env = {k: v for k, v in lab.env.items() if k != "ARKANA_HOME"}
            r = subprocess.run([sys.executable, "-I", OPS, "choose", "--component", "app", "--use", "arkana"], capture_output=True, text=True, env=env, cwd=lab.root)
            self.assertEqual(r.returncode, 3)

    def test_uninstall_devuelve_la_statusline_al_proveedor_y_borra_la_copia(self):
        with Lab() as lab:
            with open(os.path.join(lab.home, ".claude", "settings.json"), "w") as f:
                json.dump({"statusLine": {"type": "command", "command": "bash ~/.claude/statusline-command.sh"}, "theme": "dark"}, f)
            ops(lab, "install", "--replace")
            ops(lab, "choose", "--component", "app", "--use", "arkana")
            dest = os.path.join(lab.home, ".claude", "arkana-statusline")
            self.assertIn("DRY|", ops(lab, "uninstall", "--dry-run").stdout)
            self.assertTrue(os.path.isfile(os.path.join(dest, "statusline.sh")))
            r = ops(lab, "uninstall")
            self.assertEqual(r.returncode, 0, r.stdout)
            s = settings(lab)
            self.assertEqual(s["statusLine"], {"type": "command", "command": "bash ~/.claude/statusline-command.sh"})
            self.assertEqual(s["theme"], "dark")
            for n in ("statusline.sh", "dispatch.py", "statusline.py", "arkana_core"):
                self.assertFalse(os.path.exists(os.path.join(dest, n)), n)
            self.assertTrue(os.path.isdir(os.path.join(dest, "bak")))                               # las copias de seguridad se conservan
            self.assertTrue(prefs(lab)["components"])                                               # y las elecciones
            self.assertIn("no es del despachador", ops(lab, "uninstall").stdout)                    # repetible

    def test_uninstall_sin_proveedores_quita_la_statusline(self):
        with Lab() as lab:
            ops(lab, "install")
            self.assertEqual(ops(lab, "uninstall").returncode, 0)
            self.assertNotIn("statusLine", settings(lab))


class TestProveedoresYJerarquia(unittest.TestCase):
    """La jerarquía Arkana → plugin4cc → otra manda aunque un tercero que no la conoce pise la statusLine de usuario."""

    def poner(self, lab, comando):
        p = os.path.join(lab.home, ".claude", "settings.json")
        d = json.loads(Path(p).read_text()) if os.path.isfile(p) else {}
        d["statusLine"] = {"type": "command", "command": comando}
        Path(p).write_text(json.dumps(d))

    def test_provider_list_add_remove_y_auto(self):
        with Lab() as lab:
            self.assertIn("INFO|proveedores|ninguno", ops(lab, "provider", "list").stdout)
            self.assertIn("auto-reclaim|activada", ops(lab, "provider", "list").stdout)
            self.assertIn("DRY|", ops(lab, "provider", "add", "--id", "x", "--command", "bash ~/x.sh", "--dry-run").stdout)
            self.assertEqual(prefs(lab), {})
            self.assertEqual(ops(lab, "provider", "add", "--id", "x", "--command", "bash ~/x.sh").returncode, 0)
            self.assertEqual(ops(lab, "provider", "add", "--id", "p", "--command", "bash ~/.claude/statusline-command.sh").returncode, 0)
            self.assertEqual({(p["id"], p["priority"]) for p in prefs(lab)["providers"]}, {("x", 30), ("p", 20)})
            self.assertEqual(ops(lab, "provider", "add", "--id", "x", "--command", "bash ~/x2.sh", "--priority", "40").returncode, 0)   # mismo id: reemplaza
            self.assertEqual(len([p for p in prefs(lab)["providers"] if p["id"] == "x"]), 1)
            self.assertEqual(ops(lab, "provider", "remove", "--id", "x").returncode, 0)
            self.assertEqual(ops(lab, "provider", "remove", "--id", "x").returncode, 1)
            self.assertEqual(ops(lab, "provider", "add", "--id", "solo").returncode, 1)
            ops(lab, "provider", "auto", "off")
            self.assertIs(prefs(lab)["auto_reclaim"], False)
            self.assertIn("desactivada", ops(lab, "provider", "list").stdout)

    def test_varias_herramientas_sin_contrato_conviven_y_el_script_de_plugin4cc_se_detecta(self):
        with Lab() as lab:
            Path(os.path.join(lab.home, ".claude", "statusline-command.sh")).write_text("#!/bin/bash\necho p4cc\n")
            self.poner(lab, "bash ~/barra-x.sh")
            self.assertEqual(ops(lab, "install", "--replace").returncode, 0)
            self.poner(lab, "bash ~/barra-y.sh")                                                     # otra herramienta pisa el hueco
            self.assertEqual(ops(lab, "install", "--replace").returncode, 0)
            cmds = {p["command"]: p["id"] for p in prefs(lab)["providers"]}
            self.assertEqual(set(cmds), {"bash ~/barra-x.sh", "bash ~/barra-y.sh", "bash ~/.claude/statusline-command.sh"})
            self.assertEqual(cmds["bash ~/.claude/statusline-command.sh"], "plugin4cc")
            self.assertEqual(len(set(cmds.values())), 3)                                            # ids distintos: ninguna sustituye a otra
            ops(lab, "install", "--replace")
            self.assertEqual(len(prefs(lab)["providers"]), 3)                                       # y repetir no duplica

    def test_el_hook_recupera_el_hueco_cuando_un_tercero_lo_pisa_y_lo_deja_como_proveedor(self):
        with Lab() as lab:
            ops(lab, "install")
            self.poner(lab, "bash ~/barra-de-un-tercero.sh")
            for evento in ("session-start", "prompt-submit"):
                if evento == "prompt-submit":
                    self.poner(lab, "bash ~/otra-mas.sh")
                r = subprocess.run([sys.executable, "-I", HOOK, evento], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("restored", json.loads(r.stdout)["systemMessage"])
                self.assertIn("arkana-statusline/statusline.sh", settings(lab)["statusLine"]["command"])
            self.assertEqual({p["command"] for p in prefs(lab)["providers"]}, {"bash ~/barra-de-un-tercero.sh", "bash ~/otra-mas.sh"})
            r = subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
            self.assertEqual(r.stdout.strip(), "")                                                   # ya está en orden: silencio
            bak = os.path.join(lab.home, ".claude", "arkana-statusline", "bak")
            self.assertTrue(any(f.startswith("settings.json.") for f in os.listdir(bak)))

    def test_no_recupera_sin_instalacion_previa_ni_con_auto_off(self):
        with Lab() as lab:
            self.poner(lab, "bash ~/ajena.sh")
            r = subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
            self.assertEqual(r.stdout.strip(), "")
            self.assertIn("ajena.sh", settings(lab)["statusLine"]["command"])
            ops(lab, "install", "--replace")
            ops(lab, "provider", "auto", "off")
            self.poner(lab, "bash ~/ajena.sh")
            r = subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
            self.assertEqual(r.stdout.strip(), "")
            self.assertIn("ajena.sh", settings(lab)["statusLine"]["command"])                       # con auto off solo se avisa (check)
            self.assertIn("WARN|statusline", ops(lab, "check").stdout)
            f = ops(lab, "fix")
            self.assertIn("ajena.sh", settings(lab)["statusLine"]["command"])                        # y fix tampoco la sustituye

    def test_una_instalacion_anterior_a_la_marca_se_reconoce_sola_y_luego_se_protege(self):
        with Lab() as lab:
            ops(lab, "install")
            d = prefs(lab); d.pop("claimed")
            Path(os.path.join(lab.home, ".arkana", "statusline.json")).write_text(json.dumps(d))
            r = subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
            self.assertEqual(r.stdout.strip(), "")
            self.assertIs(prefs(lab)["claimed"], True)
            self.poner(lab, "bash ~/ajena.sh")
            r = subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
            self.assertIn("restored", json.loads(r.stdout)["systemMessage"])

    def test_uninstall_suelta_el_hueco_y_ya_no_se_recupera(self):
        with Lab() as lab:
            ops(lab, "install")
            ops(lab, "uninstall")
            self.assertIs(prefs(lab)["claimed"], False)
            self.poner(lab, "bash ~/ajena.sh")
            r = subprocess.run([sys.executable, "-I", HOOK, "session-start"], input=json.dumps({"cwd": lab.path("arkana")}), capture_output=True, text=True, env=lab.env, timeout=30)
            self.assertEqual(r.stdout.strip(), "")
            self.assertIn("ajena.sh", settings(lab)["statusLine"]["command"])

    def test_fix_recupera_el_hueco_tras_una_instalacion_previa(self):
        with Lab() as lab:
            ops(lab, "install")
            self.poner(lab, "bash ~/ajena.sh")
            r = ops(lab, "fix")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("arkana-statusline/statusline.sh", settings(lab)["statusLine"]["command"])
            self.assertEqual([p["command"] for p in prefs(lab)["providers"]], ["bash ~/ajena.sh"])
            self.assertIn("nada que recuperar", ops(lab, "reclaim").stdout)


class TestHook(unittest.TestCase):
    """SessionStart: solo pregunta en un componente sin elección y con el despachador instalado."""

    def contexto(self, r):
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"] if r.stdout.strip() else ""

    def test_pregunta_en_un_componente_sin_eleccion(self):
        with Lab() as lab:
            ops(lab, "install")
            r = hook(lab, lab.path("app"))
            self.assertEqual(r.returncode, 0, r.stderr)
            c = self.contexto(r)
            self.assertIn("component 'app'", c); self.assertIn("AskUserQuestion", c); self.assertIn("/arkana-statusline:choose", c); self.assertIn("--component app", c)

    def test_no_pregunta_si_ya_hay_eleccion_ni_en_arkana_ni_sin_despachador_ni_en_un_worker(self):
        with Lab() as lab:
            self.assertEqual(self.contexto(hook(lab, lab.path("app"))), "")                           # sin despachador instalado
            ops(lab, "install")
            self.assertEqual(self.contexto(hook(lab, lab.path("arkana"))), "")                        # carpeta de ARKANA
            self.assertEqual(self.contexto(hook(lab, lab.root)), "")                                  # fuera de un componente
            self.assertEqual(self.contexto(hook(lab, lab.path("app"), env=dict(lab.env, ARKANA_WORKER="1"))), "")
            ops(lab, "choose", "--component", "app", "--use", "other")
            self.assertEqual(self.contexto(hook(lab, lab.path("app"))), "")                           # ya elegido
            self.assertIn("component 'api'", self.contexto(hook(lab, lab.path("api"))))               # otro componente sigue sin elegir

    def test_entrada_basura_no_rompe(self):
        with Lab() as lab:
            r = subprocess.run([sys.executable, "-I", HOOK], input="{no json", capture_output=True, text=True, env=lab.env)
            self.assertEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
