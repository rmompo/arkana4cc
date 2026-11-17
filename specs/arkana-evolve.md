# Especificación del plugin: arkana-evolve

> **Estado:** `beta` | **Versión:** `0.5.5`

---

## Descripción general

Evolución de una instalación de Arkana: migraciones numeradas, idempotentes y con --dry-run que llevan el layout (carpetas, registro del proyecto, datos) de una versión a otra (apply, check)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `apply` | 3 | Aplica las migraciones pendientes de Arkana (registro del proyecto con UUID, carpetas fijas…) en orden, de forma idempotente y con copia de seguridad. Siempre ensaya primero con --dry-run y pide confirmación; nunca hace commit ni push. Acepta --dry-run, --to N y --json. |
| `check` | 4 | Diagnóstico de solo lectura de la evolución de Arkana - sello de layout del repo, migraciones aplicadas y pendientes, e integridad de lo ya aplicado. Avisa si el repo va por delante de esta instalación. Acepta --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 0.5.5 | Migración 0005 (layout 5, solo sello) y el sello recoge las migraciones intermedias sin cambios (núcleo 1.8.0) |
| 0.5.4 | check: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 0.5.3 | apply: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 0.5.2 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.5.1 | apply: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.5.0 | Bootstrap: plugin registrado en catalog.json |
