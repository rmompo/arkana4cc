#!/usr/bin/env python3
"""Migración del layout de `.arkana/arkana-agentic/` al reparto config / state / data.

Antes:  planes/ run/ sesiones/ actual politica.json comandos-permitidos.json   (todo junto)
Ahora:  config/{politica.json, comandos-permitidos.json}   state/{planes, run, sesiones, actual}   data/{ledger, archive}

`plan(base)` describe qué se movería; `run(base, dry)` lo hace: copia de seguridad `tar.gz` primero (en `.arkana/arkana-workspace/bak/`), se niega
si hay un plan activo o un worker vivo, es idempotente (si lo nuevo ya existe y lo viejo también, avisa y no pisa) y acepta --dry-run.
También copia `orquestacion/archivo/<plan>` de ARKANA a `data/archive/` si existiera (no borra el origen).
"""
import os
import shutil
import tarfile
import time

import state

MOVES = [("planes", "state/planes"), ("run", "state/run"), ("sesiones", "state/sesiones"), ("actual", "state/actual"),
         ("politica.json", "config/politica.json"), ("comandos-permitidos.json", "config/comandos-permitidos.json")]


def pending(base):
    return [(o, n) for o, n in MOVES if os.path.lexists(os.path.join(base, o))]


def blockers(base):
    """Razones por las que no se puede migrar ahora (plan activo, worker vivo)."""
    res = []
    pd = os.path.join(base, "planes")
    for pid in sorted(os.listdir(pd)) if os.path.isdir(pd) else []:
        try:
            est = state.load_json(os.path.join(pd, pid, "plan.json")).get("estado")
        except (OSError, ValueError):
            continue
        if est in state.ACTIVE_PLAN_STATES:
            res.append(f"el plan {pid} está {est}")
    wj = os.path.join(base, "run", "worker.json")
    if os.path.exists(wj):
        try:
            pid = int(state.load_json(wj).get("pid", 0))
            if pid > 0:
                os.kill(pid, 0)
                res.append(f"hay un worker vivo (pid {pid})")
        except (OSError, ValueError, TypeError):
            pass
    return res


def run(base, dry=False, backup_dir=None):
    """-> [(estado, id, detalle)]."""
    items = []
    todo = pending(base)
    arch_src = os.path.join(os.path.dirname(os.path.dirname(base)), "orquestacion", "archivo")
    if not todo:
        items.append(("OK", "layout", "el layout ya es config/state/data"))
    else:
        bl = blockers(base)
        if bl:
            return [("FAIL", "layout", "no se migra ahora: " + "; ".join(bl))]
        if not dry and backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            tgz = os.path.join(backup_dir, "agentic-layout-" + time.strftime("%Y%m%dT%H%M%S") + ".tar.gz")
            with tarfile.open(tgz, "w:gz") as t:
                for o, _ in todo:
                    t.add(os.path.join(base, o), arcname=o)
            os.chmod(tgz, 0o600)
            items.append(("OK", "layout-copia", f"copia de seguridad en {os.path.basename(tgz)}"))
        for o, n in todo:
            src, dst = os.path.join(base, o), os.path.join(base, n)
            if os.path.lexists(dst):
                items.append(("WARN", f"layout-{o}", f"existen {o} y {n}: no se pisa; revisa a mano"))
                continue
            if not dry:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)
            items.append(("DRY" if dry else "OK", f"layout-{o}", f"{o} → {n}"))
    if os.path.isdir(arch_src):
        for pid in sorted(os.listdir(arch_src)):
            dst = os.path.join(base, "data", "archive", pid)
            if os.path.exists(dst):
                continue
            if not dry:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copytree(os.path.join(arch_src, pid), dst)
            items.append(("DRY" if dry else "OK", f"layout-archivo-{pid}", "plan archivado copiado a data/archive (el origen en ARKANA no se borra)"))
    if not dry:
        for d in ("config", "state", "data"):
            os.makedirs(os.path.join(base, d), exist_ok=True)
            os.chmod(os.path.join(base, d), 0o700)
    return items
