"""API HTTP: reuniones, chat RAG, temas, vocabulario, edición y exportaciones."""

import os
import re
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

from database import TABLE_NAME, supabase
from edicion import guardar_version, listar_versiones, obtener_reunion, obtener_version
from exportacion import ExportError, destinos_disponibles, exportar, listar_exportaciones
from fragmentos import reindexar_reunion
from plantillas import TIPOS_REUNION
from rag import responder
from resume import generar_resumen
from temas import ESTADOS, actualizar_estado_tema, detalle_tema, extraer_temas_reunion, listar_temas, temas_de_reunion
from unificador import construir_texto_bruto
from vocabulario import (
    eliminar_termino,
    guardar_termino,
    listar_correcciones,
    listar_vocabulario,
    reemplazar_palabra,
    sugerir_correcciones,
)


API_KEY_FRONT = os.getenv("API_KEY_FRONT")
CORS_ORIGINS = [
    origen.strip() for origen in os.getenv("CORS_ORIGINS", "").split(",") if origen.strip()
]

if not API_KEY_FRONT:
    raise ValueError("Falta API_KEY_FRONT en el archivo .env")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_clave(clave: str | None = Security(api_key_header)) -> None:
    if not clave or not secrets.compare_digest(clave, API_KEY_FRONT):
        raise HTTPException(status_code=401, detail="Clave de API no válida")


