#!/usr/bin/env python3
"""Generador único de permisos de Claude Code para el workspace y evaluador semántico (base de `rew-grants`).

Modelo (todo sale del manifiesto `core/workspace.json`):
  · ARKANA: R/E/W sobre sí misma y sobre todos los componentes.
  · Cada componente: R/E/W sobre sí mismo y sobre ARKANA; solo R sobre los demás (con `deny Edit` explícito); no edita los
    componentes anidados dentro de su carpeta (p. ej. app sobre app-web/app-ui: R y `deny Edit`).
  · Para todos: `deny Read+Edit` de `.arkana/.credentials` y `deny Edit` del estado de arkana-agentic (lo escribe agentic.sh).
  · Solo ARKANA: lectura del estado de agentic, `agentic.sh` (ask en las decisiones humanas) y deny de `claude -p/--print/--bg`.
Reglas de rutas: `//ruta/absoluta`, `/relativa-a-la-raíz-del-fichero-de-ajustes`, `~/bajo-el-home`. deny > ask > allow; `Edit` cubre `Write`.

Uso:  permissions.py <expected|effective|matrix|diff|status|apply> [--component <alias>] [--home <dir>] [--json]
                     [--format text|md] [--expected|--effective] [--dry-run] [--prune]
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402

TOOLS = ("Read", "Edit", "Write")
LETTER = {"Read": "R", "Edit": "E", "Write": "W"}
SPECIALS = ("credentials", "agentic-state", "core")
RULE_RX = re.compile(r"^(Read|Edit|Write)\((.*)\)$")
HUMAN_DECISIONS = ("plan approve", "approve", "reject", "policy set", "integrate merge", "integrate discard")


# ---------------------------------------------------------------- reglas

def fmt(tool, path, rec=True):
    return f"{tool}(//{path.lstrip('/')}{'/**' if rec else ''})"


def parse(rule, settings_root=None):
    """(tool, ruta absoluta, recursiva, legacy) o None si no es una regla de ruta. `legacy`: `/x` en vez de `//x` (relativa a la raíz de ajustes)."""
    m = RULE_RX.match(rule)
    if not m:
        return None
    tool, raw = m.group(1), m.group(2)
    rec = raw.endswith("/**")
    if rec:
        raw = raw[:-3]
    legacy = False
    if raw.startswith("//"):
        path = "/" + raw[2:].lstrip("/")
    elif raw.startswith("~/") or raw == "~":
        path = os.path.expanduser(raw)
    elif raw.startswith("/"):
        legacy = True
        path = os.path.join(settings_root or "/", raw[1:])
    else:
        path = os.path.join(settings_root or "/", raw)
    return tool, os.path.normpath(path), rec, legacy


def is_legacy(ws, rule, root):
    """Regla `/ruta` (una barra) cuya ruta, leída como absoluta, cae en el workspace: casi seguro quiso decir `//ruta`."""
    p = parse(rule, root)
    if not p or not p[3]:
        return False
    absoluta = "/" + os.path.relpath(p[1], root)
    return absoluta.startswith(ws.root.rstrip("/") + "/") or absoluta.startswith(ws.state.rstrip("/") + "/")


def covers(rule_tool, tool):
    return rule_tool == tool or (tool == "Write" and rule_tool == "Edit")


def decide(rules, tool, path, settings_root=None):
    """'deny' | 'ask' | 'allow' | None para (tool, path) con las reglas {'allow','ask','deny'}."""
    path = os.path.normpath(path)
    for kind in ("deny", "ask", "allow"):
        for r in rules.get(kind, []):
            p = parse(r, settings_root)
            if not p or not covers(p[0], tool):
                continue
            _, base, rec, _ = p
            if path == base or (rec and path.startswith(base.rstrip("/") + "/")):
                return kind
    return None


def cell(rules, path, settings_root=None):
    out = ""
    for t in TOOLS:
        d = decide(rules, t, path, settings_root)
        out += {"allow": LETTER[t], "ask": LETTER[t].lower(), "deny": "x"}.get(d, "·")
    return out


# ---------------------------------------------------------------- destinos y esperado

def destinations(ws):
    """Columnas de la matriz: (nombre, ruta de prueba). Piezas del manifiesto y destinos especiales."""
    st = ws.state
    d = [(a, os.path.join(ws.path(a), "x")) for a in ws.aliases()]
    d += [(".credentials", os.path.join(st, ".credentials")),
          ("agentic-state", os.path.join(st, "arkana-agentic", "x")),
          ("core", os.path.join(st, "core", "x"))]
    return d


def settings_file(ws, actor):
    return os.path.join(ws.path(actor), ".claude", "settings.local.json")


def agentic_commands(ws):
    home = os.path.expanduser("~")
    return [f"bash {ws.path('arkana')}/plugins/arkana-agentic/scripts/agentic.sh",
            f"bash {home}/.claude/plugins/cache/arkana/arkana-agentic/*/scripts/agentic.sh"]


def expected(ws, actor):
    """Reglas esperadas de `actor`: {'allow': [...], 'ask': [...], 'deny': [...]} (formato canónico //abs/**)."""
    me = manifest.canon(actor)
    ws.get(me)
    allow, ask, deny = [], [], []
    nested = set(ws.nested_in(me))
    mine = ws.path(me).rstrip("/") + "/"
    for a in ws.aliases():
        p = ws.path(a)
        if a != me and mine.startswith(p.rstrip("/") + "/"):
            allow.append(fmt("Read", p))            # carpeta que contiene a la mía (app para app-web): solo lectura, sin deny (taparía lo mío)
        elif a in nested:
            allow.append(fmt("Read", p)); deny.append(fmt("Edit", p))
        elif a == me or me == "arkana" or a == "arkana":
            allow += [fmt(t, p) for t in TOOLS]
        else:
            allow.append(fmt("Read", p)); deny.append(fmt("Edit", p))
    st = ws.state
    deny += [fmt("Read", os.path.join(st, ".credentials"), False), fmt("Edit", os.path.join(st, ".credentials"), False),
             fmt("Edit", os.path.join(st, "arkana-agentic"))]
    allow.append(fmt("Read", os.path.expanduser("~/.claude/settings.json"), False))   # los check de herramientas leen la config de usuario
    if me == "arkana":
        for cmd in agentic_commands(ws):
            allow.append(f"Bash({cmd} *)")
            ask += [f"Bash({cmd} {h}*)" for h in HUMAN_DECISIONS]
        deny += ["Bash(claude -p *)", "Bash(claude --print *)", "Bash(claude --bg *)"]
    out = {"allow": _uniq(allow), "deny": _uniq(deny)}
    if ask:
        out["ask"] = _uniq(ask)
    return out


def _uniq(seq):
    seen, res = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x); res.append(x)
    return res


