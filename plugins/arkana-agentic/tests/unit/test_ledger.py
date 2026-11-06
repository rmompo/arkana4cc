"""Libro de planes y sesiones: hooks que leen el coste real de la statusline, tokens del transcript, retención y `costs`."""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

import common
import ledger
import state

CONTROL = os.path.join(common.PLUGIN, "scripts", "lib", "control.py")
LEDGER = os.path.join(common.PLUGIN, "scripts", "lib", "ledger.py")


def wj(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f)


def ago(days):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="led-")
        self.shared = os.path.join(self.d, "ws", "shared")
        st = os.path.join(self.shared, ".arkana")
        wj(os.path.join(st, "arkana.json"), {"schema_version": 1, "workspace": {"name": "t"}, "root": ".."})
        wj(os.path.join(st, "core", "workspace.json"), {"schema": 1, "workspace": {"name": "t"}, "arkana": {"alias": "ARKANA", "path": "shared"},
           "components": [{"alias": "app", "type": "node", "path": "app"}, {"alias": "api", "type": "maven", "path": "be"}]})
        for c in ("app", "be"):
            os.makedirs(os.path.join(self.d, "ws", c))
        self.old = dict(os.environ)
        for k in ("ARKANA_WORKSPACE_CONF", "ARKANA_WORKER"):
            os.environ.pop(k, None)
        os.environ.update(ARKANA_HOME=self.shared, HOME=os.path.join(self.d, "home"), ARKANA_AGENTIC_DIR=os.path.join(st, "arkana-agentic"))
        os.makedirs(os.environ["HOME"])
        self.st = st

    def tearDown(self):
        os.environ.clear(); os.environ.update(self.old)

    def transcript(self, n=2):
        p = os.path.join(self.d, "t.jsonl")
        with open(p, "w") as f:
            for i in range(n):
                f.write(json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000}}}) + "\n")
            f.write(json.dumps({"type": "user", "message": {"content": "hola"}}) + "\n{no json\n")
        return p


