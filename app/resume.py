from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
TRANSCRIPT_PATH = ROOT_DIR / "data" / "output" / "transcripcion_completa.txt"
SUMMARY_PATH = ROOT_DIR / "data" / "output" / "resumen_reunion.txt"

load_dotenv(ROOT_DIR / ".env")

if not TRANSCRIPT_PATH.exists():
    raise FileNotFoundError(f"No se encontró la transcripción: {TRANSCRIPT_PATH}")

transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8").strip()
if not transcript:
    raise ValueError(f"La transcripción está vacía: {TRANSCRIPT_PATH}")

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

SUMMARY_PATH.write_text(response.output_text.strip() + "\n", encoding="utf-8")
print(f"Resumen guardado en {SUMMARY_PATH.relative_to(ROOT_DIR)}")
