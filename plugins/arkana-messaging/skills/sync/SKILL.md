---
name: sync
description: Reconstruye el índice local de mensajes, repara reconciliaciones cortadas y, con --reconcile, lista candidatos a reconciliar; con reconcile apply crea UN mensaje resumen que sustituye a los solapados. Acepta --dry-run y --json.
---

# arkana-messaging:sync

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/messaging.sh" sync [--reconcile] [--dry-run] [--json]
```

Reconstruye `state/index.json` desde los mensajes, lista ficheros ilegibles (`WARN`) y completa una reconciliación que se cortó a medias. Con `--reconcile` informa de cuántos grupos de mensajes abiertos comparten destinatario.

## Reconciliar (decide el modelo, confirma el usuario)

1. `reconcile candidates [--to <alias>] --json` da grupos `{para, mensajes[{id, tipo, de, asunto, cuerpo}]}` de mensajes **abiertos con el mismo destinatario**. El script solo elige candidatos.
2. **Tú decides cuáles se solapan** de verdad (mismo asunto o decisión repetida, información superada por otra posterior). Si no se solapan, no hagas nada.
3. Redacta **un** mensaje resumen que conserve todo lo accionable de los originales. Enséñalo y pide confirmación (`AskUserQuestion`).
4. `reconcile apply --origins "<id id ...>" --subject "<texto>" [--type task|...] [--body-file f] [--instructions-file f] [--criteria-file f]` crea el resumen (guarda `origins`) y pasa los originales a `reconciled` (dejan de mostrarse). Una `task` resumen exige instrucciones y criterios. Admite `--dry-run`.

Nunca reconcilies mensajes de destinatarios distintos ni ya cerrados.
