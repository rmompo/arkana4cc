# Especificación del plugin: arkana-messaging

> **Estado:** `beta` | **Versión:** `2.1.0`

---

## Descripción general

Mensajes entre los componentes de un workspace de Arkana: put, get, delete (lógico), sync y reconcile; almacén local, sin git ni red

---

## Skills

| Skill | Versión | Descripción |
|-------|---------|-------------|
| `check` | 0 | Diagnóstico de solo lectura de la mensajería - almacén, plugin habilitado y latido de los hooks en ESTA sesión. Nunca corrige; propone install o fix. Acepta --json. |
| `delete` | 0 | Borra un mensaje de forma lógica (queda la marca `deleted`, se ignora y viaja en sync y en export). Solo ARKANA o el componente que lo escribió. Pide confirmación. Acepta --dry-run y --json. |
| `fix` | 0 | Corrige lo que check marca en la mensajería (almacén ausente, plugin deshabilitado). Interactivo, con copia .bak. Acepta --dry-run y --json. |
| `get` | 0 | Lista o muestra los mensajes dirigidos al componente actual (o todos, si eres ARKANA), con filtros por tipo, estado, destinatario, remitente, usuario y fecha; --pending para lo que hay que atender. Solo lectura, local, sin red. Acepta --json. |
| `install` | 0 | Primera puesta en marcha (repetible) de la mensajería - crea el almacén y habilita el plugin en ~/.claude/settings.json. No escribe nada en los repos. Copia .bak de lo que modifica. Acepta --dry-run y --json. |
| `put` | 0 | Guarda un mensaje del componente actual para otros componentes (aviso, tarea, revisión o pregunta) en el almacén local, o lo cierra (hecho o descartado) o lo comenta. Quién envía lo decide el directorio de trabajo, no un argumento. Pide confirmación antes de guardar. Acepta --dry-run y --json. |
| `query` | 0 | Consulta de SOLO LECTURA de los mensajes del componente actual (todos si eres ARKANA): muestra únicamente id, remitente, asunto y destinatarios. No los marca como leídos, ni como hechos, ni cambia ningún estado. Con --unread lista lo que el hook cuenta como sin leer; con --detail añade también el texto del mensaje (sin marcarlo). Local, sin red. Acepta --json. |
| `sync` | 0 | Reconstruye el índice local de mensajes, repara reconciliaciones cortadas y, con --reconcile, lista candidatos a reconciliar; con reconcile apply crea UN mensaje resumen que sustituye a los solapados. Acepta --dry-run y --json. |

---

## Historial de cambios

| Versión | Cambios |
|---------|---------|
| 2.1.0 | Bootstrap: plugin registrado en catalog.json |
