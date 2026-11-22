"""Render de la statusline: funciones puras (colores, ancho estrecho, línea 2) y estado git real con repos locales. Sin red."""
import json
import os
import re
import subprocess
import time
import unittest

import lab as L
import statusline as S

A = re.compile(r"\033\[[0-9;]*m")


def pl(lines):
    return [A.sub("", l) for l in lines]


def st(branch="develop", u=0, s=0, m=0, a=0, b=None, remote=True):
    return {"branch": branch, "untracked": u, "staged": s, "modified": m, "ahead": a, "behind": b, "has_remote": remote}


def items(cur="app"):
    base = [("ARKANA", st("refactor/arkana", 13, 113, 84, 2, 3)), ("app", st(b=0)), ("api", st("feature/una-rama-muy-larga", 1, b=None)),
            ("app-web", st(b=0)), ("app-ui", st("develop", 0, 0, 2, 0, 5)), ("docs", st("main", remote=False))]
    return [{"alias": a, "current": a.lower() == cur.lower(), "state": s} for a, s in base]


class TestBloqueDeRama(unittest.TestCase):
    def test_contadores_solo_distintos_de_cero_y_check_si_esta_limpio(self):
        self.assertEqual(S.branch_label(st("develop", 13, 113, 84, 2, 3)), "develop ◌13 ✚113 ●84 ⇡2 ⇣3")
        self.assertEqual(S.branch_label(st(b=0)), "develop ✓")
        self.assertEqual(S.branch_label(st("main", u=1, b=0)), "main ◌1")
        self.assertEqual(S.branch_label(st(a=2, b=0)), "develop ⇡2")                           # sin subir no es limpio

    def test_pull_desconocido_ocupa_su_hueco_y_sin_remoto_no_hay_flechas(self):
        self.assertEqual(S.branch_label(st(b=None)), "develop ✓ ⇣?")
        self.assertEqual(S.branch_label(st(u=2, a=1, b=None)), "develop ◌2 ⇡1 ⇣?")
        self.assertEqual(S.branch_label(st(remote=False, b=None)), "develop ✓")
        self.assertEqual(S.branch_label(st("x", 3, remote=False)), "x ◌3")

    def test_formato_alias_arroba_rama_con_sus_colores(self):
        """`ALIAS@rama:indicadores`: alias naranja (brillante el actual), @ y : rojos, rama en gris (más claro la del actual) e indicadores en inverso."""
        p, a = S.entry({"alias": "app", "current": False, "state": st(b=0)})
        self.assertEqual(p, "app@develop:✓")
        self.assertEqual(a, "\033[38;5;208mapp\033[0m\033[31m@\033[0m\033[90mdevelop\033[0m\033[31m:\033[0m\033[30;42m✓\033[0m")
        p, a = S.entry({"alias": "ARKANA", "current": True, "state": st(b=0)})
        self.assertEqual(a, "\033[1;38;5;214mARKANA\033[0m\033[31m@\033[0m\033[37mdevelop\033[0m\033[31m:\033[0m\033[30;42m✓\033[0m")
        self.assertEqual(S.entry({"alias": "specs", "current": False, "state": None})[0], "specs —")

    def test_cada_indicador_va_en_inverso_con_el_color_de_su_estado(self):
        """Texto negro sobre rojo (◌), amarillo (✚ ● ⇡ ⇣N), cian (⇣?) o verde (✓), en su tono normal (no brillante); el indicador entero (símbolo y cantidad) lleva el fondo."""
        self.assertEqual(S.branch_parts(st("develop", 1, 2, 3, 4, 5)), [("develop", "", None), ("◌", "1", S.B_RED), ("✚", "2", S.B_YELLOW), ("●", "3", S.B_YELLOW),
                                                                        ("⇡", "4", S.B_YELLOW), ("⇣", "5", S.B_YELLOW)])
        self.assertEqual(S.branch_parts(st(b=None))[-2:], [("", "✓", S.B_GREEN), ("⇣", "?", S.B_CYAN)])
        p, a = S.entry({"alias": "app", "current": False, "state": st(u=2, b=None)})
        self.assertEqual(p, "app@develop:◌2⇣?")
        self.assertTrue(a.endswith("\033[90mdevelop\033[0m\033[31m:\033[0m\033[30;41m◌2\033[0m\033[30;46m⇣?\033[0m"), a)
        p, a = S.entry({"alias": "ARKANA", "current": True, "state": st(u=13, s=1, m=2, a=3, b=4)})
        self.assertEqual(p, "ARKANA@develop:◌13✚1●2⇡3⇣4")
        for ind, bg in (("◌13", 41), ("✚1", 43), ("●2", 43), ("⇡3", 43), ("⇣4", 43)):
            self.assertIn(f"\033[30;{bg}m{ind}\033[0m", a)
        self.assertEqual(S.plain(a), p)                                                         # el color no cambia el ancho