app = FastAPI(title="Reuniones API", dependencies=[Depends(verificar_clave)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SegmentoEditado(BaseModel):
    texto: str = Field(min_length=1)


class Correccion(BaseModel):
    buscar: str = Field(min_length=1)
    reemplazar: str = Field(min_length=1)
    recordar: bool = True


class ResumenEditado(BaseModel):
    texto: str = Field(min_length=1)


class RegeneracionResumen(BaseModel):
    tipo: str | None = None


class TerminoNuevo(BaseModel):
    termino: str = Field(min_length=1)
    variante: str = ""


def _reunion_o_404(meeting_id: int, columnas: str) -> dict:
    reunion = obtener_reunion(meeting_id, columnas)
    if reunion is None:
        raise HTTPException(status_code=404, detail="Reunión no encontrada")
    return reunion


def _guardar_transcripcion(meeting_id: int, transcripcion: dict) -> None:
    correcciones = listar_correcciones()
    texto = construir_texto_bruto(transcripcion["segments"], correcciones)
    supabase.table(TABLE_NAME).update(
        {"transcripcion": transcripcion, "texto_bruto": texto}
    ).eq("id", meeting_id).execute()
    reindexar_reunion(meeting_id, transcripcion, correcciones)


@app.get("/tipos")
def listar_tipos() -> list[dict]:
    return [
        {"id": tipo_id, "nombre": plantilla["nombre"], "secciones": plantilla["secciones"]}
        for tipo_id, plantilla in TIPOS_REUNION.items()
    ]


@app.get("/reuniones")
def listar_reuniones() -> list[dict]:
    response = (
        supabase.table(TABLE_NAME)
        .select("id, created_at, tipo")
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


@app.get("/reuniones/{meeting_id}")
def detalle_reunion(meeting_id: int) -> dict:
    return _reunion_o_404(
        meeting_id, "id, created_at, tipo, texto_bruto, texto_resumido, transcripcion"
    )


@app.patch("/reuniones/{meeting_id}/segmentos/{indice}")
def editar_segmento(meeting_id: int, indice: int, cambio: SegmentoEditado) -> dict:
    reunion = _reunion_o_404(meeting_id, "transcripcion")
    transcripcion = reunion["transcripcion"]
    segmentos = transcripcion["segments"]
    if not 0 <= indice < len(segmentos):
        raise HTTPException(status_code=404, detail="Segmento no encontrado")

    original = segmentos[indice]["text"]
    guardar_version(meeting_id, "transcripcion", transcripcion, "edicion_segmento")

    nuevo_texto = cambio.texto.strip()
    segmentos[indice]["text"] = nuevo_texto
    _guardar_transcripcion(meeting_id, transcripcion)

    return {
        "segmento": segmentos[indice],
        "sugerencias_vocabulario": sugerir_correcciones(original, nuevo_texto),
    }


@app.post("/reuniones/{meeting_id}/correcciones")
def corregir_reunion(meeting_id: int, correccion: Correccion) -> dict:
    if correccion.buscar == correccion.reemplazar:
        raise HTTPException(status_code=422, detail="El texto nuevo debe ser distinto")

    reunion = _reunion_o_404(meeting_id, "transcripcion")
    transcripcion = reunion["transcripcion"]

    nuevos_segmentos = []
    total = 0
    for segmento in transcripcion["segments"]:
        texto, cantidad = reemplazar_palabra(
            segmento["text"], correccion.buscar, correccion.reemplazar
        )
        total += cantidad
        nuevos_segmentos.append({**segmento, "text": texto})

    if total == 0:
        raise HTTPException(status_code=404, detail="El texto a buscar no aparece en la reunión")

    guardar_version(meeting_id, "transcripcion", transcripcion, "correccion_global")
    _guardar_transcripcion(meeting_id, {**transcripcion, "segments": nuevos_segmentos})

    if correccion.recordar:
        guardar_termino(correccion.reemplazar, correccion.buscar)

    return {"reemplazos": total, "recordado": correccion.recordar}


@app.put("/reuniones/{meeting_id}/resumen")
def editar_resumen(meeting_id: int, cambio: ResumenEditado) -> dict:
    reunion = _reunion_o_404(meeting_id, "texto_resumido")
    guardar_version(meeting_id, "texto_resumido", reunion["texto_resumido"], "edicion_manual")

    nuevo_resumen = cambio.texto.strip()
    supabase.table(TABLE_NAME).update({"texto_resumido": nuevo_resumen}).eq(
        "id", meeting_id
    ).execute()
    return {"texto_resumido": nuevo_resumen}


@app.post("/reuniones/{meeting_id}/resumen/regenerar")
def regenerar_resumen(meeting_id: int, cuerpo: RegeneracionResumen) -> dict:
    reunion = _reunion_o_404(meeting_id, "tipo, texto_bruto, texto_resumido")
    tipo = cuerpo.tipo or reunion["tipo"]
    if tipo not in TIPOS_REUNION:
        raise HTTPException(status_code=422, detail="Tipo de reunión no válido")

    texto_bruto = (reunion["texto_bruto"] or "").strip()
    if not texto_bruto:
        raise HTTPException(status_code=409, detail="La transcripción completa está vacía")

    if reunion["texto_resumido"]:
        guardar_version(meeting_id, "texto_resumido", reunion["texto_resumido"], "antes_de_regenerar")

    resumen = generar_resumen(texto_bruto, tipo)
    supabase.table(TABLE_NAME).update({"tipo": tipo, "texto_resumido": resumen}).eq(
        "id", meeting_id
    ).execute()
    return {"tipo": tipo, "texto_resumido": resumen}


@app.get("/reuniones/{meeting_id}/versiones")
def listar_versiones_reunion(meeting_id: int) -> list[dict]:
    _reunion_o_404(meeting_id, "id")
    return listar_versiones(meeting_id)


@app.post("/reuniones/{meeting_id}/versiones/{version_id}/restaurar")
def restaurar_version(meeting_id: int, version_id: int) -> dict:
    version = obtener_version(meeting_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Versión no encontrada")

    valor = version["contenido"]["valor"]
    if version["campo"] == "transcripcion":
        reunion = _reunion_o_404(meeting_id, "transcripcion")
        guardar_version(meeting_id, "transcripcion", reunion["transcripcion"], "antes_de_restaurar")
        _guardar_transcripcion(meeting_id, valor)
    else:
        reunion = _reunion_o_404(meeting_id, "texto_resumido")
        guardar_version(meeting_id, "texto_resumido", reunion["texto_resumido"], "antes_de_restaurar")
        supabase.table(TABLE_NAME).update({"texto_resumido": valor}).eq("id", meeting_id).execute()

    return {"restaurada": version_id, "campo": version["campo"]}


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=3, max_length=1000)
    reuniones: list[int] | None = None
    limite: int = Field(default=8, ge=1, le=20)


@app.post("/preguntas")
def preguntar(cuerpo: Pregunta) -> dict:
    return responder(cuerpo.pregunta, cuerpo.reuniones, cuerpo.limite)


@app.post("/reuniones/{meeting_id}/indexar")
def indexar_reunion(meeting_id: int) -> dict:
    reunion = _reunion_o_404(meeting_id, "transcripcion")
    if not reunion["transcripcion"] or not reunion["transcripcion"].get("segments"):
        raise HTTPException(status_code=409, detail="La reunión no tiene transcripción")
    total = reindexar_reunion(meeting_id, reunion["transcripcion"], listar_correcciones())
    return {"fragmentos": total}


class CambioEstadoTema(BaseModel):
    estado: Literal["abierto", "resuelto", "pospuesto"]


@app.get("/temas")
def listar_temas_api(estado: str | None = None) -> list[dict]:
    if estado is not None and estado not in ESTADOS:
        raise HTTPException(status_code=422, detail="Estado no válido")
    return listar_temas(estado)


@app.get("/temas/{tema_id}")
def detalle_tema_api(tema_id: int) -> dict:
    tema = detalle_tema(tema_id)
    if tema is None:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return tema


@app.patch("/temas/{tema_id}")
def cambiar_estado_tema(tema_id: int, cambio: CambioEstadoTema) -> dict:
    if not actualizar_estado_tema(tema_id, cambio.estado):
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return detalle_tema(tema_id)


@app.get("/reuniones/{meeting_id}/temas")
def temas_reunion_api(meeting_id: int) -> list[dict]:
    _reunion_o_404(meeting_id, "id")
    return temas_de_reunion(meeting_id)


@app.post("/reuniones/{meeting_id}/temas/extraer")
def extraer_temas_api(meeting_id: int) -> dict:
    reunion = _reunion_o_404(meeting_id, "transcripcion")
    transcripcion = reunion["transcripcion"]
    if not transcripcion or not transcripcion.get("segments"):
        raise HTTPException(status_code=409, detail="La reunión no tiene transcripción")
    total = extraer_temas_reunion(meeting_id, transcripcion, listar_correcciones())
    return {"temas": total}


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SolicitudExportacion(BaseModel):
    destino: Literal["email", "slack"]
    destinatarios: list[str] = Field(default_factory=list, max_length=20)
    incluir_temas: bool = True

    @field_validator("destinatarios")
    @classmethod
    def validar_destinatarios(cls, valor: list[str]) -> list[str]:
        limpios = [correo.strip() for correo in valor if correo.strip()]
        for correo in limpios:
            if not EMAIL_RE.match(correo):
                raise ValueError(f"Email no válido: {correo}")
        return limpios


@app.get("/destinos")
def listar_destinos() -> list[dict]:
    return destinos_disponibles()


@app.post("/reuniones/{meeting_id}/exportar")
def exportar_reunion_api(meeting_id: int, cuerpo: SolicitudExportacion) -> dict:
    _reunion_o_404(meeting_id, "id")
    if cuerpo.destino == "email" and not cuerpo.destinatarios:
        raise HTTPException(status_code=422, detail="Indica al menos un destinatario de email")
    try:
        return exportar(meeting_id, cuerpo.destino, cuerpo.destinatarios, cuerpo.incluir_temas)
    except ExportError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error))


@app.get("/reuniones/{meeting_id}/exportaciones")
def historial_exportaciones(meeting_id: int) -> list[dict]:
    _reunion_o_404(meeting_id, "id")
    return listar_exportaciones(meeting_id)


@app.get("/vocabulario")
def listar_terminos_api() -> list[dict]:
    return listar_vocabulario()


@app.post("/vocabulario", status_code=201)
def crear_termino(nuevo: TerminoNuevo) -> dict:
    try:
        return guardar_termino(nuevo.termino, nuevo.variante)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@app.delete("/vocabulario/{termino_id}", status_code=204)
def borrar_termino(termino_id: int) -> None:
    eliminar_termino(termino_id)
