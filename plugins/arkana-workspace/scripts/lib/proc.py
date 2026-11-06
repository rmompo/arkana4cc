"""Ejecución de comandos externos con tiempo límite fiable: al vencer se mata el grupo de procesos entero.

`subprocess.run(timeout=…)` solo mata al hijo directo; `npm` o `git` (con git-remote-https) dejan nietos con las tuberías abiertas y
`communicate()` se queda esperando para siempre. Aquí el comando va en su propia sesión y se mata el grupo.
"""
import os
import signal
import subprocess


def run(cmd, timeout=10, env=None, cwd=None):
    """(rc, salida mezclada). rc 124 si vence el tiempo, 127 si no se puede ejecutar. Nunca lee de stdin."""
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             env=env, cwd=cwd, start_new_session=True)
    except OSError:
        return 127, ""
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, (out or "").strip()
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.communicate(timeout=2)
        except Exception:
            pass
        return 124, ""
