# Especificación del plugin: arkana-statusline

> **Estado:** `beta` | **Versión:** `1.1.14`

---

## Descripción general

Statusline de Arkana en dos líneas: ARKANA y los componentes con su rama y estado git, y el plan activo, coste y uso de Claude; se adapta al ancho y escribe el coste real de la sesión

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 5 | Diagnóstico de solo lectura de la statusline - python3 y git, copia instalada al día, `statusLine` activa y nuestra, otros plugins de statusline que podrían pisarla y prueba de humo. Nunca corrige. Acepta --json. |
| `fix` | 6 | Reinstala la copia de la statusline si está desactualizada y activa `statusLine` si no hay ninguna. Nunca sustituye la de otro (eso es install --replace). Con copia .bak. Acepta --dry-run y --json. |
| `install` | 7 | Instala la statusline de Arkana en ~/.claude/arkana-statusline/ (statusline.sh, statusline.py y arkana_core) y activa `statusLine` en ~/.claude/settings.json. Una statusLine ajena solo se sustituye con --replace (copia de los ajustes en bak/). Acepta --dry-run y --json. |
| `refresh` | 8 | Hace `git fetch` de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) de la statusline esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.14 | Nucleo 1.11.0 vendorizado: LAYOUT_KNOWN 8 |
| 1.1.13 | Nucleo vendorizado: registro de workspaces en ~/.arkana/workspaces.json |
| 1.1.12 | Nucleo 1.10.0 vendorizado: LAYOUT_KNOWN 7 |
| 1.1.11 | Nucleo 1.9.0 vendorizado: nombre-modulo compartido, resolucion por alias, carpeta o modulo y alias mostrados en mayusculas |
| 1.1.10 | Componente de referencia: oculto por defecto, muestra el ref y marca ≠ref si HEAD se mueve |
| 1.1.9 | watch por componente, el componente actual oculto sigue viéndose y mensaje de esquema desconocido (núcleo 1.8.0) |
| 1.1.8 | refresh: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 1.1.7 | install: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 1.1.6 | fix: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 1.1.5 | check: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 1.1.4 | refresh: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.3 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.2 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.1 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
