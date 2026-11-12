#!/usr/bin/env bash
# Pruebas de arkana-evolve (motor de migraciones y migración 0001). Sin red ni API; repos git temporales.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
