"""Directrices de Arkana para la sesión de una pieza (ARKANA o un componente).

No viven en ficheros de los repos de trabajo: las compone el hook de sesión (`SessionStart`, también tras `compact`) y las inyecta en el contexto del
modelo. Se forman con la convención de commits de la pieza (manifiesto), las reglas comunes y, si existen, las notas locales de la pieza.

`ARKANA.local.md` (en la raíz del repo de la pieza) es opcional y local: notas propias de esa copia de trabajo. No se versiona (se excluye con
`.git/info/exclude`, ver `excludes.py`) y se inyecta tal cual, con un tope de tamaño.
"""
import os

import commits

LOCAL_NOTES = "ARKANA.local.md"
MAX_NOTES = 8000
RULES = """## Reglas comunes de Arkana

- **No instales herramientas ni paquetes** (`sudo`, `apt`, `npm -g`, `pip`…), aunque falten. Pide al usuario que las instale: di cuál, para qué y el comando exacto, y espera.
- No leas ni muestres credenciales, `.env` ni tokens.
- Los metadatos de Arkana están en `.arkana/` del repo de ARKANA: no los edites a mano."""


def notes_path(ws, alias):
    return os.path.join(ws.path(alias), LOCAL_NOTES)


def read_notes(ws, alias):
    """Contenido de `ARKANA.local.md` de la pieza (recortado a MAX_NOTES), o None."""
    try:
        with open(notes_path(ws, alias), encoding="utf-8") as f:
            t = f.read(MAX_NOTES + 1).strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not t:
        return None
    return t[:MAX_NOTES] + ("\n\n(notas recortadas)" if len(t) > MAX_NOTES else "")


def render(ws, alias):
    """Texto completo de las directrices de `alias`."""
    from arkana_core import manifest
    parts = [f"[Arkana] Directrices para {manifest.display(alias)}", RULES]
    try:
        parts.append(commits.body(alias, commits.fmt_of(ws, alias), commits.scope_of(ws, alias)))
    except ValueError as e:
        parts.append(f"## Convención de commits\n\n(sin convención: {e})")
    notes = read_notes(ws, alias)
    if notes:
        parts.append(f"## Notas locales de este repo ({LOCAL_NOTES})\n\n{notes}")
    return "\n\n".join(parts) + "\n"
