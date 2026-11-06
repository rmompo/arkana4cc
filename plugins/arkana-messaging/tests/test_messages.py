"""arkana-messaging: put/get/delete/sync/reconcile/adopt sobre el almacén local. Quién actúa lo decide el cwd; ARKANA lo ve todo."""
import json
import os
import unittest

from lab import Lab


class TestPut(unittest.TestCase):
    def test_actor_por_cwd_destinatarios_y_almacen_local(self):
        with Lab() as lab:
            nid = lab.put("api", asunto="Cambia el contrato del endpoint", to="app,app-web")
            m = lab.msg(nid)
            self.assertEqual((m["de"], m["para"], m["tipo"]), ("api", ["app", "app-web"], "notice"))
            self.assertNotIn("estado", m)
            self.assertEqual(m["updated"], m["fecha"])
            idx = lab.jload(lab.store("index.json"))
            self.assertEqual(idx["messages"][nid]["de"], "api")
            self.assertEqual(os.listdir(lab.store("messages")), [nid + ".json"])

    def test_all_excluye_al_remitente_y_arkana_se_nombra(self):
        with Lab() as lab:
            a = lab.msg(lab.put("app", to="all"))
            self.assertEqual(a["para"], ["all"])                                              # lo escrito se conserva
            self.assertEqual(a["destinatarios"], ["api", "app-web", "arkana"])            # la foto de los destinatarios reales
            b = lab.msg(lab.put("app", to="arkana"))
            self.assertEqual((b["para"], b["destinatarios"]), (["arkana"], ["arkana"]))
            r = lab.run("app", "put", "--type", "notice", "--subject", "Solo yo mismo", "--to", "app")
            self.assertEqual(r.returncode, 2)

    def test_precondiciones_sin_componente_y_validaciones(self):
        with Lab() as lab:
            r = lab.run("fuera", "put", "--type", "notice", "--subject", "Desde ningún sitio")
            self.assertEqual(r.returncode, 3, r.stdout)
            self.assertIn("ningún componente", r.stdout)
            for args, txt in ((("--type", "task", "--subject", "Sin instrucciones"), "instructions"),
                              (("--type", "notice", "--subject", "x"), "asunto"),
                              (("--type", "notice", "--subject", "Destino inventado", "--to", "nadie"), "destinatario desconocido"),
                              (("--type", "question", "--subject", "Corta"), "question")):
                r = lab.run("app", "put", *args)
                self.assertEqual(r.returncode, 2, args)
                self.assertIn(txt, r.stdout)
            self.assertFalse(os.path.isdir(lab.store("messages")) and os.listdir(lab.store("messages")))

    def test_tarea_completa_dry_run_y_prioridad(self):
        with Lab() as lab:
            ins = lab.file("i.txt", "Haz A\nHaz B\n")
            cri = lab.file("c.txt", "Compila\n")
            r = lab.run("arkana", "put", "--type", "task", "--subject", "Adaptar el cliente", "--to", "api", "--instructions-file", ins,
                        "--criteria-file", cri, "--priority", "high", "--dry-run")
            self.assertIn("DRY|put", r.stdout)
            self.assertFalse(os.path.isdir(lab.store("messages")))
            nid = lab.put("arkana", "task", "Adaptar el cliente", "api", ("--instructions-file", ins, "--criteria-file", cri, "--priority", "high"))
            m = lab.msg(nid)
            self.assertEqual((m["estado"], m["instrucciones"], m["criterios"], m["prioridad"]), ("open", ["Haz A", "Haz B"], ["Compila"], "high"))

    def test_cerrar_comentar_e_idempotencia(self):
        with Lab() as lab:
            ins, cri = lab.file("i.txt", "Haz A\n"), lab.file("c.txt", "Ok\n")
            nid = lab.put("arkana", "task", "Adaptar el cliente", "api", ("--instructions-file", ins, "--criteria-file", cri))
            self.assertEqual(lab.run("app", "put", "--done", nid, "--result", "no es mío").returncode, 1)        # app no ve lo de api
            self.assertEqual(lab.run("api", "put", "--comment", nid, "--note", "empiezo").returncode, 0)
            r = lab.run("api", "put", "--done", nid, "--result", "hecho y compilado")
            self.assertIn("marcada como done", r.stdout)
            self.assertIn("ya estaba done", lab.run("api", "put", "--done", nid, "--result", "otra vez").stdout)
            r = lab.run("api", "put", "--discard", nid, "--reason", "ya no")
            self.assertEqual(r.returncode, 1)
            m = lab.msg(nid)
            self.assertEqual((m["estado"], m["resultado"]), ("done", "hecho y compilado"))
            self.assertEqual([h["accion"] for h in m["historial"]], ["created", "comment", "done"])
            n = lab.put("app", "notice", "Un aviso cualquiera", "arkana")
            self.assertEqual(lab.run("arkana", "put", "--done", n, "--result", "x").returncode, 1)               # un notice no tiene estado

    def test_cuatro_publicaciones_a_la_vez_y_cuatro_comentarios_se_conservan(self):
        with Lab() as lab:
            ps = [lab.popen("api", "put", "--type", "notice", "--subject", f"Aviso concurrente {i}", "--to", "app") for i in range(4)]
            for p in ps:
                out, err = p.communicate(timeout=60)
                self.assertEqual(p.returncode, 0, out + err)
            ids = [f[:-5] for f in os.listdir(lab.store("messages"))]
            self.assertEqual(len(ids), 4)
            ins, cri = lab.file("i.txt", "a\n"), lab.file("c.txt", "b\n")
            nid = lab.put("arkana", "task", "Tarea con comentarios", "api", ("--instructions-file", ins, "--criteria-file", cri))
            cs = [lab.popen("api", "put", "--comment", nid, "--note", f"nota {i}") for i in range(4)]
            for p in cs:
                p.communicate(timeout=60)
                self.assertEqual(p.returncode, 0)
            notas = sorted(h["nota"] for h in lab.msg(nid)["historial"] if h["accion"] == "comment")
            self.assertEqual(notas, [f"nota {i}" for i in range(4)])
            self.assertEqual(len(lab.jload(lab.store("index.json"))["messages"]), 5)


