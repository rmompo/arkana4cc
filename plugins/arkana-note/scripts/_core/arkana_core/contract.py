"""Contrato de plugin: `arkana-plugin.json` en la raíz de cada plugin.

Declara qué ofrece (provides), qué necesita (requires), qué datos guarda bajo `.arkana/` y de qué clase es cada uno
(config, data, local, secret) y qué hooks lleva. Con eso exportar, importar, `handover` y el `check` agregado no necesitan
conocer los detalles internos de ningún plugin.
"""
import json
import os

from . import datafiles, manifest, schema as _schema

CONTRACT_FILE = "arkana-plugin.json"


class ContractError(Exception):
    pass


def validate(data):
    errs = _schema.check_schema(data, manifest.load_schema("arkana-plugin.schema.json"))
    for d in (data.get("data") or []) if isinstance(data, dict) else []:
        p = d.get("path", "")
        if os.path.isabs(p) or ".." in p.split("/"):
            errs.append(f"data: la ruta {p!r} debe ser relativa a .arkana y no salir de ella")
        if d.get("class") not in datafiles.CLASSES:
            errs.append(f"data: clase desconocida en {p!r}")
    return errs


def load(plugin_dir):
    path = os.path.join(plugin_dir, CONTRACT_FILE)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        raise ContractError(f"falta {CONTRACT_FILE} en {plugin_dir}")
    except ValueError as e:
        raise ContractError(f"{path} no es JSON válido: {e}")
    errs = validate(data)
    if errs:
        raise ContractError("; ".join(errs[:5]))
    return data
