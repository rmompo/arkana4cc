# Arkana plugins

Marketplace local de plugins de [Claude Code](https://claude.com/claude-code) para gobernar, con Claude, un **workspace multi-repo**: un repositorio de gobierno (ARKANA) y los repositorios del proyecto (los componentes).

Licencia: [MIT](LICENSE). Autor: R. Mompó Pavesi.

## Contenido del repositorio

```
.
├── plugins/             el marketplace `arkana` y sus seis plugins (empieza por plugins/README.md)
│   ├── .claude-plugin/marketplace.json
│   ├── docs/            contratos comunes: plugin, salida, disposición de datos
│   └── arkana-{workspace,messaging,statusline,agentic,knowledge}/
├── lib/arkana_core/     fuente canónica del núcleo común (con sus tests)
└── scripts/
    ├── vendor-core.sh   copia el núcleo en cada plugin (scripts/_core/) y lo vigila con --check
    └── run-all-tests.sh lanza todas las suites
```

El núcleo se copia dentro de cada plugin porque un plugin instalado no puede leer a otro. **No se edita `scripts/_core/`**: se cambia `lib/arkana_core/` y se regenera.

## Puesta en marcha

```bash
claude plugin marketplace add <ruta-a-este-repo>/plugins
claude plugin install arkana-workspace@arkana      # y los que quieras: arkana-messaging, arkana-agentic, arkana-statusline, arkana-knowledge, arkana-todo
```

La secuencia de instalación en un workspace está en [`plugins/README.md`](plugins/README.md#puesta-en-marcha).

## Desarrollo

```bash
bash scripts/vendor-core.sh --check          # las copias del núcleo coinciden con lib/arkana_core
bash scripts/vendor-core.sh                  # regenerarlas tras tocar lib/arkana_core
bash scripts/run-all-tests.sh --quick        # todas las suites sin e2e (≈1 min); sin --quick incluye las e2e (≈3 min)
bash scripts/run-all-tests.sh --only workspace
claude plugin validate plugins               # y plugins/arkana-<nombre> para cada uno
```

Las pruebas no usan red ni API real y no tocan `~/.claude`. La batería de contención (`--containment`) usa `claude` real y cuesta dinero (≈0,1 USD).

## Principios

- **Sin proyectos concretos en el código.** Componentes, rutas, tipos, formatos de commit, herramientas y registros se declaran en la configuración (el manifiesto y `config tools`).
- **Extensiones opcionales apagadas por defecto**: el formato de commit `ia4d` y la integración con Jira (ver `plugins/arkana-workspace/README.md`).
- **El conocimiento se comparte por git.** `arkana-knowledge/` vive en el repositorio de ARKANA de cada proyecto, no en estos plugins.