def effective(ws, actor):
    """Reglas de `.claude/settings.local.json` del actor ({} vacío si no existe) y su modo de fichero."""
    f = settings_file(ws, actor)
    try:
        d = json.load(open(f, encoding="utf-8")).get("permissions", {})
    except (OSError, ValueError):
        return {"allow": [], "ask": [], "deny": []}, None
    mode = os.stat(f).st_mode & 0o777
    return {k: list(d.get(k, [])) for k in ("allow", "ask", "deny")}, mode


# ---------------------------------------------------------------- matriz y diferencias

def matrix(ws, which="expected", components=None):
    """{actor: {destino: 'REW'|'Rxx'|...}} esperada o efectiva."""
    cols = destinations(ws)
    res = {}
    for actor in (components or ws.aliases()):
        if which == "expected":
            rules, root = expected(ws, actor), None
        else:
            rules, _ = effective(ws, actor)
            root = ws.path(actor)
        row = {name: cell(rules, probe, root) for name, probe in cols}
        res[actor] = row
    return res


def _level(c):
    return {"R": "allow", "E": "allow", "W": "allow", "r": "ask", "e": "ask", "w": "ask", "x": "deny"}.get(c, None)


def diff(ws, actor):
    """Desviaciones del actor: lista de (tipo, detalle). Tipos: missing weaker extra stronger legacy duplicate obsolete mode bash-missing."""
    items = []
    exp = expected(ws, actor)
    eff, mode = effective(ws, actor)
    f = settings_file(ws, actor)
    root = ws.path(actor)
    if mode is None:
        return [("missing", f"falta {os.path.relpath(f, ws.root)}")]
    ce, cf = matrix(ws, "expected", [actor])[actor], matrix(ws, "effective", [actor])[actor]
    for name, _ in destinations(ws):
        for i, t in enumerate(TOOLS):
            e, g = _level(ce[name][i]), _level(cf[name][i])
            if e == g:
                continue
            if e == "allow" and g is None:
                k = "missing"
            elif e == "allow":
                k = "weaker"
            elif e == "deny":
                k = "stronger" if g == "allow" else "missing"
            elif g == "allow":
                k = "extra" if e is None else "stronger"
            else:
                continue
            items.append((k, f"{name}:{t} esperado {ce[name]} efectivo {cf[name]}"))
    allrules = [("allow", r) for r in eff["allow"]] + [("ask", r) for r in eff["ask"]] + [("deny", r) for r in eff["deny"]]
    seen = set()
    for kind, r in allrules:
        if (kind, r) in seen:
            items.append(("duplicate", f"{kind} {r}"))
        seen.add((kind, r))
        if is_legacy(ws, r, root):
            items.append(("legacy", f"{kind} {r}: `/ruta` es relativa a la raíz del repo; usa `//ruta` absoluta"))
        if kind == "deny" and r.startswith("Write("):
            items.append(("obsolete", f"deny {r}: Edit ya cubre Write"))
    for kind in ("allow", "ask", "deny"):
        for r in exp.get(kind, []):
            if not RULE_RX.match(r) and r not in eff[kind]:
                items.append(("bash-missing", f"{kind} {r}"))
    if mode != 0o600:
        items.append(("mode", f"{oct(mode)[2:]} (esperado 600)"))
    return items


