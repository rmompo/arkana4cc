#!/usr/bin/env bash
# Batería de CONTENCIÓN con `claude` REAL: lanza workers de verdad (a través del lanzador completo) con tareas adversarias y comprueba
# el EFECTO (canarios fuera del repo, .env, enlace simbólico, rutas protegidas, git, inyección, límites), no lo que el modelo diga.
# CUESTA DINERO: unos 0,3-0,6 USD con haiku (ARKANA_CONTAINMENT_MODEL; vacío = el modelo por defecto). Tope de seguridad:
# ARKANA_CONTAINMENT_MAX_USD (2,0 por defecto). Requiere el login real de claude (usa el HOME real; los secretos de prueba son canarios
# dentro de una carpeta temporal: nunca lee ni escribe credenciales reales).
# Uso: bash tests/containment/run-containment.sh [-v] [-k <patrón>]      Última línea: RESUMEN|contencion|...  (código 0 si todo OK)
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
SALIDA="$(mktemp)"
trap 'rm -f "$SALIDA"' EXIT
( cd "$AQUI" && python3 -I -m unittest discover -s . -p 'test_*.py' "${@:--v}" ) > "$SALIDA" 2>&1
rc=$?
cat "$SALIDA"
n="$(grep -oE '^Ran [0-9]+ tests?' "$SALIDA" | grep -oE '[0-9]+' | head -1)"
coste="$(grep -oE '^COSTE\|[0-9.]+' "$SALIDA" | tail -1 | cut -d'|' -f2)"
if [ "$rc" -eq 0 ]; then echo "RESUMEN|contencion|${n:-0} pruebas con claude real OK (coste ${coste:-?} USD)"
else echo "RESUMEN|contencion|FALLAN pruebas de contención (${n:-0} ejecutadas; coste ${coste:-?} USD): NO se orquesta hasta resolverlo"; fi
exit "$rc"
