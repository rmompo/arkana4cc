# Especificación del plugin: arkana-messaging

> **Estado:** `beta` | **Versión:** `2.1.23`

---

## Descripción general

Mensajes entre los componentes de un workspace de Arkana: put, get, delete (lógico), sync y reconcile; almacén local, sin git ni red

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 9 | Diagnóstico de solo lectura de la mensajería - almacén, plugin habilitado y latido de los hooks en ESTA sesión. Nunca corrige; propone install o fix. Acepta --json. |
| `delete` | 10 | Borra un mensaje de forma lógica (queda la marca `deleted`, se ignora y viaja en sync y en export). Solo ARKANA o el componente que lo escribió. Pide confirmación. Acepta --dry-run y --json. |
| `fix` | 11 | Corrige lo que check marca en la mensajería (almacén ausente, plugin deshabilitado). Interactivo, con copia .bak. Acepta --dry-run y --json. |
| `get` | 12 | Lista o muestra los mensajes dirigidos al componente actual (o todos, si eres ARKANA), con filtros por tipo, estado, destinatario, remitente, usuario y fecha; --pending para lo que hay que atender. Solo lectura, local, sin red. Acepta --json. |
| `install` | 13 | Primera puesta en marcha (repetible) de la mensajería - crea el almacén y habilita el plugin en ~/.claude/settings.json. No escribe nada en los repos. Copia .bak de lo que modifica. Acepta --dry-run y --json. |
| `put` | 14 | Guarda un mensaje del componente actual para otros componentes (aviso, tarea, revisión o pregunta) en el almacén local, o lo cierra (hecho o descartado) o lo comenta. Quién envía lo decide el directorio de trabajo, no un argumento. Pide confirmación antes de guardar. Acepta --dry-run y --json. |
| `query` | 15 | Consulta de SOLO LECTURA de los mensajes del componente actual (todos si eres ARKANA): muestra únicamente id, remitente, asunto y destinatarios. No los marca como leídos, ni como hechos, ni cambia ningún estado. Con --unread lista lo que el hook cuenta como sin leer; con --detail añade también el texto del mensaje (sin marcarlo). Local, sin red. Acepta --json. |
| `sync` | 16 | Reconstruye el índice local de mensajes, repara reconciliaciones cortadas y, con --reconcile, lista candidatos a reconciliar; con reconcile apply crea UN mensaje resumen que sustituye a los solapados. Acepta --dry-run y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 2.1.23 | Nucleo 1.12.0 vendorizado: LAYOUT_KNOWN 9 |
| 2.1.22 | Nucleo 1.11.1 vendorizado: el registro de workspaces conserva el nombre de una entrada existente |
| 2.1.21 | Nucleo 1.11.0 vendorizado: LAYOUT_KNOWN 8 |
| 2.1.20 | Nucleo vendorizado: registro de workspaces en ~/.arkana/workspaces.json |
| 2.1.19 | Nucleo 1.10.0 vendorizado: LAYOUT_KNOWN 7 |
| 2.1.18 | Nucleo 1.9.0 vendorizado: nombre-modulo compartido, resolucion por alias, carpeta o modulo y alias mostrados en mayusculas |
| 2.1.17 | Núcleo 1.8.0 vendorizado: campos mode, ref, watch y checks_skip del componente, esquema 2 del manifiesto y LAYOUT_KNOWN |
| 2.1.16 | sync: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.15 | query: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.14 | put: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.13 | install: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.12 | get: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.11 | fix: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.10 | delete: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.9 | check: Se añade allowed-tools limitado (Read, AskUserQuestion) y el sufijo de invocación en la descripción (C4 y C7 de skill-doctor) |
| 2.1.8 | sync: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.7 | query: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.6 | put: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.5 | install: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.4 | get: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.3 | fix: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.2 | delete: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.1 | check: Se añade version al frontmatter del skill (modelo de versiones de p4cc) |
| 2.1.0 | Bootstrap: plugin registrado en catalog.json |
