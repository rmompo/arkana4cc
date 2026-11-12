# Especificación del plugin: arkana-evolve

> **Estado:** `beta` | **Versión:** `0.5.2`

---

## Descripción general

Evolución de una instalación de Arkana: migraciones numeradas, idempotentes y con --dry-run que llevan el layout (carpetas, registro del proyecto, datos) de una versión a otra (apply, check)

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `apply` | 1 | Aplica las migraciones pendientes de Arkana (registro del proyecto con UUID, carpetas fijas…) en orden, de forma idempotente y con copia de seguridad. Siempre ensaya primero con --dry-run y pide confirmación; nunca hace commit ni push. Acepta --dry-run, --to N y --json. |
| `check` | 2 | Diagnóstico de solo lectura de la evolución de Arkana - sello de layout del repo, migraciones aplicadas y pendientes, e integridad de lo ya aplicado. Avisa si el repo va por delante de esta instalación. Acepta --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 0.5.2 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.5.1 | apply: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 0.5.0 | Bootstrap: plugin registrado en catalog.json |
