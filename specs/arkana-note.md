# Especificación del plugin: arkana-note

> **Estado:** `beta` | **Versión:** `1.1.9`

---

## Descripción general

Notas de la persona usuaria en un workspace de Arkana: locales, sin red, con título, texto y componente (alias o * para todos); borrado lógico; salen en el BRIEF de la sesión (install, add, list, modify, delete)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `add` | 2 | Añade una nota para la persona usuaria con título, texto y componente opcionales (alias, carpeta o módulo; * = todos). Acepta --dry-run y --json. |
| `check` | 6 | Valida las notas de solo lectura - campos obligatorios, ids únicos, estados, fechas y contador. Nunca corrige. Acepta --json. |
| `delete` | 5 | Borra una nota de forma lógica (queda con estado removed, se oculta de list y se conserva). Se recupera con modify --restore. Pide confirmación. Acepta --dry-run y --json. |
| `fix` | 7 | Repara las notas - añade los campos que faltan y recalcula el contador de ids. No borra notas. Acepta --dry-run y --json. |
| `install` | 1 | Primera puesta en marcha - crea el almacén de notas (.arkana/arkana-note/notes.json) si falta. Repetible. Acepta --dry-run y --json. |
| `list` | 3 | Consulta las notas en una tabla (identificador, componente, titulo, texto), las modificadas más recientemente primero; con --id muestra una nota entera; filtra por componente, texto o estado (active, removed, all). Solo lectura. Acepta --json. |
| `modify` | 4 | Cambia el título, el texto o el componente de una nota (* = todos), o restaura una borrada con --restore. Acepta --dry-run y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.9 | Nucleo vendorizado: registro de workspaces en ~/.arkana/workspaces.json |
| 1.1.8 | Nucleo 1.10.0 vendorizado: LAYOUT_KNOWN 7 |
| 1.1.7 | fix: Se crea el skill fix |
| 1.1.6 | check: Se crea el skill check |
| 1.1.5 | delete: Se crea el skill delete |
| 1.1.4 | modify: Se crea el skill modify |
| 1.1.3 | list: Se crea el skill list |
| 1.1.2 | add: Se crea el skill add |
| 1.1.1 | install: Se crea el skill install |
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
