"""Migraciones de base b001-b004: formatos antiguos de Arkana → layout actual. Fixtures de los layouts antiguos; sin red ni API."""
import json
import os
import unittest

from test_evolve import Lab, git, GENV  # noqa: F401  (mismo laboratorio)


def commit(lab, msg="base"):
    git(lab.arkana, "add", "-A")
    git(lab.arkana, "commit", "-q", "-m", msg)


class TestB001LayoutAgentic(unittest.TestCase):
    def old_layout(self, lab, estado="completado"):
        b = ".arkana/arkana-agentic"
        lab.write(f"{b}/planes/P1/plan.json", {"id": "P1", "estado": estado})
        lab.write(f"{b}/planes/P1/tareas/T001.json", {"id": "T001"})
        lab.write(f"{b}/run/linea.json", {})
        lab.write(f"{b}/sesiones/abc", "1 0.5\n")
        lab.write(f"{b}/actual", "P1")
        lab.write(f"{b}/politica.json", {"limites": {"total_budget_usd": 8}})

    def test_mueve_todo_sin_perder_nada_y_es_idempotente(self):
        with Lab() as lab:
            self.old_layout(lab)
            self.assertIn("WARN|b001|pendiente", lab.run("check").stdout)
            r = lab.run("apply", "--dry-run")
            self.assertIn("DRY|b001:planes|planes → state/planes", r.stdout)
            self.assertTrue(os.path.isdir(os.path.join(lab.arkana, ".arkana/arkana-agentic/planes")))      # dry-run no mueve
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            for rel in ("state/planes/P1/plan.json", "state/planes/P1/tareas/T001.json", "state/run/linea.json", "state/sesiones/abc",
                        "state/actual", "config/politica.json"):
                self.assertTrue(os.path.exists(os.path.join(lab.arkana, ".arkana/arkana-agentic", rel)), rel)
            for rel in ("planes", "run", "sesiones", "actual", "politica.json"):
                self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana/arkana-agentic", rel)), rel)
            self.assertEqual(oct(os.stat(os.path.join(lab.arkana, ".arkana/arkana-agentic/state")).st_mode & 0o777), "0o700")
            self.assertIn("nada que hacer", lab.run("apply").stdout)

    def test_se_niega_con_un_plan_activo_y_no_toca_nada(self):
        with Lab() as lab:
            self.old_layout(lab, estado="en_ejecucion")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("el plan P1 está en_ejecucion", r.stdout)
            self.assertTrue(os.path.isdir(os.path.join(lab.arkana, ".arkana/arkana-agentic/planes")))
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "arkana-project.json")))              # se detiene antes de las siguientes

    def test_no_pisa_lo_nuevo_y_copia_los_planes_archivados(self):
        with Lab() as lab:
            self.old_layout(lab)
            lab.write(".arkana/arkana-agentic/state/actual", "OTRO")
            lab.write("orquestacion/archivo/P0/plan.json", {"id": "P0"})
            r = lab.run("apply")
            self.assertIn("WARN|b001:actual|existen actual y state/actual", r.stdout)
            self.assertEqual(lab.read(".arkana/arkana-agentic/state/actual"), "OTRO")
            self.assertTrue(os.path.exists(os.path.join(lab.arkana, ".arkana/arkana-agentic/data/archive/P0/plan.json")))
            self.assertTrue(os.path.exists(os.path.join(lab.arkana, "orquestacion/archivo/P0/plan.json")))  # el origen no se borra
            self.assertIn("WARN|b001|aplicada, pero existen actual", lab.run("check").stdout)


