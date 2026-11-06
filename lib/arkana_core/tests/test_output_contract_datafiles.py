import json
import os
import stat
import tempfile
import unittest

import common
from arkana_core import contract, datafiles, output


class TestOutput(unittest.TestCase):
    def test_lineas_y_resumen(self):
        r = output.Report("arkana-x", "check").add("OK", "a", "bien").add("WARN", "b", "ojo", component="app").add("FAIL", "c", "mal")
        self.assertEqual(r.lines(), ["OK|a|bien", "WARN|b|ojo", "FAIL|c|mal", "RESUMEN|1 FAIL|1 WARN"])
        self.assertEqual(r.exit_code(), 1)
        self.assertEqual(r.status(), "fail")

    def test_sin_fallos_sale_con_cero_aunque_haya_avisos(self):
        r = output.Report("p", "s").add("WARN", "w")
        self.assertEqual((r.exit_code(), r.status()), (0, "warn"))
        self.assertEqual(output.Report("p", "s").status(), "ok")

    def test_json(self):
        r = output.Report("arkana-x", "check").add("OK", "a", "d", component="app").add("DRY", "b")
        j = json.loads(r.render(as_json=True))
        self.assertEqual(j["plugin"], "arkana-x"); self.assertEqual(j["skill"], "check")
        self.assertEqual(j["items"][0], {"id": "a", "status": "OK", "detail": "d", "component": "app"})
        self.assertEqual(j["summary"]["dry"], 1)

    def test_los_secretos_nunca_salen(self):
        r = output.Report("p", "s", secrets=["S3CRETO", ""]).add("INFO", "x", "token=S3CRETO y más S3CRETO")
        self.assertNotIn("S3CRETO", r.text()); self.assertNotIn("S3CRETO", r.render(as_json=True))
        self.assertIn("***", r.text())

    def test_estado_desconocido(self):
        with self.assertRaises(ValueError):
            output.Report("p", "s").add("MAL", "x")


class TestDatafiles(unittest.TestCase):
    def test_escritura_atomica_con_modo_y_sin_restos(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sub", ".credentials")
            datafiles.atomic_write(p, "A=1\n", mode=0o600)
            self.assertEqual(open(p).read(), "A=1\n")
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
            datafiles.atomic_write(p, "A=2\n", mode=0o600)
            self.assertEqual(open(p).read(), "A=2\n")
            self.assertEqual(os.listdir(os.path.dirname(p)), [".credentials"])      # sin temporales

    def test_json_atomico(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.json")
            datafiles.atomic_write_json(p, {"á": 1})
            self.assertEqual(datafiles.read_json(p), {"á": 1})
            self.assertIsNone(datafiles.read_json(os.path.join(d, "no.json")))
            self.assertEqual(datafiles.read_json(os.path.join(d, "no.json"), default=[]), [])

    def test_las_cuatro_clases(self):
        self.assertEqual(datafiles.CLASSES, ("config", "data", "local", "secret"))


class TestContract(unittest.TestCase):
    def plugin(self, d, **extra):
        c = {"plugin": "arkana-messaging", "contract": 1, "provides": ["install", "check", "fix"],
             "data": [{"path": "arkana-messaging/config.json", "class": "config"}, {"path": "arkana-messaging/state/", "class": "local"}],
             "hooks": ["SessionStart", "Stop"]}
        c.update(extra)
        with open(os.path.join(d, "arkana-plugin.json"), "w") as f:
            json.dump(c, f)
        return d

    def test_contrato_valido(self):
        with tempfile.TemporaryDirectory() as d:
            c = contract.load(self.plugin(d))
            self.assertEqual(c["plugin"], "arkana-messaging")

    def test_rechaza_clase_desconocida_ruta_absoluta_y_nombre_malo(self):
        for extra in ({"data": [{"path": "x", "class": "secreto-total"}]},
                      {"data": [{"path": "/etc/x", "class": "local"}]},
                      {"data": [{"path": "../x", "class": "local"}]},
                      {"plugin": "otro-nombre"}, {"hooks": ["PreToolUse"]}):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(contract.ContractError, msg=str(extra)):
                    contract.load(self.plugin(d, **extra))

    def test_falta_el_fichero_o_no_es_json(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(contract.ContractError, "falta"):
                contract.load(d)
            with open(os.path.join(d, "arkana-plugin.json"), "w") as f:
                f.write("{")
            with self.assertRaisesRegex(contract.ContractError, "JSON"):
                contract.load(d)


if __name__ == "__main__":
    unittest.main()
