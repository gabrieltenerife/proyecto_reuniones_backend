import json

# Leer JSON
with open("extraccion/transcripcion.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Ordenar segmentos cronológicamente
segments = sorted(data["segments"], key=lambda x: x["start"])

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

# Guardar TXT
with open("extraccion/transcripcion_completa.txt", "w", encoding="utf-8") as f:
    f.write(texto)

print("Transcripción agrupada guardada correctamente.")