class TestB002Novedades(unittest.TestCase):
    def legacy(self, **kw):
        d = {"id": "N261030-1729-v7fb", "asunto": "Formato de commit cerrado", "tipo": "notice", "de": "shared", "autor": "x",
             "fecha": "2026-10-30T17:29:37Z", "rama": "develop", "prioridad": "normal",
             "historial": [{"fecha": "2026-10-30T17:29:37Z", "autor": "x", "accion": "created", "nota": ""}]}
        d.update(kw)
        return d

    def test_adopta_es_idempotente_y_no_toca_el_origen(self):
        with Lab() as lab:
            lab.write("novedades/shared/N261030-1729-v7fb.json", self.legacy())
            lab.write("novedades/api/N261030-1850-6stx.json", self.legacy(id="N261030-1850-6stx", de="api", para="shared", tipo="task",
                                                                          estado="done", instrucciones=["a"], criterios=["b"]))
            lab.write("novedades/LEEME.md", "# LEEME")
            lab.write("novedades/shared/roto.json", {"id": "malo"})
            lab.write("novedades/shared/vieja.md", "texto")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("2 comunicaciones adoptadas", r.stdout)
            self.assertIn("WARN|b002:shared/roto.json", r.stdout)
            self.assertIn("WARN|b002:shared/vieja.md", r.stdout)
            self.assertNotIn("LEEME", r.stdout)
            store = ".arkana/arkana-messaging/state/messages/"
            a = json.loads(lab.read(store + "N261030-1729-v7fb.json"))
            self.assertEqual((a["de"], a["para"]), ("arkana", ["api"]))                                     # sin destinatario = todos los demás
            b = json.loads(lab.read(store + "N261030-1850-6stx.json"))
            self.assertEqual((b["de"], b["para"]), ("api", ["arkana"]))
            self.assertTrue(os.path.exists(os.path.join(lab.arkana, "novedades/shared/N261030-1729-v7fb.json")))
            self.assertIn("nada que hacer", lab.run("apply").stdout)

    def test_dry_run_no_escribe(self):
        with Lab() as lab:
            lab.write("novedades/shared/N261030-1729-v7fb.json", self.legacy())
            lab.run("apply", "--dry-run")
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana/arkana-messaging")))


class TestB003Conocimiento(unittest.TestCase):
    @staticmethod
    def meta(ver, fecha, res):
        return (f'---\nid: decision-orquestar\ntitulo: "Orquestar"\ntipo: decision\nversion: {ver}\nfecha: {fecha}\nautor: Ana\n'
                f'modulos: [app, api]\netiquetas: [a, b]\nresumen: "{res}"\n---\n')

    def legacy(self, lab):
        lab.write("conocimiento/decision/orquestar.md", self.meta("1.2", "2026-11-03", "Resumen v1.2") + "\n# Orquestar\n\nCuerpo.\n")
        lab.write("conocimiento/.historial/decision-orquestar/v1.0.md", self.meta("1.0", "2026-10-30", "Resumen v1.0") + "\nviejo\n")
        lab.write("conocimiento/.historial/decision-orquestar/v1.1.md", self.meta("1.1", "2026-10-31", "Resumen v1.1") + "\nviejo\n")
        lab.write("estado-proyecto.md", '---\nid: reference-estado-proyecto\ntitulo: "Estado"\ntipo: reference\nversion: 1.4\nfecha: 2026-11-03\n'
                                       'autor: Ana\nmodulos: []\netiquetas: [x]\nresumen: "Estado"\n---\n\n# Estado\n')
        lab.write("catalogo.json", {"version": 1, "notas": []})
        commit(lab, "legacy")

    def test_migra_historial_a_changelog_mueve_con_git_y_es_idempotente(self):
        with Lab() as lab:
            self.legacy(lab)
            self.assertIn("WARN|b003|pendiente", lab.run("check").stdout)
            r = lab.run("apply", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertTrue(os.path.isdir(os.path.join(lab.arkana, "conocimiento", ".historial")))        # dry-run no toca nada
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            nueva = "arkana-knowledge/decision/orquestar.md"
            t = lab.read(nueva)
            for x in ("topic: decision", "state: active", "slug: orquestar", "version: 1.2", "# Orquestar", "Cuerpo."):
                self.assertIn(x, t)
            self.assertNotIn("tipo:", t)
            self.assertNotIn("modulos:", t)
            ch = t.split("## Changelog")[1]
            self.assertEqual([l.split(" · ")[0] for l in ch.strip().splitlines()], ["- v1.0", "- v1.1", "- v1.2"])
            self.assertIn("Resumen v1.0", ch)
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "conocimiento")))
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "catalogo.json")))
            st = git(lab.arkana, "status", "--short").stdout
            self.assertRegex(st, r"(?m)^R.? +conocimiento/decision/orquestar.md -> arkana-knowledge/decision/orquestar.md")      # git mv
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, "estado-proyecto.md")))               # la 0004 (encadenada) la lleva a arkana-knowledge/
            ref = lab.read("arkana-knowledge/reference/estado-proyecto.md")
            self.assertIn("topic: reference", ref)
            self.assertIn("components: [all]", ref)                                                        # modulos vacío = todos
            self.assertIn("nada que hacer", lab.run("apply").stdout)

    def test_cambios_sin_commitear_en_lo_antiguo_se_niegan(self):
        with Lab() as lab:
            self.legacy(lab)
            lab.write("conocimiento/decision/orquestar.md", "editada a mano sin commitear")
            r = lab.run("apply")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertIn("cambios sin commitear", r.stdout)


