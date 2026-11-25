"""Carga reuniones de ejemplo en el entorno local, usando los scripts reales de app/.

Inserta la transcripción tal como la dejaría transcriptor.py y después ejecuta, en orden,
unificador.py, resume.py, indexador.py y extractor_temas.py para cada reunión.
Requiere el entorno local en marcha y los servicios de prueba (servicios_de_prueba.py).

    python local/semilla.py
"""
import subprocess
import sys
from pathlib import Path

import entorno

entorno.cargar()

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "app"))

from database import TABLE_NAME, supabase  # noqa: E402


REUNIONES = [
    {
        "tipo": "comercial",
        "created_at": "2026-11-03T10:00:00+00:00",
        "segmentos": [
            {"speaker": "A", "start": 12.0, "end": 40.0, "text": "Hablamos del cuberneti del proyecto con el cliente."},
            {"speaker": "B", "start": 41.0, "end": 60.0, "text": "El presupuesto acordado es de 20 mil euros."},
            {"speaker": "A", "start": 70.0, "end": 80.0, "text": "Perfecto, enviamos la propuesta el viernes."},
        ],
    },
    {
        "tipo": "daily",
        "created_at": "2026-11-22T10:00:00+00:00",
        "segmentos": [
            {"speaker": "A", "start": 0.0, "end": 10.0, "text": "Seguimos con el hosting del entorno."},
        ],
    },
    {
        "tipo": "comite",
        "created_at": "2026-11-25T10:00:00+00:00",
        "segmentos": [
            {"speaker": "B", "start": 5.0, "end": 15.0, "text": "El presupuesto sigue sin cerrarse con el cliente."},
            {"speaker": "A", "start": 20.0, "end": 30.0, "text": "Revisamos el hosting otra vez, ya cerrado."},
        ],
    },
]

PASOS = ["unificador.py", "resume.py", "indexador.py", "extractor_temas.py"]


def cargar_reunion(datos: dict) -> int:
    respuesta = (
        supabase.table(TABLE_NAME)
        .insert({
            "created_at": datos["created_at"],
            "tipo": datos["tipo"],
            "transcripcion": {"segments": datos["segmentos"]},
        })
        .execute()
    )
    return respuesta.data[0]["id"]


def ejecutar_pasos(meeting_id: int) -> None:
    for paso in PASOS:
        resultado = subprocess.run(
            [sys.executable, str(RAIZ / "app" / paso), str(meeting_id)],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            env=None,
        )
        if resultado.returncode != 0:
            raise SystemExit(f"Falló {paso} en la reunión {meeting_id}:\n{resultado.stderr}")
        print(f"  {paso}: {resultado.stdout.strip()}")


def main() -> int:
    ids = []
    for datos in REUNIONES:
        meeting_id = cargar_reunion(datos)
        ids.append(meeting_id)
        print(f"Reunión {meeting_id} creada ({datos['tipo']})")
        ejecutar_pasos(meeting_id)

    supabase.table("vocabulario").upsert(
        [
            {"termino": "Kubernetes", "variante": "cuberneti"},
            {"termino": "ACME", "variante": ""},
        ],
        on_conflict="termino,variante",
    ).execute()
    print("Vocabulario de ejemplo cargado")

    supabase.table("exportaciones").insert({
        "doc_id": ids[0],
        "destino": "slack",
        "destinatario": "canal de Slack",
        "estado": "error",
        "detalle": "Slack respondió con error 500",
    }).execute()

    print(f"Listo. Reuniones: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
