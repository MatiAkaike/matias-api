# Operación de M.A.T.I.A.S. Web

## Arquitectura

- API FastAPI en Render.
- Conversaciones, sesiones, leads, visitas y eventos en PostgreSQL/Supabase.
- RAG BM25 sobre `conocimiento/` para orientar con información verificable.
- Google Calendar Appointment Schedule para disponibilidad y reserva.
- Worker local launchd para reintentar email, Telegram y WhatsApp por Amelia.

## Estado operativo

`GET /api/operations/status` devuelve conteos y configuración operativa sin PII, y requiere `X-Admin-Token`.

Los endpoints con conversaciones, leads, journeys e IP requieren el header `X-Admin-Token` y la variable `MATIAS_ADMIN_TOKEN`. Si no está configurada, responden 503 de forma segura.

## Worker Amelia

Fuente versionada: `ops/matias_lead_worker.py`

Copia ejecutable endurecida: `~/.openclaw-runtime/matias-lead-worker/worker.py`

LaunchAgent: `~/Library/LaunchAgents/com.akaike.matias-lead-worker.plist`

Frecuencia: cada 30 segundos. El worker reclama atómicamente cada canal mediante estados `pending/failed → processing → sent` e intentos independientes. Un estado `processing` no se reenvía automáticamente: debe revisarse antes de liberarlo para evitar duplicados después de una caída ambigua del proveedor.

Verificación manual sin enviar mensajes:

`/Users/ogutimo/.openclaw-venv/bin/python ~/.openclaw-runtime/matias-lead-worker/worker.py --dry-run`

Logs:

`~/.openclaw-runtime/matias-lead-worker/worker.log`

## Pruebas

`/Users/ogutimo/.openclaw-venv/bin/python -m unittest -v`

## Seguridad

No almacenar secretos en Git. El token de Telegram y la contraseña histórica de Supabase deben rotarse desde sus proveedores y mantenerse solo en variables de entorno de Render y archivos `.env` ignorados.
