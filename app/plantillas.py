"""Define los tipos de reunión y construye las instrucciones para sus resúmenes."""

REGLAS_RESUMEN = (
    "Analiza la transcripción de una reunión y responde en español. "
    "No inventes información: si no se indica responsable o fecha, escribe "
    "'No especificado'. Distingue las propuestas de las decisiones acordadas. "
    "Si un apartado no aplica, indícalo brevemente."
)

TIPOS_REUNION = {
    "general": {
        "nombre": "General",
        "secciones": [
            "Resumen",
            "Temas e ideas clave",
            "Decisiones",
            "Tareas y compromisos",
            "Preguntas abiertas",
            "Bloqueos o riesgos",
        ],
    },
    "daily": {
        "nombre": "Daily",
        "secciones": [
            "Qué se avanzó",
            "Qué se hará hoy",
            "Bloqueos",
            "Compromisos por persona",
        ],
    },
    "comercial": {
        "nombre": "Comercial",
        "secciones": [
            "Contexto del cliente",
            "Necesidades detectadas",
            "Presupuesto y condiciones",
            "Objeciones",
            "Acuerdos con el cliente",
            "Próximos pasos",
        ],
    },
    "entrevista": {
        "nombre": "Entrevista",
        "secciones": [
            "Puesto y perfil buscado",
            "Competencias evaluadas con evidencias",
            "Puntos fuertes",
            "Dudas o riesgos",
            "Valoración según lo dicho en la reunión",
            "Siguientes pasos",
        ],
    },
    "uno_a_uno": {
        "nombre": "1:1",
        "secciones": [
            "Temas tratados",
            "Feedback dado y recibido",
            "Bloqueos y preocupaciones",
            "Acuerdos y compromisos",
            "Seguimiento para la próxima reunión",
        ],
    },
    "comite": {
        "nombre": "Comité",
        "secciones": [
            "Decisiones tomadas",
            "Aprobaciones y votaciones",
            "Riesgos y dependencias",
            "Temas pospuestos",
            "Acciones con responsable y fecha",
        ],
    },
}


def obtener_plantilla(tipo: str) -> dict:
    if tipo not in TIPOS_REUNION:
        raise ValueError(f"Tipo de reunión no válido: {tipo}")
    return TIPOS_REUNION[tipo]


def instrucciones_resumen(tipo: str, terminos: list[str]) -> str:
    apartados = "\n".join(f"- {seccion}" for seccion in obtener_plantilla(tipo)["secciones"])
    instrucciones = (
        f"{REGLAS_RESUMEN}\n"
        f"Organiza el resultado con estos apartados, en este orden:\n{apartados}"
    )
    if terminos:
        instrucciones += (
            "\nUsa exactamente estas grafías para nombres, siglas y términos: "
            + ", ".join(terminos)
        )
    return instrucciones