class TestAnchoEstrecho(unittest.TestCase):
    def datos(self, cur="app"):
        return {"items": items(cur), "plan": S.plan_view(None, "s", time.time(), lambda p: True), "session_cost": 1.5, "model": "Sonnet 5.5", "effort": "medium",
                "usage": [("C", 61), ("S", 0), ("W", 19)]}

    def test_ancho_amplio_una_linea_con_los_componentes_separados_por_un_espacio(self):
        ls = S.fit_line1(items(), 195)
        self.assertEqual(len(ls), 1)
        self.assertNotIn("·", ls[0]); self.assertNotIn("|", ls[0])                                 # sin separadores visibles: solo un espacio entre componentes
        self.assertTrue(pl(ls)[0].startswith("ARKANA@refactor/arkana:◌13✚113●84⇡2⇣3 app@develop:✓ api@"))

    def test_primero_se_acortan_las_ramas_de_los_no_actuales(self):
        ls = pl(S.fit_line1(items(), 125))
        self.assertEqual(len(ls), 1)
        self.assertIn("ARKANA", ls[0])                                                          # los alias aún enteros
        self.assertNotIn("una-rama-muy-larga", ls[0])
        self.assertIn("…", ls[0])
        self.assertIn("app@develop:✓", ls[0])                                              # la actual, intacta

    def test_luego_los_alias_y_por_ultimo_pasan_a_otra_linea(self):
        ls = S.fit_line1(items("api"), 85)
        self.assertGreater(len(ls), 1)
        todo = "\n".join(pl(ls))
        for contador in ("◌13", "✚113", "●84", "⇡2", "⇣3", "●2", "⇣5", "◌1"):
            self.assertIn(contador, todo)                                                       # los contadores nunca se recortan
        self.assertIn("api@feature/una-rama-muy-larga:◌1⇣?", todo)                      # el componente actual, entero
        for ln in pl(ls):
            self.assertLessEqual(len(ln), 85)

    def test_golden_a_cuatro_anchos(self):
        """Línea 1: ARKANA entero + plan, coste, modelo y uso. Línea 2 (y siguientes): los demás componentes."""
        arkana = "ØARKANA@refactor/arkana:◌13✚113●84⇡2⇣3 | [■]"
        gold = {
            200: ['app@develop:✓ api@feature/una-rama-muy-larga:◌1⇣? app-web@develop:✓ app-ui@develop:●2⇣5 docs@main:✓'],
            120: ['app@develop:✓ api@feature/una-rama-muy-larga:◌1⇣? app-web@develop:✓ app-ui@develop:●2⇣5 docs@main:✓'],
            80: ['app@develop:✓ api@feat…:◌1⇣? app-web@deve…:✓ app-ui@deve…:●2⇣5 docs@main:✓'],
            50: ['app@develop:✓ api@fe…:◌1⇣? ap…@de…:✓', 'ap…@de…:●2⇣5 do…@ma…:✓'],
        }
        for w, resto in gold.items():
            ls = pl(S.render(self.datos(), w))
            self.assertTrue(ls[0].startswith(arkana), ls[0])                                    # ARKANA nunca se acorta
            self.assertEqual(ls[1:], resto, w)
            for ln in ls[1:]:
                self.assertLessEqual(len(ln), w - S.RESERVED, (w, ln))
        self.assertEqual(pl(S.render(self.datos(), 200))[0], "ØARKANA@refactor/arkana:◌13✚113●84⇡2⇣3 | [■] sin plan activo | P0.00 S1.50 Sonnet 5.5 ◔ C61 S0 W19")
        completa = pl(S.render(self.datos(), 200))[0]
        justa = pl(S.render(self.datos(), len(completa) + S.RESERVED - 4))[0]                   # 4 columnas menos: solo cede la descripción
        self.assertTrue(justa.endswith("… | P0.00 S1.50 Sonnet 5.5 ◔ C61 S0 W19"), justa)
        self.assertEqual(pl(S.render(self.datos(), 50))[0], "ØARKANA@refactor/arkana:◌13✚113●84⇡2⇣3 | [■] | P0.00 S1.50 Sonnet 5.5 ◔ C61 S0 W19")

    def test_la_marca_es_una_o_tachada_amarilla_brillante_delante_de_arkana(self):
        for w in (200, 50):
            l0 = S.render(self.datos(), w)[0]
            self.assertTrue(l0.startswith("\033[93mØ\033[0m") and "ARKANA" in l0[:40], repr(l0[:40]))      # amarillo brillante (93), siempre
        self.assertNotIn("Ø", "".join(pl(S.render(self.datos(), 200)[1:])))                              # solo una vez, al inicio de la línea 1

    def test_la_marca_de_evolve_va_a_la_derecha_de_la_linea_1_en_rojo_brillante_inverso(self):
        marca = " REQUIRED /arkana-evolve:apply "
        ls = S.render(dict(self.datos(), evolve=True), 200)
        l0 = pl(ls)[0]
        self.assertTrue(l0.endswith(marca), l0)                                                      # todo a la derecha de la línea 1
        self.assertEqual(len(l0), 200 - S.RESERVED)                                                  # justo hasta el margen derecho
        self.assertTrue(ls[0].endswith("\033[7;91m" + marca + "\033[0m"), repr(ls[0][-40:]))         # rojo brillante (91) en inverso (7)
        self.assertTrue(l0.startswith("ØARKANA@"), l0)                                               # ARKANA sigue entero y delante
        self.assertEqual(len(ls), len(S.render(self.datos(), 200)))                                  # y no añade líneas
        self.assertNotIn("REQUIRED", "".join(S.render(self.datos(), 200)))                           # sin la marca cuando no hace falta
        l120 = pl(S.render(dict(self.datos(), evolve=True), 120))
        self.assertTrue(l120[0].endswith(marca) and len(l120[0]) == 115, l120[0])                      # a 120 cabe en la línea 1 si cede la descripción del plan
        self.assertNotIn("sin plan activo", l120[0])
        for w in (80, 50):                                                                           # si lo que nunca se recorta ya llena la línea 1, la marca va sola debajo, a la derecha
            sin, con = pl(S.render(self.datos(), w)), S.render(dict(self.datos(), evolve=True), w)
            self.assertEqual(pl(con)[0], sin[0], w)                                                  # la línea 1 queda intacta
            self.assertEqual(pl(con)[1], " " * (w - S.RESERVED - len(marca)) + marca, w)
            self.assertEqual(pl(con)[2:], sin[1:], w)                                                # y el resto de líneas, igual
            self.assertTrue(con[1].endswith("\033[7;91m" + marca + "\033[0m"))

    def test_si_el_manifiesto_no_carga_lo_dice_en_una_linea_en_vez_de_perderla(self):
        d = dict(self.datos(), items=items()[:1], aviso="workspace no cargado: manifiesto no válido")
        ls = pl(S.render(d, 200))
        self.assertEqual(len(ls), 2)
        self.assertTrue(ls[1].startswith("⚠ workspace no cargado"), ls[1])
        self.assertEqual(len(S.render(dict(d, aviso=None), 200)), 1)                                   # sin aviso, nada de más

    def test_una_sola_pieza_va_en_una_sola_linea(self):
        d = dict(self.datos(), items=items()[:1])
        self.assertEqual(len(S.render(d, 200)), 1)


