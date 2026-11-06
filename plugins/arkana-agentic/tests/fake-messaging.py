#!/usr/bin/env python3
"""messaging.sh falso para las pruebas: anota los argumentos en FAKE_MESSAGING_LOG y sale con FAKE_MESSAGING_RC (0 por defecto)."""
import json
import os
import sys

with open(os.environ["FAKE_MESSAGING_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
if os.environ.get("FAKE_MESSAGING_RC", "0") != "0":
    print("FAIL|put|simulado")
sys.exit(int(os.environ.get("FAKE_MESSAGING_RC", "0")))
