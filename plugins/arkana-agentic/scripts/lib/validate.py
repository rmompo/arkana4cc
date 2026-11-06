#!/usr/bin/env python3
"""Validador minimo de esquemas JSON (solo biblioteca estandar de Python).

Soporta: type, enum, const, required, properties, additionalProperties (bool o esquema), items, minItems,
maxItems, minLength, maxLength, minimum, maximum, pattern, anyOf. No hay jsonschema en este contenedor.

Uso:  validate.py <esquema.json> <instancia.json | ->      (sale con 0 si es valido, 1 si no, 2 por uso)
"""
import json
import re
import sys


def _type_ok(v, t):
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "null":
        return v is None
    return False


def check_schema(valor, esquema, ruta="$"):
    """Devuelve la lista de errores (vacia si es valido)."""
    errs = []
    t = esquema.get("type")
    if t is not None:
        tipos = t if isinstance(t, list) else [t]
        if not any(_type_ok(valor, x) for x in tipos):
            return [f"{ruta}: tipo {type(valor).__name__} no permitido (esperado {'|'.join(tipos)})"]
    if "enum" in esquema and valor not in esquema["enum"]:
        errs.append(f"{ruta}: {valor!r} no esta entre {esquema['enum']}")
    if "const" in esquema and valor != esquema["const"]:
        errs.append(f"{ruta}: debe ser {esquema['const']!r}")
    if "anyOf" in esquema and not any(not check_schema(valor, s, ruta) for s in esquema["anyOf"]):
        errs.append(f"{ruta}: no cumple ninguna de las alternativas")
    if isinstance(valor, str):
        if "minLength" in esquema and len(valor) < esquema["minLength"]:
            errs.append(f"{ruta}: longitud {len(valor)} menor que {esquema['minLength']}")
        if "maxLength" in esquema and len(valor) > esquema["maxLength"]:
            errs.append(f"{ruta}: longitud {len(valor)} mayor que {esquema['maxLength']}")
        if "pattern" in esquema and not re.search(esquema["pattern"], valor):
            errs.append(f"{ruta}: {valor!r} no cumple el patron {esquema['pattern']}")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if "minimum" in esquema and valor < esquema["minimum"]:
            errs.append(f"{ruta}: {valor} menor que {esquema['minimum']}")
        if "maximum" in esquema and valor > esquema["maximum"]:
            errs.append(f"{ruta}: {valor} mayor que {esquema['maximum']}")
    if isinstance(valor, list):
        if "minItems" in esquema and len(valor) < esquema["minItems"]:
            errs.append(f"{ruta}: {len(valor)} elementos, minimo {esquema['minItems']}")
        if "maxItems" in esquema and len(valor) > esquema["maxItems"]:
            errs.append(f"{ruta}: {len(valor)} elementos, maximo {esquema['maxItems']}")
        if isinstance(esquema.get("items"), dict):
            for i, el in enumerate(valor):
                errs += check_schema(el, esquema["items"], f"{ruta}[{i}]")
    if isinstance(valor, dict):
        for k in esquema.get("required", []):
            if k not in valor:
                errs.append(f"{ruta}: falta la clave obligatoria '{k}'")
        props = esquema.get("properties", {})
        extra = esquema.get("additionalProperties", True)
        for k, v in valor.items():
            if k in props:
                errs += check_schema(v, props[k], f"{ruta}.{k}")
            elif extra is False:
                errs.append(f"{ruta}: clave no permitida '{k}'")
            elif isinstance(extra, dict):
                errs += check_schema(v, extra, f"{ruta}.{k}")
    return errs


def main(argv):
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        esquema = json.load(f)
    inst = json.load(sys.stdin if argv[2] == "-" else open(argv[2], encoding="utf-8"))
    errs = check_schema(inst, esquema)
    for e in errs:
        print(f"FAIL|esquema|{e}")
    if not errs:
        print("OK|esquema|valido")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
