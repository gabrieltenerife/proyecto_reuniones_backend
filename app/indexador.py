"""CLI para indexar una reunión o reconstruir el índice de todas las reuniones."""

import sys
from database import TABLE_NAME, supabase
from fragmentos import reindexar_reunion
from vocabulario import listar_correcciones


def indexar(meeting_id: int) -> int:
    record = (
        supabase.table(TABLE_NAME)
        .select("transcripcion")
        .eq("id", meeting_id)
        .single()
        .execute()
    )
    transcripcion = record.data["transcripcion"]
    if not transcripcion or not transcripcion.get("segments"):
        return 0
    return reindexar_reunion(meeting_id, transcripcion, listar_correcciones())


def main() -> int:
    if len(sys.argv) > 2:
        raise ValueError("Uso: python app/indexador.py [id_reunion]")

    if len(sys.argv) == 2:
        ids = [int(sys.argv[1])]
    else:
        response = supabase.table(TABLE_NAME).select("id").order("id").execute()
        ids = [fila["id"] for fila in response.data]

    for meeting_id in ids:
        total = indexar(meeting_id)
        print(f"Reunión {meeting_id}: {total} fragmentos indexados.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
