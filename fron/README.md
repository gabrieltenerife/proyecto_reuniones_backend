# Frontend de reuniones

Interfaz web para el backend de `app/api.py`. Es HTML, CSS y JavaScript sin dependencias ni paso de compilación.

## Qué incluye

- **Reuniones**: listado y detalle con pestañas.
  - *Transcripción*: edición de cada segmento, corrección en toda la reunión, sugerencias de vocabulario y reindexado de la búsqueda.
  - *Resumen*: edición manual, cambio de tipo y regeneración.
  - *Temas*: temas de esta reunión con su historial previo, y extracción manual.
  - *Exportar*: envío por email (varios destinatarios) o Slack, con historial de envíos.
  - *Versiones*: historial de cambios y restauración.
- **Preguntar**: chat sobre tus reuniones. Cada respuesta cita reunión y minuto, y el enlace abre la transcripción en ese punto.
- **Temas**: seguimiento entre reuniones, con filtro por estado, alertas de recurrencia y antigüedad, y cambio de estado.
- **Vocabulario**: añadir y eliminar términos y variantes.
- **Ajustes**: URL de la API y clave, con prueba de conexión y estado de los destinos de exportación.

## Ejecutarlo

1. Arranca el backend desde la raíz del proyecto:

   ```bash
   python -m uvicorn api:app --app-dir app --reload
   ```

2. En el `.env` del backend, incluye el origen de esta página en CORS:

   ```dotenv
   CORS_ORIGINS=http://localhost:3000
   ```

3. Sirve esta carpeta en el puerto 3000 desde la raíz del proyecto:

   ```bash
   python -m http.server 3000 --directory fron
   ```

4. Abre `http://localhost:3000`. Para el entorno `local/api_local.py`, el frontend usa automáticamente `http://localhost:8000` y `local-test-key` (también corrige claves antiguas guardadas en el navegador). Puedes comprobarlo en **Ajustes**.

Si conectas el frontend a otro backend, configura la URL y la clave desde **Ajustes**. En dominios no locales, la aplicación no completa la clave automáticamente.

Los módulos de JavaScript no funcionan abriendo el archivo directamente (`file://`); hay que usar un servidor como el del paso 3.

## Seguridad

La clave de API se guarda en `localStorage` del navegador y viaja en cada petición. Sirve para uso personal o en red local. Si lo publicas en internet, pon la aplicación detrás de un proxy con autenticación y no uses la clave compartida tal cual.

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
