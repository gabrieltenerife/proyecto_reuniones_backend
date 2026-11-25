# Migraciones de base de datos

Los archivos numerados se aplican una sola vez y en orden. Cada uno tiene al inicio un comentario con el propósito y las dependencias de la migración.

| Archivo | Qué crea o modifica |
| --- | --- |
| `001_plantillas_versiones_vocabulario.sql` | Añade `Docs.tipo` y crea el historial de versiones y el vocabulario. |
| `002_busqueda_reuniones.sql` | Activa pgvector y crea los fragmentos y la búsqueda híbrida. |
| `003_temas.sql` | Crea temas, menciones y búsqueda de temas similares. |
| `004_exportaciones.sql` | Crea el historial de envíos por email y Slack. |

## Supabase remoto

Ejecuta el contenido de cada migración en el SQL Editor de Supabase, desde `001` hasta `004`. Asegúrate de que la tabla existente `Docs` tenga la columna `id` antes de empezar.

## Entorno local

`local/docker-compose.yml` monta estos mismos archivos en el orden correcto. En una base nueva se aplican al ejecutar:

```bash
docker compose -f local/docker-compose.yml up -d
```

Para reiniciar la base local y volver a aplicar las migraciones:

```bash
docker compose -f local/docker-compose.yml down -v
docker compose -f local/docker-compose.yml up -d
```

`down -v` elimina todos los datos de la base local; no afecta a Supabase remoto.
