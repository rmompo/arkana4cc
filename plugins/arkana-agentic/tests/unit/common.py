import json
import os
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(AQUI, "..", ".."))
sys.path.insert(0, os.path.join(PLUGIN, "scripts", "lib"))
sys.dont_write_bytecode = True


COMPONENTES = [
    ("app", "node", "app", {"commit_format": "ia4d"}),
    ("api", "node", "api", {"commit_format": "ia4d"}),                       # node: las pruebas e2e esperan el adaptador node (package.json protegido, npm test)
    ("app-web", "node", "app/src/web", {"commit_format": "ia4d", "git": {"email_domains": ["example.org", "ext.example.org"]}}),
    ("app-ui", "node", "app/src/ui", {"commit_format": "conventional", "git": {"email_domains": ["example.org", "ext.example.org"]}}),
    ("docs", "docs", "docs", {}),
    ("specs", "docs", "specs", {}),
]


def make_workspace(raiz):
    """Escribe un manifiesto de pruebas: <raiz>/shared/.arkana/{arkana.json, core/workspace.json}. Devuelve {alias: ruta absoluta} (`arkana` y `shared` = la carpeta de Arkana)."""
    sh = os.path.join(raiz, "shared")
    os.makedirs(os.path.join(sh, ".arkana", "core"), exist_ok=True)
    with open(os.path.join(sh, ".arkana", "arkana.json"), "w", encoding="utf-8") as f:
        json.dump({"schema_version": 1, "workspace": {"name": "lab"}, "root": ".."}, f)
    comps = [dict({"alias": a, "type": t, "path": p}, **extra) for a, t, p, extra in COMPONENTES]
    with open(os.path.join(sh, ".arkana", "core", "workspace.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": 1, "workspace": {"name": "lab"}, "arkana": {"alias": "ARKANA", "path": "shared", "commit_format": "ia4d", "branches": {"main": "main", "develop": "develop"}},
                   "components": comps}, f, indent=2)
    rutas = {"arkana": sh, "shared": sh}
    rutas.update({a: os.path.join(raiz, p) for a, _, p, _ in COMPONENTES})
    return rutas


def _workspace_por_defecto():
    """Los tests que no montan su propio workspace usan este (temporal), para no depender de ninguno real en la máquina."""
    import atexit
    import shutil
    raiz = tempfile.mkdtemp(prefix="arkana-unit-")
    atexit.register(shutil.rmtree, raiz, True)
    return make_workspace(raiz)["arkana"]


if not os.environ.get("ARKANA_HOME"):
    os.environ["ARKANA_HOME"] = _workspace_por_defecto()


def esquema(nombre):
    with open(os.path.join(PLUGIN, "schemas", f"{nombre}.schema.json"), encoding="utf-8") as f:
        return json.load(f)


def informe_ok():
    return {"estado": "hecha", "resumen": "ok", "criterios": [{"id": "C1", "cumplido": True, "evidencia": "src/a.ts"}],
            "cambios": [{"ruta": "src/a.ts", "tipo": "modificado", "nota": "x"}], "hallazgos": [],
            "necesita": [], "siguiente_sugerido": ""}


def plan_ok(pid="P2610301830-abcd", estado="en_ejecucion", **extra):
    p = {"id": pid, "version": 1, "asunto": "Validacion de NIF", "peticion": "texto", "estado": estado,
         "tareas": ["T001", "T002"], "politica": {"total_budget_usd": 5}, "contadores": {"gasto_usd": 1.4234},
         "gate": None, "aprobado": None, "historial": []}
    p.update(extra)
    return p


def tarea_ok(tid="T001", pid="P2610301830-abcd", estado="pendiente", **extra):
    t = {"id": tid, "plan": pid, "version": 1, "asunto": "Anadir validacion de NIF en el formulario de alta",
         "repo": "app", "tipo": "tarea", "perfil": "edicion", "objetivo": "validar NIF",
         "instrucciones": ["1. editar"], "criterios_aceptacion": [{"id": "C1", "descripcion": "valida"}],
         "estado": estado, "intentos": 0, "historial": []}
    t.update(extra)
    return t


class Entorno:
    """Directorio de ejecucion temporal (ARKANA_AGENTIC_DIR) para no tocar ~/.claude."""
    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.prev = os.environ.get("ARKANA_AGENTIC_DIR")
        os.environ["ARKANA_AGENTIC_DIR"] = self.dir.name
        return self.dir.name

    def __exit__(self, *a):
        if self.prev is None:
            os.environ.pop("ARKANA_AGENTIC_DIR", None)
        else:
            os.environ["ARKANA_AGENTIC_DIR"] = self.prev
        self.dir.cleanup()


def leer_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def leer_lineas(ruta):
    with open(ruta, encoding="utf-8") as f:
        return f.read().splitlines()
