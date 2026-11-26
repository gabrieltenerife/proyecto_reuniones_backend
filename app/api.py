"""API HTTP para iniciar el procesamiento de una reunión ya subida."""

import hmac
import logging
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.consultas import (
    OpenAIConfigurationError,
    TranscriptNotFoundError,
    answer_meeting_question,
)
from app.procesador import (
    AudioNotFoundError,
    MeetingNotFoundError,
    process_meeting,
)


logger = logging.getLogger(__name__)
app = FastAPI(title="API de reuniones")


class PreguntaRequest(BaseModel):
    pregunta: str = Field(min_length=1, max_length=2000)


allowed_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=[
        "X-API-Key",
        "Content-Type",
        "ngrok-skip-browser-warning",
    ],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _validar_api_key(x_api_key: Optional[str]) -> None:
    expected_key = os.getenv("REUNIONES_API_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=503,
            detail="El backend no tiene configurada la clave de acceso",
        )
    if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="API key inválida")


@app.post("/reuniones/{meeting_id}/procesar")
def procesar_reunion(
    meeting_id: int,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict[str, object]:
    _validar_api_key(x_api_key)

    try:
        return process_meeting(meeting_id)
    except MeetingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except AudioNotFoundError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        logger.exception("Falló el procesamiento de la reunión %s", meeting_id)
        raise HTTPException(
            status_code=500,
            detail="No se pudo procesar la reunión",
        ) from error


@app.post("/reuniones/{meeting_id}/preguntar")
def preguntar_sobre_reunion(
    meeting_id: int,
    body: PreguntaRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> dict[str, object]:
    _validar_api_key(x_api_key)
    question = body.pregunta.strip()
    if not question:
        raise HTTPException(
            status_code=422,
            detail="La pregunta no puede estar vacía",
        )

    try:
        answer = answer_meeting_question(meeting_id, question)
        return {"id": meeting_id, "pregunta": question, "respuesta": answer}
    except MeetingNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TranscriptNotFoundError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except OpenAIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Falló la consulta de la reunión %s", meeting_id)
        raise HTTPException(
            status_code=500,
            detail="No se pudo responder la pregunta",
        ) from error
