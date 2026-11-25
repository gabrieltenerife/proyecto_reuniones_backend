"""Servicios externos de prueba para el entorno local. No llaman a ningún servicio real.

- OpenAI compatible (http://127.0.0.1:8090/v1): embeddings y respuestas deterministas.
  Los embeddings reflejan palabras clave; las respuestas siguen reglas simples. Sirve para
  probar el flujo completo, no la calidad de los modelos.
- SMTP (127.0.0.1:8025): recibe y guarda los correos.
- Slack (http://127.0.0.1:8026/hook): recibe y guarda los mensajes del webhook.
- Consulta lo capturado en http://127.0.0.1:8026/_capturados y reinicia con POST /_reset.

    python local/servicios_de_prueba.py
"""
import base64
import json
import re
import struct
import threading
import time
import unicodedata
import zlib
from email import message_from_bytes
from email.header import decode_header, make_header
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from aiosmtpd.controller import Controller


PUERTO_OPENAI = 8090
PUERTO_SLACK = 8026
PUERTO_SMTP = 8025
DIMENSION = 1536

CONCEPTOS = [
    "presupuesto", "hosting", "contrat", "propuesta", "cliente", "kubernetes",
    "proyecto", "servidor", "entorno", "perfil", "comit", "cerrad", "aplaz",
    "seguimiento", "factura", "acuerdo",
]
TITULOS_TEMA = {
    "presupuesto": "Presupuesto",
    "hosting": "Hosting",
    "contrat": "Contratación",
    "propuesta": "Propuesta comercial",
}

capturados = {"slack": [], "smtp": []}
cerrojo = threading.Lock()


def normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_acentos if not unicodedata.combining(c))


def vector(texto: str) -> list[float]:
    t = normalizar(texto)
    v = [0.0] * DIMENSION
    for indice, concepto in enumerate(CONCEPTOS):
        if concepto in t:
            v[indice] = 1.0
    for palabra in re.findall(r"[a-z0-9]+", t):
        if len(palabra) > 3:
            v[100 + zlib.crc32(palabra.encode()) % 1400] += 0.05
    if not any(v):
        v[DIMENSION - 1] = 1.0
    return v


def texto_respuesta(texto: str, modelo: str) -> dict:
    return {
        "id": "resp_local",
        "object": "response",
        "created_at": int(time.time()),
        "model": modelo,
        "status": "completed",
        "output": [
            {
                "id": "msg_local",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": texto, "annotations": []}],
            }
        ],
        "output_text": texto,
    }


def respuesta_temas(entrada: str) -> str:
    fragmentos = re.findall(r"^\[(\d+)\] min [^\n]*: (.*)$", entrada, flags=re.MULTILINE)
    temas = []
    vistos = set()
    for numero, texto in fragmentos:
        t = normalizar(texto)
        for concepto, titulo in TITULOS_TEMA.items():
            if concepto in t and concepto not in vistos:
                vistos.add(concepto)
                if "cerrad" in t or "resuelt" in t:
                    estado = "resuelto"
                elif "aplaz" in t or "posponer" in t:
                    estado = "pospuesto"
                else:
                    estado = "abierto"
                temas.append({
                    "titulo": titulo,
                    "descripcion": texto.strip()[:120],
                    "estado": estado,
                    "fragmento": int(numero),
                })
    return json.dumps({"temas": temas}, ensure_ascii=False)


def respuesta_coincidencia(entrada: str) -> str:
    nuevo = re.search(r"Tema nuevo: ([^:\n]+):", entrada)
    if not nuevo:
        return json.dumps({"numero": 0})
    titulo = normalizar(nuevo.group(1)).strip()
    for numero, candidato in re.findall(r"^\[(\d+)\] ([^:\n]+):", entrada, flags=re.MULTILINE):
        if normalizar(candidato).strip() == titulo:
            return json.dumps({"numero": int(numero)})
    return json.dumps({"numero": 0})


def respuesta_pregunta(entrada: str) -> str:
    encontrados = re.findall(r"^\[(\d+)\] Reunión [^\n]*\n(.*)$", entrada, flags=re.MULTILINE)
    if not encontrados:
        return "No encuentro nada sobre eso en las reuniones guardadas."
    partes = [f"{texto.strip()} [{numero}]" for numero, texto in encontrados[:2]]
    return "Según las reuniones: " + " ".join(partes)


