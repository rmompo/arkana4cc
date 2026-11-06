---
name: sync
description: Hace `git fetch` de los remotos de ARKANA y de los componentes (con comprobación de DNS y tope de 20 s por repo) para que ⇣ (commits por bajar) esté al día. Solo descarga referencias: no toca ficheros ni ramas locales. Acepta --component, --no-fetch y --json.
---

# arkana-workspace:sync

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lib/sync.py" [--component <alias>]... [--no-fetch] [--json]
```

`status` y la statusline calculan todo con git local; lo único que depende del remoto es `⇣`, que se muestra como número si el último `fetch` fue hace menos de 30 minutos y como `⇣?` si no se sabe. Este skill hace ese `fetch` en ARKANA y en cada componente (o solo en los de `--component`) y enseña después su estado.

## Contención de red

Antes de cada host comprueba el DNS (3 s): **sin VPN no intenta nada** y lo dice (`WARN|<alias>|sin red…`). Cada `fetch` tiene tope de 20 s en su propio grupo de procesos y, si uno vence, el cortacircuitos evita esperar a los demás del mismo host. Un repositorio sin remoto no se consulta. Con `--no-fetch` no se toca la red y solo se muestra el estado.

## Pasos

1. Ejecuta `sync.py` y presenta una línea por pieza (`OK` con su rama y contadores, o `WARN`). Resalta las que tengan `⇣` (cambios por bajar).
2. Si hay `WARN` por red, sugiere `/arkana-workspace:check` (VPN, credenciales).
3. **No hagas `pull`, `merge`, `rebase`, `push` ni commit**: integrar lo descargado es decisión del usuario. Si algo está por bajar, díselo y pregunta.