class TestGetYBorrado(unittest.TestCase):
    def test_visibilidad_filtros_y_pendientes(self):
        with Lab() as lab:
            ins, cri = lab.file("i.txt", "a\n"), lab.file("c.txt", "b\n")
            t = lab.put("arkana", "task", "Tarea para el backend", "api", ("--instructions-file", ins, "--criteria-file", cri))
            n = lab.put("app", "notice", "Aviso a todos los demás", "all")
            self.assertEqual({m["id"] for m in lab.get("arkana")}, {t, n})                         # ARKANA lo ve todo
            self.assertEqual({m["id"] for m in lab.get("api")}, {t, n})
            self.assertEqual({m["id"] for m in lab.get("app-web")}, {n})                           # app-web solo lo dirigido a él
            self.assertEqual([m["id"] for m in lab.get("api", "--pending")], [t])
            self.assertEqual(lab.get("app-web", "--pending"), [])
            self.assertEqual([m["id"] for m in lab.get("arkana", "--from", "app")], [n])
            self.assertEqual([m["id"] for m in lab.get("arkana", "--to", "api", "--type", "task")], [t])
            tabla = lab.run("api", "get").stdout
            self.assertIn("ESTADO", tabla)
            self.assertIn("Tarea para el backend", tabla)
            self.assertIn("arkana→api", tabla)
            det = lab.run("api", "get", "--detail", t).stdout
            self.assertIn("Instrucciones:", det)
            self.assertEqual(lab.run("app-web", "get", "--detail", t).returncode, 1)
            self.assertIn("no hay comunicaciones pendientes", lab.run("app-web", "get", "--pending").stdout)

    def test_borrado_logico_permisos_y_marca(self):
        with Lab() as lab:
            n = lab.put("app", "notice", "Aviso que se borrará", "api")
            self.assertEqual(lab.run("api", "delete", n).returncode, 1)                       # un destinatario no borra lo ajeno
            self.assertEqual(lab.run("api", "delete", "--dry-run", n).returncode, 1)
            self.assertIn("DRY", lab.run("app", "delete", "--dry-run", n).stdout)
            self.assertEqual(lab.msg(n).get("estado"), None)
            self.assertEqual(lab.run("app", "delete", n).returncode, 0)                           # el autor sí
            self.assertIn("ya estaba borrada", lab.run("arkana", "delete", n).stdout)
            self.assertEqual(lab.get("api"), [])                                               # se ignora...
            self.assertEqual(lab.msg(n)["estado"], "deleted")                                      # ...pero queda la marca (viaja en sync/export)
            self.assertEqual([m["id"] for m in lab.get("arkana", "--include-hidden")], [n])
            m2 = lab.put("api", "notice", "Otro aviso para borrar", "app")
            self.assertEqual(lab.run("arkana", "delete", m2).returncode, 0)                        # ARKANA borra lo ajeno


