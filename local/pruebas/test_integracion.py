"""Pruebas de integración contra el entorno local real (Postgres + PostgREST + API).

Requisitos, en este orden:
  1. docker compose -f local/docker-compose.yml up -d
  2. python local/servicios_de_prueba.py      (OpenAI, SMTP y Slack de prueba)
  3. python local/semilla.py                  (reuniones de ejemplo)
  4. python local/api_local.py                (API en http://127.0.0.1:8000)

Ejecutar:
    python -m unittest discover -s local/pruebas -v
"""
import json
import os
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

LOCAL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LOCAL))

import entorno  # noqa: E402

entorno.cargar()

import semilla  # noqa: E402
from database import TABLE_NAME, supabase  # noqa: E402
from vocabulario import guardar_termino  # noqa: E402


API = os.getenv("API_URL", "http://127.0.0.1:8000")
SERVICIOS = "http://127.0.0.1:8026"
EMAIL_PRUEBAS = "integracion@reuniones.test"
PASSWORD_PRUEBAS = "Pruebas-locales-seguras-2026"
TOKEN = None
OWNER_ID = None
DATOS_BASE_CARGADOS = False


def llamar(metodo: str, ruta: str, cuerpo=None, token: str | None = "__predeterminado__"):
    cabeceras = {}
    token = TOKEN if token == "__predeterminado__" else token
    if token is not None:
        cabeceras["Authorization"] = f"Bearer {token}"
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        cabeceras["Content-Type"] = "application/json"
    peticion = urllib.request.Request(API + ruta, data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            texto = respuesta.read().decode("utf-8")
            return respuesta.status, (json.loads(texto) if texto else None)
    except urllib.error.HTTPError as error:
        texto = error.read().decode("utf-8")
        try:
            return error.code, json.loads(texto)
        except json.JSONDecodeError:
            return error.code, texto


def capturados() -> dict:
    with urllib.request.urlopen(SERVICIOS + "/_capturados", timeout=10) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def nueva_reunion(tipo: str = "comercial", segmentos=None) -> int:
    datos = {
        "tipo": tipo,
        "created_at": "2026-11-20T10:00:00+00:00",
        "segmentos": segmentos or [
            {"speaker": "A", "start": 10.0, "end": 20.0, "text": "Hablamos del cuberneti con el cliente."},
            {"speaker": "B", "start": 21.0, "end": 30.0, "text": "El presupuesto propuesto es de 15 mil euros."},
            {"speaker": "A", "start": 40.0, "end": 50.0, "text": "Enviamos la propuesta el lunes."},
        ],
    }
    meeting_id = semilla.cargar_reunion({**datos, "owner_id": OWNER_ID})
    semilla.ejecutar_pasos(meeting_id)
    return meeting_id


class BaseIntegracion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global TOKEN, OWNER_ID, DATOS_BASE_CARGADOS
        if TOKEN is None:
            estado, datos = llamar(
                "POST",
                "/auth/register",
                {"email": EMAIL_PRUEBAS, "password": PASSWORD_PRUEBAS},
                token=None,
            )
            if estado == 409:
                estado, datos = llamar(
                    "POST",
                    "/auth/login",
                    {"email": EMAIL_PRUEBAS, "password": PASSWORD_PRUEBAS},
                    token=None,
                )
            if estado not in (200, 201):
                raise unittest.SkipTest("La API no tiene el login nuevo o no responde.")
            TOKEN = datos["access_token"]
            OWNER_ID = datos["usuario"]["id"]

        estado, _ = llamar("GET", "/tipos")
        if estado != 200:
            raise unittest.SkipTest("La API local no responde. Revisa los pasos del docstring.")

        if not DATOS_BASE_CARGADOS:
            estado, reuniones = llamar("GET", "/reuniones")
            if estado == 200 and not reuniones:
                for datos in semilla.REUNIONES:
                    meeting_id = semilla.cargar_reunion({**datos, "owner_id": OWNER_ID})
                    semilla.ejecutar_pasos(meeting_id)
                guardar_termino("Kubernetes", "cuberneti", OWNER_ID)
                guardar_termino("ACME", "", OWNER_ID)
            DATOS_BASE_CARGADOS = True


class AutenticacionYLectura(BaseIntegracion):
    def test_sin_sesion_devuelve_401(self):
        estado, _ = llamar("GET", "/reuniones", token=None)
        self.assertEqual(estado, 401)

    def test_token_incorrecto_devuelve_401(self):
        estado, _ = llamar("GET", "/reuniones", token="mal")
        self.assertEqual(estado, 401)

    def test_login_y_separacion_entre_usuarios(self):
        estado, sesion = llamar(
            "POST",
            "/auth/login",
            {"email": EMAIL_PRUEBAS, "password": PASSWORD_PRUEBAS},
            token=None,
        )
        self.assertEqual(estado, 200)
        self.assertEqual(sesion["usuario"]["id"], OWNER_ID)

        correo_otro = "aislamiento@reuniones.test"
        estado, otra_sesion = llamar(
            "POST",
            "/auth/register",
            {"email": correo_otro, "password": PASSWORD_PRUEBAS},
            token=None,
        )
        if estado == 409:
            estado, otra_sesion = llamar(
                "POST",
                "/auth/login",
                {"email": correo_otro, "password": PASSWORD_PRUEBAS},
                token=None,
            )
        self.assertIn(estado, (200, 201))
        estado, reuniones_otro = llamar(
            "GET", "/reuniones", token=otra_sesion["access_token"]
        )
        self.assertEqual(estado, 200)
        self.assertEqual(reuniones_otro, [])

    def test_tipos_de_reunion(self):
        estado, datos = llamar("GET", "/tipos")
        self.assertEqual(estado, 200)
        self.assertEqual({t["id"] for t in datos}, {"general", "daily", "comercial", "entrevista", "uno_a_uno", "comite"})

    def test_listado_y_detalle(self):
        meeting_id = nueva_reunion()
        estado, lista = llamar("GET", "/reuniones")
        self.assertEqual(estado, 200)
        self.assertIn(meeting_id, [r["id"] for r in lista])

        estado, detalle = llamar("GET", f"/reuniones/{meeting_id}")
        self.assertEqual(estado, 200)
        self.assertEqual(len(detalle["transcripcion"]["segments"]), 3)
        self.assertTrue(detalle["texto_bruto"].startswith("Hablante A:"))
        self.assertTrue(detalle["texto_resumido"].startswith("**Resumen**"))

    def test_reunion_inexistente_404(self):
        estado, _ = llamar("GET", "/reuniones/999999")
        self.assertEqual(estado, 404)


class EdicionDeTranscripcion(BaseIntegracion):
    def test_editar_segmento_reindexa_y_sugiere_vocabulario(self):
        meeting_id = nueva_reunion()
        estado, antes = llamar("POST", f"/reuniones/{meeting_id}/indexar")
        self.assertEqual(estado, 200)
        fragmentos_antes = antes["fragmentos"]

        estado, datos = llamar("PATCH", f"/reuniones/{meeting_id}/segmentos/0",
                               {"texto": "Hablamos del Kubernetes con el cliente."})
        self.assertEqual(estado, 200, datos)
        self.assertIn({"variante": "cuberneti", "termino": "Kubernetes"}, datos["sugerencias_vocabulario"])

        detalle = llamar("GET", f"/reuniones/{meeting_id}")[1]
        self.assertIn("Hablamos del Kubernetes", detalle["texto_bruto"])
        filas = supabase.table("fragmentos").select("id").eq("doc_id", meeting_id).execute().data
        self.assertEqual(len(filas), fragmentos_antes)

        versiones = llamar("GET", f"/reuniones/{meeting_id}/versiones")[1]
        self.assertIn("edicion_segmento", [v["origen"] for v in versiones])

    def test_indice_fuera_de_rango(self):
        meeting_id = nueva_reunion()
        estado, _ = llamar("PATCH", f"/reuniones/{meeting_id}/segmentos/99", {"texto": "x"})
        self.assertEqual(estado, 404)

    def test_correccion_global_recuerda_en_vocabulario(self):
        meeting_id = nueva_reunion()
        estado, datos = llamar("POST", f"/reuniones/{meeting_id}/correcciones",
                               {"buscar": "propuesta", "reemplazar": "propuesta comercial", "recordar": True})
        self.assertEqual(estado, 200, datos)
        self.assertEqual(datos["reemplazos"], 1)
        self.assertTrue(datos["recordado"])

        vocabulario = llamar("GET", "/vocabulario")[1]
        self.assertTrue(any(v["termino"] == "propuesta comercial" and v["variante"] == "propuesta" for v in vocabulario))

        detalle = llamar("GET", f"/reuniones/{meeting_id}")[1]
        self.assertIn("propuesta comercial", detalle["transcripcion"]["segments"][2]["text"])

    def test_correccion_validaciones(self):
        meeting_id = nueva_reunion()
        self.assertEqual(llamar("POST", f"/reuniones/{meeting_id}/correcciones",
                                {"buscar": "a", "reemplazar": "a"})[0], 422)
        self.assertEqual(llamar("POST", f"/reuniones/{meeting_id}/correcciones",
                                {"buscar": "zzzzzz", "reemplazar": "y"})[0], 404)

    def test_palabra_completa_no_coincide_dentro_de_otra(self):
        meeting_id = nueva_reunion(segmentos=[
            {"speaker": "A", "start": 0.0, "end": 5.0, "text": "Hablamos de cuberneti y de cubernetix."},
        ])
        estado, datos = llamar("POST", f"/reuniones/{meeting_id}/correcciones",
                               {"buscar": "cuberneti", "reemplazar": "Kubernetes", "recordar": False})
        self.assertEqual(estado, 200)
        texto = llamar("GET", f"/reuniones/{meeting_id}")[1]["transcripcion"]["segments"][0]["text"]
        self.assertIn("cubernetix", texto)
        self.assertIn("Kubernetes", texto)


class ResumenYVersiones(BaseIntegracion):
    def test_editar_resumen_guarda_version(self):
        meeting_id = nueva_reunion()
        estado, datos = llamar("PUT", f"/reuniones/{meeting_id}/resumen", {"texto": "  Resumen a mano  "})
        self.assertEqual(estado, 200)
        self.assertEqual(datos["texto_resumido"], "Resumen a mano")
        versiones = llamar("GET", f"/reuniones/{meeting_id}/versiones")[1]
        self.assertIn("edicion_manual", [v["origen"] for v in versiones])

    def test_regenerar_resumen_cambia_tipo(self):
        meeting_id = nueva_reunion(tipo="general")
        estado, datos = llamar("POST", f"/reuniones/{meeting_id}/resumen/regenerar", {"tipo": "comercial"})
        self.assertEqual(estado, 200, datos)
        self.assertEqual(datos["tipo"], "comercial")
        self.assertEqual(llamar("GET", f"/reuniones/{meeting_id}")[1]["tipo"], "comercial")

    def test_regenerar_tipo_invalido(self):
        meeting_id = nueva_reunion()
        self.assertEqual(llamar("POST", f"/reuniones/{meeting_id}/resumen/regenerar", {"tipo": "xxx"})[0], 422)

    def test_restaurar_transcripcion(self):
        meeting_id = nueva_reunion()
        original = llamar("GET", f"/reuniones/{meeting_id}")[1]["transcripcion"]["segments"][0]["text"]
        llamar("PATCH", f"/reuniones/{meeting_id}/segmentos/0", {"texto": "Texto cambiado."})
        versiones = llamar("GET", f"/reuniones/{meeting_id}/versiones")[1]
        version = [v for v in versiones if v["campo"] == "transcripcion"][-1]

        estado, _ = llamar("POST", f"/reuniones/{meeting_id}/versiones/{version['id']}/restaurar")
        self.assertEqual(estado, 200)
        restaurado = llamar("GET", f"/reuniones/{meeting_id}")[1]["transcripcion"]["segments"][0]["text"]
        self.assertEqual(restaurado, original)

    def test_restaurar_version_inexistente(self):
        meeting_id = nueva_reunion()
        self.assertEqual(llamar("POST", f"/reuniones/{meeting_id}/versiones/999999/restaurar")[0], 404)


class Vocabulario(BaseIntegracion):
    def test_crear_listar_y_borrar(self):
        estado, creado = llamar("POST", "/vocabulario", {"termino": "Prueba Local", "variante": "pruebalocal"})
        self.assertEqual(estado, 201)
        # Repetir no duplica (upsert con on_conflict)
        llamar("POST", "/vocabulario", {"termino": "Prueba Local", "variante": "pruebalocal"})
        listado = llamar("GET", "/vocabulario")[1]
        self.assertEqual(sum(1 for v in listado if v["termino"] == "Prueba Local"), 1)

        estado, _ = llamar("DELETE", f"/vocabulario/{creado['id']}")
        self.assertEqual(estado, 204)
        listado = llamar("GET", "/vocabulario")[1]
        self.assertFalse(any(v["termino"] == "Prueba Local" for v in listado))

    def test_termino_vacio(self):
        self.assertEqual(llamar("POST", "/vocabulario", {"termino": "   "})[0], 422)

    def test_vocabulario_de_la_semilla(self):
        listado = llamar("GET", "/vocabulario")[1]
        self.assertTrue(any(v["termino"] == "Kubernetes" and v["variante"] == "cuberneti" for v in listado))


class Preguntas(BaseIntegracion):
    def test_pregunta_cita_reunion_y_minuto(self):
        meeting_id = nueva_reunion()
        llamar("POST", f"/reuniones/{meeting_id}/indexar")
        estado, datos = llamar("POST", "/preguntas", {
            "pregunta": "¿Qué presupuesto acordamos con el cliente?",
            "reuniones": [meeting_id],
            "limite": 5,
        })
        self.assertEqual(estado, 200, datos)
        self.assertTrue(datos["fuentes"], datos)
        fuente = datos["fuentes"][0]
        self.assertEqual(fuente["reunion_id"], meeting_id)
        self.assertRegex(fuente["minuto"], r"^\d+:\d{2}(:\d{2})?$")
        self.assertIn("reunion_fecha", fuente)

    def test_pregunta_sin_resultados(self):
        estado, datos = llamar("POST", "/preguntas", {"pregunta": "Algo inexistente total", "reuniones": [999999]})
        self.assertEqual(estado, 200)
        self.assertEqual(datos["fuentes"], [])

    def test_pregunta_corta_422(self):
        self.assertEqual(llamar("POST", "/preguntas", {"pregunta": "a"})[0], 422)

    def test_indexar_sin_transcripcion_409(self):
        vacia = supabase.table(TABLE_NAME).insert(
            {"tipo": "general", "transcripcion": None, "owner_id": OWNER_ID}
        ).execute().data[0]["id"]
        self.assertEqual(llamar("POST", f"/reuniones/{vacia}/indexar")[0], 409)


class Temas(BaseIntegracion):
    def test_presupuesto_recurrente_y_antiguo(self):
        estado, lista = llamar("GET", "/temas?estado=abierto")
        self.assertEqual(estado, 200)
        presupuesto = [t for t in lista if t["titulo"] == "Presupuesto"]
        self.assertTrue(presupuesto)
        self.assertIn("recurrente", presupuesto[0]["alertas"])

    def test_filtro_estado_invalido(self):
        self.assertEqual(llamar("GET", "/temas?estado=raro")[0], 422)

    def test_detalle_y_cambio_de_estado(self):
        tema = [t for t in llamar("GET", "/temas")[1] if t["titulo"] == "Presupuesto"][0]
        estado, detalle = llamar("GET", f"/temas/{tema['id']}")
        self.assertEqual(estado, 200)
        self.assertGreaterEqual(len(detalle["menciones"]), 2)

        estado, cambiado = llamar("PATCH", f"/temas/{tema['id']}", {"estado": "resuelto"})
        self.assertEqual(estado, 200)
        self.assertEqual(cambiado["estado"], "resuelto")
        self.assertNotIn("recurrente", cambiado["alertas"])
        llamar("PATCH", f"/temas/{tema['id']}", {"estado": "abierto"})

    def test_tema_inexistente(self):
        self.assertEqual(llamar("GET", "/temas/999999")[0], 404)
        self.assertEqual(llamar("PATCH", "/temas/999999", {"estado": "abierto"})[0], 404)

    def test_temas_de_una_reunion_y_extraccion(self):
        meeting_id = nueva_reunion()
        estado, temas = llamar("GET", f"/reuniones/{meeting_id}/temas")
        self.assertEqual(estado, 200)
        self.assertTrue(all("estado_en_esta_reunion" in t for t in temas))

        estado, datos = llamar("POST", f"/reuniones/{meeting_id}/temas/extraer")
        self.assertEqual(estado, 200)
        self.assertGreaterEqual(datos["temas"], 1)

    def test_extraer_no_duplica_menciones(self):
        meeting_id = nueva_reunion()
        llamar("POST", f"/reuniones/{meeting_id}/temas/extraer")
        antes = supabase.table("menciones_temas").select("id").eq("doc_id", meeting_id).execute().data
        llamar("POST", f"/reuniones/{meeting_id}/temas/extraer")
        despues = supabase.table("menciones_temas").select("id").eq("doc_id", meeting_id).execute().data
        self.assertEqual(len(antes), len(despues))


class Exportacion(BaseIntegracion):
    def setUp(self):
        urllib.request.urlopen(urllib.request.Request(SERVICIOS + "/_reset", method="POST"), timeout=10).read()

    def test_destinos_configurados(self):
        estado, destinos = llamar("GET", "/destinos")
        self.assertEqual(estado, 200)
        self.assertTrue(all(d["configurado"] for d in destinos))

    def test_email_sin_destinatarios_422(self):
        meeting_id = nueva_reunion()
        self.assertEqual(llamar("POST", f"/reuniones/{meeting_id}/exportar", {"destino": "email"})[0], 422)

    def test_email_real_por_smtp(self):
        meeting_id = nueva_reunion()
        estado, datos = llamar("POST", f"/reuniones/{meeting_id}/exportar",
                               {"destino": "email", "destinatarios": ["ana@ejemplo.com"]})
        self.assertEqual(estado, 200, datos)
        correos = capturados()["smtp"]
        self.assertEqual(len(correos), 1)
        self.assertIn("ana@ejemplo.com", correos[0]["para"])
        self.assertIn(f"Resumen de reunión #{meeting_id}", correos[0]["asunto"])
        self.assertIn("Presupuesto", correos[0]["cuerpo"])

    def test_slack_real_por_webhook(self):
        meeting_id = nueva_reunion()
        estado, _ = llamar("POST", f"/reuniones/{meeting_id}/exportar", {"destino": "slack"})
        self.assertEqual(estado, 200)
        mensajes = capturados()["slack"]
        self.assertEqual(len(mensajes), 1)
        self.assertIn(f"Resumen de reunión #{meeting_id}", mensajes[0]["text"])

    def test_historial_registra_envios(self):
        meeting_id = nueva_reunion()
        llamar("POST", f"/reuniones/{meeting_id}/exportar", {"destino": "slack"})
        historial = llamar("GET", f"/reuniones/{meeting_id}/exportaciones")[1]
        self.assertEqual([h["estado"] for h in historial], ["enviado"])

    def test_reunion_sin_resumen_409(self):
        meeting_id = supabase.table(TABLE_NAME).insert(
            {
                "tipo": "general",
                "transcripcion": {"segments": []},
                "texto_resumido": "",
                "owner_id": OWNER_ID,
            }
        ).execute().data[0]["id"]
        self.assertEqual(llamar("POST", f"/reuniones/{meeting_id}/exportar", {"destino": "slack"})[0], 409)


if __name__ == "__main__":
    unittest.main()
