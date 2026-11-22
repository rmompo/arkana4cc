"""Despachador (statusline.sh → dispatch.py): qué statusline se ve según el cwd y la elección. Hermético: HOME falso y proveedores que son scripts de prueba."""
from pathlib import Path
import json
import os
import subprocess
import unittest

import lab as L
from lab import Lab


def prefs_file(lab):
    return os.path.join(lab.home, ".arkana", "statusline.json")


def write_prefs(lab, providers=(), components=None):
    p = prefs_file(lab)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    Path(p).write_text(json.dumps({"version": 1, "providers": list(providers), "components": components or {}}))


def provider(lab, pid, prio, texto, rc=0):
    f = os.path.join(lab.root, f"{pid}.sh")
    Path(f).write_text(f"#!/bin/bash\ncat >/dev/null\necho '{texto}'\nexit {rc}\n")
    os.chmod(f, 0o755)
    return {"id": pid, "command": f"bash {f}", "priority": prio}


def render(lab, cwd, env=None, raw=None):
    inp = raw if raw is not None else json.dumps({"workspace": {"project_dir": cwd}, "model": {"display_name": "M"}, "cost": {"total_cost_usd": 2.5}, "session_id": "s1"})
    return subprocess.run(["bash", os.path.join(L.SL, "statusline.sh")], input=inp, capture_output=True, text=True, env=dict(env or lab.env, COLUMNS="120"), cwd=lab.root, timeout=30)


class TestDespachador(unittest.TestCase):
    def test_en_la_carpeta_de_arkana_se_ve_la_de_arkana_aunque_haya_proveedores(self):
        with Lab() as lab:
            write_prefs(lab, [provider(lab, "plugin4cc", 20, "P4CC-BAR")])
            r = render(lab, lab.path("arkana"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("ARKANA", r.stdout); self.assertNotIn("P4CC-BAR", r.stdout)

    def test_en_un_componente_sin_eleccion_se_ve_el_proveedor_pero_el_coste_se_anota(self):
        with Lab() as lab:
            write_prefs(lab, [provider(lab, "plugin4cc", 20, "P4CC-BAR")])
            r = render(lab, lab.path("app"))
            self.assertEqual(r.stdout.strip(), "P4CC-BAR")
            f = os.path.join(lab.arkana, ".arkana", "arkana-statusline", "state", "sessions", "s1.json")
            self.assertEqual(json.loads(Path(f).read_text())["cost_usd"], 2.5)                   # Arkana sigue siendo la única escritora del coste real

    def test_la_eleccion_arkana_se_ve_en_ese_componente_y_other_no(self):
        with Lab() as lab:
            p = provider(lab, "plugin4cc", 20, "P4CC-BAR")
            write_prefs(lab, [p], {f"{lab.arkana}|app": "arkana", f"{lab.arkana}|api": "other"})
            a = render(lab, lab.path("app")).stdout
            self.assertIn("APP", a); self.assertNotIn("P4CC-BAR", a)
            self.assertEqual(render(lab, lab.path("api")).stdout.strip(), "P4CC-BAR")

    def test_plugin4cc_gana_a_otra_y_un_proveedor_que_falla_cede_al_siguiente(self):
        with Lab() as lab:
            write_prefs(lab, [provider(lab, "other", 30, "OTRA-BAR"), provider(lab, "plugin4cc", 20, "P4CC-BAR")])
            self.assertEqual(render(lab, lab.path("app")).stdout.strip(), "P4CC-BAR")
            write_prefs(lab, [provider(lab, "other", 30, "OTRA-BAR"), provider(lab, "plugin4cc", 20, "P4CC-BAR", rc=1)])
            self.assertEqual(render(lab, lab.path("app")).stdout.strip(), "OTRA-BAR")

    def test_fuera_de_arkana_se_ve_el_proveedor_y_sin_proveedores_no_se_ve_nada(self):
        with Lab() as lab:
            fuera = os.path.join(lab.root, "suelto")
            os.makedirs(fuera)
            env = {k: v for k, v in lab.env.items() if k != "ARKANA_HOME"}
            write_prefs(lab, [provider(lab, "plugin4cc", 20, "P4CC-BAR")])
            self.assertEqual(render(lab, fuera, env=env).stdout.strip(), "P4CC-BAR")
            write_prefs(lab, [])
            r = render(lab, fuera, env=env)
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            os.unlink(prefs_file(lab))                                                            # sin fichero de preferencias tampoco rompe
            self.assertEqual(render(lab, fuera, env=env).returncode, 0)

    def test_entrada_basura_y_preferencias_rotas_nunca_rompen(self):
        with Lab() as lab:
            Path(prefs_file(lab)).parent.mkdir(parents=True, exist_ok=True)
            Path(prefs_file(lab)).write_text("no es json")
            for raw in ("", "{no json", "[]", "{}"):
                self.assertEqual(render(lab, lab.path("app"), raw=raw).returncode, 0, raw)


if __name__ == "__main__":
    unittest.main()
