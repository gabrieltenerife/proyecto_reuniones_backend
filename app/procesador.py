"""Descarga y procesa el audio asociado a una reunión existente."""

import mimetypes
import os
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from app.database import TABLE_NAME, supabase


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

AUDIO_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "meeting-audios")
TRANSCRIPTION_MODEL = os.getenv(
    "OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-transcribe-diarize"
)
SUMMARY_MODEL = os.getenv("OPENAI_SUMMARY_MODEL", "gpt-6-luna")


class MeetingNotFoundError(LookupError):
    """La reunión no existe en la tabla Docs."""


class AudioNotFoundError(ValueError):
    """La reunión no tiene una ruta de audio asociada."""


def _get_field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value[name]
    return getattr(value, name)


def _format_transcript(segments: list[dict[str, Any]]) -> str:
    ordered_segments = sorted(segments, key=lambda segment: segment["start"])
    blocks: list[str] = []
    current_speaker: Any = None
    current_phrases: list[str] = []

    for segment in ordered_segments:
        speaker = segment.get("speaker") or "desconocido"
        phrase = segment.get("text", "").strip()
        if not phrase:
            continue

        if speaker != current_speaker:
            if current_phrases:
                blocks.append(
                    f"Hablante {current_speaker}: {' '.join(current_phrases)}"
                )
            current_speaker = speaker
            current_phrases = [phrase]
        else:
            current_phrases.append(phrase)

    if current_phrases:
        blocks.append(f"Hablante {current_speaker}: {' '.join(current_phrases)}")

    return "\n\n".join(blocks)


def process_meeting(meeting_id: int) -> dict[str, Any]:
    """Procesa el audio ya subido y actualiza la fila existente de Docs."""
    record_response = (
        supabase.table(TABLE_NAME)
        .select("audio_path")
        .eq("id", meeting_id)
        .limit(1)
        .execute()
    )
    if not record_response.data:
        raise MeetingNotFoundError(f"No existe la reunión {meeting_id}")

    audio_path = record_response.data[0].get("audio_path")
    if not audio_path:
        raise AudioNotFoundError("La reunión todavía no tiene audio_path")

    audio_bytes = supabase.storage.from_(AUDIO_BUCKET).download(audio_path)
    if not audio_bytes:
        raise AudioNotFoundError("El archivo de audio está vacío o no existe")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Falta OPENAI_API_KEY en la configuración del backend")

    filename = Path(audio_path).name
    content_type = mimetypes.guess_type(filename)[0] or "audio/mpeg"
    client = OpenAI(api_key=api_key)

    transcription_result = client.audio.transcriptions.create(
        model=TRANSCRIPTION_MODEL,
        file=(filename, BytesIO(audio_bytes), content_type),
        response_format="diarized_json",
        chunking_strategy="auto",
    )

    segments = [
        {
            "speaker": _get_field(segment, "speaker"),
            "start": _get_field(segment, "start"),
            "end": _get_field(segment, "end"),
            "text": _get_field(segment, "text"),
        }
        for segment in transcription_result.segments
    ]
    if not segments:
        raise ValueError("El servicio de transcripción no devolvió segmentos")

    raw_transcript = _format_transcript(segments)
    if not raw_transcript:
        raise ValueError("La transcripción completa está vacía")

    summary_result = client.responses.create(
        model=SUMMARY_MODEL,
        instructions=(
            "Analiza la transcripción de una reunión y responde en español. "
            "Organiza el resultado con estos apartados: Resumen, Temas e ideas clave, "
            "Decisiones, Tareas y compromisos, Preguntas abiertas, y Bloqueos o riesgos. "
            "No inventes información: si no se indica responsable o fecha, escribe "
            "'No especificado'. Distingue las propuestas de las decisiones acordadas. "
            "Si un apartado no aplica, indícalo brevemente."
        ),
        input=raw_transcript,
    )
    summary = summary_result.output_text.strip()
    if not summary:
        raise ValueError("El servicio de resumen devolvió un resultado vacío")

    supabase.table(TABLE_NAME).update(
        {
            "transcripcion": {"segments": segments},
            "texto_bruto": raw_transcript,
            "texto_resumido": summary,
        }
    ).eq("id", meeting_id).execute()

    return {
        "id": meeting_id,
        "status": "processed",
        "segments": len(segments),
    }
