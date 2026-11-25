"""Carga las credenciales del backend y crea el cliente compartido de Supabase."""

from dotenv import load_dotenv
from pathlib import Path
from supabase import create_client
import os


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
TABLE_NAME = "Docs"

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_SECRET_KEY en el archivo .env")

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def propietario_por_email(email: str) -> str:
    response = (
        supabase.table("usuarios")
        .select("id")
        .eq("email", email.strip().lower())
        .limit(1)
        .execute()
    )
    if not response.data:
        raise ValueError(f"No existe una cuenta para REUNION_OWNER_EMAIL={email}")
    return str(response.data[0]["id"])