class TestSesiones(Base):
    def test_fin_de_sesion_registra_componente_duracion_tokens_y_coste_real_de_la_statusline(self):
        cwd = os.path.join(self.d, "ws", "app")
        ledger.record_session({"session_id": "s1", "cwd": cwd}, "start")
        r = ledger.all_sessions()["s1"]
        self.assertEqual((r["component"], r["ended"], r["cost_usd"]), ("app", None, None))
        wj(os.path.join(self.st, "arkana-statusline", "state", "sessions", "s1.json"), {"session_id": "s1", "cost_usd": 1.2345, "ts": 1})
        ledger.record_session({"session_id": "s1", "cwd": cwd, "transcript_path": self.transcript(), "reason": "other"}, "end")
        r = ledger.all_sessions()["s1"]
        self.assertEqual((r["cost_usd"], r["cost_source"], r["end_reason"]), (1.2345, "statusline", "other"))
        self.assertEqual(r["tokens"], {"input": 20, "output": 10, "cache_creation": 200, "cache_read": 2000})
        self.assertIsNotNone(r["duration_s"])
        self.assertIsNotNone(r["ended"])

    def test_sin_fichero_de_la_statusline_el_coste_queda_vacio_y_nunca_se_estima(self):
        ledger.record_session({"session_id": "s2", "cwd": os.path.join(self.d, "ws", "be")}, "end")
        r = ledger.all_sessions()["s2"]
        self.assertEqual((r["component"], r["cost_usd"], r["cost_source"]), ("api", None, None))

    def test_acepta_la_anotacion_de_la_statusline_antigua(self):
        os.makedirs(state.sessions_dir())
        with open(os.path.join(state.sessions_dir(), "s3"), "w") as f:
            f.write("1793712976 0.6973\n")
        ledger.record_session({"session_id": "s3", "cwd": self.shared}, "end")
        r = ledger.all_sessions()["s3"]
        self.assertEqual((r["component"], r["cost_usd"]), ("arkana", 0.6973))

    def test_sesiones_que_solo_conoce_la_statusline_cuentan_con_su_coste(self):
        os.makedirs(state.sessions_dir())
        with open(os.path.join(state.sessions_dir(), "solo-antigua"), "w") as f:
            f.write("1793712976 0.5\n")
        wj(os.path.join(self.st, "arkana-statusline", "state", "sessions", "solo-nueva.json"), {"session_id": "solo-nueva", "cost_usd": 1.5, "ts": 1793712976})
        ledger.record_session({"session_id": "con-apunte", "cwd": self.shared}, "end")
        ses = ledger.all_sessions()
        self.assertEqual((ses["solo-antigua"]["cost_usd"], ses["solo-nueva"]["cost_usd"], ses["solo-nueva"]["sin_apunte"]), (0.5, 1.5, True))
        self.assertEqual(sorted(ses), ["con-apunte", "solo-antigua", "solo-nueva"])

    def test_el_plan_de_la_sesion_sale_de_linea_json(self):
        wj(os.path.join(state.run_dir(), "linea.json"), {"plan": "P1", "session_id": "s4"})
        wj(os.path.join(state.plan_dir("P1"), "plan.json"), {"id": "P1", "asunto": "x", "estado": "en_ejecucion", "contadores": {"gasto_usd": 0.3}})
        ledger.record_session({"session_id": "s4", "cwd": self.shared}, "start")
        ledger.record_session({"session_id": "s5", "cwd": self.shared}, "start")
        ses = ledger.all_sessions()
        self.assertEqual((ses["s4"]["plan"], ses["s5"]["plan"]), ("P1", None))
        self.assertTrue(os.path.exists(os.path.join(ledger.plans_dir(), "P1.json")))

    def test_hook_no_hace_nada_en_un_worker_ni_fuera_de_un_workspace_y_traga_errores(self):
        def hook(ev, env=None, cwd=None, raw=None):
            return subprocess.run([sys.executable, "-I", LEDGER, "hook", "session-start"], input=raw if raw is not None else json.dumps(ev), capture_output=True, text=True,
                                  env=dict(os.environ, **(env or {})), cwd=cwd or self.d, timeout=30)
        r = hook({"session_id": "w1", "cwd": self.shared}, {"ARKANA_WORKER": "1"})
        self.assertEqual((r.returncode, r.stdout), (0, ""))
        r = hook({"session_id": "f1", "cwd": self.d}, {"ARKANA_HOME": ""})
        self.assertEqual(r.returncode, 0)
        self.assertEqual(hook(None, raw="{no json").returncode, 0)
        self.assertEqual(sorted(ledger.all_sessions()), [])
        r = hook({"session_id": "ok1", "cwd": os.path.join(self.d, "ws", "app")})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ledger.all_sessions()["ok1"]["component"], "app")


