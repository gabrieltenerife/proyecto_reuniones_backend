# Backend de transcripción de reuniones

Proyecto en desarrollo para transcribir reuniones, identificar hablantes y generar una transcripción de texto fácil de leer. El flujo actual utiliza la API de OpenAI y está pensado para procesar un archivo de audio por ejecución.

## Flujo actual

```text
data/input/reunion.mp3
        │
        ▼
app/transcriptor.py ──► data/output/transcripcion.json
                              │
                              ▼
                       app/unificador.py
                              │
                              ▼
                 data/output/transcripcion_completa.txt
```

`app/main.py` ejecuta los dos pasos en orden. El transcriptor genera segmentos con hablante y marcas de tiempo; el unificador los ordena cronológicamente y junta los segmentos consecutivos del mismo hablante.

## Requisitos

- Python 3 instalado.
- Una clave de API de OpenAI con acceso al modelo de transcripción utilizado por el proyecto.
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
python -m pip install openai python-dotenv
```

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto.
2. Añade tu clave:

   ```dotenv
   OPENAI_API_KEY=tu_clave_de_api
   ```

3. Coloca el audio que quieres procesar en `data/input/reunion.mp3`. Crea la carpeta `data/input` si todavía no existe.

No compartas ni subas `.env` al repositorio. La carpeta `data/` está excluida de Git, por lo que el audio y las transcripciones generadas se mantienen locales.

## Uso

Desde la raíz del proyecto, ejecuta:

```bash
python app/main.py
```

Al terminar, encontrarás:

- `data/output/transcripcion.json`: segmentos con hablante, tiempo de inicio, tiempo de fin y texto.
- `data/output/transcripcion_completa.txt`: texto agrupado por hablante.

La llamada a la API puede tener coste según tu cuenta y el audio procesado.

## Estructura

```text
.
├── app/
│   ├── main.py             # Ejecuta el flujo completo
│   ├── transcriptor.py     # Audio a JSON mediante OpenAI
│   └── unificador.py       # JSON a texto agrupado por hablante
├── data/                   # Archivos locales; excluidos de Git
│   ├── input/
│   │   └── reunion.mp3
│   └── output/
│       ├── transcripcion.json
│       └── transcripcion_completa.txt
├── .env                    # Clave de API; no debe subirse
└── README.md
```

## Estado del proyecto

El flujo básico está en desarrollo y puede ampliarse. La estructura y este documento describen el comportamiento actual; futuras mejoras pueden incorporar opciones de entrada, pruebas automatizadas y soporte para procesar varias reuniones.
