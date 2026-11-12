#!/usr/bin/env bash
# Pruebas de arkana-knowledge (notas con UUID, documentos, ingesta, validación, hooks). Sin red ni API. Sin red ni API.
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
cd "$AQUI" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" 2>&1
