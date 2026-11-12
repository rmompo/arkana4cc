# Especificación del plugin: arkana-statusline

> **Estado:** `beta` | **Versión:** `1.1.0`

---

## Descripción general

Statusline de Arkana en dos líneas: ARKANA y los componentes con su rama y estado git, y el plan activo, coste y uso de Claude; se adapta al ancho y escribe el coste real de la sesión

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 0 | Diagnóstico de solo lectura de la statusline - python3 y git, copia instalada al día, `statusLine` activa y nuestra, otros plugins de statusline que podrían pisarla y prueba de humo. Nunca corrige. Acepta --json. |
| `fix` | 0 | Reinstala la copia de la statusline si está desactualizada y activa `statusLine` si no hay ninguna. Nunca sustituye la de otro (eso es install --replace). Con copia .bak. Acepta --dry-run y --json. |
| `install` | 0 | Instala la statusline de Arkana en ~/.claude/arkana-statusline/ (statusline.sh, statusline.py y arkana_core) y activa `statusLine` en ~/.claude/settings.json. Una statusLine ajena solo se sustituye con --replace (copia de los ajustes en bak/). Acepta --dry-run y --json. |
| `refresh` | 0 | Hace `git fetch` de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) de la statusline esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
