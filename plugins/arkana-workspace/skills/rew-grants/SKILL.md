---
name: rew-grants
description: Muestra la matriz de permisos R/E/W entre ARKANA y los componentes - la esperada (del manifiesto) y la efectiva (de cada .claude/settings.local.json) - y sus desviaciones (missing, extra, weaker, stronger, legacy, duplicate, mode). Solo lectura; sirve también para regenerar la tabla de organizacion-proyecto.md.
---

# arkana-workspace:rew-grants

Compara **lo que debería poder hacer cada actor** (modelo generado desde `core/workspace.json`) con **lo que de verdad le concede** su `.claude/settings.local.json`. **No modifica nada**; corrige `/arkana-workspace:fix`.

Herramienta: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" <subcomando>`.

## Pasos

1. Matriz esperada y efectiva (filas = actores, columnas = destinos más `.credentials`, `agentic-state` y `core`):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" matrix --expected
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" matrix --effective
   ```
   Celda = las letras de lo que se puede hacer: **R**ead, **E**dit, **W**rite; mayúscula = concedido, minúscula = pregunta (`ask`) (`REW`, `RE`, `R`, `Re`). **Lo que no aparece, no se puede**: está denegado o no tiene regla (una celda vacía = sin ningún acceso). La diagonal es `REW` para todos, también ARKANA. Con `--component <alias>` (repetible) se limita a esas filas; con `--json` sale estructurado y **conserva las tres posiciones** (`Rxx` denegado, `R··` sin regla), que es lo que usa `diff`; con `--format md` en tabla Markdown.

2. Desviaciones (`diff`, o `status`, que es lo mismo):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/permissions.py" diff [--component <alias>] [--json]
   ```
   Tipos: `missing` (falta lo esperado), `weaker` (concede menos o pregunta/deniega donde debía conceder), `stronger` (concede más de lo esperado donde había `deny`/`ask`), `extra` (concede donde no se esperaba nada), `legacy` (regla `/ruta` con una sola barra, que Claude lee relativa a la raíz del repo: debe ser `//ruta`), `duplicate`, `obsolete` (`deny Write` redundante, `Edit` ya lo cubre), `mode` (fichero distinto de 0600) y `bash-missing` (faltan las reglas `Bash` del orquestador). Las reglas ajenas al modelo (p. ej. `Bash(ls *)`) no se consideran desviación.

3. Presenta primero la matriz efectiva, resalta las celdas que difieren de la esperada y lista las desviaciones con los `FAIL` antes que los `WARN`. Las reglas `Bash` se listan aparte de la matriz. Si hay desviaciones, termina con: «`/arkana-workspace:fix` las corrige (añade lo que falta; con tu confirmación quita lo que sobra)».

## Para documentar

`permissions.py matrix --expected --format md` genera la tabla del modelo para `organizacion-proyecto.md`.

## Reglas

- Solo lectura. No muestres el contenido de ningún fichero de credenciales.
- Un componente que no existe en disco aparece como `WARN`, no como error.