class TestB004AliasShared(unittest.TestCase):
    def test_reescribe_el_alias_en_todos_los_almacenes(self):
        with Lab() as lab:
            lab.write(".arkana/arkana-messaging/state/messages/N261030-1729-v7fb.json",
                      {"id": "N261030-1729-v7fb", "de": "shared", "para": ["shared", "api"], "destinatarios": ["shared", "api"],
                       "confirmaciones": {"shared": {"estado": "done"}}, "entregas": {"shared": {"n": 1}}, "ejecuciones": {}})
            lab.write(".arkana/arkana-messaging/state/read/shared.json", {"schema_version": 1, "ids": {"N1": "2026-01-01"}})
            lab.write(".arkana/arkana-messaging/state/read/arkana.json", {"schema_version": 1, "ids": {"N2": "2026-01-02"}})
            lab.write(".arkana/arkana-messaging/state/index.json", {"schema_version": 2, "messages": {}})
            lab.write(".arkana/arkana-agentic/state/planes/P1/tareas/T001.json", {"id": "T001", "repo": "shared"})
            lab.write(".arkana/arkana-agentic/state/planes/P1/plan.json", {"id": "P1", "estado": "completado", "ramas": {"shared": {"nombre": "x"}}})
            lab.write(".arkana/arkana-todo/todos.json", {"version": 1, "next": 2, "tareas": [{"id": "t-001", "componente": "shared"}]})
            lab.write(".arkana/arkana-workspace/local.json", {"paths": {"shared": "/x", "api": "/y"}, "git": {"shared": {"name": "n"}}})
            lab.write("arkana-knowledge/decision/n.md", '---\nid: decision-n\ntitulo: "N"\ntopic: decision\nversion: 1.0\nfecha: 2026-01-01\nautor: A\n'
                                                       'components: [shared, api]\netiquetas: []\nresumen: "r"\nstate: active\n---\n\n# N\n\n## Changelog\n\n- v1.0 · 2026-01-01 · A — creada\n')
            r = lab.run("apply")
            self.assertEqual(r.returncode, 0, r.stdout)
            m = json.loads(lab.read(".arkana/arkana-messaging/state/messages/N261030-1729-v7fb.json"))
            self.assertEqual((m["de"], m["para"], m["destinatarios"]), ("arkana", ["arkana", "api"], ["arkana", "api"]))
            self.assertEqual(list(m["confirmaciones"]), ["arkana"])
            self.assertEqual(list(m["entregas"]), ["arkana"])
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana/arkana-messaging/state/read/shared.json")))
            self.assertEqual(sorted(json.loads(lab.read(".arkana/arkana-messaging/state/read/arkana.json"))["ids"]), ["N1", "N2"])
            self.assertFalse(os.path.exists(os.path.join(lab.arkana, ".arkana/arkana-messaging/state/index.json")))
            self.assertEqual(json.loads(lab.read(".arkana/arkana-agentic/state/planes/P1/tareas/T001.json"))["repo"], "arkana")
            self.assertEqual(list(json.loads(lab.read(".arkana/arkana-agentic/state/planes/P1/plan.json"))["ramas"]), ["arkana"])
            self.assertEqual(json.loads(lab.read(".arkana/arkana-todo/todos.json"))["tareas"][0]["componente"], ["arkana"])     # b004 lo renombra y la 0009 lo deja como lista
            loc = json.loads(lab.read(".arkana/arkana-workspace/local.json"))
            self.assertEqual((sorted(loc["paths"]), list(loc["git"])), (["api", "arkana"], ["arkana"]))
            ids = {c["alias"]: c["id"] for c in json.loads(lab.read("arkana-project.json"))["components"]}      # la 0004 encadenada guarda los componentes por id
            self.assertIn(f"components: [{ids['arkana']}, {ids['api']}]", lab.read("arkana-knowledge/decision/n.md"))
            self.assertIn("nada que hacer", lab.run("apply").stdout)

    def test_sin_alias_antiguo_no_hay_nada_que_hacer(self):
        with Lab() as lab:
            lab.write(".arkana/arkana-todo/todos.json", {"version": 1, "next": 2, "tareas": [{"id": "t-001", "componente": "api"}]})
            self.assertNotIn("b004", lab.run("check").stdout.replace("OK|b004", ""))


class TestOrdenCompleto(unittest.TestCase):
    def test_check_lista_las_cinco_y_todo_aplicado_queda_ok(self):
        with Lab() as lab:
            r = lab.run("check")
            for mid in ("b001", "b002", "b003", "b004", "0001"):
                self.assertIn(f"{mid}|", r.stdout)
            lab.run("apply")
            r = lab.run("check")
            self.assertNotIn("WARN|", r.stdout)


if __name__ == "__main__":
    unittest.main()
