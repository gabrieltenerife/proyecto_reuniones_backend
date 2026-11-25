# Backend y aplicación de reuniones

## Cuenta de demostración local

- **Email:** `demo@reuniones.test`
- **Contraseña:** `Reuniones-Demo-2026!`

Solo para probar el entorno local; no reutilices estas credenciales en producción.

Aplicación para transcribir reuniones, generar resúmenes, consultar reuniones con citas, dar seguimiento a temas abiertos y exportar resultados. La interfaz web está en `fron/`; el backend y sus scripts están en `app/`.

Para orientarte rápido: `app/README.md` explica los módulos del backend, `fron/README.md` explica cómo iniciar la interfaz, `sql/README.md` documenta las migraciones y `local/README.md` explica el entorno local reproducible.

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
                               │
                               ▼
                        app/indexador.py ──► fragmentos (búsqueda)
                               │
                               ▼
                    app/extractor_temas.py ──► temas (seguimiento)
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
python -m pip install -r requirements.txt
```

## Configuración

1. Crea un archivo `.env` en la raíz del proyecto.
2. Añade tu clave:

    ```dotenv
    OPENAI_API_KEY=tu_clave_de_api
    SUPABASE_URL=https://vxagataaejcqsrojdniw.supabase.co
    SUPABASE_SECRET_KEY=tu_clave_secreta_nueva
    AUTH_SECRET=un_secreto_aleatorio_de_al_menos_32_caracteres
    CORS_ORIGINS=http://localhost:3000
    REUNION_OWNER_EMAIL=persona@empresa.com

    # Email (opcional). Déjalo vacío si no lo usas.
    SMTP_HOST=smtp.tu-proveedor.com
    SMTP_PORT=587
    SMTP_USER=usuario
    SMTP_PASSWORD=clave
    SMTP_FROM=Reuniones <reuniones@tu-dominio.com>
    SMTP_STARTTLS=true

    # Slack (opcional): URL de un webhook entrante
    SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
    ```

3. Coloca el audio que quieres procesar en `data/input/reunion.mp3`. Crea la carpeta `data/input` si todavía no existe.

4. Ejecuta en el SQL Editor de Supabase, en este orden:
    - `sql/001_plantillas_versiones_vocabulario.sql`: añade la columna `tipo` a `Docs` y crea las tablas `versiones` y `vocabulario`.
    - `sql/002_busqueda_reuniones.sql`: activa pgvector, crea la tabla `fragmentos` y la función `buscar_fragmentos`.
    - `sql/003_temas.sql`: crea las tablas `temas` y `menciones_temas` y la función `buscar_temas_similares`.
    - `sql/004_exportaciones.sql`: crea la tabla `exportaciones`, que guarda el historial de envíos.
    - `sql/005_usuarios_propietarios.sql`: crea el registro de usuarios y separa los datos por propietario.

5. Si ya tienes reuniones guardadas, indexa las antiguas una vez. Sin argumentos indexa todas; con un ID indexa solo esa reunión:

    ```bash
    python app/indexador.py
    python app/indexador.py 12
    ```

No compartas ni subas `.env` al repositorio. La clave secreta de Supabase solo debe usarse en este backend y mantenerse privada. El audio se envía a OpenAI para su transcripción, pero no se guarda en Supabase.

## Uso

Desde la raíz del proyecto, ejecuta:

```bash
python app/main.py persona@empresa.com
```

El email indica a qué cuenta se asigna la nueva reunión. También puedes definir `REUNION_OWNER_EMAIL` en `.env` y ejecutar `python app/main.py`. Al terminar, la fila de la reunión en `Docs` contiene los segmentos, la transcripción completa y el resumen. No se generan archivos de salida locales.

La llamada a la API puede tener coste según tu cuenta y el audio procesado.

### Probar en local

Para probar el backend, la base de datos, el frontend y los envíos sin conectar con tu proyecto de Supabase ni llamar a OpenAI, sigue [`local/README.md`](local/README.md). Ahí se explica qué servicios son reales, cuáles son sustitutos de prueba y cómo arrancarlos.

El frontend se ejecuta aparte con:

```bash
python -m http.server 3000 --directory fron
```

Después abre `http://localhost:3000`. El mapa de sus pantallas está en [`fron/README.md`](fron/README.md).

