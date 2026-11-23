import sys
from database import TABLE_NAME, supabase

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
segments = sorted(response.data["transcripcion"]["segments"], key=lambda x: x["start"])

# Agrupar intervenciones consecutivas
texto = ""
speaker_actual = None
frases = []

for segment in segments:
    speaker = segment["speaker"]

    if speaker != speaker_actual:
        if frases:
            texto += f"Hablante {speaker_actual}: {' '.join(frases)}\n\n"

        speaker_actual = speaker
        frases = [segment["text"]]
    else:
        frases.append(segment["text"])

# Guardar último hablante
if frases:
    texto += f"Hablante {speaker_actual}: {' '.join(frases)}"

supabase.table(TABLE_NAME).update({"texto_bruto": texto}).eq("id", meeting_id).execute()

print("Transcripción completa guardada en Supabase.")
