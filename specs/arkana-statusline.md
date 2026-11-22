# Especificación del plugin: arkana-statusline

> **Estado:** `beta` | **Versión:** `1.3.1`

---

## Descripción general

Statusline de Arkana en dos líneas, solo para workspaces de Arkana: ARKANA y los componentes con su rama y estado git, y el plan activo, coste y uso de Claude. Un despachador de usuario elige entre la de Arkana, la de plugin4cc y otra según la carpeta; escribe el coste real de la sesión

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 7 | Diagnóstico de solo lectura de la statusline - python3 y git, copia instalada al día, `statusLine` de usuario del despachador, proveedores, elección por componente, otros plugins de statusline y prueba de humo. Nunca corrige. Acepta --home y --json. |
| `choose` | 1 | Elige qué statusline se ve al abrir Claude Code en un componente gobernado por ARKANA - la de Arkana, la que ya tenga configurada (proveedores) o volver a preguntar. En la carpeta de ARKANA siempre se ve la de Arkana. Acepta --dry-run, --home y --json. |
| `fix` | 8 | Reinstala la copia del despachador de la statusline si está desactualizada, activa `statusLine` si no hay ninguna y, si otra herramienta la pisó tras instalar Arkana, la recupera dejando a la otra como proveedor. Sin instalación previa no sustituye la de otro (eso es install). Con copia .bak. Acepta --dry-run y --json. |
| `install` | 9 | Instala el despachador de la statusline de Arkana en ~/.claude/arkana-statusline/ (statusline.sh, dispatch.py, statusline.py y arkana_core) y lo activa como `statusLine` de usuario; en ARKANA se ve la de Arkana y en otros sitios la que hubiera. Con Arkana instalada, Arkana gobierna las statuslines: ocupa el hueco y la statusLine ajena que hubiera pasa a ser un proveedor (copia de los ajustes en bak/). Acepta --dry-run y --json. |
| `provider` | 1 | Gestiona los proveedores de la statusline (las otras statuslines que se ven fuera de ARKANA o cuando no se elige la de Arkana) y la recuperación automática del hueco - list, add, remove y auto on|off. Un proveedor es un comando con prioridad (plugin4cc 20, otra 30; gana el menor). Acepta --dry-run y --json. |
| `refresh` | 8 | Hace `git fetch` de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) de la statusline esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json. |
| `uninstall` | 1 | Retira el despachador de la statusline de Arkana - devuelve la `statusLine` de usuario al proveedor de mayor prioridad (o la quita si no hay) y borra la copia de ~/.claude/arkana-statusline. Hazlo antes de desinstalar el plugin. Acepta --dry-run y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.3.1 | statusline: el esfuerzo del modelo como letra (l m h H M = low, medium, high, xhigh, max) en lugar de circulo |
| 1.3.0 | Marca REQUIRED /arkana-evolve:apply en rojo brillante inverso a la derecha de la linea 1 cuando el layout del repo es anterior al conocido; barras y espacios como separadores en las lineas 1 y 2; el esfuerzo del modelo como circulo (○ ◔ ◑ ◕ ●) |
| 1.2.0 | Statusline de usuario como despachador: en ARKANA la de Arkana, en un componente la elegida (choose) y en otros sitios los proveedores (plugin4cc antes que otra); hooks SessionStart y UserPromptSubmit (pregunta por componente y recuperacion del hueco si un tercero lo pisa); skills nuevas choose, provider y uninstall |
| 1.1.15 | Nucleo 1.11.1 vendorizado: el registro de workspaces conserva el nombre de una entrada existente |
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
