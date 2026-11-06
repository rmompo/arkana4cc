# Piloto supervisado de arkana-agentic (fase 8)

> Registro histórico de los pilotos de `arkana-agentic`. Los alias (`app`, `api`…) son ejemplos; no describen ningún proyecto concreto.

Objetivo: comprobar que **una sesión nueva del modelo**, que conoce el sistema solo por `ORQUESTADOR.md` y los skills, gobierna un pipeline real de principio a fin sin saltarse nada. Todo lo demás (motor, contratos, contención) se prueba con tests; esto es lo único que prueba al **orquestador**. Pasa a 1.0.0 cuando se cumplen los criterios del final.

## Dónde estamos

| Piloto | Versión | Resultado |
|---|---|---|
| **1** (2026-10-30) | 0.1.0 | Plan completado por 0,0625 USD; 5 defectos encontrados y corregidos. Detalle en `VERIFICACION.md` (fase 8) |
| **2** (2026-10-31) | 0.3.0 | Dos planes sencillos (una línea al final de un README en cada uno de `api` y `app`), ambos completados por 0,10 USD cada uno: rama `arkana-worker/<plan>` creada por `launch` en cada repo, un commit por tarea, `merge` en `api` y `discard` en `app`, sin denegaciones ni violaciones. Hallazgos: el scope de los commits no era el id del repo y el registro no llevaba el sha del merge ni rastro de `integrate review` (corregidos en 0.3.1) |
| **3** (2026-10-31) | 0.3.2 | T001 y T002 completadas (dos commits en `arkana-worker/<plan>`, 0,17 USD); T003 omitida: el gate pidió «autorizar y reintentar» pero los ajustes del worker seguían denegando `CLAUDE.md`, así que el segundo intento falló igual (corregido en 0.3.3). El resto, correcto: rama única, scope del commit, `integrate review` con traza |
| **4** (este) | **0.3.4** | Repite lo que falló en el 3: el **gate de ruta protegida** (ahora, autorizar `CLAUDE.md` funciona), y ejercita `merge --up-to` |

Riesgo: mínimo. `api` es un andamio casi vacío. Todo va en la rama local `arkana-worker/<plan>`; `develop` no se toca y **no hay push**. Coste esperado: 0,1 a 0,25 USD. Duración: unos 5 minutos.

## Antes de empezar (lo haces tú)

| # | Qué | Cómo comprobarlo |
|---|---|---|
| 1 | `api` limpio y en `develop`, sin ramas `arkana-worker/*`. **No trabajes en él durante el piloto** | `git -C <api> status --short` y `git -C <api> branch --list 'arkana-worker/*'` vacíos |
| 2 | (Opcional) quitar la línea «prueba A» que dejó el piloto 2 (solo está en local, sin push) | `git -C <api> reset --hard 7bdd1f9` |
| 3 | **Sesión nueva** de Claude en `arkana` (no reutilices una abierta) y `/reload-plugins` | Carga `ORQUESTADOR.md` desde `CLAUDE.md`, las reglas de permisos y los skills `arkana-agentic:*` |
| 4 | `/arkana-agentic:check` | **0 FAIL y 0 WARN** |
| 5 | La tercera línea de la statusline | `[■] sin plan activo P0,00$ S0,00$` (los importes en rojo normal, el `$` en verde normal y el resto en gris). **Aunque haya un plan reciente de otra sesión, esta sesión nueva no debe verlo**. Necesita el script nuevo: `/arkana-workspace:install` si no lo tienes |

Los skills se leen de la copia de trabajo de `arkana` (el marketplace es de tipo directorio): no hace falta actualizar plugins para el piloto.

## Escenario

Dile al orquestador, con tus palabras (no le des el plan hecho: es parte de lo que se prueba):

> Añade al final del `README.md` de `api` una línea «Piloto de orquestación: prueba C» y, después, otra con «Piloto de orquestación: prueba D». Por último añade una viñeta al final de la sección «Notas» del `CLAUDE.md` de `api`: «Piloto 3: prueba del gate de rutas protegidas». Una tarea para cada cosa, en ese orden. No quiero push. Tope de 0,5 USD.

Plan de referencia (para comparar; el suyo puede variar). Está en `docs/piloto3-plan-referencia.json` y valida con el motor actual con un único aviso esperado (la tarea que toca `CLAUDE.md`):

| Tarea | Repo | Qué hace | Se espera |
|---|---|---|---|
| T001 | `api` | Línea «prueba C» al final del README | Se completa y se commitea en `arkana-worker/<plan>` |
| T002 | `api` | Línea «prueba D» al final del README (depende de T001) | Se completa y se commitea **en la misma rama** (segundo commit) |
| T003 | `api` | Viñeta en `CLAUDE.md` (depende de T002) | **Gate `ruta_protegida`** (con la ruta y lo que quería escribir): al autorizarlo, el **segundo intento la edita**, se verifica y se commitea |

## Qué observar (marca cada punto)

**Planificar**
- [ ] `plan validate` sin FAIL y te cuenta el aviso de `CLAUDE.md`.
- [ ] `autoriza.commits_locales: true` y `total_budget_usd: 0.5`.
- [ ] Tres tareas pequeñas, sin pedir al worker que ejecute comandos.
- [ ] Te enseña el plan y **te pregunta antes de aprobar**; `plan approve` pide **tu confirmación** (regla `ask`).
- [ ] «Aprobar y ejecutar» arranca el plan **sin pedirte otro comando**.

