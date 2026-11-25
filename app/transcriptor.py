"""Transcribe el audio de entrada, conserva hablantes y tiempos, e inserta segmentos."""

from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
import os
from database import TABLE_NAME, supabase

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

with open("data/input/reunion.mp3", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="gpt-4o-transcribe-diarize",
        file=audio,
        response_format="diarized_json",
        chunking_strategy="auto"
    )

transcription = {
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

response = supabase.table(TABLE_NAME).insert(
    {
        "texto_bruto": "",
        "texto_resumido": "",
        "transcripcion": transcription,
    }
).execute()

print(response.data[0]["id"])
