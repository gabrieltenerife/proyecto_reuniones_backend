"""Detecta temas, los relaciona entre reuniones y calcula su memoria y estado."""

import json
from datetime import date, datetime, timezone

from database import TABLE_NAME, supabase
from fragmentos import construir_fragmentos, generar_embeddings, obtener_cliente_openai
from rag import fechas_reuniones, formatear_minuto


TEMAS_TABLE = "temas"
MENCIONES_TABLE = "menciones_temas"
MODELO_TEMAS = "gpt-6-luna"
ESTADOS = ("abierto", "resuelto", "pospuesto")
UMBRAL_SIMILITUD = 0.45
CANDIDATOS_MAX = 5
DIAS_ANTIGUO = 14

INSTRUCCIONES_EXTRACCION = (
    "Extraes los temas de una reunión a partir de sus fragmentos numerados. Responde en español. "
    "Incluye solo asuntos relevantes: decisiones, preguntas abiertas, bloqueos, compromisos y temas aplazados. "
    "Para cada tema indica un título corto, una descripción de una frase, su estado y el número del "
    "fragmento donde se trata por primera vez. "
    "Estado: 'resuelto' si se decidió o cerró en esta reunión; 'pospuesto' si se aplazó explícitamente; "
    "'abierto' en cualquier otro caso. No inventes temas que no aparezcan en la reunión."
)
INSTRUCCIONES_COINCIDENCIA = (
    "Decides si un tema nuevo es el mismo asunto que alguno de los temas anteriores: mismo problema, "
    "decisión, pregunta o negociación, aunque se formule distinto. Responde con el número del tema "
    "anterior que coincide, o 0 si ninguno coincide. Ante la duda, responde 0."
)

