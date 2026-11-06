#!/usr/bin/env bash
# Pruebas unitarias de arkana-agentic (sin API, sin red). Uso: bash tests/run-unit.sh
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI/unit" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
