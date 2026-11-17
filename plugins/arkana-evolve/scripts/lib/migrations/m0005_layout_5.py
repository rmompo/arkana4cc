"""0005 · Layout 5: el manifiesto admite los campos de componente `mode`, `ref`, `watch` y `checks_skip` (esquema 2).

No cambia ningún dato: los campos nuevos son opcionales y un manifiesto de esquema 1 sigue siendo válido tal cual. La migración solo estampa `layout: 5` en el registro del
proyecto, que es la señal compartida de «este repo ya usa un manifiesto que las versiones anteriores del plugin no entienden». Las instalaciones nuevas que ven un layout
superior al que conocen avisan de que hay que actualizar el plugin (no de aplicar nada). El manifiesto local solo pasa a `schema: 2` cuando alguien guarda un campo nuevo.
"""
ID = "0005"
TITLE = "layout 5: campos mode, ref, watch y checks_skip del componente (solo sello)"
SCOPE = ("shared",)
LAYOUT = 5


def touches(ctx):
    return []                                  # el sello lo escribe el motor; la migración no toca ningún fichero


def detect(ctx):
    p = ctx.project()
    return isinstance(p, dict) and int(p.get("layout", 0) or 0) < LAYOUT


def apply(ctx, rep):
    rep.add("DRY" if ctx.dry else "OK", f"{ID}:layout", "el sello pasa a layout 5; no cambia ningún dato (los campos nuevos del componente son opcionales)")


def verify(ctx):
    return []