### API

Desde la carpeta raíz del proyecto:

```bash
python -m uvicorn api:app --app-dir app --reload
```

`POST /auth/register` crea una cuenta de email/contraseña y `POST /auth/login` inicia sesión. Las demás rutas requieren `Authorization: Bearer <access_token>`. Las contraseñas deben tener al menos 12 caracteres. El token dura 8 horas.

El primer usuario registrado adopta las reuniones y datos heredados que aún no tengan propietario. A partir de entonces, cada cuenta consulta únicamente sus propias reuniones, temas, vocabulario, búsquedas e historial.

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | `/auth/register` | Crea una cuenta y devuelve una sesión |
| POST | `/auth/login` | Inicia sesión |
| GET | `/auth/me` | Devuelve la cuenta autenticada |
| GET | `/tipos` | Tipos de reunión y sus apartados de resumen |
| GET | `/reuniones` | Lista de reuniones |
| GET | `/reuniones/{id}` | Detalle: segmentos, transcripción, resumen y tipo |
| PATCH | `/reuniones/{id}/segmentos/{indice}` | Corrige un segmento. Devuelve sugerencias de vocabulario |
| POST | `/reuniones/{id}/correcciones` | Cambia un texto en toda la reunión y, si `recordar` es `true`, lo guarda en el vocabulario |
| PUT | `/reuniones/{id}/resumen` | Edita el resumen a mano |
| POST | `/reuniones/{id}/resumen/regenerar` | Regenera el resumen con un `tipo` opcional |
| GET | `/reuniones/{id}/versiones` | Historial de cambios de transcripción y resumen |
| POST | `/reuniones/{id}/versiones/{version_id}/restaurar` | Restaura una versión anterior |
| GET, POST | `/vocabulario` | Lista o añade términos y variantes |
| DELETE | `/vocabulario/{id}` | Elimina un término |
| POST | `/preguntas` | Pregunta a tus reuniones. Devuelve respuesta y fuentes con reunión y minuto |
| POST | `/reuniones/{id}/indexar` | Vuelve a indexar una reunión para la búsqueda |
| GET | `/temas?estado=abierto` | Temas detectados en todas las reuniones, con antigüedad y alertas |
| GET | `/temas/{id}` | Detalle de un tema con todas sus menciones |
| PATCH | `/temas/{id}` | Cambia el estado de un tema (`abierto`, `resuelto`, `pospuesto`) |
| GET | `/reuniones/{id}/temas` | Temas tratados en una reunión, con su historial previo |
| POST | `/reuniones/{id}/temas/extraer` | Vuelve a extraer los temas de una reunión |
| GET | `/destinos` | Destinos de exportación y si ya están configurados |
| POST | `/reuniones/{id}/exportar` | Envía el resumen por `email` o `slack`, con sus temas |
| GET | `/reuniones/{id}/exportaciones` | Historial de envíos de una reunión, con errores |

El vocabulario se aplica al texto completo al regenerarlo y se incluye en las instrucciones del resumen para que use la grafía correcta.

### Exportar y enviar

Un solo `POST /reuniones/{id}/exportar` envía el resumen de la reunión y, si quieres, sus temas con el historial de cada uno.

```bash
curl -X POST http://localhost:8000/reuniones/12/exportar \
  -H "Authorization: Bearer tu_token" -H "Content-Type: application/json" \
  -d '{"destino": "email", "destinatarios": ["ana@empresa.com"], "incluir_temas": true}'
```

- **Email**: envío por SMTP con STARTTLS (configurable). Hace falta `SMTP_HOST` y `SMTP_FROM`. Si el servidor exige login, añade `SMTP_USER` y `SMTP_PASSWORD`. Con Gmail u Outlook usa una contraseña de aplicación, no la contraseña normal.
- **Slack**: publica en el canal del webhook entrante (`SLACK_WEBHOOK_URL`). Los `**negritas**` del resumen se convierten al formato de Slack, y los mensajes muy largos se recortan con aviso.

