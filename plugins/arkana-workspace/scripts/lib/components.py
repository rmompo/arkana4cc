#!/usr/bin/env python3
"""Gestión de los componentes del manifiesto (`core/workspace.json`): list, add, edit, remove.

  components.py list   [--json]
  components.py add    --alias A --path RUTA [--type node|maven|docs|generic] [--remote URL] [--main M] [--develop D]
                      [--git-user U --git-email E] [--git-email-domain D]... [--commit-format F] [--token-ref CLAVE] [--git-username U] [--vpn|--no-vpn]
                      [--statusline|--no-statusline] [--tool-version tool=ver]... [--tool-path tool=ruta]... [--seed-file CLAUDE.md|CLAUDE.local.md]
  components.py edit   --alias A  (mismas opciones que add; solo se cambia lo indicado). `--alias arkana` edita ARKANA: su `--commit-format`,
                      `--git-email-domain`, remoto, ramas, `--token-ref`/`--git-username` y `--seed-file` (no admite --type, --path, --vpn, --statusline ni --tool-*)
  components.py remove --alias A  [--yes]
  Opciones comunes: --home DIR  --dry-run  --json

`--path` se da absoluta o relativa a la raíz del workspace y se guarda relativa. La identidad git (user/email) y las rutas absolutas van
a `local.json`, no al manifiesto exportable. `--git-email-domain` (repetible) fija los dominios de correo que debe tener el autor de los commits del
componente (`git.email_domains`); sin ella no hay regla. Cada cambio deja copia .bak del manifiesto y valida el resultado. Nunca se aceptan secretos en argumentos: `--token-ref` es solo el NOMBRE de la clave.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import datafiles, locate, manifest, output  # noqa: E402


def _load(home):
    path = os.path.join(locate.state_dir(home), manifest.WORKSPACE_JSON)
    return path, json.loads(Path(path).read_text(encoding="utf-8"))


def _rel(ws_root, p):
    p = os.path.expanduser(p)
    p = p if os.path.isabs(p) else os.path.join(ws_root, p)
    return os.path.relpath(os.path.realpath(p), ws_root)


def _kv(items, what):
    res = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError(f"{what}: se espera nombre=valor ({it!r})")
        k, v = it.split("=", 1)
        res[k] = v
    return res


def apply_options(block, a, root):
    if a.type:
        block["type"] = a.type
    if a.path:
        block["path"] = _rel(root, a.path)
    if a.remote:
        block["remote"] = a.remote
        import re
        m = re.match(r"^\w+://(?:[^/@]*@)?([^/:]+)", a.remote)
        if m:
            block["remote_host"] = m.group(1)
        if "@" in a.remote.split("://", 1)[-1].split("/", 1)[0]:
            raise ValueError("--remote no puede llevar usuario ni contraseña en la URL")
    if a.main or a.develop:
        b = block.setdefault("branches", {})
        b["main"] = a.main or b.get("main", "main")
        b["develop"] = a.develop or b.get("develop", "develop")
    if a.commit_format:
        block["commit_format"] = a.commit_format
    if a.token_ref or a.git_username or a.git_email_domain:
        g = block.setdefault("git", {})
        if a.token_ref:
            g["token_ref"] = a.token_ref
        if a.git_username:
            g["username"] = a.git_username
        if a.git_email_domain:
            g["email_domains"] = [d.lstrip("@") for d in a.git_email_domain]
    if a.vpn is not None:
        block["vpn"] = a.vpn
    if a.seed_file:
        block["seed_file"] = a.seed_file
    if a.statusline is not None:
        block["statusline"] = a.statusline
    tv, tp = _kv(a.tool_version, "--tool-version"), _kv(a.tool_path, "--tool-path")
    if tv:
        tools = {t["tool"]: t for t in block.get("tools", [])}
        for k, v in tv.items():
            tools[k] = {"tool": k, "version": v}
        block["tools"] = list(tools.values())
    return tp


def _local(home):
    try:
        return json.loads(Path(os.path.join(locate.state_dir(home), manifest.LOCAL_JSON)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(home, path, data, dry):
    errs = manifest.validate(data)
    if errs:
        raise ValueError("; ".join(errs[:3]))
    if dry:
        return
    bak = os.path.join(locate.state_dir(home), "arkana-workspace", "bak")
    os.makedirs(bak, exist_ok=True)
    shutil.copy2(path, os.path.join(bak, "workspace.json." + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())))
    datafiles.atomic_write_json(path, data)


def update_local(home, alias, tool_paths, git_user, git_email, dry, new_abs_path=None):
    if dry or not (tool_paths or git_user or git_email or new_abs_path):
        return
    p = os.path.join(locate.state_dir(home), manifest.LOCAL_JSON)
    d = _local(home) or {"schema_version": 1}
    if new_abs_path and alias in d.get("paths", {}):          # una ruta fijada en local.json manda sobre el manifiesto: se mantiene coherente
        d["paths"][alias] = new_abs_path
    if git_user or git_email:
        g = d.setdefault("git", {}).setdefault(alias, {})
        if git_user:
            g["name"] = git_user
        if git_email:
            g["email"] = git_email
    for t, tp in tool_paths.items():
        d.setdefault("tool_paths", {}).setdefault(alias, {})[t] = tp
    datafiles.atomic_write_json(p, d, mode=0o644)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="components.py")
    ap.add_argument("cmd", choices=["list", "add", "edit", "remove"])
    ap.add_argument("--alias")
    ap.add_argument("--path")
    ap.add_argument("--type", choices=list(manifest.TYPES))
    ap.add_argument("--remote")
    ap.add_argument("--main")
    ap.add_argument("--develop")
    ap.add_argument("--git-user")
    ap.add_argument("--git-email")
    ap.add_argument("--git-username")
    ap.add_argument("--git-email-domain", action="append")
    ap.add_argument("--commit-format")
    ap.add_argument("--token-ref")
    ap.add_argument("--vpn", dest="vpn", action="store_true", default=None)
    ap.add_argument("--no-vpn", dest="vpn", action="store_false")
    ap.add_argument("--statusline", dest="statusline", action="store_true", default=None)
    ap.add_argument("--no-statusline", dest="statusline", action="store_false")
    ap.add_argument("--tool-version", action="append")
    ap.add_argument("--tool-path", action="append")
    ap.add_argument("--seed-file", choices=["CLAUDE.md", "CLAUDE.local.md"])
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--home")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    home = os.path.realpath(a.home) if a.home else locate.find_home()
    rep = output.Report("arkana-workspace", f"component-{a.cmd}")
    if not home:
        print("FAIL|workspace|no se encontró un workspace de Arkana", file=sys.stderr)
        return 3
    try:
        path, data = _load(home)
        root = locate.workspace_root(home)
        alias = manifest.canon(a.alias) if a.alias else None
        if a.cmd == "list":
            ws = manifest.load(home)
            for al in ws.aliases():
                b = ws.get(al)
                rep.add("INFO", al, f"{b.get('type', 'arkana')} {os.path.relpath(ws.path(al), root)} {b.get('remote_host', '-')}", component=al)
        elif a.cmd == "add":
            if not alias or not a.path:
                raise ValueError("add necesita --alias y --path")
            if any(c["alias"] == alias for c in data["components"]) or alias in manifest.RESERVED or alias in manifest.SYNONYMS:
                raise ValueError(f"el alias {alias!r} ya existe o está reservado")
            block = {"alias": alias, "type": a.type or "generic", "path": ""}
            tp = apply_options(block, a, root)
            data["components"].append(block)
            save(home, path, data, a.dry_run)
            update_local(home, alias, tp, a.git_user, a.git_email, a.dry_run)
            rep.add("DRY" if a.dry_run else "OK", alias, f"componente añadido en {block['path']}", component=alias)
        elif a.cmd == "edit":
            if alias == "arkana":                                             # ARKANA también tiene sus directrices de commit, su remoto y su identidad git
                solo_componentes = [o for o, v in (("--type", a.type), ("--path", a.path), ("--vpn/--no-vpn", a.vpn), ("--statusline/--no-statusline", a.statusline), ("--tool-version", a.tool_version), ("--tool-path", a.tool_path)) if v is not None]
                if solo_componentes:
                    raise ValueError(f"{', '.join(solo_componentes)} no se aplica a ARKANA (solo a los componentes)")
                block = data["arkana"]
            else:
                block = next((c for c in data["components"] if c["alias"] == alias), None)
            if block is None:
                raise ValueError(f"no existe el componente {a.alias!r}")
            tp = apply_options(block, a, root)
            update_local(home, alias, tp, a.git_user, a.git_email, a.dry_run, os.path.realpath(os.path.join(root, block["path"])) if a.path else None)
            save(home, path, data, a.dry_run)
            rep.add("DRY" if a.dry_run else "OK", alias, "componente actualizado", component=alias)
        elif a.cmd == "remove":
            if not any(c["alias"] == alias for c in data["components"]):
                raise ValueError(f"no existe el componente {a.alias!r}")
            if not (a.yes or a.dry_run):
                raise ValueError("remove pide confirmación explícita: --yes (no borra la carpeta ni el repo, solo lo quita del manifiesto)")
            data["components"] = [c for c in data["components"] if c["alias"] != alias]
            save(home, path, data, a.dry_run)
            rep.add("DRY" if a.dry_run else "OK", alias, "componente quitado del manifiesto (la carpeta no se toca)", component=alias)
    except (ValueError, OSError, KeyError, manifest.ManifestError) as e:
        rep.add("FAIL", a.cmd, str(e))
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