def respuesta_resumen(entrada: str) -> str:
    limpio = re.sub(r"\s+", " ", entrada).strip()
    return "**Resumen**: " + limpio[:250]


class HandlerOpenAI(BaseHTTPRequestHandler):
    def _enviar(self, codigo: int, datos: dict) -> None:
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self):
        longitud = int(self.headers.get("Content-Length", 0))
        peticion = json.loads(self.rfile.read(longitud) or b"{}")

        if self.path.endswith("/embeddings"):
            entradas = peticion["input"] if isinstance(peticion["input"], list) else [peticion["input"]]
            datos = []
            for indice, texto in enumerate(entradas):
                v = vector(texto)
                if peticion.get("encoding_format") == "base64":
                    codificado = base64.b64encode(struct.pack(f"<{DIMENSION}f", *v)).decode("ascii")
                else:
                    codificado = v
                datos.append({"object": "embedding", "index": indice, "embedding": codificado})
            return self._enviar(200, {
                "object": "list",
                "data": datos,
                "model": peticion.get("model", "text-embedding-3-small"),
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            })

        if self.path.endswith("/responses"):
            formato = (peticion.get("text") or {}).get("format", {})
            entrada = peticion.get("input") or ""
            instrucciones = peticion.get("instructions") or ""
            if formato.get("type") == "json_schema":
                nombre = formato.get("name")
                if nombre == "temas_reunion":
                    texto = respuesta_temas(entrada)
                elif nombre == "coincidencia_tema":
                    texto = respuesta_coincidencia(entrada)
                else:
                    texto = json.dumps({})
            elif "Fragmentos:" in entrada:
                texto = respuesta_pregunta(entrada)
            elif "apartados" in instrucciones:
                texto = respuesta_resumen(entrada)
            else:
                texto = "Respuesta de prueba."
            return self._enviar(200, texto_respuesta(texto, peticion.get("model", "gpt-6-luna")))

        self._enviar(404, {"error": "ruta no soportada por el servicio de prueba"})

    def log_message(self, *args):
        pass


class HandlerSlack(BaseHTTPRequestHandler):
    def _texto(self, codigo: int, texto: str) -> None:
        cuerpo = texto.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self):
        longitud = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(longitud)
        if self.path == "/_reset":
            with cerrojo:
                capturados["slack"].clear()
                capturados["smtp"].clear()
            return self._texto(200, "ok")
        if self.path == "/hook":
            with cerrojo:
                capturados["slack"].append(json.loads(cuerpo or b"{}"))
            return self._texto(200, "ok")
        self._texto(404, "no encontrado")

    def do_GET(self):
        if self.path == "/_capturados":
            with cerrojo:
                cuerpo = json.dumps(capturados, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        self._texto(404, "no encontrado")

    def log_message(self, *args):
        pass


class CapturaSMTP:
    async def handle_DATA(self, server, session, envelope):
        mensaje = message_from_bytes(envelope.content)
        asunto = str(make_header(decode_header(mensaje["Subject"] or "")))
        cuerpo = mensaje.get_payload(decode=True).decode("utf-8", errors="replace")
        with cerrojo:
            capturados["smtp"].append({
                "de": envelope.mail_from,
                "para": envelope.rcpt_tos,
                "asunto": asunto,
                "cuerpo": cuerpo,
            })
        return "250 OK"


def main() -> int:
    servidor_openai = ThreadingHTTPServer(("127.0.0.1", PUERTO_OPENAI), HandlerOpenAI)
    servidor_slack = ThreadingHTTPServer(("127.0.0.1", PUERTO_SLACK), HandlerSlack)
    threading.Thread(target=servidor_openai.serve_forever, daemon=True).start()
    threading.Thread(target=servidor_slack.serve_forever, daemon=True).start()

    smtp = Controller(CapturaSMTP(), hostname="127.0.0.1", port=PUERTO_SMTP)
    smtp.start()

    print(f"OpenAI de prueba: http://127.0.0.1:{PUERTO_OPENAI}/v1", flush=True)
    print(f"Slack de prueba:  http://127.0.0.1:{PUERTO_SLACK}/hook", flush=True)
    print(f"SMTP de prueba:   127.0.0.1:{PUERTO_SMTP}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        smtp.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
