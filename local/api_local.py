"""Arranca la API contra el entorno local (Postgres + PostgREST de local/docker-compose.yml).

    python local/api_local.py            # http://127.0.0.1:8000
"""
import os
import sys
from pathlib import Path

import entorno

entorno.cargar()

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))

import uvicorn  # noqa: E402
import api  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        api.app,
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        log_level="warning",
    )
