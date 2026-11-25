import sys
from database import TABLE_NAME, supabase
from vocabulario import aplicar_correcciones, listar_correcciones


def construir_texto_bruto(segments: list[dict], correcciones=()) -> str:
    texto = ""
    speaker_actual = None
    frases = []

    for segment in sorted(segments, key=lambda x: x["start"]):
        speaker = segment["speaker"]
        frase = aplicar_correcciones(segment["text"], correcciones)

        if speaker != speaker_actual:
            if frases:
                texto += f"Hablante {speaker_actual}: {' '.join(frases)}\n\n"

            speaker_actual = speaker
            frases = [frase]
        else:
            frases.append(frase)

    if frases:
        texto += f"Hablante {speaker_actual}: {' '.join(frases)}"

    return texto


def main() -> int:
    if len(sys.argv) != 2:
        raise ValueError("Se necesita el ID de la reunión en Supabase")

    meeting_id = int(sys.argv[1])
    response = (
        supabase.table(TABLE_NAME)
        .select("transcripcion")
        .eq("id", meeting_id)
        .single()
        .execute()
    )
    texto = construir_texto_bruto(
        response.data["transcripcion"]["segments"],
        listar_correcciones(),
    )

    supabase.table(TABLE_NAME).update({"texto_bruto": texto}).eq("id", meeting_id).execute()

    print("Transcripción completa guardada en Supabase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
