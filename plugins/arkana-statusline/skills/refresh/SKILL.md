---
name: refresh
description: Hace `git fetch` de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) de la statusline esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json.
---

# arkana-statusline:refresh

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/refresh.py" [--component <alias>]... [--no-fetch] [--json]
```

El estado local de la statusline (`◌ ✚ ● ⇡` y la rama) se recalcula solo en cada refresco; lo único que depende del remoto es `⇣`, que se muestra como número si el último `fetch` de ese componente fue hace menos de 30 minutos y como `⇣?` si no se sabe. Este skill hace ese `fetch`.

## Contención de red

Antes de cada host comprueba el DNS (3 s): **sin VPN no intenta nada** y lo dice (`WARN|<alias>|sin red…`). Cada `fetch` tiene tope de 20 s en su propio grupo de procesos y, si uno vence, el cortacircuitos evita esperar a los demás del mismo host.

## Pasos

1. Ejecuta `refresh.py` y presenta una línea por componente (`OK` con su rama y contadores, o `WARN`).
2. Si hay `WARN` por red, sugiere `/arkana-workspace:check` (VPN, credenciales). No hagas `pull`, `merge`, `rebase`, `push` ni commit.
