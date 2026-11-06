#!/usr/bin/env bash
# Núcleo de Arkana para bash: localizador del workspace, manifiesto y ayudas de salida. Se carga con `source`. Requiere jq.
# Misma resolución que arkana_core/locate.py y manifest.py (hay un test de paridad):
#   ac_home [dir]            carpeta del repo de Arkana: $ARKANA_HOME, un ancestro con .arkana/arkana.json, o el registro
#                            ~/.arkana-workspaces.json; sale con 1 (sin imprimir nada) si no hay workspace
#   ac_state <home>          <home>/.arkana
#   ac_root <home>           raíz del workspace (`root` de arkana.json, por defecto ..)
#   ac_canon <alias>         alias canónico (minúsculas; el id histórico `shared` es `arkana`)
#   ac_aliases <home>        arkana y los componentes, uno por línea
#   ac_path <home> <alias>   ruta absoluta de una pieza (local.json manda sobre el manifiesto)
#   ac_field <home> <alias> <campo>   campo del bloque de una pieza (p. ej. type, remote_host)
#   ac_emit ESTADO ID detalle         línea `ESTADO|ID|detalle`
AC_STATE_DIR=".arkana"

ac__registry() { printf '%s/.arkana-workspaces.json' "$HOME"; }
ac__is_home() { [ -f "$1/$AC_STATE_DIR/arkana.json" ]; }

ac_home() {
  local start d cur out a
  if [ -n "${ARKANA_HOME:-}" ] && [ -d "$ARKANA_HOME" ]; then (cd "$ARKANA_HOME" && pwd -P); return 0; fi
  start="${1:-$PWD}"
  d="$(cd "$start" 2>/dev/null && pwd -P)" || return 1
  cur="$d"
  while :; do
    if ac__is_home "$cur"; then printf '%s\n' "$cur"; return 0; fi
    [ "$cur" = "/" ] && break
    cur="$(dirname "$cur")"
  done
  [ -f "$(ac__registry)" ] || return 1
  out="$(jq -r --arg d "$d" '.workspaces[]? | select(.root != null and .arkana != null)
        | select(.root as $r | $d == $r or ($d | startswith($r + "/"))) | .arkana' "$(ac__registry)" 2>/dev/null)"
  while IFS= read -r a; do
    if [ -n "$a" ] && ac__is_home "$a"; then (cd "$a" && pwd -P); return 0; fi
  done <<< "$out"
  return 1
}

ac_state() { printf '%s/%s\n' "$1" "$AC_STATE_DIR"; }

ac_root() {
  local home="$1" r
  r="$(jq -r '.root // ".."' "$(ac_state "$home")/arkana.json" 2>/dev/null)"; [ -n "$r" ] || r=".."
  case "$r" in /*) ;; *) r="$home/$r" ;; esac
  (cd "$r" 2>/dev/null && pwd -P) || printf '%s\n' "$r"
}

ac_canon() { local a="${1,,}"; [ "$a" = "shared" ] && a="arkana"; printf '%s\n' "$a"; }

ac_aliases() { jq -r '["arkana"] + [.components[]?.alias] | .[]' "$(ac_state "$1")/core/workspace.json"; }

ac_path() {
  local home="$1" a st ov rel
  a="$(ac_canon "$2")"; st="$(ac_state "$home")"
  ov="$(jq -r --arg a "$a" '.paths[$a] // empty' "$st/arkana-workspace/local.json" 2>/dev/null)"
  if [ -n "$ov" ]; then
    case "$ov" in "~"*) printf '%s\n' "$HOME${ov#\~}" ;; *) printf '%s\n' "$ov" ;; esac
    return 0
  fi
  rel="$(jq -r --arg a "$a" 'if $a == "arkana" then .arkana.path else (.components[]? | select(.alias == $a) | .path) end // empty' \
        "$st/core/workspace.json" 2>/dev/null)"
  [ -n "$rel" ] || return 1
  printf '%s/%s\n' "$(ac_root "$home")" "$rel"
}

ac_field() {
  local home="$1" a f; a="$(ac_canon "$2")"; f="$3"
  jq -r --arg a "$a" --arg f "$f" '(if $a == "arkana" then .arkana else (.components[]? | select(.alias == $a)) end) | .[$f] // empty' \
    "$(ac_state "$home")/core/workspace.json" 2>/dev/null
}

ac_emit() { printf '%s|%s|%s\n' "$1" "$2" "${3:-}"; }
