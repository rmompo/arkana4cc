"""Hook de sesión: BRIEF al usuario (systemMessage) y directrices de la pieza al modelo (additionalContext); solo local; nada en workers ni fuera de un workspace."""
import json
import re
import os
import subprocess
import sys
import unittest

import environment as E
import test_credentials as TC

HOOK = os.path.join(E.SCRIPTS, "hooks.py")


def run(lab, cwd, env=None, source="startup"):
    return subprocess.run([sys.executable, "-I", HOOK, "session-status"], input=json.dumps({"cwd": cwd, "source": source}), capture_output=True, text=True,
                          env=dict(lab.env, **(env or {})), cwd=cwd, timeout=30)


def migrada(lab):
    """Marca la instalación del laboratorio como ya migrada (registro del proyecto en el layout que esperan los plugins)."""
    wj(os.path.join(lab.arkana, "arkana-project.json"), {"schema_version": 1, "layout": 4, "workspace": {"id": "x", "name": "t"}, "components": []})


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


class TestVigilanciaYLayoutEnElBrief(unittest.TestCase):
    def sesion(self, lab):
        r = run(lab, os.path.join(lab.ws, "app"))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout).get("systemMessage", "")

    def test_un_componente_sin_vigilar_no_sale_en_git_pending(self):
        with TC.CLab() as lab:
            migrada(lab)
            app = os.path.join(lab.ws, "app")
            subprocess.run(["git", "init", "-q", app], check=True)
            with open(os.path.join(app, "nuevo.txt"), "w") as f:
                f.write("x")
            self.assertRegex(self.sesion(lab), r"\d\. APP \(")
            f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
            d = json.load(open(f, encoding="utf-8"))
            for c in d["components"]:
                if c["alias"] == "app":
                    c["watch"] = False
            d["schema"] = 2
            wj(f, d)
            self.assertNotRegex(self.sesion(lab), r"\d\. APP \(")                       # sin vigilar: sus cambios no cuentan

    def test_repo_en_un_layout_mas_nuevo_dice_que_hay_que_actualizar_el_plugin(self):
        with TC.CLab() as lab:
            wj(os.path.join(lab.arkana, "arkana-project.json"), {"schema_version": 1, "layout": 99, "workspace": {"id": "x", "name": "t"}, "components": []})
            m = self.sesion(lab)
            self.assertIn("layout 99", m)
            self.assertIn("actualiza el plugin", m)
            self.assertNotIn("/arkana-evolve:apply", m.split("\n")[0])                       # el aviso no manda aplicar nada: manda actualizar

    def test_en_el_layout_conocido_no_hay_aviso(self):
        with TC.CLab() as lab:
            wj(os.path.join(lab.arkana, "arkana-project.json"), {"schema_version": 1, "layout": 5, "workspace": {"id": "x", "name": "t"}, "components": []})
            self.assertNotIn("layout", self.sesion(lab))


