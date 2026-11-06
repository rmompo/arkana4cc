#!/usr/bin/env bash
# Pruebas de extremo a extremo del motor con el claude FALSO (sin API ni coste). Uso: bash tests/run-e2e.sh [-v|-q|<test>]
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI/e2e" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
