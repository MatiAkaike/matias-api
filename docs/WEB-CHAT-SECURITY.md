# Seguridad del chat comercial público

## Política comercial

El agente explica el valor de Akaike y M.A.T.I.A.S., orienta sobre soluciones y propone una reunión. Desde el 26-oct-2026 puede explicar los planes vigentes (Starter, Expert, Pro y Corporate), los Akaike Units (AKUs) y lo que consume cada capacidad, y recomendar un plan según el uso, con `conocimiento/MATIAS_OS_SUSCRIPCION_AKUS_PUBLICO.md` (lo mismo que publica akaike.lat). Nunca publica importes, monedas, tarifas, valor del AKU o del setup ni descuentos: `guard_reply` bloquea cualquier monto en dinero (las cantidades de AKUs y de uso no cuentan como monto) y los nombres viejos Scale y Enterprise Pro. Las consultas de precio, costo, cotización o presupuesto reciben una respuesta comercial fija con el configurador y la agenda; no consumen el modelo. Las preguntas legítimas sobre scoring, implementación, protección de datos y ahorro operativo mantienen la conversación normal.

## Capas de protección

- `chat_security.py`: inspección normalizada y acotada de patrones de extracción, suplantación de roles, SQL y codificaciones comunes; no ejecuta el texto.
- `server.py`: ambas rutas públicas (`/api/chat` y `/api/presentacion`) aplican política de entrada y salida. Identificadores de sesión limitados; solicitudes de hasta 64 KiB, incluso chunked. Rate limit y autorización ocurren antes de leer el cuerpo; su lectura tiene un plazo total de 15 segundos.
- `agent_prompt.py`: identidad comercial, referencias como datos no confiables y prohibición de divulgar instrucciones, infraestructura, proveedor, catálogo o información privada.
- Historial: se reconstruye con una sola política de sistema. Ataques, respuestas antiguas sensibles y roles falsos no vuelven al modelo. Los registros originales se conservan para auditoría.
- Referencias: el chat busca con `public_only=True`; elimina fuentes de precios y fragmentos sensibles. El contenido de referencia y la pregunta se transmiten como valores JSON, no como nuevas instrucciones.
- Salida: una respuesta sensible del modelo se sustituye por una orientación comercial segura antes de publicarse o persistirse. Se inspecciona también después de retirar HTML y se detectan importes sin moneda y cifras escritas en palabras asociadas a cobros. Se restringen enlaces de salida.
- Leads: un ataque no activa captación ni notificaciones y tampoco se recupera como contacto desde el historial. Las consultas comerciales legítimas conservan la captación habitual.

## Pruebas aisladas

Instalar las dependencias existentes y `pytest` en el entorno de pruebas. Ejecutar:

```
python ops/run_web_chat_tests.py --pytest
```

El runner vacía el entorno, impide cargar `.env`, bloquea conexiones y utiliza una SQLite temporal propia. Incluye pruebas HTTP reales sobre ASGI con proveedor y persistencia simulados; no son llamadas al modelo real. Los casos cubren rechazo de ataques, catálogos y precios, historial contaminado, salida sensible, cuerpos chunked, sesión SQL y conversaciones comerciales permitidas. También ejecuta la suite existente de presentación y leads.

## Publicación y verificación

1. Revisar diff y escanear archivos de release con gitleaks redactado.
2. Publicar únicamente los archivos de este cambio, con autorización del propietario.
3. Esperar que `/api/health` muestre el SHA exacto publicado.
4. Probar consultas normales, propuesta comercial y ataques controlados en ambas rutas; usar sesiones QA y no incluir correo, teléfono ni datos de clientes.
5. Comprobar CORS de la página y que los endpoints administrativos siguen bloqueados sin autenticación.
6. Conservar evidencia de respuestas y SHA fuera del repositorio, sin secretos.

## Alcance

Son controles por capas, no una garantía de detección universal. Las consultas SQL deben seguir parametrizadas; la inspección de texto no sustituye esa protección. No se elimina evidencia ni se determina que un visitante es falso por un solo patrón. La rotación de una credencial antigua exige coordinación; retirarla del archivo no la invalida ni modifica por sí solo la configuración de producción.
