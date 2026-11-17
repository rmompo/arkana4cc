#!/usr/bin/env python3
"""Gestión de los componentes del manifiesto (`core/workspace.json`): list, add, edit, remove.

  components.py list   [--json]
  components.py add    --alias A --path RUTA [--type node|maven|docs|generic] [--remote URL] [--main M] [--develop D]
                      [--git-user U --git-email E] [--git-email-domain D]... [--commit-format F] [--token-ref CLAVE] [--git-username U] [--vpn|--no-vpn]
                      [--statusline|--no-statusline] [--watch|--no-watch] [--tool-version tool=ver]... [--tool-path tool=ruta]...
  components.py edit   --alias A  (mismas opciones que add; solo se cambia lo indicado). `--alias arkana` edita ARKANA: su `--commit-format`,
                      `--git-email-domain`, remoto, ramas, `--token-ref`/`--git-username` (no admite --type, --path, --vpn, --statusline, --watch ni --tool-*; en un componente
                      sí se pueden cambiar en cualquier momento, también `--statusline/--no-statusline` y `--watch/--no-watch`)
  components.py edit   --alias A --rename NUEVO   cambia el ALIAS de un componente (su id no cambia): manifiesto, `local.json`, registro del proyecto y los datos
                      locales de los plugins que declaren `rename` en su contrato. Los documentos compartidos referencian por id y no se tocan.
  components.py remove --alias A  [--yes]
  Opciones comunes: --home DIR  --dry-run  --json  [--plugins-dir DIR]

`--statusline|--no-statusline` muestra u oculta el componente en la barra de estado; `--watch|--no-watch` hace que cuenten o no sus cambios (◌ ✚ ● y ⇣) en la barra, en `status` y en el
BRIEF. Son ejes independientes: un componente puede estar oculto pero vigilado, o visible y sin vigilar. Al guardar cualquiera de los campos de esquema 2 (`watch`…) el manifiesto
pasa a `schema: 2`; si la copia de la statusline (`~/.claude/arkana-statusline/`) es anterior, se avisa de que hay que ejecutar `/arkana-statusline:fix`.

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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "_core"))
from arkana_core import contract, datafiles, locate, manifest, output, project  # noqa: E402
import proc  # noqa: E402


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
    if a.statusline is not None:
        block["statusline"] = a.statusline
    if a.watch is not None:
        block["watch"] = a.watch
    tv, tp = _kv(a.tool_version, "--tool-version"), _kv(a.tool_path, "--tool-path")
    if tv:
        tools = {t["tool"]: t for t in block.get("tools", [])}
        for k, v in tv.items():
            tools[k] = {"tool": k, "version": v}
        block["tools"] = list(tools.values())
    return tp


def aviso_statusline(rep, a):
    """WARN si ESTA llamada escribe campos de esquema 2 y la copia de la statusline instalada es anterior (no los entendería: «workspace no cargado»)."""
    if a.watch is None:                                                  # (B añadirá aquí --mode, --ref y --checks-skip)
        return
    old = statusline_copy_outdated()
    if old:
        rep.add("WARN", "statusline", f"la copia de la statusline (~/.claude/arkana-statusline) lleva el núcleo {old} y no conoce los campos nuevos del manifiesto: ejecuta /arkana-statusline:fix")


def _local(home):
    try:
        return json.loads(Path(os.path.join(locate.state_dir(home), manifest.LOCAL_JSON)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def stamp_schema(data):
    """Un manifiesto que usa campos de esquema 2 lo declara (`schema: 2`): las versiones anteriores lo rechazan con un aviso claro en lugar de una lista de claves sobrantes."""
    if any(k in c for c in data.get("components", []) for k in manifest.NEW_FIELDS) and data.get("schema", 1) < manifest.KNOWN_SCHEMA:
        data["schema"] = manifest.KNOWN_SCHEMA


def statusline_copy_outdated():
    """Versión del núcleo de la copia de la statusline si es anterior a la de este plugin (o None): esa copia no conocería los campos nuevos del manifiesto."""
    import re
    f = os.path.join(os.path.expanduser("~"), ".claude", "arkana-statusline", "arkana_core", "__init__.py")
    try:
        m = re.search(r'CORE_VERSION\s*=\s*"([\d.]+)"', Path(f).read_text(encoding="utf-8"))
    except OSError:
        return None
    if not m:
        return None
    ver = lambda v: tuple(int(x) for x in v.split("."))
    from arkana_core import CORE_VERSION
    return m.group(1) if ver(m.group(1)) < ver(CORE_VERSION) else None


def save(home, path, data, dry):
    stamp_schema(data)
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


def rename_local(home, old, new, dry):
    """Renombra el alias en las claves de `local.json` (rutas, identidad git y rutas de herramientas)."""
    p = os.path.join(locate.state_dir(home), manifest.LOCAL_JSON)
    d = _local(home)
    ch = False
    for k in ("paths", "git", "tool_paths"):
        if isinstance(d.get(k), dict) and old in d[k]:
            d[k][new] = d[k].pop(old)
            ch = True
    if ch and not dry:
        datafiles.atomic_write_json(p, d, mode=0o644)
    return ch


def rename_hooks(rep, plugins_dir, home, old, new, dry):
    """Ejecuta el comando `rename` que cada plugin declara en su contrato (reescribe SUS datos locales); una línea ESTADO|ID|detalle por resultado."""
    if not os.path.isdir(plugins_dir):
        return
    for name in sorted(os.listdir(plugins_dir)):
        pdir = os.path.join(plugins_dir, name)
        if name == "arkana-workspace" or not os.path.isfile(os.path.join(pdir, contract.CONTRACT_FILE)):
            continue
        try:
            c = contract.load(pdir)
        except contract.ContractError as e:
            rep.add("FAIL", f"{name}:contrato", str(e))
            continue
        if not c.get("rename"):
            continue
        cmd = f"{c['rename']} --from {old} --to {new}" + (" --dry-run" if dry else "")
        rc, out = proc.run(["bash", "-c", cmd], 120, dict(os.environ, ARKANA_HOME=home, CLAUDE_PLUGIN_ROOT=pdir), cwd=pdir)
        n = 0
        for l in out.splitlines():
            p = l.split("|", 2)
            if len(p) == 3 and p[0] in output.STATUSES:
                rep.add(p[0], f"{name}:{p[1]}", p[2]); n += 1
        if rc != 0 and not n:
            rep.add("FAIL", f"{name}:rename", "el comando de renombrado falló sin salida en el formato común")


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
    ap.add_argument("--watch", dest="watch", action="store_true", default=None)
    ap.add_argument("--no-watch", dest="watch", action="store_false")
    ap.add_argument("--tool-version", action="append")
    ap.add_argument("--tool-path", action="append")
    ap.add_argument("--rename")
    ap.add_argument("--plugins-dir")
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
            if any(c["alias"] == alias for c in data["components"]) or alias in manifest.RESERVED:
                raise ValueError(f"el alias {alias!r} ya existe o está reservado")
            block = {"alias": alias, "type": a.type or "generic", "path": ""}
            reg = project.Registry.load(home)
            if reg.present:                                                    # con registro, el componente nace con su id (inmutable)
                block["id"] = reg.id_of(alias) or project.new_id()
            tp = apply_options(block, a, root)
            data["components"].append(block)
            save(home, path, data, a.dry_run)
            update_local(home, alias, tp, a.git_user, a.git_email, a.dry_run)
            if reg.present and not a.dry_run:
                project.add_component(home, alias, cid=block["id"])
            rep.add("DRY" if a.dry_run else "OK", alias, f"componente añadido en {block['path']}" + (f" (id {block['id'][:8]}…)" if block.get("id") else ""), component=alias)
            aviso_statusline(rep, a)
        elif a.cmd == "edit":
            if alias == "arkana":                                             # ARKANA también tiene sus directrices de commit, su remoto y su identidad git
                solo_componentes = [o for o, v in (("--type", a.type), ("--path", a.path), ("--vpn/--no-vpn", a.vpn), ("--statusline/--no-statusline", a.statusline), ("--watch/--no-watch", a.watch), ("--tool-version", a.tool_version), ("--tool-path", a.tool_path)) if v is not None]
                if solo_componentes:
                    raise ValueError(f"{', '.join(solo_componentes)} no se aplica a ARKANA (solo a los componentes)")
                block = data["arkana"]
            else:
                block = next((c for c in data["components"] if c["alias"] == alias), None)
            if block is None:
                raise ValueError(f"no existe el componente {a.alias!r}")
            new = None
            if a.rename:
                new = manifest.canon(a.rename)
                if alias == "arkana":
                    raise ValueError("ARKANA no se renombra")
                if not manifest.ALIAS_RX.match(new) or new in manifest.RESERVED:
                    raise ValueError(f"alias no válido o reservado: {a.rename!r}")
                if new != alias and any(c["alias"] == new for c in data["components"]):
                    raise ValueError(f"ya existe un componente llamado {new}")
                block["alias"] = new
                if new != alias and not a.dry_run:                             # ensayo previo: si algún plugin no puede renombrar ahora, no se cambia nada
                    pre = output.Report("arkana-workspace", "rename-ensayo")
                    rename_hooks(pre, os.path.realpath(a.plugins_dir) if a.plugins_dir else os.path.join(home, "plugins"), home, alias, new, True)
                    fallos = [i for i in pre.items if i["status"] == "FAIL"]
                    if fallos:
                        raise ValueError("el renombrado no es posible ahora (no se ha cambiado nada): " + "; ".join(f"{i['id']}: {i['detail']}" for i in fallos[:3]))
            tp = apply_options(block, a, root)
            target = new or alias
            if new and new != alias:
                reg = project.Registry.load(home)
                if reg.present and (reg.id_of(alias) or reg.id_of(new)) and not a.dry_run:
                    project.rename_component(home, alias, new)                 # el id no cambia: los documentos compartidos siguen valiendo
                    block.setdefault("id", reg.id_of(alias) or reg.id_of(new))
                elif reg.present and block.get("id") is None:
                    block["id"] = reg.id_of(alias) or reg.id_of(new)
            if new and new != alias:
                rename_local(home, alias, new, a.dry_run)                      # antes que update_local: las claves nuevas no deben pisarse
            update_local(home, target, tp, a.git_user, a.git_email, a.dry_run, os.path.realpath(os.path.join(root, block["path"])) if a.path else None)
            save(home, path, data, a.dry_run)
            if new and new != alias:
                rep.add("DRY" if a.dry_run else "OK", target, f"alias {alias} → {new} en el manifiesto y en local.json", component=target)
                rename_hooks(rep, os.path.realpath(a.plugins_dir) if a.plugins_dir else os.path.join(home, "plugins"), home, alias, new, a.dry_run)
            else:
                rep.add("DRY" if a.dry_run else "OK", alias, "componente actualizado", component=alias)
            aviso_statusline(rep, a)
        elif a.cmd == "remove":
            if not any(c["alias"] == alias for c in data["components"]):
                raise ValueError(f"no existe el componente {a.alias!r}")
            if not (a.yes or a.dry_run):
                raise ValueError("remove pide confirmación explícita: --yes (no borra la carpeta ni el repo, solo lo quita del manifiesto)")
            data["components"] = [c for c in data["components"] if c["alias"] != alias]
            save(home, path, data, a.dry_run)
            if not a.dry_run and project.Registry.load(home).present:
                project.retire_component(home, alias)                          # el id se conserva (retirado) para que las referencias sigan mostrándose
            rep.add("DRY" if a.dry_run else "OK", alias, "componente quitado del manifiesto (la carpeta no se toca)", component=alias)
    except (ValueError, OSError, KeyError, manifest.ManifestError) as e:
        rep.add("FAIL", a.cmd, str(e))
    sys.stdout.write(rep.render(a.json))
    return rep.exit_code()


if __name__ == "__main__":
    sys.exit(main())
