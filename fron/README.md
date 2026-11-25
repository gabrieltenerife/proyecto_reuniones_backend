# Frontend de reuniones

Interfaz web para el backend de `app/api.py`. Es HTML, CSS y JavaScript sin dependencias ni paso de compilación.

## Qué incluye

- **Reuniones**: listado y detalle con pestañas.
  - Las pestañas del detalle se desplazan horizontalmente y mantienen el contenido cargado; en móvil también se puede deslizar.
  - *Transcripción*: edición de cada segmento, corrección en toda la reunión, sugerencias de vocabulario y reindexado de la búsqueda.
  - *Resumen*: edición manual, cambio de tipo y regeneración.
  - *Temas*: temas de esta reunión con su historial previo, y extracción manual.
  - *Exportar*: envío por email (varios destinatarios) o Slack, con historial de envíos.
  - *Versiones*: historial de cambios y restauración.
- **Preguntar**: chat sobre tus reuniones. Cada respuesta cita reunión y minuto, y el enlace abre la transcripción en ese punto.
- **Temas**: seguimiento entre reuniones, con filtro por estado, alertas de recurrencia y antigüedad, y cambio de estado.
- **Vocabulario**: añadir y eliminar términos y variantes.
- **Ajustes**: URL de la API, prueba de conexión y estado de los destinos de exportación.
- **Acceso privado**: registro e inicio de sesión con contraseña; cada cuenta queda aislada en el backend.

## Ejecutarlo

1. Arranca el backend desde la raíz del proyecto:

   ```bash
   python -m uvicorn api:app --app-dir app --reload
   ```

2. En el `.env` del backend, incluye el origen de esta página en CORS y define `AUTH_SECRET` (al menos 32 caracteres):

   ```dotenv
   CORS_ORIGINS=http://localhost:3000
   AUTH_SECRET=un_secreto_aleatorio_de_al_menos_32_caracteres
   ```

3. Sirve esta carpeta en el puerto 3000 desde la raíz del proyecto:

   ```bash
   python -m http.server 3000 --directory fron
   ```

4. Abre `http://localhost:3000` y crea una cuenta. Para el entorno `local/api_local.py`, el frontend usa automáticamente `http://localhost:8000`. La sesión se guarda solo en la pestaña y caduca a las 8 horas. Puedes comprobar la conexión en **Ajustes**.

Si conectas el frontend a otro backend, configura la URL desde **Ajustes** y vuelve a iniciar sesión en ese backend. No se comparte el token de una API con otra.

Los módulos de JavaScript no funcionan abriendo el archivo directamente (`file://`); hay que usar un servidor como el del paso 3.

## Seguridad

El token de sesión se guarda en `sessionStorage` y viaja como `Authorization: Bearer`; se borra al cerrar la sesión o la pestaña. Para publicar la app en internet, sirve todo bajo HTTPS y configura `AUTH_SECRET`, CORS y límites de intentos de acceso.

## Estructura

```text
fron/
├── index.html          # Página base y menú lateral
├── css/
│   └── estilos.css
└── js/
    ├── api.js          # Llamadas a la API, con clave y gestión de errores
    ├── ui.js           # Helpers de interfaz: elementos, avisos, formatos
    ├── app.js          # Enrutador por hash (#/reuniones/12?tab=resumen)
    └── vistas/
        ├── reuniones.js
        ├── preguntas.js
        ├── temas.js
        ├── vocabulario.js
        └── ajustes.js
```
