"""Carga la configuración local (local/.env) en el entorno del proceso.

Úsalo antes de importar nada de app/: los scripts de app/ leen SUPABASE_URL al importarse.
Se niega a continuar si la URL de Supabase no es local, para no tocar un proyecto real.
"""
import os
from pathlib import Path


LOCAL = Path(__file__).resolve().parent
RAIZ = LOCAL.parent
RUTA_ENV = LOCAL / ".env"
HOSTS_LOCALES = ("http://localhost:", "http://127.0.0.1:")


def cargar() -> dict:
    if not RUTA_ENV.exists():
        raise SystemExit("Falta local/.env. Ejecuta: python local/preparar.py")

    valores = {}
    for linea in RUTA_ENV.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        valores[clave.strip()] = valor.strip()
        os.environ[clave.strip()] = valor.strip()

    if not os.environ["SUPABASE_URL"].startswith(HOSTS_LOCALES):
        raise SystemExit("SUPABASE_URL no es local. Estos scripts solo trabajan con el entorno local.")
    return valores
