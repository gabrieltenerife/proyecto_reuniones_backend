# Backend (`app/`)

Los módulos de esta carpeta se mantienen juntos a propósito: los scripts se ejecutan directamente desde la raíz (`python app/main.py`) y comparten imports entre archivos. La tabla agrupa sus responsabilidades para que sea fácil localizar cada función sin cambiar esas rutas.

## Flujo de procesamiento

| Archivo | Responsabilidad |
| --- | --- |
| `main.py` | Orquesta el procesamiento completo de una reunión. |
| `transcriptor.py` | Envía el audio a OpenAI y guarda los segmentos con hablante y tiempos. |
| `unificador.py` | Agrupa segmentos y construye la transcripción legible. |
| `resume.py` | Genera el resumen según el tipo de reunión. |
| `indexador.py` | Crea los fragmentos y embeddings para búsquedas. |
| `extractor_temas.py` | Detecta temas y los relaciona con reuniones anteriores. |

## API y funciones de producto

| Archivo | Responsabilidad |
| --- | --- |
| `api.py` | Endpoints HTTP, autenticación y validación de peticiones. |
| `rag.py` | Búsqueda de contexto y respuestas con citas. |
| `temas.py` | Memoria, coincidencias y seguimiento de temas abiertos. |
| `exportacion.py` | Email, Slack y registro de exportaciones. |
| `edicion.py` | Historial de versiones y acceso a reuniones. |

## Módulos compartidos

| Archivo | Responsabilidad |
| --- | --- |
| `database.py` | Configuración del cliente Supabase. |
| `plantillas.py` | Tipos de reunión e instrucciones de resumen. |
| `vocabulario.py` | Vocabulario propio y correcciones aprendidas. |
| `fragmentos.py` | Fragmentación, embeddings y reindexación. |

## Comandos habituales

Desde la raíz del repositorio:

```bash
python app/main.py
python -m uvicorn api:app --app-dir app --reload
python app/indexador.py
python app/extractor_temas.py
```
