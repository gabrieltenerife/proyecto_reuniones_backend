# Entorno local

Ejecuta la aplicación contra una base de datos local, con los SQL de `sql/` aplicados tal cual, sin tocar tu proyecto de Supabase.

## Qué hay aquí

| Archivo | Para qué sirve |
| --- | --- |
| `docker-compose.yml` | Postgres 16 con pgvector, PostgREST y nginx. nginx expone la API en `/rest/v1`, igual que Supabase. |
| `init/00_base.sql` | Roles de PostgREST y la tabla `Docs`. El resto de tablas las crea `sql/001`–`004` al arrancar. |
| `nginx.conf` | Quita el prefijo `/rest/v1` antes de llegar a PostgREST. |
| `preparar.py` | Genera `local/.env` con los secretos (JWT, clave de servicio). Solo se ejecuta una vez. |
| `entorno.py` | Carga `local/.env` y se niega a seguir si la URL no es local. |
| `servicios_de_prueba.py` | Sustituto local de OpenAI (embeddings y respuestas), SMTP y Slack. |
| `api_local.py` | Arranca la API en `http://127.0.0.1:8000` contra el entorno local. |
| `semilla.py` | Carga tres reuniones de ejemplo usando los scripts reales de `app/`. |
| `pruebas/test_integracion.py` | Pruebas de integración HTTP contra la API y la base de datos reales. |

## Requisitos

- Docker Desktop en marcha.
- Python con las dependencias de `requirements.txt`, más `aiosmtpd` (`python -m pip install aiosmtpd`).

## Puesta en marcha

Desde la raíz del proyecto:

```bash
python local/preparar.py                                  # una sola vez
docker compose -f local/docker-compose.yml up -d          # Postgres + PostgREST + nginx
docker cp sql/005_usuarios_propietarios.sql local-db-1:/tmp/005_usuarios_propietarios.sql
docker exec local-db-1 psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f /tmp/005_usuarios_propietarios.sql
python local/servicios_de_prueba.py                       # en una terminal aparte; déjala abierta
python local/semilla.py                                   # carga las reuniones de ejemplo
python local/api_local.py                                 # API en http://127.0.0.1:8000
```

URL del backend local: `http://localhost:8000`. Abre `http://localhost:3000` y crea una cuenta desde la pantalla de acceso. La primera cuenta se queda con las reuniones de ejemplo existentes; las demás empiezan con su espacio privado vacío.

Para cargar reuniones de ejemplo en una cuenta ya creada, define `REUNION_OWNER_EMAIL` en `local/.env` y ejecuta `python local/semilla.py` (cada ejecución añade tres ejemplos). El pipeline real `app/main.py` usa el `.env` raíz y las credenciales reales de OpenAI/Supabase.

## Probar

```bash
python -m unittest discover -s local/pruebas -v
```

Las pruebas crean sus propias reuniones con los scripts reales, así que se pueden ejecutar varias veces. Si quieres empezar de cero:

```bash
docker compose -f local/docker-compose.yml down -v
docker compose -f local/docker-compose.yml up -d
python local/semilla.py
```

## Qué es real y qué no

- **Real:** PostgreSQL 16 con pgvector, las funciones SQL de `sql/`, PostgREST, la API, los scripts de `app/`, los envíos por SMTP y el webhook de Slack (llegan a los servicios de prueba por red).
- **Sustituto:** los modelos de OpenAI. El servicio de prueba devuelve embeddings basados en palabras clave y respuestas con reglas sencillas. Sirve para probar el flujo, no la calidad de las respuestas.
- **No incluido:** `main.py` y `transcriptor.py`, porque necesitan un audio y la transcripción de OpenAI. La semilla inserta la transcripción igual que la dejaría `transcriptor.py` y ejecuta después el resto del pipeline.
- **Tu tabla `Docs`:** no está en el repositorio, así que `init/00_base.sql` la recrea con las columnas del README. Si tu tabla tiene más columnas o restricciones, ajústalo ahí.
