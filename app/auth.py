"""Autenticación local con contraseñas derivadas y tokens firmados."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time

from fastapi import Header, HTTPException

from database import supabase


USERS_TABLE = "usuarios"
TOKEN_TTL_SECONDS = 8 * 60 * 60
PASSWORD_ITERATIONS = 600_000
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def validar_email(email: str) -> bool:
    return bool(EMAIL_RE.fullmatch(normalizar_email(email)))


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _secret() -> bytes:
    secret = os.getenv("AUTH_SECRET") or os.getenv("JWT_SECRET") or os.getenv("SUPABASE_SECRET_KEY")
    if not secret or len(secret) < 32:
        raise RuntimeError("Configura AUTH_SECRET (mínimo 32 caracteres) en el .env")
    return secret.encode("utf-8")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verificar_password(password: str, almacenada: str) -> bool:
    try:
        algoritmo, iteraciones, salt, esperado = almacenada.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _unb64(salt), int(iteraciones)
        )
        return hmac.compare_digest(actual, _unb64(esperado))
    except (TypeError, ValueError):
        return False


def registrar_usuario(email: str, password: str) -> dict | None:
    email = normalizar_email(email)
    if not validar_email(email):
        raise ValueError("Introduce un correo electrónico válido")
    password_hash = hash_password(password)
    response = supabase.rpc(
        "registrar_usuario",
        {"p_email": email, "p_password_hash": password_hash},
    ).execute()
    user_id = response.data
    if isinstance(user_id, list):
        user_id = user_id[0] if user_id else None
    if isinstance(user_id, dict):
        user_id = user_id.get("registrar_usuario")
    if not user_id:
        return None
    return {"id": str(user_id), "email": email}


def buscar_usuario(email: str) -> dict | None:
    response = (
        supabase.table(USERS_TABLE)
        .select("id, email, password_hash, avatar_url, token_version")
        .eq("email", normalizar_email(email))
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def _token_para(usuario: dict) -> str:
    ahora = int(time.time())
    encabezado = {"alg": "HS256", "typ": "JWT"}
    contenido = {
        "sub": str(usuario["id"]),
        "email": usuario["email"],
        "ver": int(usuario.get("token_version", 0)),
        "iat": ahora,
        "exp": ahora + TOKEN_TTL_SECONDS,
        "iss": "reuniones-api",
    }
    base = f"{_b64(json.dumps(encabezado, separators=(',', ':')).encode())}.{_b64(json.dumps(contenido, separators=(',', ':')).encode())}"
    firma = hmac.new(_secret(), base.encode("ascii"), hashlib.sha256).digest()
    return f"{base}.{_b64(firma)}"


def crear_sesion(usuario: dict) -> dict:
    return {
        "access_token": _token_para(usuario),
        "token_type": "bearer",
        "expires_in": TOKEN_TTL_SECONDS,
        "usuario": {
            "id": str(usuario["id"]),
            "email": usuario["email"],
            "avatar_url": usuario.get("avatar_url"),
        },
    }


def _decodificar_token(token: str) -> dict:
    try:
        encabezado, carga, firma = token.split(".", 2)
        cabecera = json.loads(_unb64(encabezado))
        if cabecera != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("cabecera")
        base = f"{encabezado}.{carga}"
        esperada = hmac.new(_secret(), base.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(esperada, _unb64(firma)):
            raise ValueError("firma")
        datos = json.loads(_unb64(carga))
        if (
            datos.get("iss") != "reuniones-api"
            or int(datos.get("exp", 0)) <= int(time.time())
            or not datos.get("sub")
        ):
            raise ValueError("caducado")
        return datos
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="Sesión no válida o caducada") from None


def usuario_actual(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar")
    claims = _decodificar_token(authorization[7:].strip())
    response = (
        supabase.table(USERS_TABLE)
        .select("id, email, token_version")
        .eq("id", claims["sub"])
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=401, detail="La cuenta ya no está disponible")
    usuario = response.data[0]
    if int(usuario.get("token_version", 0)) != int(claims.get("ver", -1)):
        raise HTTPException(status_code=401, detail="La sesión se cerró por un cambio de contraseña")
    return usuario
