# Especificación del plugin: arkana-evolve

> **Estado:** `beta` | **Versión:** `0.5.11`

---

## Descripción general

Evolución de una instalación de Arkana: migraciones numeradas, idempotentes y con --dry-run que llevan el layout (carpetas, registro del proyecto, datos) de una versión a otra (apply, check)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `apply` | 7 | Aplica las migraciones pendientes de Arkana (registro del proyecto con UUID, carpetas fijas…) en orden, de forma idempotente y con copia de seguridad. Siempre ensaya primero con --dry-run y pide confirmación; nunca hace commit ni push. Acepta --dry-run, --to N y --json. |
| `check` | 4 | Diagnóstico de solo lectura de la evolución de Arkana - sello de layout del repo, migraciones aplicadas y pendientes, e integridad de lo ya aplicado. Avisa si el repo va por delante de esta instalación. Acepta --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 0.5.11 | Nucleo 1.11.1 vendorizado: el registro de workspaces conserva el nombre de una entrada existente |
| 0.5.10 | Migracion 0001: crea las carpetas finales de arkana-docs (src, md y out) con .gitkeep y no la carpeta contenedora |
| 0.5.9 | Migracion 0008: arkana-docs/ en src/, md/ y out/, layout 8 |
| 0.5.8 | apply mueve el registro de workspaces de ~/.arkana-workspaces.json a ~/.arkana/workspaces.json |
| 0.5.7 | apply: Migraciones 0006 (modelo de estados de arkana-todo) y 0007 (/.arkana/ en el .gitignore), layout 7, aviso de la copia de la statusline y bucle de apply que reevalua tras cada migracion |
| 0.5.6 | Nucleo 1.9.0 vendorizado: nombre-modulo compartido, resolucion por alias, carpeta o modulo y alias mostrados en mayusculas |
| 0.5.5 | Migración 0005 (layout 5, solo sello) y el sello recoge las migraciones intermedias sin cambios (núcleo 1.8.0) |
| 0.5.4 | check: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 0.5.3 | apply: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 0.5.2 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.5.1 | apply: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.5.0 | Bootstrap: plugin registrado en catalog.json |
