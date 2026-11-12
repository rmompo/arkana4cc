# Arkana plugins

Marketplace local de plugins de [Claude Code](https://claude.com/claude-code) para gobernar, con Claude, un **workspace multi-repo**: un repositorio de gobierno (ARKANA) y los repositorios del proyecto (los componentes).

Licencia: [MIT](LICENSE). Autor: R. Mompó Pavesi.

## Contenido del repositorio

```
.
├── .claude-plugin/marketplace.json   el marketplace `arkana`
├── plugins/             los plugins (empieza por plugins/README.md)
│   ├── docs/            contratos comunes: plugin, salida, disposición de datos
│   └── arkana-{workspace,messaging,statusline,agentic,knowledge,todo,evolve}/
├── lib/arkana_core/     fuente canónica del núcleo común (con sus tests)
└── scripts/
    ├── vendor-core.sh   copia el núcleo en cada plugin (scripts/_core/) y lo vigila con --check
    └── run-all-tests.sh lanza todas las suites
```

El núcleo se copia dentro de cada plugin porque un plugin instalado no puede leer a otro. **No se edita `scripts/_core/`**: se cambia `lib/arkana_core/` y se regenera.

## Puesta en marcha

```bash
claude plugin marketplace add <ruta-a-este-repo>        # la raíz del repo, donde está .claude-plugin/marketplace.json
claude plugin install arkana-workspace@arkana      # y los que quieras: arkana-messaging, arkana-agentic, arkana-statusline, arkana-knowledge, arkana-todo, arkana-evolve
```

La secuencia de instalación en un workspace está en [`plugins/README.md`](plugins/README.md#puesta-en-marcha).

## Desarrollo

```bash
bash scripts/vendor-core.sh --check          # las copias del núcleo coinciden con lib/arkana_core
bash scripts/vendor-core.sh                  # regenerarlas tras tocar lib/arkana_core
bash scripts/run-all-tests.sh --quick        # todas las suites sin e2e (≈1 min); sin --quick incluye las e2e (≈3 min)
bash scripts/run-all-tests.sh --only workspace
claude plugin validate .                     # el marketplace; y plugins/arkana-<nombre> para cada plugin
```

Las pruebas no usan red ni API real y no tocan `~/.claude`. La batería de contención (`--containment`) usa `claude` real y cuesta dinero (≈0,3–0,6 USD).

## Principios

- **Sin proyectos concretos en el código.** Componentes, rutas, tipos, formatos de commit, herramientas y registros se declaran en la configuración (el manifiesto y `config tools`).
- **Extensiones opcionales apagadas por defecto**: el formato de commit `ia4d` y la integración con Jira (ver `plugins/arkana-workspace/README.md`).
- **Herramientas del sistema: se usan las que hay y se piden las que faltan.** Arkana aprovecha lo que ya trae el entorno (contenedor o máquina). Si necesita otra herramienta o paquete, **se lo pide a la persona usuaria** indicando cuál, para qué y el comando exacto; **jamás lo instala por su cuenta** (ni `sudo`, ni gestores de paquetes del sistema). Una herramienta opcional que falte reduce la función, no la rompe.
- **Nada de Arkana en los repos de trabajo.** Arkana no crea ni modifica `CLAUDE.md` ni `CLAUDE.local.md` en los repos del proyecto ni deja bloques en ellos: las directrices de cada sesión (convención de commits, reglas comunes, mensajería, reglas del orquestador) las inyectan los hooks de los plugins. Las notas propias de una copia de trabajo van en `ARKANA.local.md` (local; se excluye con `.git/info/exclude`, nunca con el `.gitignore`).
- **El conocimiento se comparte por git.** `arkana-knowledge/` (notas) y `arkana-docs/` (documentos de origen, con su Markdown en `arkana-docs/md/`) viven en el repositorio de ARKANA de cada proyecto, no en estos plugins. Todo lleva un UUID que no cambia; las personas ven alias.
