#!/usr/bin/env bash
# Ejecuta, una detrás de otra, todas las suites de tests de los plugins de Arkana y da un resumen.
#
# Descubre las suites en plugins/*/tests/ y lib/*/tests/: run-unit.sh y run-tests.sh (rápidas) y run-e2e.sh (lenta, siempre al final).
# La batería de contención (run-containment.sh) usa `claude` real y cuesta dinero: solo con --containment.
#
# Se niega a empezar si hay procesos de orquestación vivos (launch.py / watchdog.py): los tests de e2e y los de migración
# los detectan y se confundirían con un plan real en marcha.
#
# Uso: scripts/run-all-tests.sh [--quick] [--only <texto>] [--containment] [--list]
#   --quick         omite las suites e2e (≈3 min)
#   --only <texto>  solo las suites cuya ruta contiene <texto> (p. ej. --only workspace)
#   --containment   añade la batería de contención con claude real (≈0,1 USD)
#   --list          muestra las suites que ejecutaría y termina
# Salida: una línea ESTADO|suite|detalle por suite y, al final, RESUMEN|n FAIL|n OK. Logs completos en la carpeta indicada.
# Código de salida: 0 todo correcto, 1 alguna suite falla, 2 uso, 3 precondición (procesos vivos).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUICK=0; ONLY=""; CONTAINMENT=0; LIST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --only) ONLY="${2:-}"; [ -n "$ONLY" ] || { echo "FAIL|uso|--only necesita un texto" >&2; exit 2; }; shift 2 ;;
    --containment) CONTAINMENT=1; shift ;;
    --list) LIST=1; shift ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "FAIL|uso|opción desconocida: $1" >&2; exit 2 ;;
  esac
done

# Suites: rápidas primero (orden alfabético), luego e2e, luego contención.
fast=(); slow=(); contain=()
while IFS= read -r f; do
  rel="${f#"$ROOT"/}"
  [ -n "$ONLY" ] && [[ "$rel" != *"$ONLY"* ]] && continue
  case "$f" in
    */run-e2e.sh) slow+=("$f") ;;
    */run-containment.sh) contain+=("$f") ;;
    *) fast+=("$f") ;;
  esac
done < <(find "$ROOT/plugins" "$ROOT/lib" -type f \( -path '*/tests/run-*.sh' -o -path '*/tests/containment/run-containment.sh' \) | sort)

suites=("${fast[@]}")
[ "$QUICK" -eq 0 ] && suites+=("${slow[@]}")
[ "$CONTAINMENT" -eq 1 ] && suites+=("${contain[@]}")

if [ "$LIST" -eq 1 ]; then
  for s in "${suites[@]}"; do echo "${s#"$ROOT"/}"; done
  exit 0
fi
[ "${#suites[@]}" -gt 0 ] || { echo "FAIL|suites|no se encontró ninguna suite${ONLY:+ para «$ONLY»}" >&2; exit 2; }

if pgrep -f 'scripts/lib/(launch|watchdog)\.py' >/dev/null 2>&1; then
  echo "FAIL|precondicion|hay procesos de orquestación vivos (launch.py o watchdog.py); espera a que terminen o páralos" >&2
  exit 3
fi

OUT="$(mktemp -d "${TMPDIR:-/tmp}/arkana-tests-XXXXXX")"
before="$(git -C "$ROOT" diff --name-only 2>/dev/null | sort)"   # ficheros versionados ya modificados antes de empezar
export PYTHONDONTWRITEBYTECODE=1
# Guarda de aislamiento: foto (rama, HEAD y estado) de los repos REALES del workspace antes y después. Si una prueba se sale del laboratorio y toca un
# repo real (como pasó con un e2e que resolvió api por el manifiesto), la corrida falla y dice qué cambió. Solo lee; no restaura nada.
snapshot_real() {
  python3 -I - "$ROOT" <<'PY'
import json, os, subprocess, sys
root = sys.argv[1]
try:
    d = json.load(open(os.path.join(root, ".arkana", "core", "workspace.json"), encoding="utf-8"))
except (OSError, ValueError):
    sys.exit(0)
base = os.path.realpath(os.path.join(root, json.load(open(os.path.join(root, ".arkana", "arkana.json"))).get("root", "..")))
for c in d.get("components", []):
    p = os.path.realpath(os.path.join(base, c["path"]))
    if not os.path.isdir(p):
        continue
    def g(*a):
        r = subprocess.run(["git", "--no-optional-locks", "-C", p, *a], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else "?"
    print(f"{c['alias']}|{g('branch', '--show-current')}|{g('rev-parse', 'HEAD')}|{g('status', '--porcelain')!r}")
PY
}
real_before="$(snapshot_real)"
fail=0; ok=0; t0=$SECONDS
for s in "${suites[@]}"; do
  rel="${s#"$ROOT"/}"; name="${rel#plugins/}"; name="${name%/tests/*}/$(basename "${s%.sh}" | sed 's/^run-//')"
  log="$OUT/$(echo "$name" | tr '/' '_').log"
  s0=$SECONDS
  bash "$s" -q > "$log" 2>&1; rc=$?
  ran="$(grep -E '^Ran [0-9]+ tests?' "$log" | tail -1 | sed -E 's/^Ran ([0-9]+) tests? in ([0-9.]+)s.*/\1 tests en \2 s/')"
  if [ "$rc" -eq 0 ]; then
    ok=$((ok+1)); echo "OK|$name|${ran:-sin recuento} (${SECONDS}s acumulados)"
  else
    fail=$((fail+1)); echo "FAIL|$name|rc=$rc; ${ran:-sin recuento}; log: $log"
    grep -E '^(ERROR|FAIL):' "$log" | head -5 | sed 's/^/        /'
  fi
done
# Aviso de higiene: ¿las pruebas dejaron modificado algún fichero versionado? (no se restaura nada: podría ser trabajo real)
after="$(git -C "$ROOT" diff --name-only 2>/dev/null | sort)"
nuevos="$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | sed '/^$/d')"
[ -n "$nuevos" ] && echo "WARN|higiene|las pruebas modificaron ficheros versionados: $(echo "$nuevos" | tr '\n' ' ')"
real_after="$(snapshot_real)"
if [ "$real_before" != "$real_after" ]; then
  echo "FAIL|aislamiento|las pruebas cambiaron un repo real del workspace (rama, HEAD o ficheros):"
  diff <(printf '%s\n' "$real_before") <(printf '%s\n' "$real_after") | grep '^[<>]' | sed 's/^/        /'
  fail=$((fail+1))
fi
echo "RESUMEN|$fail FAIL|$ok OK ($((SECONDS - t0)) s en total; logs en $OUT)"
[ "$fail" -eq 0 ]