class TestPlanesYRetencion(Base):
    def plan(self, pid, gasto, creado, estado="completado"):
        pd = state.plan_dir(pid)
        wj(os.path.join(pd, "plan.json"), {"id": pid, "asunto": "p " + pid, "estado": estado, "creado": creado, "contadores": {"gasto_usd": gasto},
           "ramas": {"api": {"nombre": f"arkana-worker/{pid}", "original": "develop", "decision": "merge"}},
           "historial": [{"fecha": creado, "accion": "x"}]})
        wj(os.path.join(pd, "tareas", "T001.json"), {"id": "T001", "repo": "api", "estado": "completada", "intentos": 2})
        wj(os.path.join(pd, "informes", "T001.1.raw.json"), {"duracion_s": 10, "salida_json": {"total_cost_usd": 0.1}})
        wj(os.path.join(pd, "informes", "T001.2.raw.json"), {"duracion_s": 20, "salida_json": {"total_cost_usd": 0.25}})

    def test_registro_de_plan_con_gasto_por_tarea_e_intento_y_ramas(self):
        self.plan("P1", 0.35, ago(1))
        r = ledger.snapshot_plan("P1")
        self.assertEqual((r["gasto_usd"], r["componentes"], r["ramas"]["api"]["decision"]), (0.35, ["api"], "merge"))
        t = r["tareas"][0]
        self.assertEqual((t["gasto_usd"], [i["gasto_usd"] for i in t["intentos"]]), (0.35, [0.1, 0.25]))

    def test_retencion_conserva_apuntes_y_purga_detalle(self):
        self.plan("P1", 0.35, ago(200))
        self.plan("P2", 0.5, ago(2))
        ledger.snapshot_plan("P1"); ledger.snapshot_plan("P2")
        wj(ledger.session_file("viejo"), {"schema_version": 1, "session_id": "viejo", "started": ago(300), "ended": ago(300), "component": "app", "plan": None,
           "tokens": {"input": 1, "output": 2, "cache_creation": 3, "cache_read": 4}, "cost_usd": 2.0, "cost_source": "statusline"})
        wj(ledger.session_file("nuevo"), {"schema_version": 1, "session_id": "nuevo", "started": ago(1), "ended": ago(1), "component": "app",
           "tokens": {"input": 1, "output": 2, "cache_creation": 3, "cache_read": 4}, "cost_usd": 1.0, "cost_source": "statusline"})
        self.assertEqual(ledger.purge(90, dry=True), {"planes": 1, "sesiones": 1})
        self.assertNotIn("detalle_purgado", json.load(open(os.path.join(ledger.plans_dir(), "P1.json"))))
        self.assertEqual(ledger.purge(90), {"planes": 1, "sesiones": 1})
        p1 = json.load(open(os.path.join(ledger.plans_dir(), "P1.json")))
        self.assertTrue(p1["detalle_purgado"])
        self.assertEqual((p1["gasto_usd"], p1["tareas"]), (0.35, [{"id": "T001", "repo": "api", "gasto_usd": 0.35}]))
        s = ledger.all_sessions()
        self.assertEqual((s["viejo"]["tokens"], s["viejo"]["cost_usd"], s["viejo"]["detalle_purgado"]), ({"total": 10}, 2.0, True))
        self.assertEqual(s["nuevo"]["tokens"]["output"], 2)
        self.assertEqual(ledger.purge(90), {"planes": 0, "sesiones": 0})                       # idempotente

    def costs(self, *args):
        r = subprocess.run([sys.executable, "-I", CONTROL, "costs", *args, "--json"], capture_output=True, text=True, env=os.environ, cwd=self.d, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_costs_filtros_y_agrupaciones(self):
        self.plan("P1", 0.35, "2026-10-01T10:00:00Z")
        self.plan("P2", 0.35, "2026-11-02T10:00:00Z")
        wj(ledger.session_file("a"), {"schema_version": 1, "session_id": "a", "started": "2026-10-01T09:00:00Z", "ended": "2026-10-01T10:00:00Z", "component": "app", "plan": "P1", "cost_usd": 2.0})
        wj(ledger.session_file("b"), {"schema_version": 1, "session_id": "b", "started": "2026-11-02T09:00:00Z", "ended": "2026-11-02T10:00:00Z", "component": "api", "plan": "P2", "cost_usd": 3.0})
        wj(ledger.session_file("c"), {"schema_version": 1, "session_id": "c", "started": "2026-11-02T11:00:00Z", "ended": "2026-11-02T12:00:00Z", "component": "app", "plan": None, "cost_usd": None})
        d = self.costs()
        self.assertEqual((d["total_usd"], d["workers_usd"], d["sesiones_usd"], d["sesiones_sin_coste"]), (5.7, 0.7, 5.0, 1))
        self.assertEqual(self.costs("--plan", "P1")["total_usd"], 2.35)
        self.assertEqual(self.costs("--component", "app")["total_usd"], 2.0)
        self.assertEqual(self.costs("--component", "API")["total_usd"], 3.7)          # sus dos planes (0,70) y la sesión b (3,00)
        self.assertEqual(self.costs("--since", "2026-11-01")["total_usd"], 3.35)
        self.assertEqual(self.costs("--session", "b")["total_usd"], 3.0)
        por_dia = {g["clave"]: (g["workers_usd"], g["sesiones_usd"]) for g in self.costs("--by", "day")["grupos"]}
        self.assertEqual(por_dia, {"2026-10-01": (0.35, 2.0), "2026-11-02": (0.35, 3.0)})
        por_comp = {g["clave"]: g["sesiones_usd"] for g in self.costs("--by", "component")["grupos"]}
        self.assertEqual(por_comp, {"api": 3.0, "app": 2.0})
        por_plan = {g["clave"]: round(g["workers_usd"] + g["sesiones_usd"], 2) for g in self.costs("--by", "plan")["grupos"]}
        self.assertEqual(por_plan, {"-": 0.0, "P1": 2.35, "P2": 3.35})
        r = subprocess.run([sys.executable, "-I", CONTROL, "costs", "--purge", "--dry-run"], capture_output=True, text=True, env=os.environ, cwd=self.d)
        self.assertIn("DRY|costs|retención", r.stdout)


if __name__ == "__main__":
    unittest.main()
