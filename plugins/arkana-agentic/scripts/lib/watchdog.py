#!/usr/bin/env python3
"""Vigilante de un worker: tiempo maximo, parada forzosa (run/STOP-FORCE) y dead-man switch (si la sesion duena muere).

Lo arranca el lanzador, separado y sin terminal. Nunca localiza procesos por el texto de su linea de comandos:
usa el pid y el grupo de procesos guardados en run/worker.json.

Variables: ARKANA_AGENTIC_WATCH_INTERVAL (segundos entre comprobaciones, 5), ARKANA_AGENTIC_KILL_GRACE (SIGTERM -> SIGKILL, 10).
"""
import os
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import launch  # noqa: E402
import state  # noqa: E402


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def main():
    intervalo = float(os.environ.get("ARKANA_AGENTIC_WATCH_INTERVAL", "5"))
    gracia = float(os.environ.get("ARKANA_AGENTIC_KILL_GRACE", "10"))
    ruta = os.path.join(state.run_dir(), "worker.json")
    try:
        w = state.load_json(ruta)
    except (FileNotFoundError, ValueError):
        return 0
    inicio = w.get("inicio_ts", time.time())
    pidfile = os.path.join(state.run_dir(), "watchdog.pid")
    with open(pidfile, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    try:
        return _watch(w, ruta, inicio, intervalo, gracia)
    finally:
        try:
            os.unlink(pidfile)
        except FileNotFoundError:
            pass


def _watch(w, ruta, inicio, intervalo, gracia):
    while True:
        time.sleep(intervalo)
        try:
            actual = state.load_json(ruta)
        except (FileNotFoundError, ValueError):
            return 0
        if actual.get("pid") != w["pid"] or not group_alive(w["pgid"]):
            return 0
        motivo = None
        if os.path.exists(os.path.join(state.run_dir(), "STOP-FORCE")):
            motivo = "stop_force"
        elif time.time() - inicio > w.get("limite_s", 1e9):
            motivo = "tiempo_watchdog"
        elif w.get("owner_pid") and not launch.pid_alive(w["owner_pid"]):
            motivo = "dueno_muerto"
        if motivo:
            launch.kill_worker(w, motivo, gracia)
            time.sleep(max(intervalo, 0.5) * 2)
            lanzador = w.get("launcher_pid")
            if not lanzador or not launch.pid_alive(lanzador):   # el lanzador tambien cayo: transiciona el vigilante
                launch.cleanup_after_kill(w, motivo)
            return 0


if __name__ == "__main__":
    sys.exit(main())
