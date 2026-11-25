"""Recupera fragmentos relevantes y responde preguntas con citas verificables."""

import re

from database import TABLE_NAME, supabase
from fragmentos import generar_embeddings, obtener_cliente_openai


MODELO_RESPUESTA = "gpt-6-luna"
INSTRUCCIONES = (
    "Respondes preguntas sobre reuniones usando solo los fragmentos que se te dan. "
    "Responde en español, de forma directa. Después de cada dato, indica el fragmento "
    "que lo respalda con su número entre corchetes, por ejemplo [2] o [1][3]. "
    "Si los fragmentos no contienen la respuesta, dilo claramente y no completes con suposiciones. "
    "Si varias reuniones tratan lo mismo con datos distintos, indica la fecha de cada una. "
    "Distingue lo propuesto de lo acordado."
)


def formatear_minuto(segundos: float) -> str:
    total = int(segundos)
    horas, resto = divmod(total, 3600)
    minutos, segundos_restantes = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02}:{segundos_restantes:02}"
    return f"{minutos:02}:{segundos_restantes:02}"


def buscar_fragmentos(
    pregunta: str, reuniones: list[int] | None, limite: int, owner_id: str
) -> list[dict]:
    embedding = generar_embeddings([pregunta])[0]
    response = supabase.rpc(
        "buscar_fragmentos",
        {
            "propietario": owner_id,
            "consulta": pregunta,
            "embedding_consulta": embedding,
            "reuniones": reuniones,
            "limite": limite,
        },
    ).execute()
    return response.data


def fechas_reuniones(ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    response = (
        supabase.table(TABLE_NAME)
        .select("id, created_at")
        .in_("id", list(ids))
        .execute()
    )
    return {fila["id"]: fila["created_at"][:10] for fila in response.data}


def linea_de_contexto(numero: int, fragmento: dict, fecha: str | None) -> str:
    cabecera = (
        f"[{numero}] Reunión #{fragmento['reunion_id']}"
        f"{f' ({fecha})' if fecha else ''}"
        f" · min {formatear_minuto(fragmento['inicio'])}"
        f" · Hablante {fragmento['hablante']}"
    )
    return f"{cabecera}\n{fragmento['texto']}"


def numeros_citados(respuesta: str, total: int) -> list[int]:
    citados = []
    for coincidencia in re.findall(r"\[(\d+)\]", respuesta):
        numero = int(coincidencia)
        if 1 <= numero <= total and numero not in citados:
            citados.append(numero)
    return citados


def responder(
    pregunta: str,
    reuniones: list[int] | None = None,
    limite: int = 8,
    owner_id: str = "",
) -> dict:
    pregunta = pregunta.strip()
    fragmentos = buscar_fragmentos(pregunta, reuniones, limite, owner_id)
    if not fragmentos:
        return {
            "respuesta": "No encuentro nada sobre eso en las reuniones guardadas.",
            "fuentes": [],
        }

    fechas = fechas_reuniones({fragmento["reunion_id"] for fragmento in fragmentos})
    contexto = "\n\n".join(
        linea_de_contexto(numero, fragmento, fechas.get(fragmento["reunion_id"]))
        for numero, fragmento in enumerate(fragmentos, 1)
    )

    response = obtener_cliente_openai().responses.create(
        model=MODELO_RESPUESTA,
        instructions=INSTRUCCIONES,
        input=f"Pregunta: {pregunta}\n\nFragmentos:\n\n{contexto}",
    )
    respuesta = response.output_text.strip()

    fuentes = []
    for numero in numeros_citados(respuesta, len(fragmentos)):
        fragmento = fragmentos[numero - 1]
        fuentes.append(
            {
                "referencia": numero,
                "reunion_id": fragmento["reunion_id"],
                "reunion_fecha": fechas.get(fragmento["reunion_id"]),
                "minuto": formatear_minuto(fragmento["inicio"]),
                "inicio_segundos": fragmento["inicio"],
                "hablante": fragmento["hablante"],
                "texto": fragmento["texto"],
            }
        )

    return {"respuesta": respuesta, "fuentes": fuentes}
