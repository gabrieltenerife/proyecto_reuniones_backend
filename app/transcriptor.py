from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import json
import os

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("data/input/reunion.mp3", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="gpt-4o-transcribe-diarize",
        file=audio,
        response_format="diarized_json",
        chunking_strategy="auto"
    )

# Crear carpeta si no existe
os.makedirs("data/output", exist_ok=True)

# Guardar transcripción
data = {
    "segments": [
        {
            "speaker": segment.speaker,
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        }
        for segment in result.segments
    ]
}

with open("data/output/transcripcion.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("Transcripción guardada en data/output/transcripcion.json")