def snapshot(root):
    """{ruta relativa: (tamaño, contenido)} de todo el almacén: para comprobar que una consulta no escribe nada."""
    res = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            res[os.path.relpath(p, root)] = open(p, "rb").read()
    return res


class TestQuery(unittest.TestCase):
    def q(self, lab, who, *a):
        r = lab.run(who, "query", *a)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_solo_muestra_id_remitente_asunto_y_destinatarios_sin_el_mensaje(self):
        with Lab() as lab:
            ins = lab.file("i.txt", "Cambia el cliente MUY SECRETO\n")
            t = lab.put("arkana", "task", "Adaptar el cliente al nuevo contrato", "api", ("--instructions-file", ins, "--criteria-file", lab.file("c.txt", "Compila\n")))
            out = self.q(lab, "api")
            for x in (t, "arkana", "api", "Adaptar el cliente al nuevo contrato"):
                self.assertIn(x, out)
            self.assertNotIn("MUY SECRETO", out)                                                # el mensaje no se expone
            self.assertNotIn("Compila", out)
            self.assertTrue(out.rstrip().endswith("usa /arkana-messaging:get --detail <id>."), out)           # al final: es de solo lectura y cómo consumir
            self.assertIn("solo lectura", out.splitlines()[-2])
            self.assertNotIn("solo lectura", self.q(lab, "api", "--json"))                          # el JSON no lleva el aviso: sigue siendo parseable
            js = json.loads(self.q(lab, "api", "--json"))
            self.assertEqual(js, [{"id": t, "de": "arkana", "asunto": "Adaptar el cliente al nuevo contrato", "para": ["api"]}])

    def test_detail_expone_tambien_el_mensaje(self):
        with Lab() as lab:
            ins = lab.file("i.txt", "Cambia el cliente MUY SECRETO\n")
            t = lab.put("arkana", "task", "Adaptar el cliente", "api", ("--instructions-file", ins, "--criteria-file", lab.file("c.txt", "Compila\n")))
            out = self.q(lab, "api", "--detail")
            self.assertIn("MUY SECRETO", out); self.assertIn("Compila", out)
            js = json.loads(self.q(lab, "api", "--detail", "--json"))[0]
            self.assertEqual((js["id"], js["instrucciones"], js["criterios"]), (t, ["Cambia el cliente MUY SECRETO"], ["Compila"]))

    def test_el_dry_run_de_put_hace_las_mismas_validaciones_que_la_ejecucion_real_y_no_escribe(self):
        with Lab() as lab:
            aviso = lab.put("app", "notice", "Aviso", "api")
            tarea = lab.put("arkana", "task", "Tarea", "api", ("--instructions-file", lab.file("i.txt", "a\n"), "--criteria-file", lab.file("c.txt", "b\n")))
            norma = lab.put("arkana", "notice", "Norma", "api", ("--repeat",))
            antes = snapshot(lab.store())

            for who, args in (("api", ("--done", aviso, "--result", "x")),                     # un notice no tiene estado
                              ("api", ("--done", norma, "--result", "x")),                      # un repeat no se cierra
                              ("api", ("--activate", norma)),                                   # solo ARKANA activa
                              ("arkana", ("--activate", tarea)),                                    # solo un repeat se activa
                              ("api", ("--delivered", tarea, "--for", "api"))):             # solo ARKANA anota entregas
                seco = lab.run(who, "put", *args, "--dry-run")
                self.assertEqual(snapshot(lab.store()), antes, args)                               # el ensayo no escribió nada
                real = lab.run(who, "put", *args)
                self.assertEqual((seco.returncode, seco.stdout.count("FAIL|")), (real.returncode, real.stdout.count("FAIL|")), args)   # y falla exactamente como la real
                self.assertNotEqual(seco.returncode, 0, args)
            ok = lab.run("api", "put", "--done", tarea, "--result", "hecho", "--dry-run")          # lo válido sigue saliendo como DRY y sin escribir
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertIn("DRY|put", ok.stdout)
            self.assertEqual(snapshot(lab.store()), antes)
            self.assertEqual(lab.msg(tarea)["estado"], "open")

    def test_detail_con_id_muestra_solo_ese_mensaje_con_su_texto_y_sigue_sin_marcarlo(self):
        with Lab() as lab:
            ins = lab.file("i.txt", "Texto del primero\n")
            a1 = lab.put("app", "notice", "Primero", "api", ("--instructions-file", ins))
            a2 = lab.put("app-web", "notice", "Segundo", "api", ("--instructions-file", lab.file("j.txt", "Texto del segundo\n")))
            antes = snapshot(lab.store())
            out = self.q(lab, "api", "--detail", a1)
            self.assertIn("Texto del primero", out); self.assertIn(a1, out)
            self.assertNotIn(a2, out); self.assertNotIn("Texto del segundo", out)                  # solo el pedido
            self.assertEqual([m["id"] for m in json.loads(self.q(lab, "api", "--detail", a2, "--json"))], [a2])
            self.assertEqual(snapshot(lab.store()), antes)                                         # y no se marcó nada
            self.assertEqual(lab.run("api", "query", "--detail", "N261103-9999-zzzz").returncode, 0)
            self.assertIn("no hay comunicaciones", self.q(lab, "api", "--detail", "N261103-9999-zzzz"))

    def test_no_escribe_nada_ni_marca_leido_ni_cambia_el_estado_ni_con_detail(self):
        with Lab() as lab:
            t = lab.put("arkana", "task", "Tarea abierta", "api", ("--instructions-file", lab.file("i.txt", "a\n"), "--criteria-file", lab.file("c.txt", "b\n")))
            n = lab.put("app", "notice", "Aviso", "api")
            antes = snapshot(lab.store())
            for args in ((), ("--unread",), ("--pending",), ("--detail",), ("--unread", "--detail", "--json"), ("--id", t, "--detail")):
                self.q(lab, "api", *args)
            self.assertEqual(snapshot(lab.store()), antes)                                        # ni un byte distinto en el almacén
            self.assertNotIn(n, lab.jload(lab.store("read/api.json"))["ids"]) if os.path.exists(lab.store("read/api.json")) else None
            self.assertEqual(lab.msg(t)["estado"], "open")                                       # y nada pasa a done

    def test_unread_coincide_con_lo_que_cuenta_el_hook_y_get_detail_si_lo_consume(self):
        with Lab() as lab:
            a1 = lab.put("app", "notice", "Primer aviso", "api")
            a2 = lab.put("app-web", "notice", "Segundo aviso", "api")
            lab.put("api", "notice", "Lo escribo yo", "app")                              # propio: no cuenta
            ids = [m["id"] for m in json.loads(self.q(lab, "api", "--unread", "--json"))]
            self.assertEqual(sorted(ids), sorted([a1, a2]))
            self.assertEqual(lab.run("api", "get", "--detail", a1).returncode, 0)            # get --detail sí marca leído
            self.assertEqual([m["id"] for m in json.loads(self.q(lab, "api", "--unread", "--json"))], [a2])
            self.assertEqual(len(json.loads(self.q(lab, "api", "--json"))), 3)               # sin --unread siguen saliendo todos

    def test_filtros_vacio_y_directrices_propuestas_no_cuentan_como_sin_leer(self):
        with Lab() as lab:
            vacia = self.q(lab, "api", "--unread")
            self.assertIn("no hay comunicaciones sin leer", vacia)
            self.assertIn("get --detail <id>", vacia)                                                  # también sin resultados lleva el aviso
            lab.put("app", "notice", "Norma propuesta", "api", ("--repeat",))               # propuesta: no cuenta
            q = lab.put("arkana", "question", "¿Qué endpoint?", "api")
            self.assertEqual([m["id"] for m in json.loads(self.q(lab, "api", "--unread", "--json"))], [q])
            self.assertEqual([m["id"] for m in json.loads(self.q(lab, "api", "--pending", "--json"))], [q])
            self.assertEqual(json.loads(self.q(lab, "api", "--from", "app", "--type", "notice", "--json"))[0]["de"], "app")


