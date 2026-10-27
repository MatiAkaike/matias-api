# Portafolio vigente del agente web

## Fuente y alcance

Fuente suministrada por Oscar: `MATIAS_OS_Vision_Funcional_y_Portafolio.md`, visión funcional 1.0, octubre de 2026.

SHA-256 de la fuente: `b46f08d0680183c75f60e81b0fb395993aca0bce67dc40faaf4a8df3e0d7f227`.

La síntesis pública versionada está en `conocimiento/MATIAS_OS_PORTAFOLIO_PUBLICO.md`. El documento original no se publica como contexto: mezcla visión funcional, propuestas e inclusiones comerciales por nivel. La síntesis conserva los seis productos y sus funciones, Brain, independencia de Credit Score para Copilot/Credit Agent, API/MCP/terminal, misiones, análisis por línea, documentos, canales, integraciones, habilidades, gobierno y controles de operaciones. No lleva importes. Desde el 26-oct-2026 se suma `conocimiento/MATIAS_OS_SUSCRIPCION_AKUS_PUBLICO.md` (planes Starter, Expert, Pro y Corporate, AKUs, consumo por capacidad, cómo recomendar un plan y qué se cotiza aparte), sacado del Manual Canónico de AKUs v1.0 sin ninguna cifra en dinero.

## Comportamiento

- `public_portfolio.py` carga la fuente pública con la aplicación; ausencia del archivo falla el arranque y no deja un catálogo vacío silencioso.
- Las consultas generales del portafolio tienen respuesta determinística con los seis productos, Training Center / Brain y agenda.
- El resumen general solo intercepta solicitudes inequívocas del portafolio propio. Una mención de portafolio o una consulta sobre otra empresa no activa ese atajo. La intención explícita de demo/reunión se evalúa antes del resumen.
- Las consultas específicas usan todo el portafolio vigente como referencia, separado de las instrucciones de sistema y con prioridad factual sobre el material anterior.
- El chat público solo asesora comercialmente; no consulta créditos reales, ejecuta misiones ni desembolsa recursos.
- Las capacidades descritas como visión/propuesta no se prometen disponibles; el alcance concreto debe confirmarse en reunión.
- Cotización, presupuesto y precios se interceptan antes del modelo con el configurador (https://www.akaike.lat/#configurador) y el enlace oficial de agenda (https://calendar.app.google/9L3paRWXnsMjkXKU7). Las preguntas de planes y AKUs sí llegan al modelo.
- Presupuesto de contratación no equivale a presupuesto del solicitante: consultas sobre capacidad de pago y análisis presupuestario permanecen en el flujo de orientación comercial del producto.
- Las protecciones de entrada, historial, salida y captación de leads permanecen activas en las dos rutas públicas.

## Pruebas

Ejecutar el runner aislado `python ops/run_web_chat_tests.py --pytest`.

Regresiones agregadas: cobertura completa en las dos rutas, portafolio y límites en el contexto del modelo, cotízame/presupuesto/cotización sin invocar el modelo, preguntas específicas que mencionan portafolio, Credit Agent con ERP sin grafo/slide, conservación de nombres públicos de productos. La prueba previa de separación de contexto usa ahora una pregunta específica, para seguir comprobando realmente el camino del modelo.

## Verificación de release

Solo publicar archivos explícitos del backend. Comparar SHA remoto con `/api/health`. Probar portafolio y cotización en las dos rutas y preguntas legítimas específicas del portafolio con sesiones QA, sin datos personales, sin ataques ni contactos artificiales. Revisar que no aparecen importes, monedas, nombres viejos de planes (Scale, Enterprise Pro) ni datos internos. No enviar más de diez consultas a presentación por IP: su cuota se aplica durante veinticuatro horas y se reinicia con el proceso.
