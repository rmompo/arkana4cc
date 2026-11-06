# Orquestación multi-repo (arkana-agentic): guía para personas

`arkana` gobierna a los demás repos: tú pides algo en `arkana`, el orquestador (la sesión de Claude de `arkana`) redacta un **plan**, tú lo apruebas y se ejecuta **una tarea cada vez** con un worker en el repo que toque. Cada resultado lo verifica un script (no el worker) y tú decides en las paradas obligatorias. El modelo propone; el script decide.

La referencia completa (todos los skills y subcomandos con sus parámetros) está en [`../README.md`](../README.md); la visión de conjunto de los seis plugins, en [`../../README.md`](../../README.md).

## Antes de empezar

Una sola vez, desde `arkana` y en este orden:

1. `/arkana-workspace:install` y `/arkana-workspace:component add`: el manifiesto con tus repos (alias como `app`, `api`, `app-web`, `app-ui`, `docs`, `specs`), su tipo (`node`, `maven`, `docs`, `generic`) y su formato de commit.
2. `/arkana-workspace:config tools`: Node, JDK, Maven y registros, **con su ruta**. Las verificaciones no heredan el `PATH` de tu shell: solo ven las herramientas declaradas así (más `/usr/local/bin:/usr/bin:/bin`).
3. `/arkana-agentic:install` (reglas del orquestador en el `CLAUDE.md` de ARKANA) y luego `/arkana-workspace:fix` (reglas de permisos: el orquestador solo puede ejecutar `agentic.sh`, y te pregunta siempre antes de aprobar, rechazar, cambiar límites o integrar).
4. `/arkana-agentic:check`. Un `FAIL` impide orquestar; un `WARN` no. En particular, **sin VPN `red-vpn` es solo un aviso**: el trabajo y el commit son locales; usa `check --need-network` si vas a necesitar los remotos.

## Cómo se usa

| Quieres… | Haz |
|---|---|
| Pedir trabajo en varios repos | `/arkana-agentic:plan` y cuenta qué quieres |
| Atender un mensaje de otro componente | Dile al orquestador el id del mensaje (`--from-message`): lo asigna al plan o genera uno desde él |
| Ejecutar un plan aprobado | `/arkana-agentic:run` |
| Ver cómo va | `/arkana-agentic:status` |
| Contestar a una parada (gate), reintentar u omitir una tarea, ajustar límites | `/arkana-agentic:control` |
| Parar (suave: termina la tarea actual) o pausar y reanudar | `/arkana-agentic:stop` |
| Parar ya (mata al worker) | `/arkana-agentic:stop` y pide la parada forzosa |
| Tras una caída de la sesión | `/arkana-agentic:fix` |
| Cuánto se ha gastado | `/arkana-agentic:costs` |
| Integrar las ramas del plan y guardarlo | `/arkana-agentic:archive` |
| Comprobar que todo está en orden | `/arkana-agentic:check` |

Sin Claude también se puede consultar y parar: `bash plugins/arkana-agentic/scripts/agentic.sh status | log <T> | stop [--force]` (y `--help` en cada subcomando).

## Una sesión típica

1. **Plan.** El orquestador lee el código, escribe el plan (tareas pequeñas, un repo cada una, con criterios y verificaciones) y te lo enseña con sus límites, lo que autoriza y los mensajes que recibirá cada worker. Eliges: aprobar y ejecutar, aprobar sin ejecutar, cambiar o descartar. Aprobar es tu decisión: un plan aprobado queda sellado y, si se altera, no se ejecuta.
2. **Ejecución.** Una tarea cada vez: el worker edita ficheros en su repo (sin shell ni git), el script verifica (alcance, rutas protegidas, comandos de una lista cerrada por tipo de componente, criterios) y el orquestador acepta, reintenta, divide o te pregunta. Cada tarea aceptada es **un commit local** en la rama `arkana-worker/<plan>` de su repo, con el formato de commit del componente. (Los planes antiguos usaron `m3a/<plan>`; se reconocen.)
3. **Paradas (gates).** Se abren al faltar un permiso, herramienta, dato o decisión, al tocar una ruta protegida, ante una violación, al llegar a un límite, cada 3 tareas (checkpoint) y cuando el plan cambia. Te explican qué pasó y qué opciones hay; `approve` o `reject` (con `--stop` para detener el plan). Una violación solo admite detener. Las rutas `.git`, `.husky`, `.claude` y `.env*` no se pueden autorizar.
4. **Final.** `integrate review` enseña, por repo, los commits y el diff; tú decides **repo a repo**: integrar (merge local), dejar la rama o descartarla. El push es siempre aparte. Después, archivar el plan si quieres conservarlo.

## Qué te garantiza

- Los workers **no tienen shell ni git**, no salen de su repo y no tocan rutas protegidas (`.git`, `.husky`, `.claude`, `CLAUDE.md`, `.env*`, y según el tipo de componente `package.json`, lockfiles, `angular.json`, `pom.xml`…).
- **Un solo worker a la vez.** Límites de turnos, tiempo, coste, intentos, tareas, cambios de plan y duración, con techos; los fija el script (`agentic.sh policy show`; un plan solo puede bajarlos).
- Los comandos de verificación los ejecuta el script, de una lista cerrada por tipo de componente (`node`, `maven`, `docs`, `generic`).
- Nada se commitea, integra ni sube sin tu autorización; `develop` no se toca hasta que decides.
- Un plan alterado después de aprobarlo **no se ejecuta**.
- Si la sesión muere, un dead-man switch mata al worker y `/arkana-agentic:fix` te pregunta qué hacer.

## Qué no se puede garantizar

Que el trabajo sea correcto (por eso verifica el script y tú revisas el diff), la exfiltración por red, la inyección de prompts a través de lo que el worker lea y el código malicioso que un worker pudiera dejar para que lo ejecute el verificador (por eso se revisa el diff de las rutas sensibles antes de ejecutar nada). El tope de coste no es exacto.

## Dónde está cada cosa

- Reglas del orquestador: bloque `arkana:agentic` del `CLAUDE.md` de ARKANA (lo pone `/arkana-agentic:install`; plantilla en `plugins/arkana-agentic/templates/orquestador.md`).
- Estado de ejecución (local, no se versiona): `<arkana>/.arkana/arkana-agentic/` (`state/` con los planes y el worker en marcha, `config/` con tu política, `data/` con el libro de costes y los planes archivados).
- Límites: `agentic.sh policy show` y `policy set <clave> <valor>` (`--ceiling` para el techo).
- Herramientas, formato de commit y repos: el manifiesto y `tools.json` de `arkana-workspace`.
- Costes: `/arkana-agentic:costs` (workers y sesiones; el coste de las sesiones lo anota la statusline, que también pinta el plan en su línea 1).
- Planes terminados: `.arkana/arkana-agentic/data/archive/<plan>/` (local; no se versiona).
- Pruebas: `bash tests/run-unit.sh`, `bash tests/run-e2e.sh` y, con `claude` real y coste, `bash tests/containment/run-containment.sh`.
