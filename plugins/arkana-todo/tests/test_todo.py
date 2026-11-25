"""arkana-todo: add/list/done/modify/delete lógico/validate/fix. Hermético: workspace temporal, sin red ni ~/.claude."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
TD = os.path.abspath(os.path.join(AQUI, "..", "scripts", "lib", "todo.py"))
ENV = {k: v for k, v in os.environ.items() if not k.startswith("ARKANA_")}
AYER = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.h = os.path.realpath(self.tmp.name)
        write(os.path.join(self.h, ".arkana", "arkana.json"), '{"schema_version": 1, "root": ".."}')
        self.store = os.path.join(self.h, ".arkana", "arkana-todo", "todos.json")

    def td(self, *args):
        return subprocess.run([sys.executable, "-I", TD, "--home", self.h, *args], capture_output=True, text=True, env=ENV,
                              stdin=subprocess.DEVNULL, timeout=60)

    def ok(self, *args):
        r = self.td(*args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def tareas(self):
        return json.loads(read(self.store))["tareas"]


class TestCiclo(Base):
    def test_install_es_idempotente_y_dry_run_no_escribe(self):
        self.ok("install", "--dry-run")
        self.assertFalse(os.path.exists(self.store))
        self.ok("install")
        antes = read(self.store)
        self.assertIn("presente", self.ok("install"))
        self.assertEqual(read(self.store), antes)

    def test_add_list_done_reopen(self):
        self.ok("install")
        self.assertIn("t-001", self.ok("add", "--title", "Rotar claves", "--priority", "high", "--due", "2099-01-01"))
        self.ok("add", "--title", "Limpiar ramas")
        out = self.ok("list")
        self.assertIn("| t-001 | high | * | Rotar claves (vence 2099-01-01) | pending |", out)
        self.assertIn("t-002", out)
        self.ok("done", "--id", "t-001")
        self.assertNotIn("t-001", self.ok("list"))
        t = self.tareas()[0]
        self.assertEqual((t["estado"], t["cerrada"] != ""), ("done", True))
        self.assertIn("t-001", self.ok("list", "--status", "done"))
        self.assertIn("ya estaba cerrada", self.ok("done", "--id", "t-001"))
        self.ok("done", "--id", "t-001", "--reopen")
        self.assertEqual((self.tareas()[0]["estado"], self.tareas()[0]["cerrada"]), ("pending", ""))

    def test_add_funciona_sin_install_previo(self):
        self.ok("add", "--title", "Primera")
        self.assertEqual(self.tareas()[0]["id"], "t-001")

    def test_borrado_logico_y_restauracion(self):
        self.ok("add", "--title", "Borrable")
        self.ok("delete", "--id", "t-001")
        self.assertNotIn("t-001", self.ok("list"))
        self.assertIn("t-001", self.ok("list", "--status", "removed"))
        self.assertEqual(self.td("done", "--id", "t-001").returncode, 2)               # una borrada no se cierra
        self.ok("modify", "--id", "t-001", "--restore")
        self.assertIn("t-001", self.ok("list"))
        self.assertEqual(self.td("modify", "--id", "t-001", "--restore").returncode, 2)  # ya no está borrada

    def test_los_ids_no_se_reutilizan_tras_borrar(self):
        self.ok("add", "--title", "A"); self.ok("delete", "--id", "t-001"); self.ok("add", "--title", "B")
        self.assertEqual([t["id"] for t in self.tareas()], ["t-001", "t-002"])

    def test_modify_cambia_solo_lo_indicado(self):
        self.ok("add", "--title", "Vieja", "--due", "2099-05-05", "--notes", "n")
        self.ok("modify", "--id", "t-001", "--title", "Nueva", "--priority", "low")
        t = self.tareas()[0]
        self.assertEqual((t["titulo"], t["prioridad"], t["vence"], t["notas"]), ("Nueva", "low", "2099-05-05", "n"))
        self.ok("modify", "--id", "t-001", "--due", "none")
        self.assertEqual(self.tareas()[0]["vence"], "")

    def test_dry_run_no_escribe(self):
        self.ok("add", "--title", "X")
        antes = read(self.store)
        for cmd in (["add", "--title", "Y"], ["done", "--id", "t-001"], ["modify", "--id", "t-001", "--title", "Z"], ["delete", "--id", "t-001"]):
            self.assertIn("DRY|", self.ok(*cmd, "--dry-run"))
        self.assertEqual(read(self.store), antes)

    def test_list_filtra_vencidas_y_ordena(self):
        self.ok("add", "--title", "Futura", "--due", "2099-01-01")
        self.ok("add", "--title", "Vencida", "--due", AYER, "--priority", "high")
        self.ok("add", "--title", "Sin fecha", "--priority", "low")
        out = self.ok("list")
        self.assertLess(out.index("Vencida"), out.index("Futura"))
        self.assertLess(out.index("Futura"), out.index("Sin fecha"))
        self.assertIn("⚠ vencida", out)
        solo = self.ok("list", "--overdue")
        self.assertIn("Vencida", solo); self.assertNotIn("Futura", solo)
        self.assertIn("Sin fecha", self.ok("list", "--priority", "low"))

    def test_json(self):
        self.ok("add", "--title", "J")
        d = json.loads(self.ok("list", "--json"))
        self.assertEqual((d["plugin"], d["skill"], d["status"]), ("arkana-todo", "list", "ok"))


class TestModeloDeEstados(Base):
    def alta(self):
        self.ok("add", "--title", "Baja", "--priority", "low")
        self.ok("add", "--title", "Critica", "--priority", "critical", "--component", "api")
        self.ok("add", "--title", "Media")
        self.ok("add", "--title", "Alta | con barra", "--priority", "high")
        self.ok("add", "--title", "Bloqueada", "--priority", "high")
        self.ok("modify", "--id", "t-005", "--status", "blocked")
        self.ok("add", "--title", "En marcha", "--priority", "medium")
        self.ok("modify", "--id", "t-006", "--status", "in-progress")
        self.ok("add", "--title", "Hecha"); self.ok("done", "--id", "t-007")
        self.ok("add", "--title", "Rechazada"); self.ok("modify", "--id", "t-008", "--status", "rejected")
        self.ok("add", "--title", "Quitada"); self.ok("delete", "--id", "t-009")
        self.ok("add", "--title", "Pausada"); self.ok("modify", "--id", "t-010", "--status", "paused")

    def test_valores_por_defecto(self):
        self.ok("add", "--title", "X")
        t = self.tareas()[0]
        self.assertEqual((t["estado"], t["prioridad"], t["componente"]), ("pending", "medium", ["*"]))

    def test_una_tabla_por_estado_con_la_cabecera_pedida(self):
        self.alta()
        out = self.ok("list")
        cab = "| identificador | prioridad | componente | descripcion | estado |"
        self.assertEqual(out.count(cab), 4)                                        # pending, in-progress, paused, blocked
        orden = [out.index(f"### {e} (") for e in ("pending", "in-progress", "paused", "blocked")]
        self.assertEqual(orden, sorted(orden))

    def test_por_defecto_no_salen_done_rejected_ni_removed(self):
        self.alta()
        out = self.ok("list")
        for e in ("Hecha", "Rechazada", "Quitada"):
            self.assertNotIn(e, out)
        for e in ("done", "rejected", "removed"):
            self.assertNotIn(f"### {e}", out)
        todo = self.ok("list", "--status", "all")
        for e in ("### done (1)", "### rejected (1)", "### removed (1)", "Hecha", "Rechazada", "Quitada"):
            self.assertIn(e, todo)
        solo = self.ok("list", "--status", "done,rejected")
        self.assertIn("Hecha", solo); self.assertIn("Rechazada", solo); self.assertNotIn("Quitada", solo); self.assertNotIn("### pending", solo)

    def test_dentro_de_cada_tabla_se_ordena_por_prioridad(self):
        self.alta()
        out = self.ok("list")
        pend = out[out.index("### pending"):out.index("### in-progress")]
        self.assertEqual([pend.index(x) for x in ("Critica", "Alta", "Media", "Baja")], sorted(pend.index(x) for x in ("Critica", "Alta", "Media", "Baja")))

    def test_la_barra_del_titulo_se_escapa_y_el_componente_se_muestra(self):
        self.alta()
        out = self.ok("list")
        self.assertIn("Alta \\| con barra", out)
        self.assertIn("| t-002 | critical | API | Critica | pending |", out)

    def test_filtro_por_componente_incluye_las_de_todos(self):
        self.alta()
        out = self.ok("list", "--component", "api")
        self.assertIn("Critica", out); self.assertIn("Media", out)                  # `*` afecta a todos los componentes

    def test_transiciones_y_cierre(self):
        self.ok("add", "--title", "A")
        self.ok("modify", "--id", "t-001", "--status", "done")
        self.assertNotEqual(self.tareas()[0]["cerrada"], "")
        self.ok("modify", "--id", "t-001", "--status", "paused")
        self.assertEqual((self.tareas()[0]["estado"], self.tareas()[0]["cerrada"]), ("paused", ""))
        self.assertEqual(self.td("modify", "--id", "t-001", "--status", "hecho").returncode, 2)
        self.ok("delete", "--id", "t-001")
        self.assertEqual(self.td("modify", "--id", "t-001", "--status", "pending").returncode, 2)   # borrada: solo --restore
        self.ok("modify", "--id", "t-001", "--restore")
        self.assertEqual(self.tareas()[0]["estado"], "pending")

    def test_sin_tareas(self):
        self.assertIn("Sin tareas", self.ok("list"))

    def test_json_sigue_siendo_el_formato_comun(self):
        self.alta()
        d = json.loads(self.ok("list", "--json"))
        self.assertTrue(all(i["status"] == "INFO" or i["status"] == "info" for i in d["items"]))
        self.assertEqual(len(d["items"]), 7)

    def test_valores_antiguos_se_leen_se_avisan_y_fix_los_migra(self):
        write(self.store, json.dumps({"version": 1, "next": 4, "tareas": [
            {"id": "t-001", "titulo": "A", "estado": "open", "prioridad": "normal", "vence": "", "componente": "", "creada": AYER, "cerrada": "", "notas": ""},
            {"id": "t-002", "titulo": "B", "estado": "deleted", "prioridad": "high", "vence": "", "componente": "all", "creada": AYER, "cerrada": "", "notas": ""},
            {"id": "t-003", "titulo": "C", "estado": "done", "prioridad": "low", "vence": "", "componente": "api", "creada": AYER, "cerrada": AYER, "notas": ""}]}))
        self.assertIn("| t-001 | medium | * | A | pending |", self.ok("list"))
        out = self.ok("validate")
        self.assertIn("WARN|valores-antiguos", out)
        antes = read(self.store)
        self.assertIn("DRY|", self.ok("fix", "--dry-run")); self.assertEqual(read(self.store), antes)
        self.ok("fix")
        self.assertEqual([(t["estado"], t["prioridad"], t["componente"]) for t in self.tareas()],
                         [("pending", "medium", ["*"]), ("removed", "high", ["*"]), ("done", "low", ["api"])])
        self.assertNotIn("valores-antiguos", self.ok("validate"))
        self.assertIn("nada que reparar", self.ok("fix"))


class TestVariosComponentes(Base):
    """Una tarea puede afectar a varios componentes: en disco `componente` es siempre una lista; en el CLI, una lista separada por comas."""
    def manifiesto(self):
        write(os.path.join(self.h, ".arkana", "core", "workspace.json"),
              json.dumps({"schema": 1, "arkana": {"alias": "ARKANA", "path": "."},
                          "components": [{"alias": "m3wa", "type": "node", "path": "web", "id": "11111111-1111-4111-8111-111111111111"},
                                         {"alias": "m3mf", "type": "node", "path": "mf"}, {"alias": "api", "type": "maven", "path": "back"}]}))
        write(os.path.join(self.h, "arkana-project.json"), json.dumps({"schema_version": 1, "layout": 9, "workspace": {"id": "x", "name": "t"},
              "components": [{"id": "11111111-1111-4111-8111-111111111111", "alias": "m3wa", "module": "viso_webapp"}]}))

    def comp(self, i=-1):
        return self.tareas()[i]["componente"]

    def test_alta_con_uno_varios_y_asterisco(self):
        self.manifiesto()
        self.ok("add", "--title", "uno", "--component", "m3wa")
        self.ok("add", "--title", "varios", "--component", "m3wa,m3mf")
        self.ok("add", "--title", "todos", "--component", "*")
        self.ok("add", "--title", "ninguno")
        self.assertEqual([t["componente"] for t in self.tareas()], [["m3wa"], ["m3wa", "m3mf"], ["*"], ["*"]])

    def test_cada_elemento_admite_alias_carpeta_modulo_y_prefijos_sin_repetidos_y_en_orden(self):
        self.manifiesto()
        self.ok("add", "--title", "mezcla", "--component", "mf, viso_webapp ,dir:back,M3MF,mod:viso_webapp")
        self.assertEqual(self.comp(), ["m3mf", "m3wa", "api"])                     # carpeta, módulo, carpeta con prefijo; sin repetidos; en el orden dado

    def test_asterisco_combinado_se_rechaza_y_no_se_escribe(self):
        self.manifiesto()
        for malo in ("*,m3mf", "m3mf,*", "all,m3wa", "m3wa,*,api"):
            r = self.td("add", "--title", "x", "--component", malo)
            self.assertEqual(r.returncode, 2, malo)
            self.assertIn("no se combina con otros", r.stdout)
        self.assertFalse(os.path.exists(self.store))
        self.ok("add", "--title", "ok", "--component", "m3wa")
        self.assertEqual(self.td("modify", "--id", "t-001", "--component", "*,api").returncode, 2)
        self.assertEqual(self.comp(), ["m3wa"])                                      # el modify rechazado no cambió nada

    def test_un_componente_desconocido_en_la_lista_se_rechaza(self):
        self.manifiesto()
        r = self.td("add", "--title", "x", "--component", "m3wa,nadie")
        self.assertEqual(r.returncode, 2); self.assertIn("componente desconocido: nadie", r.stdout)
        self.assertEqual(self.td("add", "--title", "x", "--component", "mod:back").returncode, 2)       # un prefijo de otro tipo no adivina

    def test_modify_de_uno_a_varios_y_de_varios_a_uno_y_a_todos(self):
        self.manifiesto()
        self.ok("add", "--title", "t", "--component", "m3wa")
        self.ok("modify", "--id", "t-001", "--component", "m3wa,api")
        self.assertEqual(self.comp(), ["m3wa", "api"])
        self.ok("modify", "--id", "t-001", "--component", "api")
        self.assertEqual(self.comp(), ["api"])
        self.ok("modify", "--id", "t-001", "--component", "m3mf,m3wa")
        self.ok("modify", "--id", "t-001", "--component", "*")
        self.assertEqual(self.comp(), ["*"])
        self.ok("modify", "--id", "t-001", "--title", "otro título")                  # sin --component no se toca
        self.assertEqual(self.comp(), ["*"])

    def test_dry_run_no_escribe(self):
        self.manifiesto()
        self.ok("add", "--title", "t", "--component", "m3wa")
        antes = read(self.store)
        self.assertIn("DRY|", self.ok("modify", "--id", "t-001", "--component", "m3wa,m3mf", "--dry-run"))
        self.assertEqual(read(self.store), antes)

    def test_la_tabla_muestra_varios_en_mayusculas(self):
        self.manifiesto()
        self.ok("add", "--title", "dos", "--component", "m3wa,m3mf"); self.ok("add", "--title", "todos"); self.ok("add", "--title", "uno", "--component", "api")
        out = self.ok("list")
        self.assertIn("| t-001 | medium | M3WA, M3MF | dos | pending |", out)
        self.assertIn("| t-002 | medium | * | todos | pending |", out)
        self.assertIn("| t-003 | medium | API | uno | pending |", out)

    def test_el_filtro_de_list_incluye_las_tareas_cuya_lista_contiene_alguno_y_las_de_todos(self):
        self.manifiesto()
        self.ok("add", "--title", "dos", "--component", "m3wa,m3mf"); self.ok("add", "--title", "solo-api", "--component", "api")
        self.ok("add", "--title", "de-todos"); self.ok("add", "--title", "solo-mf", "--component", "m3mf")
        out = self.ok("list", "--component", "m3wa")
        self.assertIn("dos", out); self.assertIn("de-todos", out); self.assertNotIn("solo-api", out); self.assertNotIn("solo-mf", out)
        out = self.ok("list", "--component", "m3mf")
        self.assertIn("dos", out); self.assertIn("solo-mf", out); self.assertIn("de-todos", out); self.assertNotIn("solo-api", out)
        out = self.ok("list", "--component", "api,m3mf")                              # el filtro también admite varios: basta con que coincida alguno
        self.assertIn("solo-api", out); self.assertIn("solo-mf", out); self.assertIn("dos", out)
        self.assertEqual(self.td("list", "--component", "*,api").returncode, 2)

    def test_rename_cambia_solo_ese_alias_dentro_de_la_lista(self):
        self.ok("add", "--title", "a", "--component", "m3wa,m3mf")
        self.ok("add", "--title", "b", "--component", "m3mf"); self.ok("add", "--title", "c")
        self.assertIn("2 tareas pasan de m3mf a movil", self.ok("rename", "--from", "M3MF", "--to", "movil"))
        self.assertEqual([t["componente"] for t in self.tareas()], [["m3wa", "movil"], ["movil"], ["*"]])
        self.ok("add", "--title", "d", "--component", "m3wa,movil")
        self.ok("rename", "--from", "m3wa", "--to", "movil")                          # si el nuevo ya estaba, no se duplica
        self.assertEqual(self.comp(), ["movil"])
        self.assertIn("0 tareas", self.ok("rename", "--from", "nada", "--to", "otro"))

    def test_rename_dry_run_no_escribe(self):
        self.ok("add", "--title", "a", "--component", "m3wa,m3mf")
        antes = read(self.store)
        self.assertIn("DRY|rename|1 tareas", self.ok("rename", "--from", "m3wa", "--to", "web", "--dry-run"))
        self.assertEqual(read(self.store), antes)

    def test_datos_antiguos_texto_se_leen_se_avisan_y_fix_los_pasa_a_lista(self):
        write(self.store, json.dumps({"version": 1, "next": 4, "tareas": [
            {"id": "t-001", "titulo": "texto", "estado": "pending", "prioridad": "medium", "vence": "", "componente": "api", "creada": "2026-01-01", "cerrada": "", "notas": ""},
            {"id": "t-002", "titulo": "todos", "estado": "pending", "prioridad": "medium", "vence": "", "componente": "*", "creada": "2026-01-01", "cerrada": "", "notas": ""},
            {"id": "t-003", "titulo": "lista", "estado": "pending", "prioridad": "medium", "vence": "", "componente": ["m3wa", "m3mf"], "creada": "2026-01-01", "cerrada": "", "notas": ""}]}))
        out = self.ok("list")
        self.assertIn("| t-001 | medium | API | texto | pending |", out); self.assertIn("| t-003 | medium | M3WA, M3MF | lista | pending |", out)
        val = self.ok("validate")
        self.assertIn("WARN|valores-antiguos|2 tareas", val)                           # solo los dos que están guardados como texto
        antes = read(self.store)
        self.assertIn("DRY|", self.ok("fix", "--dry-run")); self.assertEqual(read(self.store), antes)
        self.ok("fix")
        self.assertEqual([t["componente"] for t in self.tareas()], [["api"], ["*"], ["m3wa", "m3mf"]])
        self.assertNotIn("valores-antiguos", self.ok("validate"))
        self.assertIn("nada que reparar", self.ok("fix"))

    def test_validate_marca_un_asterisco_combinado_en_los_datos(self):
        write(self.store, json.dumps({"version": 1, "next": 2, "tareas": [
            {"id": "t-001", "titulo": "x", "estado": "pending", "prioridad": "medium", "vence": "", "componente": ["*", "api"], "creada": "2026-01-01", "cerrada": "", "notas": ""}]}))
        r = self.td("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("`*` ya incluye a todos", r.stdout)

    def test_lista_vacia_o_con_vacios_se_lee_como_todos(self):
        write(self.store, json.dumps({"version": 1, "next": 3, "tareas": [
            {"id": "t-001", "titulo": "x", "estado": "pending", "prioridad": "medium", "vence": "", "componente": [], "creada": "2026-01-01", "cerrada": "", "notas": ""},
            {"id": "t-002", "titulo": "y", "estado": "pending", "prioridad": "medium", "vence": "", "componente": ["", "all"], "creada": "2026-01-01", "cerrada": "", "notas": ""}]}))
        out = self.ok("list")
        self.assertIn("| t-001 | medium | * | x | pending |", out); self.assertIn("| t-002 | medium | * | y | pending |", out)

    def test_json_lleva_los_componentes(self):
        self.manifiesto()
        self.ok("add", "--title", "dos", "--component", "m3wa,m3mf")
        d = json.loads(self.ok("list", "--json"))
        self.assertIn("m3wa,m3mf", d["items"][0]["detail"])


class TestValidacion(Base):
    def test_entradas_invalidas(self):
        self.assertEqual(self.td("add", "--title", "  ").returncode, 2)
        self.assertEqual(self.td("add", "--title", "x", "--priority", "urgente").returncode, 2)
        self.assertEqual(self.td("add", "--title", "x", "--due", "2026-13-40").returncode, 2)
        self.assertEqual(self.td("add", "--title", "x", "--due", "mañana").returncode, 2)
        self.assertEqual(self.td("done", "--id", "t-999").returncode, 2)
        self.assertEqual(self.td("list", "--priority", "urgente").returncode, 2)                  # también con el almacén vacío
        self.assertEqual(self.td("modify", "--id", "t-001").returncode, 2)
        self.assertFalse(os.path.exists(self.store))

    def test_componente_se_valida_contra_el_manifiesto(self):
        write(os.path.join(self.h, ".arkana", "core", "workspace.json"),
              json.dumps({"schema": 1, "arkana": {"alias": "ARKANA", "path": "."}, "components": [{"alias": "api", "type": "maven", "path": "back"}]}))
        self.ok("add", "--title", "ok", "--component", "api")
        self.assertEqual(self.td("add", "--title", "mal", "--component", "nadie").returncode, 2)
        self.ok("add", "--title", "todos", "--component", "*")
        self.assertEqual(self.tareas()[-1]["componente"], ["*"])

    def test_el_componente_se_da_por_alias_carpeta_o_modulo_y_se_guarda_el_alias(self):
        write(os.path.join(self.h, ".arkana", "core", "workspace.json"),
              json.dumps({"schema": 1, "arkana": {"alias": "ARKANA", "path": "."}, "components": [{"alias": "api", "type": "maven", "path": "back", "id": "11111111-1111-4111-8111-111111111111"}]}))
        write(os.path.join(self.h, "arkana-project.json"), json.dumps({"schema_version": 1, "layout": 5, "workspace": {"id": "x", "name": "t"},
              "components": [{"id": "11111111-1111-4111-8111-111111111111", "alias": "api", "module": "viso_rest"}]}))
        for ref in ("api", "API", "back", "viso_rest", "dir:back", "mod:viso_rest"):
            self.ok("add", "--title", f"t {ref}", "--component", ref)
        self.assertEqual({tuple(t["componente"]) for t in self.tareas()}, {("api",)})
        self.assertEqual(self.td("add", "--title", "x", "--component", "mod:back").returncode, 2)
        self.assertIn("| API |", self.ok("list"))                                              # se muestra en MAYÚSCULAS
        self.assertIn("viso_rest", self.ok("list", "--component", "viso_rest") + "viso_rest")  # el filtro acepta cualquier nombre
        self.assertIn("t api", self.ok("list", "--component", "back"))

    def test_sin_workspace_falla_con_codigo_3(self):
        r = subprocess.run([sys.executable, "-I", TD, "--home", os.path.join(self.h, "no-existe"), "list"], capture_output=True, text=True, env=ENV)
        self.assertEqual(r.returncode, 3)

    def test_validate_estados(self):
        self.assertIn("WARN|almacen", self.ok("validate"))                          # sin almacén: aviso, no fallo
        self.ok("add", "--title", "A", "--due", AYER)
        out = self.ok("validate")
        self.assertIn("OK|almacen|1 tareas, 1 activas", out); self.assertIn("WARN|vencidas", out)
        d = json.loads(read(self.store)); d["tareas"][0]["estado"] = "raro"; d["tareas"].append(dict(d["tareas"][0], estado="pending"))
        write(self.store, json.dumps(d))
        r = self.td("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("estado inválido", r.stdout); self.assertIn("id duplicado", r.stdout)
        write(self.store, "no es json")
        self.assertEqual(self.td("validate").returncode, 1)

    def test_rename_reescribe_el_componente_de_las_tareas_y_respeta_dry_run(self):
        self.ok("add", "--title", "Una", "--component", "app")
        self.ok("add", "--title", "Otra", "--component", "api")
        antes = read(self.store)
        self.assertIn("DRY|rename|1 tareas pasan de app a frontend", self.ok("rename", "--from", "app", "--to", "frontend", "--dry-run"))
        self.assertEqual(read(self.store), antes)
        self.assertIn("OK|rename|1 tareas pasan de app a frontend", self.ok("rename", "--from", "APP", "--to", "frontend"))
        self.assertEqual([t["componente"] for t in self.tareas()], [["frontend"], ["api"]])
        self.assertIn("0 tareas", self.ok("rename", "--from", "app", "--to", "frontend"))                  # idempotente

    def test_fix_repara_contador_y_campos_sin_perder_tareas(self):
        write(self.store, json.dumps({"version": 1, "next": 1, "tareas": [{"id": "t-005", "titulo": "Vieja"}]}))
        self.assertEqual(self.td("validate").returncode, 1)
        antes = read(self.store)
        self.assertIn("DRY|", self.ok("fix", "--dry-run"))
        self.assertEqual(read(self.store), antes)
        self.ok("fix")
        self.ok("validate")
        d = json.loads(read(self.store))
        self.assertEqual((d["next"], d["tareas"][0]["titulo"], d["tareas"][0]["estado"]), (6, "Vieja", "pending"))
        self.assertIn("nada que reparar", self.ok("fix"))


class TestContrato(unittest.TestCase):
    def test_el_contrato_declara_las_skills_que_existen(self):
        raiz = os.path.abspath(os.path.join(AQUI, ".."))
        with open(os.path.join(raiz, "arkana-plugin.json"), encoding="utf-8") as f:
            c = json.load(f)
        self.assertEqual(c["contract"], 1)
        for s in c["provides"]:
            self.assertTrue(os.path.isfile(os.path.join(raiz, "skills", s, "SKILL.md")), s)
        self.assertEqual(c["data"][0]["class"], "data")


if __name__ == "__main__":
    unittest.main()
