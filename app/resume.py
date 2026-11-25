"""Genera el resumen de una reunión con su plantilla y lo guarda en Supabase."""

from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import os
import sys
from database import TABLE_NAME, supabase
from plantillas import instrucciones_resumen
from vocabulario import listar_terminos

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")


def generar_resumen(texto: str, tipo: str, owner_id: str | None = None) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Falta OPENAI_API_KEY en el archivo .env")

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-6-luna",
        instructions=instrucciones_resumen(tipo, listar_terminos(owner_id)),
        input=texto,
    )
    return response.output_text.strip()


def main() -> int:
    if len(sys.argv) != 2:
        raise ValueError("Se necesita el ID de la reunión en Supabase")

    meeting_id = int(sys.argv[1])
    record = (
        supabase.table(TABLE_NAME)
        .select("texto_bruto, tipo, owner_id")
        .eq("id", meeting_id)
        .single()
        .execute()
    )
    transcript = record.data["texto_bruto"].strip()
    if not transcript:
        raise ValueError("La transcripción completa está vacía en Supabase")

    resumen = generar_resumen(transcript, record.data["tipo"], record.data["owner_id"])

    supabase.table(TABLE_NAME).update({"texto_resumido": resumen}).eq("id", meeting_id).execute()

    print("Resumen guardado en Supabase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