class TestEsfuerzo(unittest.TestCase):
    def modelo(self, effort):
        plan = S.plan_view(None, "s", time.time(), lambda p: True)
        return A.sub("", S.line2(plan, 0.0, "Sonnet 5.5", effort, [("C", 61)], 195))

    def test_cada_nivel_de_esfuerzo_tiene_su_circulo(self):
        for nivel, simbolo in (("low", "○"), ("medium", "◔"), ("high", "◑"), ("xhigh", "◕"), ("max", "●")):
            self.assertIn(f"Sonnet 5.5 {simbolo} C61", self.modelo(nivel), nivel)
        self.assertIn("Sonnet 5.5 ◑ C61", self.modelo("HIGH"))                                        # sin distinguir mayúsculas
        self.assertEqual(len({S.EFFORT_GLYPH[n] for n in S.EFFORT_GLYPH}), 5)                         # cinco símbolos distintos

    def test_sin_nivel_o_con_uno_desconocido(self):
        self.assertIn("Sonnet 5.5 C61", self.modelo(None))
        self.assertIn("Sonnet 5.5 (ultra) C61", self.modelo("ultra"))                                 # en texto, no se pierde


class TestLinea2(unittest.TestCase):
    def render2(self, plan, width=200, cost=0.0, usage=((("C", 61)), ("S", 0), ("W", 19))):
        return S.line2(plan, cost, "Sonnet 5.5", "medium", list(usage), width - S.RESERVED)

    def test_sin_plan_y_con_costes_y_bloques_por_umbral(self):
        l = self.render2(S.plan_view(None, "s", time.time(), lambda p: True), cost=0.0)
        self.assertEqual(A.sub("", l), "[■] sin plan activo | P0.00 S0.00 Sonnet 5.5 ◔ C61 S0 W19")
        self.assertIn("\033[31mP0.00 S0.00\033[0m", l)                                                          # costes: texto rojo oscuro, sin fondo
        self.assertIn("\033[35mSonnet 5.5 ◔\033[0m", l)                                                  # modelo: texto magenta, sin fondo
        self.assertEqual(l.count(f" {S.DARK_BLUE}|{S.RESET} "), 1)                                           # una barra | en azul oscuro entre el plan y los costes
        self.assertNotIn("·", A.sub("", l))                                                                    # y ningún punto: el resto va separado por un espacio
        self.assertNotIn("\033[7;", l); self.assertNotRegex(l, r"\033\[[0-9;]*;4[0-9]m|\033\[10[0-9]m")           # nada con fondo
        for v, fg in ((0, 32), (40, 32), (41, 33), (75, 33), (76, 91), (100, 91)):                          # uso: color del texto por tramo
            self.assertIn(f"\033[{fg}mC{v}\033[0m", S.line2(S.plan_view(None, "s", 0, lambda p: True), 0, "M", None, [("C", v)], 100), v)
        self.assertNotIn("%", l)

    def test_el_estado_va_en_inverso_con_el_color_de_su_simbolo(self):
        """`[■]` entero con texto negro sobre el color del estado (gris en reposo); el texto que lo acompaña sigue fuera del bloque."""
        l = self.render2(S.plan_view(None, "s", time.time(), lambda p: True))
        self.assertTrue(l.startswith("\033[30;100m[■]\033[0m \033[90msin plan activo\033[0m"), l)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        base = {"ts": ts, "plan": "P1", "tarea": "T001", "tareas": {"actual": 1, "total": 3}, "repo": "app", "asunto_corto": "algo", "worker_pid": 7, "gasto_usd": 0, "session_id": "s"}
        for estado, sym, bg in (("en_ejecucion", "▶", 102), ("esperando_usuario", "?", 106), ("pausado", "‖", 103), ("fallido", "✗", 101), ("completado", "✓", 102), ("detenido", "■", 101)):
            v = S.plan_view(dict(base, estado=estado), "s", time.time(), lambda p: True)
            self.assertEqual(v["sym"], sym, estado)
            self.assertTrue(self.render2(v).startswith(f"\033[30;{bg}m[{sym}]\033[0m"), estado)

    def test_plan_activo_con_worker_plan_tarea_y_descripcion(self):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        linea = {"ts": ts, "plan": "P2611030652-ysov", "estado": "en_ejecucion", "tarea": "T002", "tareas": {"actual": 2, "hechas": 1, "omitidas": 1, "total": 7},
                 "repo": "api", "asunto_corto": "Añadir el perfil", "worker_pid": 4242, "gasto_usd": 0.4, "session_id": "s"}
        v = S.plan_view(linea, "s", time.time(), lambda p: True)
        t = A.sub("", self.render2(v, cost=1.23))
        self.assertTrue(t.startswith("[▶] 002/007 (✗1) api@P2611030652-ysov:T002 Añadir el perfil | P0.40 S1.23 "), t)
        self.assertEqual(S.plan_view(linea, "otra", time.time(), lambda p: True)["desc"], "sin plan activo")             # el plan es de otra sesión
        self.assertEqual(S.plan_view(linea, "s", time.time(), lambda p: False)["sym"], "✗")                    # worker muerto
        self.assertIn("/arkana-agentic:fix", S.plan_view(linea, "s", time.time(), lambda p: False)["desc"])
        viejo = dict(linea, estado="completado", ts="2020-01-01T00:00:00Z")
        self.assertEqual(S.plan_view(viejo, "s", time.time(), lambda p: True)["desc"], "sin plan activo")                  # terminado hace más de 30 min

    def test_solo_se_recorta_la_descripcion(self):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        linea = {"ts": ts, "plan": "P1", "estado": "en_ejecucion", "tarea": "T001", "tareas": {"actual": 1, "total": 3}, "repo": "app",
                 "asunto_corto": "x" * 80, "worker_pid": 1, "gasto_usd": 0, "session_id": "s"}
        v = S.plan_view(linea, "s", time.time(), lambda p: True)
        corta = A.sub("", self.render2(v, width=100))
        self.assertIn("…", corta)
        self.assertLessEqual(len(corta), 95)
        self.assertIn("P0.00 S0.00", corta)                                                     # costes, modelo y bloques intactos
        self.assertIn("C61", corta)
        minima = A.sub("", self.render2(v, width=40))
        self.assertNotIn("x" * 6, minima)                                                       # ni así cabe: se quita la descripción
        self.assertIn("app@P1:T001", minima)                                                   # el resto no se recorta


