"""La statusline es la ÚNICA escritora del coste real de la sesión; funciona dentro y fuera de un workspace y en menos de 300 ms."""
from pathlib import Path
import json
import os
import stat
import subprocess
import sys
import time
import unittest

import lab as L
import statusline as S


class TestCoste(unittest.TestCase):
    def fichero(self, lab, sid="sess-1"):
        return os.path.join(lab.arkana, ".arkana", "arkana-statusline", "state", "sessions", sid + ".json")

    def test_escribe_el_ultimo_coste_con_modo_600_y_solo_si_cambia(self):
        with L.Lab() as lab:
            self.assertEqual(lab.run("app", {"cost": {"total_cost_usd": 0}}).returncode, 0)
            self.assertFalse(os.path.exists(self.fichero(lab)))                                  # coste 0: nada
            lab.run("app", {"cost": {"total_cost_usd": 2.5}})
            f = self.fichero(lab)
            d = json.loads(Path(f).read_text())
            self.assertEqual((d["session_id"], d["cost_usd"]), ("sess-1", 2.5))
            self.assertEqual(stat.S_IMODE(os.stat(f).st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(f)).st_mode), 0o700)
            os.utime(f, (1, 1))
            lab.run("app", {"cost": {"total_cost_usd": 2.5}})
            self.assertEqual(os.path.getmtime(f), 1)                                             # mismo valor: no se reescribe
            lab.run("app", {"cost": {"total_cost_usd": 7.25}})
            self.assertEqual(json.loads(Path(f).read_text())["cost_usd"], 7.25)                               # se reescribe con el último
            lab.run("app", {"cost": {"total_cost_usd": 1.0}, "session_id": "sess-2"})
            lab.run("app", {"cost": {"total_cost_usd": 3.0}, "session_id": "../mala"})
            self.assertEqual(sorted(os.listdir(os.path.dirname(f))), ["sess-1.json", "sess-2.json"])      # ids con caracteres raros, nunca
            self.assertFalse([x for x in os.listdir(os.path.dirname(f)) if x.endswith(".tmp")])

    def test_los_hooks_de_agentic_leen_justo_ese_fichero(self):
        with L.Lab() as lab:
            lab.run("app", {"cost": {"total_cost_usd": 4.2}, "session_id": "sess-9"})
            agentic = os.path.join(L.PLUGIN, "..", "arkana-agentic", "scripts", "lib")
            r = subprocess.run([sys.executable, "-I", "-c", "import sys;sys.path.insert(0,sys.argv[1]);import ledger;print(ledger.statusline_cost('sess-9')[0])", agentic],
                               capture_output=True, text=True, env=dict(lab.env, ARKANA_HOME=lab.arkana))
            self.assertEqual(r.stdout.strip(), "4.2", r.stderr)

    def test_fuera_de_un_workspace_funciona_y_no_escribe_nada(self):
        with L.Lab() as lab:
            fuera = os.path.join(lab.root, "suelto")
            os.makedirs(fuera)
            subprocess.run(["git", "init", "-q", "-b", "main", fuera], check=True, env=L.GITENV)
            env = {k: v for k, v in lab.env.items() if k != "ARKANA_HOME"}
            r = subprocess.run(["bash", os.path.join(L.SL, "statusline.sh")], input=json.dumps({"workspace": {"project_dir": fuera}, "model": {"display_name": "M"},
                               "cost": {"total_cost_usd": 1.0}, "session_id": "s"}), capture_output=True, text=True, env=dict(env, COLUMNS="100"), cwd=lab.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            lineas = S.plain(r.stdout).splitlines()
            self.assertEqual(len(lineas), 1)                                       # una sola pieza: va con el plan y los costes
            self.assertIn("suelto@main:", lineas[0]); self.assertIn("main", lineas[0])
            self.assertIn("P0.00 S1.00", lineas[0])
            self.assertFalse(os.path.exists(self.fichero(lab, "s")))

    def test_entrada_basura_y_workspace_sin_repos_nunca_rompen(self):
        with L.Lab() as lab:
            for entrada in ("", "{no json", "[]", "{}"):
                r = subprocess.run(["bash", os.path.join(L.SL, "statusline.sh")], input=entrada, capture_output=True, text=True, env=dict(lab.env, COLUMNS="80"), cwd=lab.root)
                self.assertEqual(r.returncode, 0, entrada)
                self.assertTrue(r.stdout.strip(), entrada)

    def test_la_actual_sale_en_naranja_brillante_y_los_docs_no_salen(self):
        with L.Lab() as lab:
            r = lab.run("api", columns=200)
            self.assertIn("\033[1;38;5;214mapi\033[0m\033[31m@\033[0m", r.stdout)
            self.assertIn("\033[38;5;208mapp\033[0m\033[31m@\033[0m", r.stdout)
            self.assertNotIn("docs", S.plain(r.stdout))                                          # tipo docs sin `statusline: true`: oculto

    def test_menos_de_300_ms_con_siete_componentes(self):
        with L.Lab() as lab:
            lab.run("app")                                                                      # calienta cachés
            t = time.time()
            for _ in range(3):
                self.assertEqual(lab.run("app").returncode, 0)
            self.assertLess((time.time() - t) / 3, 0.3)


if __name__ == "__main__":
    unittest.main()
