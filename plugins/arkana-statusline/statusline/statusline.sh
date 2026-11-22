#!/usr/bin/env bash
# Statusline de Arkana (a nivel de usuario): lee el JSON de Claude Code por stdin y delega en dispatch.py (hermano de este fichero), que decide qué statusline se ve.
exec python3 -I "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/dispatch.py"
