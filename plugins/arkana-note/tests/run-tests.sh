#!/usr/bin/env bash
# Pruebas de arkana-note (add, list, modify, delete lógico, validate, fix y rename). Sin red ni API.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