class TestSyncReconcileAdopt(unittest.TestCase):
    def test_sync_reconstruye_el_indice_y_lista_ilegibles(self):
        with Lab() as lab:
            n = lab.put("app", "notice", "Un aviso cualquiera", "api")
            os.remove(lab.store("index.json"))
            with open(lab.store("messages/roto.json"), "w") as f:
                f.write("{no json")
            r = lab.run("arkana", "sync")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("WARN|sync:roto.json", r.stdout)
            self.assertIn(n, lab.jload(lab.store("index.json"))["messages"])

    def test_reconcile_candidatos_aplicar_y_origins(self):
        with Lab() as lab:
            a = lab.put("app", "notice", "Cambia el endpoint de altas", "api")
            b = lab.put("app-web", "notice", "También cambia el de bajas", "api")
            c = lab.put("app-web", "notice", "Aviso para otro destinatario", "app")
            r = lab.run("app-web", "put", "--type", "notice", "--subject", "Tercer aviso para el backend", "--to", "api")
            self.assertIn("INFO|reconcile", r.stdout)                                              # el put sugiere reconciliar
            grupos = json.loads(lab.run("arkana", "reconcile", "candidates", "--json").stdout)
            self.assertEqual([(g["para"], len(g["mensajes"])) for g in grupos], [(["api"], 3)])
            cuerpo = lab.file("b.txt", "Resumen: cambios en altas y bajas del backend.")
            ids = " ".join(sorted(m["id"] for m in grupos[0]["mensajes"]))
            self.assertEqual(lab.run("arkana", "reconcile", "apply", "--origins", a, "--subject", "Un solo origen").returncode, 2)
            self.assertEqual(lab.run("arkana", "reconcile", "apply", "--origins", f"{a} {c}", "--subject", "Destinatarios distintos").returncode, 1)
            r = lab.run("arkana", "reconcile", "apply", "--origins", ids, "--subject", "Resumen de cambios del backend", "--body-file", cuerpo, "--dry-run")
            self.assertIn("DRY", r.stdout)
            r = lab.run("arkana", "reconcile", "apply", "--origins", ids, "--subject", "Resumen de cambios del backend", "--body-file", cuerpo)
            self.assertEqual(r.returncode, 0, r.stdout)
            nuevo = [m for m in lab.get("arkana") if m.get("origins")]
            self.assertEqual(len(nuevo), 1)
            self.assertEqual((nuevo[0]["origins"], nuevo[0]["para"], nuevo[0]["de"]), (ids.split(), ["api"], "arkana"))
            for i in ids.split():
                m = lab.msg(i)
                self.assertEqual((m["estado"], m["reconciled_into"]), ("reconciled", nuevo[0]["id"]))
            self.assertEqual({m["id"] for m in lab.get("api")}, {nuevo[0]["id"]})              # los originales dejan de verse
            self.assertEqual(json.loads(lab.run("arkana", "reconcile", "candidates", "--json").stdout), [])

    def test_sync_completa_una_reconciliacion_cortada(self):
        with Lab() as lab:
            a = lab.put("app", "notice", "Un aviso para el backend", "api")
            b = lab.put("app-web", "notice", "Otro aviso para el backend", "api")
            lab.run("arkana", "reconcile", "apply", "--origins", f"{a} {b}", "--subject", "Resumen para el backend")
            m = lab.msg(a)
            m.pop("reconciled_into"); m["estado"] = "open"; m["tipo"] = "notice"; m.pop("estado")   # simula el corte: el original no llegó a cambiar
            lab.jdump(lab.store(f"messages/{a}.json"), m)
            r = lab.run("arkana", "sync", "--reconcile")
            self.assertIn("sync-reparar", r.stdout)
            self.assertEqual(lab.msg(a)["estado"], "reconciled")

    def test_adopt_formato_antiguo_es_idempotente_y_no_toca_el_origen(self):
        with Lab() as lab:
            src = os.path.join(lab.arkana, "novedades")
            os.makedirs(os.path.join(src, "shared")); os.makedirs(os.path.join(src, "app-web"))
            leg = {"id": "N261030-1729-v7fb", "asunto": "Formato de commit cerrado", "tipo": "notice", "de": "shared", "autor": "x", "fecha": "2026-10-30T17:29:37Z",
                   "rama": "develop", "prioridad": "normal", "historial": [{"fecha": "2026-10-30T17:29:37Z", "autor": "x", "accion": "created", "nota": ""}]}
            tarea = dict(leg, id="N261030-1850-6stx", de="app-web", para="app", tipo="task", estado="done", instrucciones=["a"], criterios=["b"])
            lab.jdump(os.path.join(src, "shared", leg["id"] + ".json"), leg)
            lab.jdump(os.path.join(src, "app-web", tarea["id"] + ".json"), tarea)
            lab.file(os.path.join("ws", "shared", "novedades", "LEEME.md"), "# LEEME")
            lab.jdump(os.path.join(src, "shared", "roto.json"), {"id": "malo"})
            r = lab.run("arkana", "adopt", "--dry-run")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertFalse(os.path.isdir(lab.store("messages")))
            r = lab.run("arkana", "adopt")
            self.assertIn("2 adoptadas, 0 ya estaban", r.stdout)
            self.assertIn("WARN|adopt:shared/roto.json", r.stdout)
            a = lab.msg("N261030-1729-v7fb")
            self.assertEqual((a["de"], a["para"]), ("arkana", ["api", "app", "app-web"]))     # sin destinatario = a todos los demás
            self.assertEqual(lab.msg("N261030-1850-6stx")["para"], ["app"])
            self.assertIn("0 adoptadas, 2 ya estaban", lab.run("arkana", "adopt").stdout)
            self.assertTrue(os.path.exists(os.path.join(src, "shared", leg["id"] + ".json")))        # el origen no se toca


