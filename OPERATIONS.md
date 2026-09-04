# Operación de M.A.T.I.A.S. Web

## Arquitectura

- API FastAPI en Render.
- Conversaciones, sesiones, leads, visitas y eventos en PostgreSQL/Supabase.
- RAG BM25 sobre `conocimiento/` para orientar con información verificable.
- Google Calendar Appointment Schedule para disponibilidad y reserva.
- Worker local launchd para reintentar email, Telegram y WhatsApp por Amelia.

## Estado operativo

`GET /api/operations/status` devuelve solo conteos y configuración booleana, sin PII.

Los endpoints con conversaciones, leads, journeys e IP requieren el header `X-Admin-Token` y la variable `MATIAS_ADMIN_TOKEN`. Si no está configurada, responden 503 de forma segura.

## Worker Amelia

Archivo: `ops/matias_lead_worker.py`

LaunchAgent: `~/Library/LaunchAgents/com.akaike.matias-lead-worker.plist`

Frecuencia: cada 30 segundos. Los envíos son idempotentes mediante `email_sent`, `whatsapp_sent` y `telegram_sent` en `leads`.

Verificación manual sin enviar mensajes:

`/Users/ogutimo/.openclaw-venv/bin/python ops/matias_lead_worker.py --dry-run`

Logs:

`~/.openclaw-runtime/matias-lead-worker/worker.log`

## Pruebas

`/Users/ogutimo/.openclaw-venv/bin/python -m unittest -v`

## Seguridad

No almacenar secretos en Git. El token de Telegram y la contraseña histórica de Supabase deben rotarse desde sus proveedores y mantenerse solo en variables de entorno de Render y archivos `.env` ignorados.