**Ejecutar**
- [ ] Una sola orden por llamada, con la ruta sin comillas ni `&&`/`cd` (si no, pide permiso: anótalo).
- [ ] La línea 3 cambia: `001/003 api@<plan>:T001 …` → `002/003 …:T002 …` → `003/003 …:T003 … (esperando tu respuesta: ruta_protegida)`, con el coste del plan y el de la sesión.
- [ ] El script crea **una sola** rama `arkana-worker/<plan>` (`git -C <api> branch --list 'arkana-worker/*'`) y T001 y T002 son **dos commits** en ella (`git -C <api> log --oneline develop..arkana-worker/<plan>`).
- [ ] Antes de cada `act continue` mira el diff, y el mensaje del commit lleva **el id del repo como scope** (`docs(api) …`, ≤72, sin punto, sin `Co-Authored-By`).
- [ ] Una línea por tarea y decimales con coma.

**Gate real (T003)**
- [ ] Se para y te explica **qué ruta se tocó** y qué opciones hay; te enseña el diff **antes** de pedirte que autorices.
- [ ] El gate es `ruta_protegida` (no `permiso`) y dice qué quería escribir el worker; no ofrece «reintentar sin más».
- [ ] Autorizas (`approve`): el **segundo intento edita `CLAUDE.md`**, la tarea se verifica, se commitea y el plan termina. Si falla otra vez, es un defecto de primer orden.

**Cierre**
- [ ] Te enseña `integrate review` (commits por tarea con su sha, `diff --stat` y coste) y te pregunta qué hacer.
- [ ] Pide `integrate merge --repo api --up-to T002`: integra T001 y T002 en `develop` con **un merge** (`chore(api) merge arkana-worker/<plan> up to T002`) y **conserva la rama** con T003 (`git -C <api> log --oneline --graph -6 --all`).
- [ ] Para el resto: `integrate discard --repo api` (borra la rama; T003 se pierde) o `integrate merge --repo api` (lo integra).
- [ ] `registro.jsonl` lleva `review` y un `integrate` con el sha del merge. `status` coincide con lo que pasó y el gasto es coherente con el tope.
- [ ] Nunca ejecuta `claude`, edita el estado, aprueba por ti ni hace push.

## Pruebas de control durante el piloto (opcionales)

1. **Parada suave:** en cuanto la statusline muestre `[▶] 001/003 …`, ejecuta `/arkana-agentic:stop`. T001 debe terminar y el plan quedar `pausado` (`[‖] …`); `/arkana-agentic:run` lo reanuda. (Las tareas duran unos 10 s: hay que ser rápido.)
2. **Recuperación** (más intrusiva): con un worker en marcha, cierra la sesión y abre otra: `/arkana-agentic:status` y `/arkana-agentic:recover`. Debe avisar de la tarea interrumpida y **no reintentar sola**.

## Limitaciones conocidas (no son defectos del piloto)

- Un worker **no puede leer `.env.example`**: la regla de seguridad `Read(.env*)` también lo bloquea (y `app` tiene un `.env` y un `.env.bak` locales). Por eso el escenario no lo pide. Si el orquestador lo incluye, el gate `permiso` que salga es correcto.
- El orquestador hace sus propias comprobaciones con `git` (`diff`, `log`, `status`), que piden permiso en cada llamada: no hay reglas `allow` para git de solo lectura (decisión pendiente tuya).

## Si algo sale mal

| Situación | Qué hacer |
|---|---|
| Quieres parar ya | `/arkana-agentic:stop` y pide la parada **forzosa** (o `agentic.sh stop --force`) |
| Un gate que no entiendes | No aprobar: `agentic.sh status` y `log <T>`; `reject <G> --stop` si hay duda |
| El orquestador hace algo fuera de las reglas | Párale y anota **qué** y **en qué momento**: es un hallazgo de primer orden |
| Quedaron ramas a medias | `agentic.sh integrate discard --repo api` (vuelve a la rama original y borra `arkana-worker/<plan>`), o a mano: `git -C <repo> switch develop && git -C <repo> branch -D arkana-worker/<plan>` |
| Quedó una tarea interrumpida | `agentic.sh recover` |

Limpieza final: `integrate discard` si no quieres conservar nada, `archive` si quieres guardar el plan en `orquestacion/archivo/`, y `git -C <repo> status` en `app` y `api` para confirmar que están limpios.

## Qué traer de vuelta

Para corregir lo aprendido hace falta, de cada ejecución:
- `agentic.sh status` final y, por tarea, `agentic.sh log <T>`;
- `<arkana>/.arkana/arkana-agentic/planes/<plan>/registro.jsonl` (decisiones, con quién y cuándo) y `plan.json`;
- la lista de **puntos marcados en contra** de arriba, con lo que pasó;
- cualquier **petición de permiso** inesperada y cualquier momento en que tuviste que corregir al orquestador.

Una fila por hallazgo: *qué pasó · qué se esperaba · gravedad (bloquea 1.0.0 / mejora) · arreglo propuesto*. Los arreglos de `ORQUESTADOR.md` o de los skills se aplican con `/reload-plugins` y una sesión nueva.

## Criterios para pasar a 1.0.0

1. Un pipeline completo (el escenario) terminado **sin intervención correctiva** tuya más allá de las aprobaciones, o con las correcciones ya incorporadas a `ORQUESTADOR.md` y repetido otra vez limpio.
2. Ninguna acción fuera de las reglas (`claude` lanzado a mano, estado editado, aprobación por ti, push, commit sin gate).
3. El gate real de T003 comprobado y el cierre con la decisión por repo (`integrate review`, `merge --repo --up-to`, `discard`). La parada suave se comprueba en este piloto o en una repetición.
4. La tercera línea de la statusline comprobada a ojo en sus estados (P0-13).
5. `doctor --deep` en verde tras los arreglos.
6. Commit y push de los cambios por repo con tu aprobación (formato IA4D, ≤72, sin `Co-Authored-By`), y `claude plugin update` en tu máquina.
