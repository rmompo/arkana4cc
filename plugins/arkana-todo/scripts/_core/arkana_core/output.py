"""Contrato de salida común de los skills de Arkana.

Texto:  una línea por comprobación `ESTADO|ID|detalle` (OK, WARN, FAIL, INFO, DRY) y al final `RESUMEN|n FAIL|n WARN`.
--json: {"plugin", "skill", "status", "items": [{"id", "status", "detail", "component"}], "summary": {"fail", "warn", ...}}
Códigos de salida: 0 sin fallos, 1 fallos o error, 2 uso incorrecto, 3 precondición no cumplida.
Nunca se imprime un secreto: `Report(secrets=[...])` sustituye esos valores por «***» en el detalle de cada línea.
"""
import json

OK, WARN, FAIL, INFO, DRY = "OK", "WARN", "FAIL", "INFO", "DRY"
STATUSES = (OK, WARN, FAIL, INFO, DRY)
EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_PRECONDITION = 0, 1, 2, 3


class Report:
    def __init__(self, plugin, skill, secrets=()):
        self.plugin, self.skill = plugin, skill
        self.items = []
        self._secrets = [s for s in secrets if s]

    def _clean(self, text):
        for s in self._secrets:
            text = text.replace(s, "***")
        return text

    def add(self, status, id, detail="", component=None):
        if status not in STATUSES:
            raise ValueError(f"estado desconocido: {status}")
        self.items.append({"id": id, "status": status, "detail": self._clean(str(detail)), "component": component})
        return self

    def count(self, status):
        return sum(1 for i in self.items if i["status"] == status)

    def status(self):
        return "fail" if self.count(FAIL) else ("warn" if self.count(WARN) else "ok")

    def lines(self):
        out = [f"{i['status']}|{i['id']}|{i['detail']}" for i in self.items]
        out.append(f"RESUMEN|{self.count(FAIL)} FAIL|{self.count(WARN)} WARN")
        return out

    def text(self):
        return "\n".join(self.lines()) + "\n"

    def to_json(self):
        return {"plugin": self.plugin, "skill": self.skill, "status": self.status(), "items": self.items,
                "summary": {"fail": self.count(FAIL), "warn": self.count(WARN), "ok": self.count(OK),
                            "info": self.count(INFO), "dry": self.count(DRY)}}

    def render(self, as_json=False):
        return json.dumps(self.to_json(), ensure_ascii=False, indent=2) + "\n" if as_json else self.text()

    def exit_code(self):
        return EXIT_FAIL if self.count(FAIL) else EXIT_OK
