#!/usr/bin/env bash
# Statusline de Arkana: lee el JSON de Claude Code por stdin y delega en statusline.py (hermano de este fichero).
exec python3 -I "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/statusline.py"
