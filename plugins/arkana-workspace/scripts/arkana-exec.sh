#!/usr/bin/env bash
# Ejecuta un comando con las credenciales de <home>/.arkana/.credentials en su entorno (sin imprimirlas ni dejarlas en argumentos).
# Uso: arkana-exec.sh [--keys A,B] -- <comando> [args…]
# Ejemplo: arkana-exec.sh -- mvn -s config/maven-settings.xml -B package   (el settings usa ${env.REGISTRY_USER})
# Las variables que ya estén definidas en el entorno no se pisan. Nada se escribe en disco.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --keys) KEYS="$2"; shift 2 ;;
    --) shift; break ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) break ;;
  esac
done
[ $# -gt 0 ] || { echo "FAIL|uso|falta el comando: arkana-exec.sh -- <comando>" >&2; exit 2; }
export PYTHONDONTWRITEBYTECODE=1
exports="$(python3 -I - "$HERE/_core" "$HERE/lib" "$KEYS" <<'PY'
import os, shlex, sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from arkana_core import locate
import credentials
home = locate.find_home()
if home:
    keys = [k for k in sys.argv[3].split(",") if k] or None
    for k, v in credentials.environ(home, keys).items():
        print(f"export {k}={shlex.quote(v)}")
PY
)"
eval "$exports"
exec "$@"
