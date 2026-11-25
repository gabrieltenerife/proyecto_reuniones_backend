"""API HTTP: reuniones, chat RAG, temas, vocabulario, edición y exportaciones."""

import os
import re
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from auth import (
    buscar_usuario,
    crear_sesion,
    normalizar_email,
    registrar_usuario,
    usuario_actual,
    validar_email,
    verificar_password,
)
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


CORS_ORIGINS = [
    origen.strip() for origen in os.getenv("CORS_ORIGINS", "").split(",") if origen.strip()
]

app = FastAPI(title="Reuniones API")
router = APIRouter(dependencies=[Depends(usuario_actual)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Credenciales(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class Registro(Credenciales):
    @field_validator("password")
    @classmethod
    def validar_password(cls, valor: str) -> str:
        if len(valor) < 12:
            raise ValueError("La contraseña debe tener al menos 12 caracteres")
        return valor


@app.post("/auth/register", status_code=201)
def registrar(cuenta: Registro) -> dict:
    if not validar_email(cuenta.email):
        raise HTTPException(status_code=422, detail="Introduce un correo electrónico válido")
    try:
        usuario = registrar_usuario(cuenta.email, cuenta.password)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if usuario is None:
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese correo")
    return crear_sesion(usuario)


@app.post("/auth/login")
def iniciar_sesion(cuenta: Credenciales) -> dict:
    email = normalizar_email(cuenta.email)
    if not validar_email(email):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    usuario = buscar_usuario(email)
    hash_guardado = usuario["password_hash"] if usuario else (
        "pbkdf2_sha256$600000$MDEyMzQ1Njc4OWFiY2RlZg$"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    )
    password_correcta = verificar_password(cuenta.password, hash_guardado)
    if not usuario or not password_correcta:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    return crear_sesion(usuario)


@app.get("/auth/me")
def mi_cuenta(usuario: dict = Depends(usuario_actual)) -> dict:
    return {"id": str(usuario["id"]), "email": usuario["email"]}


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


def _reunion_o_404(meeting_id: int, columnas: str, owner_id: str) -> dict:
    reunion = obtener_reunion(meeting_id, columnas, owner_id)
    if reunion is None:
        raise HTTPException(status_code=404, detail="Reunión no encontrada")
    return reunion


def _guardar_transcripcion(meeting_id: int, transcripcion: dict, owner_id: str) -> None:
    correcciones = listar_correcciones(owner_id)
    texto = construir_texto_bruto(transcripcion["segments"], correcciones)
    supabase.table(TABLE_NAME).update(
        {"transcripcion": transcripcion, "texto_bruto": texto}
    ).eq("id", meeting_id).eq("owner_id", owner_id).execute()
    reindexar_reunion(meeting_id, transcripcion, correcciones)


@router.get("/tipos")
def listar_tipos() -> list[dict]:
    return [
        {"id": tipo_id, "nombre": plantilla["nombre"], "secciones": plantilla["secciones"]}
        for tipo_id, plantilla in TIPOS_REUNION.items()
    ]


@router.get("/reuniones")
def listar_reuniones(usuario: dict = Depends(usuario_actual)) -> list[dict]:
    response = (
        supabase.table(TABLE_NAME)
        .select("id, created_at, tipo")
        .eq("owner_id", usuario["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


@router.get("/reuniones/{meeting_id}")
def detalle_reunion(meeting_id: int, usuario: dict = Depends(usuario_actual)) -> dict:
    return _reunion_o_404(
        meeting_id,
        "id, created_at, tipo, texto_bruto, texto_resumido, transcripcion",
        usuario["id"],
    )


@router.patch("/reuniones/{meeting_id}/segmentos/{indice}")
def editar_segmento(
    meeting_id: int,
    indice: int,
    cambio: SegmentoEditado,
    usuario: dict = Depends(usuario_actual),
) -> dict:
    owner_id = usuario["id"]
    reunion = _reunion_o_404(meeting_id, "transcripcion", owner_id)
    transcripcion = reunion["transcripcion"]
    segmentos = transcripcion["segments"]
    if not 0 <= indice < len(segmentos):
        raise HTTPException(status_code=404, detail="Segmento no encontrado")

    original = segmentos[indice]["text"]
    guardar_version(meeting_id, "transcripcion", transcripcion, "edicion_segmento")

    nuevo_texto = cambio.texto.strip()
    segmentos[indice]["text"] = nuevo_texto
    _guardar_transcripcion(meeting_id, transcripcion, owner_id)

    return {
        "segmento": segmentos[indice],
        "sugerencias_vocabulario": sugerir_correcciones(original, nuevo_texto),
    }


@router.post("/reuniones/{meeting_id}/correcciones")
def corregir_reunion(
    meeting_id: int, correccion: Correccion, usuario: dict = Depends(usuario_actual)
) -> dict:
    owner_id = usuario["id"]
    if correccion.buscar == correccion.reemplazar:
        raise HTTPException(status_code=422, detail="El texto nuevo debe ser distinto")

    reunion = _reunion_o_404(meeting_id, "transcripcion", owner_id)
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
    _guardar_transcripcion(meeting_id, {**transcripcion, "segments": nuevos_segmentos}, owner_id)

    if correccion.recordar:
        guardar_termino(correccion.reemplazar, correccion.buscar, owner_id)

    return {"reemplazos": total, "recordado": correccion.recordar}


@router.put("/reuniones/{meeting_id}/resumen")
def editar_resumen(
    meeting_id: int, cambio: ResumenEditado, usuario: dict = Depends(usuario_actual)
) -> dict:
    owner_id = usuario["id"]
    reunion = _reunion_o_404(meeting_id, "texto_resumido", owner_id)
    guardar_version(meeting_id, "texto_resumido", reunion["texto_resumido"], "edicion_manual")

    nuevo_resumen = cambio.texto.strip()
    supabase.table(TABLE_NAME).update({"texto_resumido": nuevo_resumen}).eq(
        "id", meeting_id
    ).eq("owner_id", owner_id).execute()
    return {"texto_resumido": nuevo_resumen}


@router.post("/reuniones/{meeting_id}/resumen/regenerar")
def regenerar_resumen(
    meeting_id: int,
    cuerpo: RegeneracionResumen,
    usuario: dict = Depends(usuario_actual),
) -> dict:
    owner_id = usuario["id"]
    reunion = _reunion_o_404(meeting_id, "tipo, texto_bruto, texto_resumido", owner_id)
    tipo = cuerpo.tipo or reunion["tipo"]
    if tipo not in TIPOS_REUNION:
        raise HTTPException(status_code=422, detail="Tipo de reunión no válido")

    texto_bruto = (reunion["texto_bruto"] or "").strip()
    if not texto_bruto:
        raise HTTPException(status_code=409, detail="La transcripción completa está vacía")

    if reunion["texto_resumido"]:
        guardar_version(meeting_id, "texto_resumido", reunion["texto_resumido"], "antes_de_regenerar")

    resumen = generar_resumen(texto_bruto, tipo, owner_id)
    supabase.table(TABLE_NAME).update({"tipo": tipo, "texto_resumido": resumen}).eq(
        "id", meeting_id
    ).eq("owner_id", owner_id).execute()
    return {"tipo": tipo, "texto_resumido": resumen}


@router.get("/reuniones/{meeting_id}/versiones")
def listar_versiones_reunion(
    meeting_id: int, usuario: dict = Depends(usuario_actual)
) -> list[dict]:
    _reunion_o_404(meeting_id, "id", usuario["id"])
    return listar_versiones(meeting_id)


@router.post("/reuniones/{meeting_id}/versiones/{version_id}/restaurar")
def restaurar_version(
    meeting_id: int, version_id: int, usuario: dict = Depends(usuario_actual)
) -> dict:
    owner_id = usuario["id"]
    _reunion_o_404(meeting_id, "id", owner_id)
    version = obtener_version(meeting_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Versión no encontrada")

    valor = version["contenido"]["valor"]
    if version["campo"] == "transcripcion":
        reunion = _reunion_o_404(meeting_id, "transcripcion", owner_id)
        guardar_version(meeting_id, "transcripcion", reunion["transcripcion"], "antes_de_restaurar")
        _guardar_transcripcion(meeting_id, valor, owner_id)
    else:
        reunion = _reunion_o_404(meeting_id, "texto_resumido", owner_id)
        guardar_version(meeting_id, "texto_resumido", reunion["texto_resumido"], "antes_de_restaurar")
        supabase.table(TABLE_NAME).update({"texto_resumido": valor}).eq(
            "id", meeting_id
        ).eq("owner_id", owner_id).execute()

    return {"restaurada": version_id, "campo": version["campo"]}


class Pregunta(BaseModel):
    pregunta: str = Field(min_length=3, max_length=1000)
    reuniones: list[int] | None = None
    limite: int = Field(default=8, ge=1, le=20)


@router.post("/preguntas")
def preguntar(cuerpo: Pregunta, usuario: dict = Depends(usuario_actual)) -> dict:
    return responder(cuerpo.pregunta, cuerpo.reuniones, cuerpo.limite, usuario["id"])


@router.post("/reuniones/{meeting_id}/indexar")
def indexar_reunion(meeting_id: int, usuario: dict = Depends(usuario_actual)) -> dict:
    owner_id = usuario["id"]
    reunion = _reunion_o_404(meeting_id, "transcripcion", owner_id)
    if not reunion["transcripcion"] or not reunion["transcripcion"].get("segments"):
        raise HTTPException(status_code=409, detail="La reunión no tiene transcripción")
    total = reindexar_reunion(
        meeting_id, reunion["transcripcion"], listar_correcciones(owner_id)
    )
    return {"fragmentos": total}


class CambioEstadoTema(BaseModel):
    estado: Literal["abierto", "resuelto", "pospuesto"]


@router.get("/temas")
def listar_temas_api(
    estado: str | None = None, usuario: dict = Depends(usuario_actual)
) -> list[dict]:
    if estado is not None and estado not in ESTADOS:
        raise HTTPException(status_code=422, detail="Estado no válido")
    return listar_temas(usuario["id"], estado)


@router.get("/temas/{tema_id}")
def detalle_tema_api(tema_id: int, usuario: dict = Depends(usuario_actual)) -> dict:
    tema = detalle_tema(usuario["id"], tema_id)
    if tema is None:
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return tema


@router.patch("/temas/{tema_id}")
def cambiar_estado_tema(
    tema_id: int, cambio: CambioEstadoTema, usuario: dict = Depends(usuario_actual)
) -> dict:
    owner_id = usuario["id"]
    if not actualizar_estado_tema(tema_id, cambio.estado, owner_id):
        raise HTTPException(status_code=404, detail="Tema no encontrado")
    return detalle_tema(owner_id, tema_id)


@router.get("/reuniones/{meeting_id}/temas")
def temas_reunion_api(
    meeting_id: int, usuario: dict = Depends(usuario_actual)
) -> list[dict]:
    owner_id = usuario["id"]
    _reunion_o_404(meeting_id, "id", owner_id)
    return temas_de_reunion(meeting_id, owner_id)


@router.post("/reuniones/{meeting_id}/temas/extraer")
def extraer_temas_api(meeting_id: int, usuario: dict = Depends(usuario_actual)) -> dict:
    owner_id = usuario["id"]
    reunion = _reunion_o_404(meeting_id, "transcripcion", owner_id)
    transcripcion = reunion["transcripcion"]
    if not transcripcion or not transcripcion.get("segments"):
        raise HTTPException(status_code=409, detail="La reunión no tiene transcripción")
    total = extraer_temas_reunion(
        meeting_id, transcripcion, listar_correcciones(owner_id), owner_id
    )
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


@router.get("/destinos")
def listar_destinos() -> list[dict]:
    return destinos_disponibles()


@router.post("/reuniones/{meeting_id}/exportar")
def exportar_reunion_api(
    meeting_id: int,
    cuerpo: SolicitudExportacion,
    usuario: dict = Depends(usuario_actual),
) -> dict:
    owner_id = usuario["id"]
    _reunion_o_404(meeting_id, "id", owner_id)
    if cuerpo.destino == "email" and not cuerpo.destinatarios:
        raise HTTPException(status_code=422, detail="Indica al menos un destinatario de email")
    try:
        return exportar(
            meeting_id,
            cuerpo.destino,
            cuerpo.destinatarios,
            cuerpo.incluir_temas,
            owner_id,
        )
    except ExportError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error))


@router.get("/reuniones/{meeting_id}/exportaciones")
def historial_exportaciones(
    meeting_id: int, usuario: dict = Depends(usuario_actual)
) -> list[dict]:
    _reunion_o_404(meeting_id, "id", usuario["id"])
    return listar_exportaciones(meeting_id)


@router.get("/vocabulario")
def listar_terminos_api(usuario: dict = Depends(usuario_actual)) -> list[dict]:
    return listar_vocabulario(usuario["id"])


@router.post("/vocabulario", status_code=201)
def crear_termino(nuevo: TerminoNuevo, usuario: dict = Depends(usuario_actual)) -> dict:
    try:
        return guardar_termino(nuevo.termino, nuevo.variante, usuario["id"])
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.delete("/vocabulario/{termino_id}", status_code=204)
def borrar_termino(termino_id: int, usuario: dict = Depends(usuario_actual)) -> None:
    eliminar_termino(termino_id, usuario["id"])


app.include_router(router)
