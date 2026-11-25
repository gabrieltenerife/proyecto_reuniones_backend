"""Prepara y envía resúmenes por email o Slack, y registra cada intento."""

import json
import os
import re
import smtplib
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage

from database import supabase
from edicion import obtener_reunion
from plantillas import TIPOS_REUNION
from temas import temas_de_reunion


EXPORTACIONES_TABLE = "exportaciones"
LIMITE_SLACK = 35000


class ExportError(Exception):
    def __init__(self, mensaje: str, status_code: int):
        super().__init__(mensaje)
        self.status_code = status_code


@dataclass
class Contenido:
    titulo: str
    resumen: str
    temas: list[dict]


def destinos_disponibles() -> list[dict]:
    return [
        {"id": "email", "nombre": "Email", "configurado": _email_configurado()},
        {"id": "slack", "nombre": "Slack", "configurado": _slack_configurado()},
    ]


def _email_configurado() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def _slack_configurado() -> bool:
    return bool(os.getenv("SLACK_WEBHOOK_URL"))


def _config_email() -> dict:
    if not _email_configurado():
        raise ExportError("Email no configurado: faltan SMTP_HOST o SMTP_FROM en .env", 409)
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "usuario": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "remitente": os.getenv("SMTP_FROM"),
        "starttls": os.getenv("SMTP_STARTTLS", "true").lower() != "false",
    }


def _config_slack() -> str:
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        raise ExportError("Slack no configurado: falta SLACK_WEBHOOK_URL en .env", 409)
    return url


def construir_contenido(
    meeting_id: int, owner_id: str | None, incluir_temas: bool = True
) -> Contenido:
    reunion = obtener_reunion(meeting_id, "id, created_at, tipo, texto_resumido", owner_id)
    if reunion is None:
        raise ExportError("Reunión no encontrada", 404)
    if not (reunion["texto_resumido"] or "").strip():
        raise ExportError("La reunión no tiene resumen que exportar", 409)

    fecha = reunion["created_at"][:10]
    tipo = TIPOS_REUNION.get(reunion["tipo"], {"nombre": reunion["tipo"]})["nombre"]
    return Contenido(
        titulo=f"Resumen de reunión #{meeting_id} · {fecha} · {tipo}",
        resumen=reunion["texto_resumido"].strip(),
        temas=temas_de_reunion(meeting_id, owner_id) if incluir_temas else [],
    )


def _linea_tema(tema: dict) -> str:
    linea = f"{tema['titulo']} ({tema['estado_en_esta_reunion']}) · min {tema['minuto_en_esta_reunion']}"
    if tema["veces_mencionado"] > 1:
        linea += f" · visto en {tema['veces_mencionado']} reuniones desde hace {tema['dias_desde_primera']} días"
    return linea


def texto_email(contenido: Contenido) -> str:
    partes = [contenido.titulo, "", contenido.resumen]
    if contenido.temas:
        partes += ["", "Temas de esta reunión:"]
        partes += [f"- {_linea_tema(tema)}" for tema in contenido.temas]
    return "\n".join(partes)


def _mrkdwn(texto: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", texto)


def texto_slack(contenido: Contenido) -> str:
    resumen = _mrkdwn(contenido.resumen)
    partes = [f"*{contenido.titulo}*", "", resumen]
    if contenido.temas:
        partes += ["", "*Temas de esta reunión*"]
        partes += [f"• {_linea_tema(tema)}" for tema in contenido.temas]
    texto = "\n".join(partes)
    if len(texto) > LIMITE_SLACK:
        aviso = "\n\n_(mensaje recortado; ver el resumen completo en la app)_"
        texto = texto[: LIMITE_SLACK - len(aviso)].rstrip() + aviso
    return texto


def enviar_email(destinatarios: list[str], contenido: Contenido) -> None:
    config = _config_email()

    mensaje = EmailMessage()
    mensaje["Subject"] = contenido.titulo
    mensaje["From"] = config["remitente"]
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.set_content(texto_email(contenido))

    try:
        with smtplib.SMTP(config["host"], config["port"], timeout=20) as smtp:
            if config["starttls"]:
                smtp.starttls()
            if config["usuario"]:
                smtp.login(config["usuario"], config["password"] or "")
            smtp.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as error:
        raise ExportError(f"No se pudo enviar el email: {error}", 502)


def enviar_slack(contenido: Contenido) -> None:
    url = _config_slack()
    cuerpo = json.dumps({"text": texto_slack(contenido)}).encode("utf-8")
    peticion = urllib.request.Request(
        url, data=cuerpo, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(peticion, timeout=20) as respuesta:
            resultado = respuesta.read().decode("utf-8").strip()
            estado = respuesta.status
    except urllib.error.HTTPError as error:
        raise ExportError(f"Slack respondió con error {error.code}", 502)
    except (urllib.error.URLError, OSError) as error:
        raise ExportError(f"No se pudo conectar con Slack: {error}", 502)

    if estado != 200 or resultado != "ok":
        raise ExportError(f"Slack no confirmó el envío: {resultado[:200]}", 502)


def _registrar(meeting_id: int, destino: str, destinatario: str, estado: str, detalle: str) -> None:
    supabase.table(EXPORTACIONES_TABLE).insert(
        {
            "doc_id": meeting_id,
            "destino": destino,
            "destinatario": destinatario,
            "estado": estado,
            "detalle": detalle,
        }
    ).execute()


def exportar(
    meeting_id: int,
    destino: str,
    destinatarios: list[str] | None = None,
    incluir_temas: bool = True,
    owner_id: str | None = None,
) -> dict:
    destinatarios = destinatarios or []
    contenido = construir_contenido(meeting_id, owner_id, incluir_temas)
    etiqueta = ", ".join(destinatarios) if destino == "email" else "canal de Slack"

    try:
        if destino == "email":
            enviar_email(destinatarios, contenido)
        elif destino == "slack":
            enviar_slack(contenido)
        else:
            raise ExportError(f"Destino no soportado: {destino}", 422)
    except ExportError as error:
        _registrar(meeting_id, destino, etiqueta, "error", str(error))
        raise

    _registrar(meeting_id, destino, etiqueta, "enviado", "")
    return {"destino": destino, "estado": "enviado", "destinatarios": destinatarios}


def listar_exportaciones(meeting_id: int) -> list[dict]:
    response = (
        supabase.table(EXPORTACIONES_TABLE)
        .select("id, destino, destinatario, estado, detalle, created_at")
        .eq("doc_id", meeting_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data
