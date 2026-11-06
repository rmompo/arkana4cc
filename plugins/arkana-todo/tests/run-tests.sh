#!/usr/bin/env bash
# Pruebas de arkana-todo (add, list, done/reopen, modify, delete lógico, validate y fix). Sin red ni API.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
