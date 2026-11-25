# Backend de procesamiento de reuniones

El backend descarga de Supabase Storage el audio asociado a una reunión, identifica hablantes y genera una transcripción y un resumen con OpenAI. Actualiza la fila existente de `Docs`; no crea una reunión nueva.

## Flujo actual

```text
Docs.audio_path ──► Supabase Storage (meeting-audios)
                              │
                              ▼
                     app/procesador.py
                              │
                              ├──► Docs.transcripcion
                              ├──► Docs.texto_bruto
                              └──► Docs.texto_resumido
```

El frontend primero sube el archivo al bucket `meeting-audios` y guarda su ruta en `Docs.audio_path`. Después llama al endpoint de procesamiento con el ID de esa fila.

## Requisitos

- Python 3 instalado.
- Una clave de API de OpenAI con acceso al modelo de transcripción utilizado por el proyecto.
- Un proyecto de Supabase con una tabla `Docs` y las columnas `id`, `audio_path`, `texto_bruto`, `texto_resumido` y `transcripcion`.
- Un bucket privado de Supabase Storage llamado `meeting-audios` (o el nombre configurado en `SUPABASE_STORAGE_BUCKET`).
- Conexión a Internet al ejecutar la transcripción.

## Instalación

Desde la carpeta raíz del repositorio, crea y activa un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En macOS o Linux, la activación es:

```bash
source .venv/bin/activate
```

Instala las dependencias:

```bash
python -m pip install openai python-dotenv supabase fastapi uvicorn
```

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto.
2. Añade tu clave:

    ```dotenv
    OPENAI_API_KEY=tu_clave_de_api
    SUPABASE_URL=https://vxagataaejcqsrojdniw.supabase.co
    SUPABASE_SECRET_KEY=tu_clave_secreta_nueva
    REUNIONES_API_KEY=una_clave_larga_aleatoria
    SUPABASE_STORAGE_BUCKET=meeting-audios
    OPENAI_SUMMARY_MODEL=gpt-6-luna
    # Opcional: orígenes web permitidos, separados por comas.
    CORS_ORIGINS=https://tu-frontend.example
    ```

No compartas ni subas `.env` al repositorio. La clave secreta de Supabase y la clave de OpenAI solo deben usarse en este backend. El audio se envía a OpenAI para su transcripción.

## Uso

Arranca la API desde la raíz del proyecto:

```powershell
python -m uvicorn app.api:app --host 0.0.0.0 --port 8000
```

Después de subir el audio y guardar `audio_path`, el frontend debe solicitar el procesamiento:

```js
const apiBase = API_URL.replace(/\/+$/, "");
const respuesta = await fetch(`${apiBase}/reuniones/${meetingId}/procesar`, {
  method: "POST",
  headers: {
    "X-API-Key": API_KEY,
    "ngrok-skip-browser-warning": "1",
  },
});

if (!respuesta.ok) {
  throw new Error(await respuesta.text());
}
```

Al terminar, la misma fila de `Docs` contiene `transcripcion`, `texto_bruto` y `texto_resumido`. Este endpoint procesa audios subidos a Storage; `app/main.py` conserva su flujo local anterior.

La llamada a la API puede tener coste según tu cuenta y el audio procesado.

## Estructura

```text
.
├── app/
│   ├── api.py              # Endpoint para solicitar el procesamiento
│   ├── database.py         # Conexión a Supabase
│   ├── main.py             # Ejecución por línea de comandos
│   ├── procesador.py       # Descarga, transcripción, resumen y actualización
│   ├── transcriptor.py     # Flujo anterior con audio local (legacy)
│   ├── unificador.py       # Flujo anterior (legacy)
│   └── resume.py           # Flujo anterior (legacy)
├── .env                    # Clave de API; no debe subirse
└── README.md
```

## Estado del proyecto

La API procesa la reunión de forma síncrona; el cliente debe esperar su respuesta antes de asumir que la transcripción y el resumen están listos. No incluyas una clave secreta en código frontend desplegado públicamente; para producción, protege este endpoint mediante autenticación de usuario o un servicio backend de confianza.
