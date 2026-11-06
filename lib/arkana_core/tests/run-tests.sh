#!/usr/bin/env bash
# Pruebas del núcleo de Arkana (shared/lib/arkana_core). Sin red y sin tocar nada real. Uso: bash tests/run-tests.sh [-v|-q] [-k <patron>]
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
