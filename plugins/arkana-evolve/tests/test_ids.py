"""Migración 0003: el manifiesto local recibe el id de cada componente desde el registro compartido; el registro se completa con lo que falte."""
import json
import os
import unittest

from test_evolve import Lab, UUID_RX  # noqa: F401


def manifiesto(lab, aliases, ids=None):
    m = Lab.manifest(aliases)
    for blk in [m["arkana"]] + m["components"]:
        a = "arkana" if blk is m["arkana"] else blk["alias"]
        if ids and a in ids:
            blk["id"] = ids[a]
    lab.write(".arkana/core/workspace.json", m)


def leer(lab):
    return json.loads(lab.read(".arkana/core/workspace.json"))


class TestMigracion0003(unittest.TestCase):
    def test_el_manifiesto_recibe_los_ids_del_registro_y_el_registro_no_cambia(self):
        with Lab() as lab:
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api", "app"]))
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            reg = lab.project()
            ids = {c["alias"]: c["id"] for c in reg["components"]}
            mf = leer(lab)
            self.assertEqual(mf["arkana"]["id"], ids["arkana"])
            self.assertEqual({c["alias"]: c["id"] for c in mf["components"]}, {"api": ids["api"], "app": ids["app"]})
            self.assertTrue(all(UUID_RX.match(i) for i in ids.values()))
            self.assertEqual(reg["layout"], 4)
            self.assertEqual([h["id"] for h in reg["history"]], ["0001", "0002", "0003", "0004"])
            self.assertIn("nada que hacer", lab.run("apply").stdout)
            self.assertNotIn("WARN|", lab.run("check").stdout)

    def test_un_componente_solo_en_el_manifiesto_se_da_de_alta_en_el_registro(self):
        with Lab() as lab:
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api"]))
            lab.run("apply")
            ids_antes = {c["alias"]: c["id"] for c in lab.project()["components"]}
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api", "docs"]))               # alguien añadió `docs` sin pasar por el registro
            git_ok = lab.run("check")
            self.assertIn("WARN|0003|pendiente", git_ok.stdout)
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("docs dado de alta en el registro compartido", r.stdout)
            ids = {c["alias"]: c["id"] for c in lab.project()["components"]}
            self.assertEqual({k: ids[k] for k in ids_antes}, ids_antes)                           # los ids de siempre no cambian
            self.assertEqual(next(c for c in leer(lab)["components"] if c["alias"] == "docs")["id"], ids["docs"])

    def test_segunda_persona_recibe_los_ids_del_registro_sin_regenerarlos(self):
        with Lab() as lab:
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api"]))
            lab.run("apply")
            reg = lab.project()
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api"]))                       # su manifiesto local no lleva ids
            os.remove(os.path.join(lab.arkana, ".arkana", "arkana-evolve", "state.json"))
            lab.run("apply")
            self.assertEqual(lab.project()["components"], reg["components"])
            self.assertEqual(next(c for c in leer(lab)["components"] if c["alias"] == "api")["id"], next(c for c in reg["components"] if c["alias"] == "api")["id"])

    def test_un_id_que_el_registro_asocia_a_otro_alias_se_avisa_y_no_se_toca(self):
        with Lab() as lab:
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api", "app"]))
            lab.run("apply")
            reg = lab.project()
            api_id = next(c["id"] for c in reg["components"] if c["alias"] == "api")
            for c in reg["components"]:
                if c["alias"] == "api":
                    c["alias"] = "backend"                                                         # renombrado por otra persona
            lab.write("arkana-project.json", reg)
            lab.write(".arkana/core/workspace.json", Lab.manifest(["api", "app"], ) | {})
            mf = leer(lab)
            for c in mf["components"]:
                if c["alias"] == "api":
                    c["id"] = api_id
                if c["alias"] == "app":
                    c.pop("id", None)
            lab.write(".arkana/core/workspace.json", mf)
            r = lab.run("apply")
            self.assertIn("WARN|0003:api|el registro compartido llama backend a este componente", r.stdout)
            self.assertEqual(next(c for c in leer(lab)["components"] if c["alias"] == "api")["id"], api_id)


if __name__ == "__main__":
    unittest.main()