class TestGitReal(unittest.TestCase):
    def test_contadores_reales_y_pull_conocido_solo_con_fetch_reciente(self):
        with L.Lab() as lab:
            d = lab.path("app")
            bare = os.path.join(lab.root, "origin.git")
            subprocess.run(["git", "init", "-q", "--bare", "-b", "develop", bare], check=True)
            L.git(d, "remote", "add", "origin", bare)
            L.git(d, "push", "-q", "-u", "origin", "develop")
            with open(os.path.join(d, "nuevo.txt"), "w") as f:
                f.write("x")
            with open(os.path.join(d, "staged.txt"), "w") as f:
                f.write("x")
            L.git(d, "add", "staged.txt")
            L.git(d, "commit", "-q", "--allow-empty", "-m", "local")
            s = S.git_state(d)
            self.assertEqual((s["branch"], s["untracked"], s["staged"], s["modified"], s["ahead"], s["has_remote"]), ("develop", 2, 0, 0, 1, True))        # nuevo.txt y el repo anidado de app-web
            self.assertIsNone(s["behind"])                                                      # nunca se ha hecho fetch: ⇣?
            L.git(d, "fetch", "-q", "origin")
            self.assertEqual(S.git_state(d)["behind"], 0)
            old = time.time() - 3600
            os.utime(os.path.join(d, ".git", "FETCH_HEAD"), (old, old))
            self.assertIsNone(S.git_state(d)["behind"])                                         # fetch de hace una hora: desconocido
            self.assertIsNone(S.git_state(os.path.join(lab.root, "no-existe")))
            self.assertIsNone(S.git_state(lab.root))                                            # no es un repo


