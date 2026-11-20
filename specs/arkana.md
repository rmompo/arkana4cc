# Especificación del plugin: arkana

> **Estado:** `beta` | **Versión:** `1.1.9`

---

## Descripción general

Instalación guiada de Arkana: monta el espacio de trabajo mínimo de una vez (workspace, statusline, mensajería, orquestación, conocimiento, tareas, permisos y herramientas) y sugiere añadir el primer componente

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `install` | 8 | Monta de una vez el espacio de trabajo mínimo de Arkana - comprueba que están los plugins arkana-*, crea la disposición de .arkana y el registro del proyecto, instala statusline, mensajería, orquestación, conocimiento y tareas, aplica los permisos, revisa credenciales y herramientas y verifica todo. No añade componentes - al terminar sugiere dar de alta el primero. Repetible e idempotente, con ensayo previo de cada paso. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 1.1.9 | Nucleo 1.11.1 vendorizado: el registro de workspaces conserva el nombre de una entrada existente |
| 1.1.8 | install: install: el paso knowledge garantiza el andamiaje completo con .gitkeep en cada carpeta final |
| 1.1.7 | Nucleo 1.11.0 vendorizado: LAYOUT_KNOWN 8 |
| 1.1.6 | Nucleo vendorizado: registro de workspaces en ~/.arkana/workspaces.json |
| 1.1.5 | gitinit: el ensayo muestra la identidad que se fijaria en lugar de una linea vacia |
| 1.1.4 | install: install: nuevo paso git (git init y usuario y correo del repo) y entrevista de remoto y token de ARKANA sin pasar el token por la conversacion |
| 1.1.3 | install: Tras la verificacion ofrece /arkana-workspace:fix para lo corregible y documenta el .gitignore de .arkana (hallazgos del laboratorio) |
| 1.1.2 | install: Se añade el paso note (arkana-note) al pipeline de instalacion |
| 1.1.1 | install: Se crea la skill: pipeline de instalación de todo el espacio de trabajo mínimo y sugerencia del primer componente |
| 1.1.0 | Bootstrap: plugin registrado en catalog.json |
