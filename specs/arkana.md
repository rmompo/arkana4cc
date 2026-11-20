# Especificación del plugin: arkana

> **Estado:** `beta` | **Versión:** `1.1.2`

---

## Descripción general

Instalación guiada de Arkana: monta el espacio de trabajo mínimo de una vez (workspace, statusline, mensajería, orquestación, conocimiento, tareas, permisos y herramientas) y sugiere añadir el primer componente

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `install` | 2 | Monta de una vez el espacio de trabajo mínimo de Arkana - comprueba que están los plugins arkana-*, crea la disposición de .arkana y el registro del proyecto, instala statusline, mensajería, orquestación, conocimiento y tareas, aplica los permisos, revisa credenciales y herramientas y verifica todo. No añade componentes - al terminar sugiere dar de alta el primero. Repetible e idempotente, con ensayo previo de cada paso. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.2 | install: Se añade el paso note (arkana-note) al pipeline de instalacion |
| 1.1.1 | install: Se crea la skill: pipeline de instalación de todo el espacio de trabajo mínimo y sugerencia del primer componente |
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
