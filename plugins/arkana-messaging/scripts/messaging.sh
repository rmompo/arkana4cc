#!/usr/bin/env bash
# Mensajes entre componentes (almacén local en .arkana/arkana-messaging/state/; sin git ni red).
# Uso: messaging.sh <put|get|delete|sync|reconcile|adopt|install|check|fix> [opciones]   (ver --help)
# Quién actúa lo decide el cwd y el manifiesto.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "${1:-}" in
  install|check|fix) exec python3 -I "$HERE/lib/ops.py" "$@" ;;
  *) exec python3 -I "$HERE/lib/messages.py" "$@" ;;
esac
