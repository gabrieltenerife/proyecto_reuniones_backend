"""Administra términos propios y aplica las correcciones aprendidas al texto."""

import difflib
import re

from database import supabase


TABLE_NAME = "vocabulario"
PUNTUACION = ' .,;:!?¿¡"\'()[]'


def _filtrar_propietario(consulta, owner_id: str | None):
    return consulta.is_("owner_id", "null") if owner_id is None else consulta.eq("owner_id", owner_id)


def listar_vocabulario(owner_id: str | None = None) -> list[dict]:
    consulta = supabase.table(TABLE_NAME).select("id, termino, variante, created_at")
    response = _filtrar_propietario(consulta, owner_id).order("termino").execute()
    return response.data


def listar_terminos(owner_id: str | None = None) -> list[str]:
    return sorted({fila["termino"] for fila in listar_vocabulario(owner_id)})


def listar_correcciones(owner_id: str | None = None) -> list[dict]:
    return [fila for fila in listar_vocabulario(owner_id) if fila["variante"]]


def guardar_termino(termino: str, variante: str = "", owner_id: str | None = None) -> dict:
    termino = termino.strip()
    variante = variante.strip()
    if not termino:
        raise ValueError("El término no puede estar vacío")
    if owner_id is None:
        consulta = supabase.table(TABLE_NAME).select("id, termino, variante, created_at")
        existente = (
            _filtrar_propietario(consulta, None)
            .eq("termino", termino)
            .eq("variante", variante)
            .limit(1)
            .execute()
        )
        if existente.data:
            return existente.data[0]
        response = supabase.table(TABLE_NAME).insert(
            {"termino": termino, "variante": variante}
        ).execute()
    else:
        response = (
            supabase.table(TABLE_NAME)
            .upsert(
                {"owner_id": owner_id, "termino": termino, "variante": variante},
                on_conflict="owner_id,termino,variante",
            )
            .execute()
        )
    return response.data[0]


def eliminar_termino(termino_id: int, owner_id: str | None = None) -> None:
    consulta = supabase.table(TABLE_NAME).delete().eq("id", termino_id)
    _filtrar_propietario(consulta, owner_id).execute()


def reemplazar_palabra(texto: str, buscar: str, reemplazar: str) -> tuple[str, int]:
    patron = rf"(?<!\w){re.escape(buscar)}(?!\w)"
    return re.subn(patron, lambda _: reemplazar, texto, flags=re.IGNORECASE)


def aplicar_correcciones(texto: str, correcciones) -> str:
    for correccion in sorted(correcciones, key=lambda c: len(c["variante"]), reverse=True):
        texto, _ = reemplazar_palabra(texto, correccion["variante"], correccion["termino"])
    return texto


def sugerir_correcciones(antes: str, despues: str) -> list[dict]:
    palabras_antes = re.findall(r"\S+", antes)
    palabras_despues = re.findall(r"\S+", despues)
    sugerencias = []

    cambios = difflib.SequenceMatcher(None, palabras_antes, palabras_despues, autojunk=False)
    for operacion, i1, i2, j1, j2 in cambios.get_opcodes():
        if operacion != "replace" or i2 - i1 > 3 or j2 - j1 > 3:
            continue
        variante = " ".join(palabras_antes[i1:i2]).strip(PUNTUACION)
        termino = " ".join(palabras_despues[j1:j2]).strip(PUNTUACION)
        if len(variante) >= 3 and termino and variante != termino:
            sugerencias.append({"variante": variante, "termino": termino})

    return sugerencias
