from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import os
import sys
from database import TABLE_NAME, supabase

ROOT_DIR = Path(__file__).resolve().parent.parent

load_dotenv(ROOT_DIR / ".env")

if len(sys.argv) != 2:
    raise ValueError("Se necesita el ID de la reunión en Supabase")

meeting_id = int(sys.argv[1])
record = (
    supabase.table(TABLE_NAME)
    .select("texto_bruto")
    .eq("id", meeting_id)
    .single()
    .execute()
)
transcript = record.data["texto_bruto"].strip()
if not transcript:
    raise ValueError("La transcripción completa está vacía en Supabase")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Falta OPENAI_API_KEY en el archivo .env")

client = OpenAI(api_key=api_key)
response = client.responses.create(
    model="gpt-6-luna",
    instructions=(
        "Analiza la transcripción de una reunión y responde en español. "
        "Organiza el resultado con estos apartados: Resumen, Temas e ideas clave, "
        "Decisiones, Tareas y compromisos, Preguntas abiertas, y Bloqueos o riesgos. "
        "No inventes información: si no se indica responsable o fecha, escribe "
        "'No especificado'. Distingue las propuestas de las decisiones acordadas. "
        "Si un apartado no aplica, indícalo brevemente."
    ),
    input=transcript,
)

supabase.table(TABLE_NAME).update(
    {"texto_resumido": response.output_text.strip()}
).eq("id", meeting_id).execute()

print("Resumen guardado en Supabase.")
