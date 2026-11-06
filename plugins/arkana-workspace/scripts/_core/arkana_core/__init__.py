"""Núcleo de Arkana: localizador del workspace, manifiesto, contrato de salida y utilidades comunes de los plugins.

Fuente canónica en `lib/arkana_core/`. Cada plugin lleva una copia en `scripts/_core/` generada por
`scripts/vendor-core.sh` (un plugin instalado no puede referenciar a otro: Claude Code los copia por versión).
Solo biblioteca estándar de Python.
"""
CORE_VERSION = "1.3.0"
