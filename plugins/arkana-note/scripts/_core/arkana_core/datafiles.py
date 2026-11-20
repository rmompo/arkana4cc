"""Ficheros de datos de Arkana: clases de portabilidad y escritura atómica."""
import json
import os
import tempfile

# Clase de cada dato bajo .arkana/ (la declara cada plugin en su arkana-plugin.json)
CLASS_CONFIG = "config"   # portable: se exporta siempre
CLASS_DATA = "data"       # se exporta solo con --include-data
CLASS_LOCAL = "local"     # propio de esta instalación: nunca se exporta
CLASS_SECRET = "secret"   # solo se guarda la referencia; el valor nunca sale de .credentials
CLASSES = (CLASS_CONFIG, CLASS_DATA, CLASS_LOCAL, CLASS_SECRET)


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def atomic_write(path, data, mode=None):
    """Escribe `data` (str o bytes) en `path` de forma atómica: fichero temporal en la misma carpeta y `os.replace`.

    `mode` (p. ej. 0o600) se aplica al fichero temporal antes de moverlo, para que nunca exista con permisos más amplios.
    """
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=d)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_json(path, obj, mode=None):
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n", mode=mode)
