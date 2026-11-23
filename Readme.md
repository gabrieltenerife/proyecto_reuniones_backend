# Backend de transcripción de reuniones

Proyecto en desarrollo para transcribir reuniones, identificar hablantes y generar una transcripción de texto fácil de leer. El flujo actual utiliza la API de OpenAI y está pensado para procesar un archivo de audio por ejecución.

## Flujo actual

```text
data/input/reunion.mp3
        │
        ▼
app/transcriptor.py ──► Docs.transcripcion
                              │
                              ▼
                       app/unificador.py ──► Docs.texto_bruto
                              │
                              ▼
                          app/resume.py ──► Docs.texto_resumido
```

`app/main.py` ejecuta los pasos en orden. Cada resultado se envía a Supabase al terminar; los scripts no guardan los resultados en archivos locales. El audio permanece en `data/input` y no se sube a Supabase.

## Requisitos

- Python 3 instalado.
- Una clave de API de OpenAI con acceso al modelo de transcripción utilizado por el proyecto.
- Un proyecto de Supabase con una tabla `Docs` y las columnas `id`, `created_at`, `texto_bruto`, `texto_resumido` y `transcripcion`.
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
python -m pip install openai python-dotenv supabase
```

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto.
2. Añade tu clave:

    ```dotenv
    OPENAI_API_KEY=tu_clave_de_api
    SUPABASE_URL=https://vxagataaejcqsrojdniw.supabase.co
    SUPABASE_SECRET_KEY=tu_clave_secreta_nueva
    ```

3. Coloca el audio que quieres procesar en `data/input/reunion.mp3`. Crea la carpeta `data/input` si todavía no existe.

No compartas ni subas `.env` al repositorio. La clave secreta de Supabase solo debe usarse en este backend y mantenerse privada. El audio se envía a OpenAI para su transcripción, pero no se guarda en Supabase.

## Uso

Desde la raíz del proyecto, ejecuta:

```bash
python app/main.py
```

Al terminar, la fila de la reunión en `Docs` contiene los segmentos, la transcripción completa y el resumen. No se generan archivos de salida locales.

La llamada a la API puede tener coste según tu cuenta y el audio procesado.

## Estructura

```text
.
├── app/
│   ├── main.py             # Ejecuta el flujo completo
│   ├── database.py         # Conexión a Supabase
│   ├── transcriptor.py     # Audio a segmentos y los inserta en Supabase
│   ├── unificador.py       # Agrupa segmentos y actualiza Supabase
│   └── resume.py           # Genera y guarda el resumen en Supabase
├── data/                   # Archivos locales; excluidos de Git
│   └── input/
│       └── reunion.mp3
├── .env                    # Clave de API; no debe subirse
└── README.md
```

## Estado del proyecto

El flujo básico está en desarrollo y puede ampliarse. La estructura y este documento describen el comportamiento actual; futuras mejoras pueden incorporar opciones de entrada, pruebas automatizadas y soporte para procesar varias reuniones.