STATUS_OF = {"missing": "FAIL", "weaker": "FAIL", "bash-missing": "FAIL", "stronger": "WARN", "extra": "WARN", "legacy": "WARN",
             "duplicate": "WARN", "obsolete": "WARN", "mode": "WARN"}


def status_report(ws, components=None, skill="rew-grants"):
    rep = output.Report("arkana-workspace", skill)
    for a in (components or ws.aliases()):
        if not os.path.isdir(ws.path(a)):
            rep.add("WARN", f"perm:{a}", "la carpeta no existe", component=a)
            continue
        its = diff(ws, a)
        if not its:
            rep.add("OK", f"perm:{a}", "permisos conformes al modelo", component=a)
        for k, d in its:
            rep.add(STATUS_OF[k], f"perm:{a}:{k}", d, component=a)
    return rep


# ---------------------------------------------------------------- aplicar

def apply(ws, actor, dry=False, prune=False):
    """Añade lo que falta (sin quitar reglas ajenas); con prune quita además las que dan más de lo esperado. Devuelve (cambios, ruta)."""
    exp = expected(ws, actor)
    eff, mode = effective(ws, actor)
    f = settings_file(ws, actor)
    root = ws.path(actor)
    new = {k: list(eff[k]) for k in ("allow", "ask", "deny")}
    changes = []
    # limpieza: duplicados, reglas legacy sin efecto y deny Write redundantes
    for kind in new:
        seen, keep = set(), []
        for r in new[kind]:
            drop = r in seen or is_legacy(ws, r, root) or (kind == "deny" and r.startswith("Write("))
            if drop:
                changes.append(("quitar", kind, r))
            else:
                keep.append(r)
            seen.add(r)
        new[kind] = keep
    if prune:
        cf = matrix(ws, "effective", [actor])  # noqa: F841 (la comparación se hace regla a regla abajo)
        ce = matrix(ws, "expected", [actor])[actor]
        for name, probe in destinations(ws):
            for i, t in enumerate(TOOLS):
                if _level(ce[name][i]) in (None, "deny", "ask") and decide({"allow": new["allow"]}, t, probe, root) == "allow":
                    for r in list(new["allow"]):
                        p = parse(r, root)
                        if p and covers(p[0], t) and (probe == p[1] or (p[2] and probe.startswith(p[1].rstrip("/") + "/"))) and p[1] != os.path.expanduser("~/.claude/settings.json"):
                            new["allow"].remove(r); changes.append(("quitar", "allow", r))
    for kind in ("allow", "ask", "deny"):
        for r in exp.get(kind, []):
            if r in new[kind]:
                continue
            p = parse(r, root)
            if p:
                probe = p[1] + ("/x" if p[2] else "")
                if decide(new, p[0], probe, root) == kind:
                    continue
                if kind == "allow" and decide(new, p[0], probe, root) in ("deny", "ask"):
                    continue            # lo tapa una regla más fuerte: se informa en diff, no se añade
            new[kind].append(r); changes.append(("añadir", kind, r))
    if not changes and mode == 0o600:
        return [], f
    if dry:
        return changes + ([("modo", "", "600")] if mode not in (None, 0o600) else []), f
    d = {}
    try:
        d = json.load(open(f, encoding="utf-8"))
    except OSError:
        pass
    if os.path.isfile(f):
        import shutil, time
        bak = os.path.join(ws.state, "arkana-workspace", "bak")
        os.makedirs(bak, exist_ok=True)
        shutil.copy2(f, os.path.join(bak, f"{actor}-settings.local.json.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"))
    perm = d.setdefault("permissions", {})
    for k in ("allow", "ask", "deny"):
        if new[k] or k in perm:
            perm[k] = new[k]
    datafiles.atomic_write_json(f, d, mode=0o600)
    return changes, f


