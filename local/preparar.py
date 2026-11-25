"""Genera local/.env con los secretos del entorno local. Se ejecuta una sola vez.

    python local/preparar.py
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path


LOCAL = Path(__file__).resolve().parent
RUTA_ENV = LOCAL / ".env"


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _jwt(payload: dict, secreto: str) -> str:
    cabecera = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    cuerpo = _b64(json.dumps(payload).encode())
    firma = hmac.new(secreto.encode(), f"{cabecera}.{cuerpo}".encode(), hashlib.sha256).digest()
    return f"{cabecera}.{cuerpo}.{_b64(firma)}"


def main() -> int:
    if RUTA_ENV.exists():
        print(f"{RUTA_ENV} ya existe; no se modifica.")
        return 0

    secreto = secrets.token_urlsafe(48)
    ahora = int(time.time())
    clave_service_role = _jwt(
        {"role": "service_role", "iss": "local", "iat": ahora, "exp": ahora + 10 * 365 * 86400},
        secreto,
    )

    RUTA_ENV.write_text(
        "\n".join(
            [
                "# Generado por local/preparar.py. No subir a Git.",
                f"JWT_SECRET={secreto}",
                "SUPABASE_URL=http://localhost:54321",
                f"SUPABASE_SECRET_KEY={clave_service_role}",
                "API_KEY_FRONT=local-test-key",
                "CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000",
                "OPENAI_API_KEY=local-no-real",
                "OPENAI_BASE_URL=http://127.0.0.1:8090/v1",
                "SMTP_HOST=127.0.0.1",
                "SMTP_PORT=8025",
                "SMTP_FROM=Reuniones <bot@ejemplo.com>",
                "SMTP_STARTTLS=false",
                "SLACK_WEBHOOK_URL=http://127.0.0.1:8026/hook",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Creado {RUTA_ENV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