class TestRepeatYDestinatarios(unittest.TestCase):
    def task(self, lab, who="arkana", to="api,app", extra=()):
        ins, cri = lab.file("i.txt", "Hazlo\n"), lab.file("c.txt", "Compila\n")
        return lab.put(who, "task", "Adaptar el cliente al nuevo contrato", to, ("--instructions-file", ins, "--criteria-file", cri, *extra))

    def test_confirmacion_por_destinatario_y_estado_derivado(self):
        with Lab() as lab:
            t = self.task(lab)
            r = lab.run("arkana", "put", "--done", t, "--result", "x")
            self.assertEqual(r.returncode, 1)                                                   # varios destinatarios: hace falta --for
            self.assertIn("--for", r.stdout)
            self.assertEqual(lab.run("api", "put", "--done", t, "--result", "hecho en be").returncode, 0)
            m = lab.msg(t)
            self.assertEqual((m["estado"], list(m["confirmaciones"])), ("open", ["api"]))   # falta app: sigue abierto
            self.assertIn("ya estaba done", lab.run("api", "put", "--done", t, "--result", "otra vez").stdout)
            self.assertEqual(lab.run("api", "put", "--done", t, "--result", "x", "--for", "app").returncode, 1)   # no confirma por otro
            self.assertEqual([x["id"] for x in lab.get("api", "--pending")], [])            # ya no le queda pendiente
            self.assertEqual([x["id"] for x in lab.get("app", "--pending")], [t])
            self.assertEqual(lab.run("arkana", "put", "--discard", t, "--reason", "no aplica", "--for", "app").returncode, 0)
            self.assertEqual(lab.msg(t)["estado"], "done")                                      # todos confirmados: estado global derivado

    def test_repeat_no_se_cierra_y_nace_vigente_o_propuesto(self):
        with Lab() as lab:
            a = lab.put("arkana", "notice", "Usa siempre commits en inglés", "api", ("--repeat",))
            b = lab.put("app", "notice", "Norma propuesta por app aquí", "api", ("--repeat",))
            self.assertEqual((lab.msg(a)["repeticion"], lab.msg(a)["vigencia"]), ("repeat", "vigente"))
            self.assertEqual(lab.msg(b)["vigencia"], "propuesto")
            self.assertEqual(lab.run("api", "put", "--activate", b).returncode, 1)          # solo ARKANA activa
            self.assertEqual(lab.run("arkana", "put", "--activate", b).returncode, 0)
            self.assertEqual(lab.msg(b)["vigencia"], "vigente")
            t = self.task(lab, extra=("--repeat",))
            r = lab.run("api", "put", "--done", t, "--result", "x")
            self.assertEqual(r.returncode, 1)
            self.assertIn("repeat", r.stdout)                                                   # un repeat no se cierra
            self.assertEqual(sorted(x["id"] for x in lab.get("api", "--repeat")), sorted([a, b, t]))      # el orden es por fecha (al segundo) y luego por id aleatorio: se compara el conjunto
            self.assertEqual(lab.get("api", "--pending"), [])                               # las directrices no son pendientes
            self.assertEqual(lab.run("api", "delete", a).returncode, 1)                     # baja: solo remitente o ARKANA
            self.assertEqual(lab.run("arkana", "delete", a).returncode, 0)
            self.assertEqual(lab.run("app", "delete", b).returncode, 0)

    def test_set_repeticion_solo_remitente_o_arkana(self):
        with Lab() as lab:
            n = lab.put("app", "notice", "Aviso que pasa a ser permanente", "api")
            self.assertEqual(lab.run("api", "put", "--set-repeticion", n, "repeat").returncode, 1)
            self.assertEqual(lab.run("app", "put", "--set-repeticion", n, "repeat").returncode, 0)
            self.assertEqual((lab.msg(n)["repeticion"], lab.msg(n)["vigencia"]), ("repeat", "propuesto"))
            self.assertEqual(lab.run("arkana", "put", "--set-repeticion", n, "once").returncode, 0)
            self.assertNotIn("vigencia", lab.msg(n))

    def test_entregas_y_ejecuciones_solo_arkana_para_un_destinatario(self):
        with Lab() as lab:
            n = lab.put("app", "notice", "Aviso informativo para api", "api")
            self.assertEqual(lab.run("app", "put", "--delivered", n, "--for", "api").returncode, 1)
            self.assertEqual(lab.run("arkana", "put", "--delivered", n, "--for", "app-web").returncode, 1)   # no es destinatario
            for _ in range(2):
                self.assertEqual(lab.run("arkana", "put", "--delivered", n, "--for", "api", "--plan", "P1", "--task", "T001").returncode, 0)
            self.assertEqual(lab.run("arkana", "put", "--executed", n, "--for", "api", "--plan", "P1", "--task", "T001").returncode, 0)
            m = lab.msg(n)
            self.assertEqual((m["entregas"]["api"]["n"], m["entregas"]["api"]["plan"]), (2, "P1"))
            self.assertEqual(m["ejecuciones"]["api"]["n"], 1)                               # también en un notice, sin tocar su estado
            self.assertNotIn("estado", m)
            self.assertEqual(lab.jload(lab.store("index.json"))["messages"][n]["ejecutados"], ["api"])

    def test_mensaje_antiguo_sin_campos_nuevos_sigue_funcionando(self):
        with Lab() as lab:
            leg = {"id": "N261030-1000-aaaa", "asunto": "Mensaje del esquema antiguo", "tipo": "task", "de": "arkana", "para": ["api"], "autor": "x",
                   "fecha": "2026-10-30T10:00:00Z", "rama": "main", "prioridad": "normal", "estado": "open", "instrucciones": ["a"], "criterios": ["b"],
                   "historial": [], "updated": "2026-10-30T10:00:00Z"}
            os.makedirs(lab.store("messages"), exist_ok=True)
            lab.jdump(lab.store("messages/N261030-1000-aaaa.json"), leg)
            self.assertEqual([x["id"] for x in lab.get("api", "--pending")], [leg["id"]])
            self.assertEqual(lab.run("api", "put", "--done", leg["id"], "--result", "ok").returncode, 0)
            self.assertEqual(lab.msg(leg["id"])["estado"], "done")                              # un solo destinatario: igual que antes

    def test_repeat_a_all_tiene_alcance_vivo(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "lib"))
        import messages as M

        class WS:
            def aliases(self):
                return ["arkana", "app", "api", "nuevo"]
        m = {"de": "app", "para": ["all"], "destinatarios": ["arkana", "api"], "repeticion": "repeat"}
        self.assertEqual(M.recipients_of(m, WS()), ["arkana", "api", "nuevo"])             # el componente nuevo hereda la directriz
        self.assertEqual(M.recipients_of(dict(m, repeticion="once")), ["arkana", "api"])   # un once es una foto
        self.assertTrue(M.is_recipient(m, "nuevo") and not M.is_recipient(m, "app"))


if __name__ == "__main__":
    unittest.main()