# ---------------------------------------------------------------- presentación

def shown(c):
    """Celda para mostrar: solo las letras concedidas o en `ask` (`Rxx` → `R`, `R··` → `R`, `xxx` → vacío). La matriz interna y el --json conservan la cadena completa."""
    return c.replace("x", "").replace("·", "")


def render_matrix(ws, which, fmt_="text", components=None):
    cols = [n for n, _ in destinations(ws)]
    m = matrix(ws, which, components)
    if fmt_ == "md":
        out = ["| actor \\ destino | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        out += [f"| {manifest.display(a)} | " + " | ".join(f"`{shown(row[c])}`" if shown(row[c]) else "" for c in cols) + " |" for a, row in m.items()]
        return "\n".join(out) + "\n"
    w = max(len(c) for c in cols + ["actor"]) + 1
    lines = ["actor".ljust(w) + " ".join(c.ljust(max(4, len(c))) for c in cols)]
    lines += [manifest.display(a).ljust(w) + " ".join(shown(row[c]).ljust(max(4, len(c))) for c in cols) for a, row in m.items()]
    return "\n".join(lines).rstrip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="permissions.py")
    ap.add_argument("cmd", choices=["expected", "effective", "matrix", "diff", "status", "apply"])
    ap.add_argument("--component", action="append")
    ap.add_argument("--home")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--format", choices=["text", "md"], default="text")
    ap.add_argument("--effective", action="store_true")
    ap.add_argument("--expected", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true")
    a = ap.parse_args(argv)
    try:
        ws = manifest.load(os.path.realpath(a.home) if a.home else None)
        comps = [manifest.canon(c) for c in a.component] if a.component else None
        for c in comps or []:
            ws.get(c)
    except (manifest.ManifestError, KeyError) as e:
        print(f"FAIL|workspace|{e}", file=sys.stderr)
        return 3
    if a.cmd in ("expected", "effective"):
        res = {c: (expected(ws, c) if a.cmd == "expected" else effective(ws, c)[0]) for c in (comps or ws.aliases())}
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    if a.cmd == "matrix":
        which = "effective" if a.effective and not a.expected else "expected"
        if a.json:
            print(json.dumps(matrix(ws, which, comps), indent=2, ensure_ascii=False))
        else:
            sys.stdout.write(render_matrix(ws, which, a.format, comps))
        return 0
    if a.cmd in ("diff", "status"):
        rep = status_report(ws, comps)
        sys.stdout.write(rep.render(a.json))
        return rep.exit_code()
    rep = output.Report("arkana-workspace", "permissions-apply")
    for c in comps or ws.aliases():
        if not os.path.isdir(ws.path(c)):
            rep.add("WARN", f"perm:{c}", "la carpeta no existe", component=c)
            continue
        changes, f = apply(ws, c, a.dry_run, a.prune)
        if not changes:
            rep.add("OK", f"perm:{c}", "permisos ya completos", component=c)
        else:
            rep.add("DRY" if a.dry_run else "OK", f"perm:{c}", f"{len(changes)} cambios en {os.path.relpath(f, ws.root)}", component=c)
            for acc, kind, r in changes:
                rep.add("INFO", f"perm:{c}:{acc}", f"{kind} {r}", component=c)
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
