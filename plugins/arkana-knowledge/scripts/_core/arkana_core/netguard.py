"""Contención de red: ningún comando externo puede dejar una sesión esperando para siempre.

Origen: con la VPN caída, la resolución DNS del contenedor (resolvedor de Docker) no falla rápido y `git fetch` se queda esperando.
`subprocess.run(timeout=…)` no basta: solo mata al hijo directo y `git-remote-https` deja nietos con las tuberías abiertas, así que
`communicate()` no vuelve. Aquí cada comando va en su propia sesión y, al vencer el tiempo, se mata el grupo entero.

  run(cmd, timeout, ...)        -> CompletedProcess; returncode 124 si vence el tiempo, 127 si no se puede ejecutar
  git(repo, *args, net=False)   -> igual, con entorno de git sin preguntas ni esperas; `net=True` pasa por el cortacircuitos
  preflight(host, timeout=3)    -> (ok, detalle): ¿resuelve el DNS? (la VPN suele ser la causa de que no)
  breaker_open() / trip()       -> cortacircuitos compartido entre procesos: tras un fallo de red, las siguientes operaciones de red
                                   fallan al instante (rc 125) durante BREAKER_TTL segundos en vez de esperar su tiempo cada una

Solo biblioteca estándar. Nunca lee de stdin.
"""
import json
import os
import signal
import subprocess
import tempfile
import time

TIMEOUT_NET = 20        # git fetch/push/ls-remote
TIMEOUT_LOCAL = 10      # git local (status, rev-parse, …)
BREAKER_TTL = 60        # segundos que el cortacircuitos rechaza operaciones de red tras un fallo
RC_TIMEOUT, RC_NOEXEC, RC_OPEN = 124, 127, 125

NO_NETWORK = "red no disponible (¿VPN caída?): operación de red omitida"


def run(cmd, timeout=TIMEOUT_LOCAL, env=None, cwd=None, input=None):
    """subprocess.CompletedProcess con stdout/stderr como texto. Mata el grupo de procesos al vencer `timeout`."""
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, env=env, cwd=cwd, start_new_session=True)
    except OSError as e:
        return subprocess.CompletedProcess(cmd, RC_NOEXEC, "", str(e))
    try:
        out, err = p.communicate(input, timeout=timeout)
        return subprocess.CompletedProcess(cmd, p.returncode, out or "", err or "")
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            p.communicate(timeout=2)
        except Exception:
            pass
        return subprocess.CompletedProcess(cmd, RC_TIMEOUT, "", f"timed out after {timeout}s")


def git_env(base=None):
    """Entorno de git que no pregunta y se rinde si la conexión va a menos de 1 KB/s durante 15 s (git no tiene tiempo de conexión)."""
    e = dict(os.environ if base is None else base)
    e.update(GIT_TERMINAL_PROMPT="0", GIT_PAGER="cat", LC_ALL="C", GIT_HTTP_LOW_SPEED_LIMIT="1000", GIT_HTTP_LOW_SPEED_TIME="15")
    return e


# ---------- cortacircuitos ----------
def _breaker_file():
    return os.environ.get("ARKANA_NET_BREAKER_FILE") or os.path.join(tempfile.gettempdir(), f"arkana-net-breaker-{os.getuid()}.json")


def breaker_open(now=None):
    """True si hay un fallo de red reciente (menos de BREAKER_TTL s)."""
    try:
        with open(_breaker_file()) as f:
            until = float(json.load(f).get("until", 0))
    except (OSError, ValueError, TypeError):
        return False
    return (time.time() if now is None else now) < until


def trip(reason="timeout", ttl=BREAKER_TTL):
    try:
        with open(_breaker_file(), "w") as f:
            json.dump({"until": time.time() + ttl, "reason": reason}, f)
    except OSError:
        pass


def reset():
    try:
        os.remove(_breaker_file())
    except OSError:
        pass


def git(repo, *args, net=False, timeout=None, input=None):
    """git -C repo … con tiempo límite. Con net=True: respeta el cortacircuitos y lo dispara si vence el tiempo."""
    if net and breaker_open():
        return subprocess.CompletedProcess(["git", *args], RC_OPEN, "", NO_NETWORK)
    p = run(["git", "-C", repo, *args], timeout or (TIMEOUT_NET if net else TIMEOUT_LOCAL), git_env(), input=input)
    if net and p.returncode == RC_TIMEOUT:
        trip("git " + (args[0] if args else ""))
    return p


# ---------- preflight de VPN/DNS ----------
def preflight(host, timeout=3):
    """(ok, detalle). `getent hosts` bajo tiempo límite: si no resuelve en `timeout` s, la VPN (o el DNS) no está disponible.
    Dispara el cortacircuitos si falla; si resuelve, lo restablece."""
    if not host:
        return True, "sin host que comprobar"
    p = run(["getent", "hosts", host], timeout)
    if p.returncode == 0:
        reset()
        return True, f"{host} resuelve"
    trip("dns " + host)
    return False, f"{host} no resuelve ({'tiempo agotado' if p.returncode == RC_TIMEOUT else 'sin respuesta'}): ¿VPN caída?"


def host_of(url):
    """Host de una URL de remoto (https://u@h/x, git@h:x, ssh://h/x)."""
    import re
    u = url.split("://", 1)[1] if "://" in url else url
    u = u.split("@", 1)[-1]
    return re.split(r"[/:]", u, maxsplit=1)[0]