class TestSeccionTodo(unittest.TestCase):
    def tareas(self, lab, tareas):
        wj(os.path.join(lab.arkana, ".arkana", "arkana-todo", "todos.json"), {"version": 1, "next": 99, "tareas": tareas})

    def brief(self, lab):
        r = run(lab, os.path.join(lab.ws, "app"))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout).get("systemMessage", "")

    def test_lista_las_activas_ordenadas_por_prioridad_con_estado_vencimiento_y_componente(self):
        with TC.CLab() as lab:
            migrada(lab)
            t = lambda i, titulo, **kw: dict({"id": i, "titulo": titulo, "estado": "pending", "prioridad": "medium", "vence": "", "componente": "*"}, **kw)
            self.tareas(lab, [t("t-001", "Sin fecha"), t("t-002", "Urgente", prioridad="high", vence="2099-01-01", componente="api"),
                              t("t-003", "Atrasada", vence="2000-01-01"), t("t-004", "Hecha", estado="done"), t("t-005", "Borrada", estado="removed"),
                              t("t-006", "Bloqueada", estado="blocked", prioridad="low"), t("t-007", "Legado", estado="open", prioridad="normal", componente=""),
                              t("t-008", "Rechazada", estado="rejected")])
            m = self.brief(lab)
            self.assertIn("\n### TODOS\n", m)
            self.assertIn("1. [T-002] (high, API, vence 2099-01-01) Urgente\n2. [T-003] (medium, *, ⚠ vencida 2000-01-01) Atrasada\n3. [T-001] (medium, *) Sin fecha\n"
                          "4. [T-007] (medium, *) Legado\n5. [T-006] (low, *, blocked) Bloqueada\n", m)
            for oculta in ("Hecha", "Borrada", "Rechazada"):
                self.assertNotIn(oculta, m)
            self.assertIn("- /arkana-todo:list         - active tasks grouped by status, with priority and due date", m)

    def notas(self, lab, notas):
        wj(os.path.join(lab.arkana, ".arkana", "arkana-note", "notes.json"), {"version": 1, "next": 99, "notas": notas})

    def test_las_notas_activas_salen_en_el_brief_y_en_el_quick_start(self):
        with TC.CLab() as lab:
            migrada(lab)
            n = lambda i, titulo, **kw: dict({"id": i, "titulo": titulo, "estado": "active", "componente": "*", "modificada": "2026-01-01"}, **kw)
            self.notas(lab, [n("n-001", "Vieja"), n("n-002", "Reciente", modificada="2026-06-01", componente="api"), n("n-003", "Borrada", estado="removed")])
            m = self.brief(lab)
            self.assertIn("\n### NOTES\n1. [N-002] (API) Reciente\n2. [N-001] (*) Vieja\n", m)
            self.assertNotIn("Borrada", m)
            self.assertIn("- /arkana-note:list         - your notes (add one with /arkana-note:add)", m)

    def test_las_notas_van_despues_de_todos_y_antes_de_git_y_salen_todas(self):
        with TC.CLab() as lab:
            migrada(lab)
            app = os.path.join(lab.ws, "app")
            with open(os.path.join(app, "nuevo.txt"), "w") as f:
                f.write("x")
            self.tareas(lab, [{"id": "t-001", "titulo": "Algo", "estado": "pending", "prioridad": "medium"}])
            self.notas(lab, [{"id": f"n-{i:03d}", "titulo": f"Nota {i}", "estado": "active", "modificada": f"2026-01-{i:02d}"} for i in range(1, 9)])
            m = self.brief(lab)
            self.assertLess(m.index("### TODOS"), m.index("### NOTES")); self.assertLess(m.index("### NOTES"), m.index("### GIT (pending)"))
            self.assertIn("1. [N-008] (*) Nota 8\n", m); self.assertIn("8. [N-001] (*) Nota 1\n", m)      # todas, las modificadas más recientemente primero
            self.assertNotIn("more", m)

    def test_sin_notas_no_hay_seccion_ni_linea_en_el_quick_start(self):
        with TC.CLab() as lab:
            migrada(lab)
            self.tareas(lab, [{"id": "t-001", "titulo": "Algo", "estado": "pending", "prioridad": "medium"}])
            m = self.brief(lab)
            self.assertNotIn("NOTES", m); self.assertNotIn("/arkana-note:list", m)

    def test_las_tareas_de_varios_componentes_salen_con_todos_ellos(self):
        with TC.CLab() as lab:
            migrada(lab)
            base = {"estado": "pending", "prioridad": "medium", "vence": ""}
            self.tareas(lab, [dict(base, id="t-001", titulo="Varias", componente=["app", "api"]), dict(base, id="t-002", titulo="Texto", componente="api"),
                              dict(base, id="t-003", titulo="Todas", componente=["*"]), dict(base, id="t-004", titulo="Sin campo")])
            m = self.brief(lab)
            self.assertIn("1. [T-001] (medium, APP, API) Varias", m) if False else self.assertIn("[T-001] (medium, APP, API) Varias", m)
            self.assertIn("[T-002] (medium, API) Texto", m)                                     # el texto de versiones anteriores se sigue leyendo
            self.assertIn("[T-003] (medium, *) Todas\n", m); self.assertIn("[T-004] (medium, *) Sin campo\n", m)      # * y sin campo: se muestra *

    def test_tras_un_compact_o_un_resume_el_brief_sale_siempre_y_tambien_llega_al_modelo(self):
        with TC.CLab() as lab:
            migrada(lab)
            wj(os.path.join(lab.arkana, ".arkana", "arkana-todo", "todos.json"), {"version": 1, "next": 2, "tareas": [{"id": "t-001", "titulo": "Pendiente", "estado": "pending", "prioridad": "high", "componente": ["*"]}]})
            app = os.path.join(lab.ws, "app")
            for fuente, frase in (("compact", "tras compactar"), ("resume", "tras reanudar")):
                out = json.loads(run(lab, app, source=fuente).stdout)
                self.assertIn("### TODOS", out["systemMessage"])                                   # la persona usuaria lo ve
                ctx = out["hookSpecificOutput"]["additionalContext"]
                self.assertIn(frase, ctx); self.assertIn("### QUICK START", ctx); self.assertIn("[T-001] (high, *) Pendiente", ctx)   # y el modelo también
                self.assertIn("Directrices para APP", ctx)                                         # sin perder las directrices de la pieza

    def test_sin_nada_pendiente_el_arranque_no_da_brief_pero_compact_y_resume_si(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("arkana_hooks_under_test", HOOK)
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        self.assertIsNone(h.brief([], [], None))                                                    # arranque limpio: sin ruido, como antes
        forzado = h.brief([], [], None, force=True)                                                 # tras un compact o un resume: siempre, aunque solo lleve el QUICK START
        self.assertIn("### QUICK START", forzado)
        for seccion in ("### TODO", "### NOTES", "### GIT", "### MESSAGING", "### ORCHESTRATION"):
            self.assertNotIn(seccion, forzado)

    def test_clear_y_startup_no_meten_el_brief_en_el_contexto_del_modelo(self):
        with TC.CLab() as lab:
            migrada(lab)
            wj(os.path.join(lab.arkana, ".arkana", "arkana-todo", "todos.json"), {"version": 1, "next": 2, "tareas": [{"id": "t-001", "titulo": "Pendiente", "estado": "pending", "prioridad": "medium", "componente": ["*"]}]})
            app = os.path.join(lab.ws, "app")
            for fuente in ("startup", "clear"):
                out = json.loads(run(lab, app, source=fuente).stdout)
                self.assertIn("### TODOS", out["systemMessage"])
                self.assertNotIn("QUICK START", out["hookSpecificOutput"]["additionalContext"], fuente)

    def test_fuera_de_una_pieza_el_brief_tras_un_compact_llega_igualmente_al_modelo(self):
        with TC.CLab() as lab:
            migrada(lab)
            os.makedirs(os.path.join(lab.ws, "otra-carpeta"), exist_ok=True)
            out = json.loads(run(lab, lab.arkana, source="compact").stdout)                         # el cwd es ARKANA (también una pieza)
            self.assertIn("QUICK START", out["hookSpecificOutput"]["additionalContext"])

    def test_la_cabecera_es_una_caja_de_40_y_el_quick_start_va_en_columnas(self):
        with TC.CLab() as lab:
            migrada(lab)
            m = self.brief(lab)
            lineas = m.split("\n")
            self.assertEqual(lineas[0], "")                                                       # salto de línea inicial intencionado
            self.assertEqual(lineas[1:4], ["*" * 40, "*" * 12 + " [ARKANA] BRIEF " + "*" * 12, "*" * 40])
            self.assertEqual({len(l) for l in lineas[1:4]}, {40})
            self.assertEqual(lineas[4:6], ["", "### QUICK START"])
            qs = lineas[6:lineas.index("", 6)]
            self.assertTrue(len(qs) >= 5)
            for l in qs:
                self.assertTrue(l.startswith("- /arkana-"), l)
                if len(l.split(" - ")[0]) <= 2 + 25:                                              # los comandos cortos alinean el « - » en la misma columna
                    self.assertEqual(l[27:30], " - ", l)
            self.assertIn("- /arkana-workspace:config  - set tool versions (and optional Jira)", qs)
            self.assertNotIn("Use '", m)

    def test_todos_y_notas_listan_todo_con_ids_en_mayusculas(self):
        with TC.CLab() as lab:
            migrada(lab)
            self.tareas(lab, [{"id": f"t-{i:03d}", "titulo": f"Tarea {i}", "estado": "pending", "prioridad": "critical" if i == 1 else "medium", "componente": ["m3wa"]} for i in range(1, 13)])
            wj(os.path.join(lab.arkana, ".arkana", "arkana-note", "notes.json"), {"version": 1, "next": 99, "notas": [
                {"id": f"n-{i:03d}", "titulo": f"Nota {i}", "estado": "active" if i != 4 else "removed", "componente": "*", "modificada": f"2026-02-{i:02d}"} for i in range(1, 11)]})
            m = self.brief(lab)
            self.assertEqual(len(re.findall(r"^\d+\. \[T-\d+\]", m, re.M)), 12)                  # las 12, sin recortar
            self.assertIn("1. [T-001] (critical, M3WA) Tarea 1\n", m); self.assertIn("12. [T-012] (medium, M3WA) Tarea 12\n", m)
            self.assertEqual(len(re.findall(r"^\d+\. \[N-\d+\]", m, re.M)), 9)                   # las 10 menos la eliminada
            self.assertNotIn("Nota 4", m); self.assertNotIn("more", m)
            self.assertNotRegex(m, r"\[t-\d+\]|\[n-\d+\]")                                       # ids siempre en mayúsculas

    def test_orden_de_las_secciones(self):
        with TC.CLab() as lab:
            migrada(lab)
            app = os.path.join(lab.ws, "app")
            subprocess.run(["git", "init", "-q", app], check=True)
            with open(os.path.join(app, "nuevo.txt"), "w") as f:
                f.write("x")
            self.tareas(lab, [{"id": "t-001", "titulo": "Algo", "estado": "open", "prioridad": "normal"}])
            wj(os.path.join(lab.arkana, ".arkana", "arkana-messaging", "state", "index.json"), {"messages": {
                "N1": {"de": "arkana", "para": ["app"], "tipo": "task", "estado": "open"}}})
            m = self.brief(lab)
            pos = [m.index(x) for x in ("### QUICK START", "### MESSAGING", "### TODOS", "### GIT (pending)")]
            self.assertEqual(pos, sorted(pos), m)                                               # QUICK START, MESSAGING, TODO y luego GIT
            self.assertTrue(m.startswith("\n" + "*" * 40 + "\n" + "*" * 12 + " [ARKANA] BRIEF " + "*" * 12 + "\n" + "*" * 40 + "\n\n### QUICK START\n"), m)

    def test_lista_todas_las_tareas_sin_recortar(self):
        with TC.CLab() as lab:
            migrada(lab)
            self.tareas(lab, [{"id": f"t-{i:03d}", "titulo": f"Tarea {i}", "estado": "open", "prioridad": "normal"} for i in range(1, 9)])
            m = self.brief(lab)
            self.assertIn("1. [T-001] (medium, *) Tarea 1\n", m); self.assertIn("8. [T-008] (medium, *) Tarea 8\n", m)
            self.assertNotIn("more", m)                                                           # sin «... and N more»: salen todas

    def test_sin_tareas_abiertas_no_hay_seccion_ni_brief(self):
        with TC.CLab() as lab:
            migrada(lab)
            self.tareas(lab, [{"id": "t-001", "titulo": "Hecha", "estado": "done", "prioridad": "normal"}])
            m = self.brief(lab)
            self.assertNotIn("### TODOS", m)
            self.assertNotIn("/arkana-todo:list", m)

    def test_fichero_roto_o_ausente_no_rompe_el_hook(self):
        with TC.CLab() as lab:
            migrada(lab)
            p = os.path.join(lab.arkana, ".arkana", "arkana-todo", "todos.json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write("{no es json")
            self.assertNotIn("### TODOS", self.brief(lab))

    def test_quick_start_incluye_ingest_y_evolve(self):
        with TC.CLab() as lab:
            migrada(lab)
            self.tareas(lab, [{"id": "t-001", "titulo": "Algo", "estado": "open", "prioridad": "normal"}])
            m = self.brief(lab)
            self.assertIn("- /arkana-knowledge:ingest  - turn what is waiting in arkana-incoming/ into notes and documents", m)
            self.assertIn("- /arkana-evolve:check      - check whether this installation needs migrations", m)


class TestComandoBrief(unittest.TestCase):
    """`hooks.py brief`: el BRIEF a demanda (lo usa /arkana-workspace:brief)."""
    def brief(self, lab, *extra, cwd=None, home=None):
        return subprocess.run([sys.executable, "-I", HOOK, "brief", *extra, *(["--home", lab.arkana] if home is None else [])], capture_output=True, text=True,
                              env=lab.env, cwd=cwd or lab.ws, stdin=subprocess.DEVNULL, timeout=30)

    def test_imprime_el_mismo_brief_que_el_hook(self):
        with TC.CLab() as lab:
            migrada(lab)
            self.tareas = None
            wj(os.path.join(lab.arkana, ".arkana", "arkana-todo", "todos.json"), {"version": 1, "next": 2, "tareas": [{"id": "t-001", "titulo": "Pendiente", "estado": "pending", "prioridad": "high", "componente": ["*"]}]})
            r = self.brief(lab)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("\n" + "*" * 40 + "\n"), r.stdout)
            self.assertIn("### TODOS\n1. [T-001] (high, *) Pendiente", r.stdout)
            hook = json.loads(run(lab, os.path.join(lab.ws, "app")).stdout)["systemMessage"]
            self.assertEqual(r.stdout, hook)                                                     # idéntico al del arranque

    def test_se_localiza_desde_el_directorio_actual_y_da_siempre_el_quick_start(self):
        with TC.CLab() as lab:
            migrada(lab)
            r = subprocess.run([sys.executable, "-I", HOOK, "brief"], capture_output=True, text=True, env=dict(lab.env, ARKANA_HOME=lab.arkana), cwd=lab.ws, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("### QUICK START", r.stdout)

    def test_fuera_de_un_workspace_falla_con_codigo_3_sin_traza(self):
        with TC.CLab() as lab:
            fuera = os.path.join(lab.root, "fuera"); os.makedirs(fuera)
            env = {k: v for k, v in lab.env.items() if not k.startswith("ARKANA_")}
            r = subprocess.run([sys.executable, "-I", HOOK, "brief"], capture_output=True, text=True, env=env, cwd=fuera, timeout=30)
            self.assertEqual(r.returncode, 3)
            self.assertIn("FAIL|workspace|", r.stderr); self.assertNotIn("Traceback", r.stderr)


class TestHookEstado(unittest.TestCase):
    def test_resumen_con_cambios_plan_y_mensajes_sin_inyectar_en_el_contexto(self):
        with TC.CLab() as lab:
            migrada(lab)
            app = os.path.join(lab.ws, "app")
            subprocess.run(["git", "init", "-q", app], check=True)
            with open(os.path.join(app, "nuevo.txt"), "w") as f:
                f.write("x")
            st = os.path.join(lab.arkana, ".arkana")
            os.makedirs(os.path.join(st, "arkana-agentic", "state", "planes", "P1"), exist_ok=True)
            with open(os.path.join(st, "arkana-agentic", "state", "actual"), "w") as f:
                f.write("P1")
            wj(os.path.join(st, "arkana-agentic", "state", "planes", "P1", "plan.json"), {"id": "P1", "estado": "en_ejecucion", "contadores": {"gasto_usd": 0.4}})
            wj(os.path.join(st, "arkana-messaging", "state", "index.json"), {"messages": {
                "N261103-0001-aaaa": {"de": "arkana", "para": ["app"], "tipo": "notice", "estado": None},
                "N261103-0002-bbbb": {"de": "arkana", "para": ["app"], "tipo": "task", "estado": "open"},
                "N261103-0003-cccc": {"de": "arkana", "para": ["app"], "tipo": "notice", "estado": "deleted"},
                "N261103-0004-dddd": {"de": "arkana", "para": ["app"], "tipo": "notice", "estado": None, "repeticion": "repeat", "vigencia": "vigente"},
                "N261103-0005-eeee": {"de": "api", "para": ["app"], "tipo": "notice", "estado": None, "repeticion": "repeat", "vigencia": "propuesto"},
                "N261103-0006-ffff": {"de": "arkana", "para": ["app"], "tipo": "task", "estado": "open", "confirmaciones": {"app": "done"}}}})
            wj(os.path.join(st, "arkana-messaging", "state", "read", "app.json"), {"ids": {"N261103-0001-aaaa": "x"}})
            r = run(lab, app)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(sorted(out), ["hookSpecificOutput", "systemMessage"])      # BRIEF al usuario y directrices al modelo, por canales distintos
            self.assertNotIn("BRIEF", out["hookSpecificOutput"]["additionalContext"])
            m = out["systemMessage"]
            self.assertTrue(m.startswith("\n" + "*" * 40 + "\n"), m)
            self.assertIn("### GIT (pending)\n", m)
            self.assertRegex(m, r"\d\. APP \(\S+\)")
            self.assertIn("### MESSAGING\n1. APP (1 tasks, 1 repeat)", m)
            self.assertIn("plan P1 (en_ejecucion, 0.40 USD)", m)
            self.assertIn("### QUICK START", m)
            usos = [l for l in m.split("### QUICK START\n")[1].splitlines()]
            orden = ["/arkana-workspace:config", "/arkana-workspace:check", "/arkana-workspace:fix", "/arkana-messaging:query --unread",
                     "/arkana-workspace:sync", "/arkana-workspace:status", "/arkana-agentic:status"]
            pos = [next(i for i, l in enumerate(usos) if f"- {c} " in l) for c in orden]
            self.assertEqual(pos, sorted(pos), usos)                            # config → check → fix, y luego lo del día
            self.assertTrue(m.endswith("\n"), repr(m[-40:]))                    # línea en blanco final
            self.assertNotIn(lab.root, m)

    def test_silencio_sin_nada_que_decir_en_worker_y_fuera_de_workspace(self):
        with TC.CLab() as lab:
            self.assertNotIn("MESSAGING", run(lab, lab.arkana).stdout)
            r = run(lab, os.path.join(lab.ws, "app"), env={"ARKANA_WORKER": "1"})
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            r = run(lab, lab.root, env={"ARKANA_HOME": ""})
            self.assertEqual((r.returncode, r.stdout), (0, ""))

class TestAvisoDeMigracion(unittest.TestCase):
    def test_avisa_al_usuario_si_el_layout_es_anterior_y_no_si_esta_al_dia(self):
        with TC.CLab() as lab:
            m = json.loads(run(lab, os.path.join(lab.ws, "app")).stdout)["systemMessage"]
            self.assertTrue(m.startswith("[ARKANA] ⚠ Instalación en layout 0; esta versión necesita 4. Ejecuta /arkana-evolve:apply."), m)
            migrada(lab)
            out = json.loads(run(lab, os.path.join(lab.ws, "app")).stdout)
            self.assertNotIn("Instalación en layout", out.get("systemMessage", ""))          # al día: sin aviso (el BRIEF normal sí puede salir)
            self.assertIn("hookSpecificOutput", out)


class TestHookDirectrices(unittest.TestCase):
    def ctx(self, r):
        return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_inyecta_las_directrices_de_la_pieza_del_cwd_sin_ficheros_en_el_repo(self):
        with TC.CLab() as lab:
            app = os.path.join(lab.ws, "app")
            r = run(lab, app)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "SessionStart")
            c = out["additionalContext"]
            self.assertIn("[Arkana] Directrices para APP", c)
            self.assertIn("No instales herramientas ni paquetes", c)
            self.assertIn("Conventional Commits con dos puntos", c)                 # formato por defecto
            self.assertIn("chore(app):", c)
            self.assertNotIn("CLAUDE", c)                                           # nada de Claude en lo que ve el repo
            for f in ("CLAUDE.md", "CLAUDE.local.md", "ARKANA.local.md"):          # y el hook no escribe ningún fichero de instrucciones
                self.assertFalse(os.path.exists(os.path.join(app, f)), f)

    def test_cada_pieza_recibe_la_suya_y_arkana_tambien(self):
        with TC.CLab() as lab:
            f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
            for c in d["components"]:
                if c["alias"] == "api":
                    c["commit_format"] = "ia4d"
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(d, fh)
            self.assertIn("**IA4D**", self.ctx(run(lab, os.path.join(lab.ws, "api"))))
            self.assertIn("Directrices para ARKANA", self.ctx(run(lab, lab.arkana)))
            sub = os.path.join(lab.ws, "app", "src", "ui")
            os.makedirs(sub, exist_ok=True)
            self.assertIn("Directrices para APP-UI", self.ctx(run(lab, sub)))      # la pieza más específica

    def test_las_notas_locales_se_inyectan_con_tope_y_solo_si_existen(self):
        with TC.CLab() as lab:
            app = os.path.join(lab.ws, "app")
            self.assertNotIn("Notas locales", self.ctx(run(lab, app)))
            with open(os.path.join(app, "ARKANA.local.md"), "w", encoding="utf-8") as fh:
                fh.write("Los tests se lanzan con `npm run test:ci`.\n")
            c = self.ctx(run(lab, app))
            self.assertIn("## Notas locales de este repo (ARKANA.local.md)", c)
            self.assertIn("npm run test:ci", c)
            with open(os.path.join(app, "ARKANA.local.md"), "w", encoding="utf-8") as fh:
                fh.write("x" * 20000)
            c = self.ctx(run(lab, app))
            self.assertIn("(notas recortadas)", c)
            self.assertLess(len(c), 12000)

    def test_sin_directrices_en_worker_ni_fuera_de_una_pieza(self):
        with TC.CLab() as lab:
            self.assertEqual(run(lab, os.path.join(lab.ws, "app"), env={"ARKANA_WORKER": "1"}).stdout, "")
            self.assertNotIn("hookSpecificOutput", run(lab, lab.root).stdout)       # cwd fuera de todas las piezas


if __name__ == "__main__":
    unittest.main()
