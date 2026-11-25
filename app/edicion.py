"""Lectura de reuniones y persistencia del historial de transcripciones y resúmenes."""

from database import TABLE_NAME, supabase


VERSIONES_TABLE = "versiones"


def obtener_reunion(meeting_id: int, columnas: str) -> dict | None:
    response = supabase.table(TABLE_NAME).select(columnas).eq("id", meeting_id).execute()
    return response.data[0] if response.data else None


def guardar_version(meeting_id: int, campo: str, valor, origen: str) -> None:
    supabase.table(VERSIONES_TABLE).insert(
        {
            "doc_id": meeting_id,
            "campo": campo,
            "contenido": {"valor": valor},
            "origen": origen,
        }
    ).execute()


def listar_versiones(meeting_id: int) -> list[dict]:
    response = (
        supabase.table(VERSIONES_TABLE)
        .select("id, campo, origen, created_at")
        .eq("doc_id", meeting_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data


def obtener_version(meeting_id: int, version_id: int) -> dict | None:
    response = (
        supabase.table(VERSIONES_TABLE)
        .select("id, campo, contenido")
        .eq("doc_id", meeting_id)
        .eq("id", version_id)
        .execute()
    )
    return response.data[0] if response.data else None