Cada intento queda registrado en `GET /reuniones/{id}/exportaciones`, tanto si sale bien como si falla, con el motivo del error. `GET /destinos` indica qué destinos están configurados, para que la interfaz muestre solo los disponibles.

Para añadir otros destinos (Notion, Trello, Todoist, Google Docs...) basta con una función `enviar_*` en `app/exportacion.py` y añadirla al `if` de `exportar`.

### Memoria de temas

Después de cada reunión, el sistema extrae sus temas (decisiones, preguntas abiertas, bloqueos, compromisos y temas aplazados), con un estado (`abierto`, `resuelto` o `pospuesto`) y el minuto donde se tratan. Para cada tema busca temas anteriores parecidos, con embeddings. Si encuentra candidatos, el modelo decide si es el mismo asunto. Si no, crea un tema nuevo. Así un tema que aparece en varias reuniones queda como un solo seguimiento con varias menciones.

En `GET /temas` cada tema incluye:

- `veces_mencionado`, `primera_mencion` y `ultima_mencion`, con reunión, fecha y minuto.
- `dias_desde_primera`: días desde la primera vez que se trató.
- `alertas`:
  - `recurrente`: aparece en dos o más reuniones y sigue sin resolverse.
  - `antiguo`: lleva 14 días o más sin resolverse.

Si un tema se resuelve en la última reunión, la alerta desaparece. Puedes cambiar el estado a mano con `PATCH /temas/{id}`.

La extracción se ejecuta al final de `main.py`. No se vuelve a ejecutar al editar una transcripción; para eso usa `POST /reuniones/{id}/temas/extraer` o `python app/extractor_temas.py <id>`. Las reuniones antiguas se procesan con `python app/extractor_temas.py`, sin argumentos.

### Preguntar a tus reuniones

```bash
curl -X POST http://localhost:8000/preguntas \
  -H "Authorization: Bearer tu_token" -H "Content-Type: application/json" \
  -d '{"pregunta": "¿qué acordamos con el cliente sobre el presupuesto?", "reuniones": null, "limite": 8}'
```

La respuesta incluye `respuesta` y `fuentes`. Cada fuente tiene `reunion_id`, `reunion_fecha`, `minuto` (por ejemplo `14:32`), `hablante` y `texto`. En el texto, `[1]`, `[2]`… se refieren a esas fuentes. Las fuentes las genera el sistema a partir de los fragmentos recuperados, así que el minuto no lo inventa el modelo.

Cada fragmento agrupa intervenciones consecutivas del mismo hablante, de hasta 60 segundos y 800 caracteres. La búsqueda combina similitud semántica (embeddings `text-embedding-3-small`) con búsqueda por palabras clave en español, y se fusionan los resultados. Un cambio en la transcripción o una corrección vuelve a indexar la reunión automáticamente.

Los hablantes aparecen como `A`, `B`… tal como los etiqueta la transcripción.

## Estructura

```text
.
├── app/                    # Backend Python; mapa de módulos en app/README.md
├── fron/                   # Interfaz web; instrucciones en fron/README.md
├── sql/                    # Migraciones numeradas; guía en sql/README.md
├── local/                  # Docker, servicios de prueba y pruebas de integración
│   ├── init/               # Esquema base del entorno local
│   └── pruebas/            # Pruebas HTTP contra Postgres/PostgREST locales
├── data/                   # Audio de entrada local; excluido de Git
│   └── input/
├── requirements.txt        # Dependencias Python del backend
├── .env                    # Credenciales remotas; no subir a Git
└── Readme.md               # Guía general y documentación de la API
```

Los módulos de `app/` permanecen en una sola carpeta porque los scripts se ejecutan directamente y se importan entre sí. Su agrupación por responsabilidad está explicada en `app/README.md`; así se mantiene la estructura fácil de buscar sin cambiar los comandos ni el funcionamiento.

## Estado del proyecto

El backend ofrece transcripción, resúmenes por plantilla, edición con historial, búsqueda RAG con citas, memoria de temas y exportación por email y Slack. La interfaz web está en `fron/`. El entorno local reproducible y sus pruebas de integración están documentados en `local/README.md`.