class TestVisibilidadYVigilancia(unittest.TestCase):
    """statusline y watch por componente (esquema 2): ocultar/mostrar, el cwd oculto sigue siendo «actual», sin vigilar no hay ◌ ✚ ●, esquema desconocido."""

    def manifiesto(self, lab, **por_alias):
        f = os.path.join(lab.arkana, ".arkana", "core", "workspace.json")
        d = json.load(open(f, encoding="utf-8"))
        for c in d["components"]:
            c.update(por_alias.get(c["alias"], {}))
        d["schema"] = por_alias.get("_schema", d["schema"])
        L.wj(f, d)

    def linea(self, lab, cwd="app"):
        r = lab.run(cwd)
        self.assertEqual(r.returncode, 0, r.stderr)
        return S.ANSI.sub("", r.stdout)

    def test_por_defecto_se_ve_todo_menos_docs_y_se_puede_ocultar_o_mostrar(self):
        with L.Lab() as lab:
            t = self.linea(lab)
            self.assertIn("API@", t)
            self.assertNotIn("DOCS@", t)                                                        # type docs: oculto por defecto (como siempre)
            self.manifiesto(lab, api={"statusline": False}, docs={"statusline": True}, _schema=2)
            t = self.linea(lab)
            self.assertNotIn("API@", t)
            self.assertIn("DOCS@", t)

    def test_un_componente_de_referencia_se_oculta_salvo_que_se_active(self):
        with L.Lab() as lab:
            self.manifiesto(lab, api={"mode": "reference", "ref": "v1"}, _schema=2)
            self.assertNotIn("API@", self.linea(lab))
            self.manifiesto(lab, api={"statusline": True}, _schema=2)                           # explícito gana al defecto del modo
            self.assertIn("API@", self.linea(lab))

    def test_el_componente_oculto_donde_estas_sigue_viendose(self):
        with L.Lab() as lab:
            self.manifiesto(lab, api={"statusline": False}, _schema=2)
            self.assertNotIn("API@", self.linea(lab, "app"))
            self.assertIn("API@", self.linea(lab, "api"))                                       # estás dentro: la barra te ubica

    def test_sin_vigilar_no_cuentan_los_cambios_locales(self):
        with L.Lab() as lab:
            with open(os.path.join(lab.path("api"), "nuevo.txt"), "w") as f:
                f.write("x")
            self.assertIn("API@develop:◌1", self.linea(lab))
            self.manifiesto(lab, api={"watch": False}, _schema=2)
            self.assertIn("API@develop:✓", self.linea(lab))                                     # visible pero sin vigilar: sin ◌ ✚ ●

    def test_referencia_en_su_ref_sin_indicadores_y_con_noref_si_se_mueve(self):
        with L.Lab() as lab:
            d = lab.path("api")
            L.git(d, "tag", "v1")
            L.git(d, "commit", "-q", "--allow-empty", "-m", "dos")
            L.git(d, "checkout", "-q", "--detach", "v1")
            with open(os.path.join(d, "angular.json"), "w") as f:
                f.write("{}")                                                                   # lo reescribe el tooling del repo: no se vigila
            self.manifiesto(lab, api={"mode": "reference", "ref": "v1", "statusline": True}, _schema=2)
            t = self.linea(lab)
            self.assertIn("API@v1:✓", t)                                                        # HEAD separado en el tag: se muestra el ref, sin ◌
            self.assertNotIn("≠ref", t)
            L.git(d, "checkout", "-q", "--detach", "HEAD~0")
            L.git(d, "checkout", "-q", "develop")                                               # HEAD se ha movido del ref fijado
            t = self.linea(lab)
            self.assertIn("API@develop:≠ref", t)
            self.assertNotIn("API@develop:✓", t)

    def test_un_manifiesto_de_esquema_futuro_dice_que_hay_que_actualizar(self):
        with L.Lab() as lab:
            self.manifiesto(lab, _schema=99)
            self.assertIn("actualiza el plugin", self.linea(lab))

    def test_git_state_sin_watch_conserva_lo_sin_subir(self):
        with L.Lab() as lab:
            d = lab.path("app")
            with open(os.path.join(d, "x.txt"), "w") as f:
                f.write("x")
            s = S.git_state(d, False)
            self.assertEqual((s["untracked"], s["staged"], s["modified"], s["behind"]), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