ESQUEMA_TEMAS = {
    "type": "object",
    "properties": {
        "temas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "descripcion": {"type": "string"},
                    "estado": {"type": "string", "enum": list(ESTADOS)},
                    "fragmento": {"type": "integer"},
                },
                "required": ["titulo", "descripcion", "estado", "fragmento"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["temas"],
    "additionalProperties": False,
}

ESQUEMA_COINCIDENCIA = {
    "type": "object",
    "properties": {"numero": {"type": "integer"}},
    "required": ["numero"],
    "additionalProperties": False,
}


def _pedir_json(instrucciones: str, entrada: str, nombre: str, esquema: dict) -> dict:
    response = obtener_cliente_openai().responses.create(
        model=MODELO_TEMAS,
        instructions=instrucciones,
        input=entrada,
        text={"format": {"type": "json_schema", "name": nombre, "schema": esquema, "strict": True}},
    )
    return json.loads(response.output_text)


def extraer_temas_de_fragmentos(fragmentos: list[dict]) -> list[dict]:
    entrada = "\n".join(
        f"[{numero}] min {formatear_minuto(fragmento['inicio'])} · Hablante {fragmento['hablante']}: {fragmento['texto']}"
        for numero, fragmento in enumerate(fragmentos, 1)
    )
    return _pedir_json(INSTRUCCIONES_EXTRACCION, entrada, "temas_reunion", ESQUEMA_TEMAS)["temas"]


def decidir_coincidencia(tema: dict, candidatos: list[dict]) -> int | None:
    lineas = "\n".join(
        f"[{numero}] {candidato['titulo']}: {candidato['descripcion']} (estado: {candidato['estado']})"
        for numero, candidato in enumerate(candidatos, 1)
    )
    entrada = f"Tema nuevo: {tema['titulo']}: {tema['descripcion']}\n\nTemas anteriores:\n{lineas}"
    numero = _pedir_json(INSTRUCCIONES_COINCIDENCIA, entrada, "coincidencia_tema", ESQUEMA_COINCIDENCIA)["numero"]
    if 1 <= numero <= len(candidatos):
        return candidatos[numero - 1]["tema_id"]
    return None


def _buscar_similares(embedding: list[float], meeting_id: int) -> list[dict]:
    response = supabase.rpc(
        "buscar_temas_similares",
        {
            "embedding_consulta": embedding,
            "umbral": UMBRAL_SIMILITUD,
            "limite": CANDIDATOS_MAX,
            "excluir_reunion": meeting_id,
        },
    ).execute()
    return response.data


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _limpiar_reunion(meeting_id: int) -> None:
    supabase.table(MENCIONES_TABLE).delete().eq("doc_id", meeting_id).execute()

    temas_ids = [fila["id"] for fila in supabase.table(TEMAS_TABLE).select("id").execute().data]
    con_menciones = {fila["tema_id"] for fila in supabase.table(MENCIONES_TABLE).select("tema_id").execute().data}
    huerfanos = [tema_id for tema_id in temas_ids if tema_id not in con_menciones]
    if huerfanos:
        supabase.table(TEMAS_TABLE).delete().in_("id", huerfanos).execute()


def _crear_tema(tema: dict, embedding: list[float]) -> int:
    response = (
        supabase.table(TEMAS_TABLE)
        .insert(
            {
                "titulo": tema["titulo"],
                "descripcion": tema["descripcion"],
                "estado": tema["estado"],
                "embedding": embedding,
            }
        )
        .execute()
    )
    return response.data[0]["id"]


def extraer_temas_reunion(meeting_id: int, transcripcion: dict, correcciones=()) -> int:
    fragmentos = construir_fragmentos(transcripcion["segments"], correcciones)
    extraidos = extraer_temas_de_fragmentos(fragmentos) if fragmentos else []
    embeddings = generar_embeddings([f"{tema['titulo']}. {tema['descripcion']}" for tema in extraidos])

    _limpiar_reunion(meeting_id)

    for tema, embedding in zip(extraidos, embeddings):
        indice = min(max(tema["fragmento"], 1), len(fragmentos)) - 1
        minuto = fragmentos[indice]["inicio"]

        tema_id = None
        candidatos = _buscar_similares(embedding, meeting_id)
        if candidatos:
            tema_id = decidir_coincidencia(tema, candidatos)

        if tema_id is None:
            tema_id = _crear_tema(tema, embedding)
        else:
            supabase.table(TEMAS_TABLE).update(
                {"estado": tema["estado"], "updated_at": _ahora()}
            ).eq("id", tema_id).execute()

        supabase.table(MENCIONES_TABLE).insert(
            {
                "tema_id": tema_id,
                "doc_id": meeting_id,
                "estado": tema["estado"],
                "minuto": minuto,
                "resumen": tema["descripcion"],
            }
        ).execute()

    return len(extraidos)


def _mencion_publica(mencion: dict, fechas: dict) -> dict:
    return {
        "reunion_id": mencion["doc_id"],
        "reunion_fecha": fechas.get(mencion["doc_id"]),
        "minuto": formatear_minuto(mencion["minuto"]),
        "segundos": mencion["minuto"],
        "estado": mencion["estado"],
        "resumen": mencion["resumen"],
    }


def _formatear_tema(tema: dict, menciones: list[dict], fechas: dict, hoy: date) -> dict:
    menciones = sorted(menciones, key=lambda m: fechas.get(m["doc_id"], ""))
    primera = menciones[0] if menciones else None
    dias = (hoy - date.fromisoformat(fechas[primera["doc_id"]])).days if primera else 0

    alertas = []
    if tema["estado"] != "resuelto":
        if len(menciones) >= 2:
            alertas.append("recurrente")
        if dias >= DIAS_ANTIGUO:
            alertas.append("antiguo")

    return {
        "id": tema["id"],
        "titulo": tema["titulo"],
        "descripcion": tema["descripcion"],
        "estado": tema["estado"],
        "veces_mencionado": len(menciones),
        "dias_desde_primera": dias,
        "primera_mencion": _mencion_publica(primera, fechas) if primera else None,
        "ultima_mencion": _mencion_publica(menciones[-1], fechas) if menciones else None,
        "alertas": alertas,
        "menciones": [_mencion_publica(m, fechas) for m in menciones],
    }


def _cargar_temas(estado: str | None = None, tema_ids: list[int] | None = None) -> list[dict]:
    if tema_ids is not None and not tema_ids:
        return []

    consulta = supabase.table(TEMAS_TABLE).select("id, titulo, descripcion, estado")
    if estado:
        consulta = consulta.eq("estado", estado)
    if tema_ids is not None:
        consulta = consulta.in_("id", tema_ids)
    temas = consulta.execute().data
    if not temas:
        return []

    menciones = (
        supabase.table(MENCIONES_TABLE)
        .select("tema_id, doc_id, estado, minuto, resumen")
        .in_("tema_id", [tema["id"] for tema in temas])
        .execute()
        .data
    )
    fechas = fechas_reuniones({m["doc_id"] for m in menciones})
    hoy = date.today()

    por_tema: dict[int, list[dict]] = {}
    for mencion in menciones:
        por_tema.setdefault(mencion["tema_id"], []).append(mencion)

    formateados = [_formatear_tema(t, por_tema.get(t["id"], []), fechas, hoy) for t in temas]
    formateados.sort(key=lambda t: (len(t["alertas"]), t["dias_desde_primera"]), reverse=True)
    return formateados


def listar_temas(estado: str | None = None) -> list[dict]:
    return _cargar_temas(estado=estado)


def detalle_tema(tema_id: int) -> dict | None:
    temas = _cargar_temas(tema_ids=[tema_id])
    return temas[0] if temas else None


def temas_de_reunion(meeting_id: int) -> list[dict]:
    menciones = (
        supabase.table(MENCIONES_TABLE)
        .select("tema_id, estado, minuto")
        .eq("doc_id", meeting_id)
        .execute()
        .data
    )
    actuales = {m["tema_id"]: m for m in menciones}
    temas = _cargar_temas(tema_ids=list(actuales))

    for tema in temas:
        actual = actuales[tema["id"]]
        tema["estado_en_esta_reunion"] = actual["estado"]
        tema["minuto_en_esta_reunion"] = formatear_minuto(actual["minuto"])
        tema["segundos_en_esta_reunion"] = actual["minuto"]
    return temas


def actualizar_estado_tema(tema_id: int, estado: str) -> bool:
    if estado not in ESTADOS:
        raise ValueError(f"Estado no válido: {estado}")
    response = (
        supabase.table(TEMAS_TABLE)
        .update({"estado": estado, "updated_at": _ahora()})
        .eq("id", tema_id)
        .execute()
    )
    return bool(response.data)
