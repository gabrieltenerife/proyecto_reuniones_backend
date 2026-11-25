import os

from openai import OpenAI

from database import supabase
from vocabulario import aplicar_correcciones


FRAGMENTOS_TABLE = "fragmentos"
MODELO_EMBEDDING = "text-embedding-3-small"
TAMANO_LOTE_EMBEDDINGS = 100
TAMANO_LOTE_INSERT = 200
MAX_SEGUNDOS = 60
MAX_CARACTERES = 800


def obtener_cliente_openai() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Falta OPENAI_API_KEY en el archivo .env")
    return OpenAI(api_key=api_key)


def generar_embeddings(textos: list[str]) -> list[list[float]]:
    if not textos:
        return []

    client = obtener_cliente_openai()
    vectores = []
    for inicio in range(0, len(textos), TAMANO_LOTE_EMBEDDINGS):
        lote = textos[inicio : inicio + TAMANO_LOTE_EMBEDDINGS]
        response = client.embeddings.create(model=MODELO_EMBEDDING, input=lote)
        vectores.extend(dato.embedding for dato in sorted(response.data, key=lambda d: d.index))
    return vectores


def construir_fragmentos(segments: list[dict], correcciones=()) -> list[dict]:
    fragmentos = []
    actual = None

    for segment in sorted(segments, key=lambda x: x["start"]):
        texto = aplicar_correcciones(segment["text"].strip(), correcciones)
        if not texto:
            continue

        hablante = str(segment["speaker"])
        continua = (
            actual is not None
            and actual["hablante"] == hablante
            and segment["end"] - actual["inicio"] <= MAX_SEGUNDOS
            and len(actual["texto"]) + len(texto) + 1 <= MAX_CARACTERES
        )

        if continua:
            actual["texto"] += " " + texto
            actual["fin"] = segment["end"]
        else:
            if actual is not None:
                fragmentos.append(actual)
            actual = {
                "inicio": segment["start"],
                "fin": segment["end"],
                "hablante": hablante,
                "texto": texto,
            }

    if actual is not None:
        fragmentos.append(actual)

    return fragmentos


def reindexar_reunion(meeting_id: int, transcripcion: dict, correcciones=()) -> int:
    fragmentos = construir_fragmentos(transcripcion["segments"], correcciones)
    embeddings = generar_embeddings([fragmento["texto"] for fragmento in fragmentos])

    filas = [
        {"doc_id": meeting_id, **fragmento, "embedding": embedding}
        for fragmento, embedding in zip(fragmentos, embeddings)
    ]

    supabase.table(FRAGMENTOS_TABLE).delete().eq("doc_id", meeting_id).execute()
    for inicio in range(0, len(filas), TAMANO_LOTE_INSERT):
        supabase.table(FRAGMENTOS_TABLE).insert(
            filas[inicio : inicio + TAMANO_LOTE_INSERT]
        ).execute()

    return len(filas)
