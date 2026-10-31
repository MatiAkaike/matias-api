# Oferta comercial M.A.T.I.A.S. para Alurí (confidencial)

Fuente única de verdad del asistente de esta oferta. Emitida por Akaike Credit Risk Solutions S.A.S. (NIT 901.943.344-3, Bogotá) para Alurí, atención Óscar Zapata (zapata@aluri.co). Presentada por Oscar G. Gutiérrez M., CEO y Fundador de Akaike (oscar@akaike.co, +57 320 475 6752, www.akaike.co).

## Vigencia
- Emisión: 31 de octubre de 2026. Vence: 30 de noviembre de 2026 a las 11:59 p. m., hora de Bogotá. Plazo: 30 días calendario.
- La página de la oferta muestra los días que quedan. Si vence sin aceptación, Akaike actualiza la propuesta con las condiciones vigentes en ese momento.

## Lo que entendimos de Alurí
- Alurí conecta solicitantes que necesitan financiación con una red de inversionistas que proveen los recursos.
- Opera principalmente crédito de consumo respaldado con garantía hipotecaria. Alurí recibe la solicitud, reúne documentos, analiza al solicitante y la garantía, y estructura la operación antes de presentarla al inversionista.
- Volumen actual aproximado: 20 a 30 solicitudes al mes.
- La garantía reduce la severidad de una pérdida, pero no elimina el riesgo de crédito.
- Reto: muchos solicitantes son independientes, comerciantes o personas sin nómina tradicional; ahí el análisis manual es lento, subjetivo y difícil de defender ante el inversionista.
- Una buena decisión responde ocho preguntas: capacidad de pago, endeudamiento, comportamiento, ingresos (estabilidad y verificabilidad), probabilidad de incumplimiento, garantía, Loan to Value (LTV) y condiciones.

## La solución
M.A.T.I.A.S. como analista de crédito con IA de Alurí. Matías (Brain) es el cerebro: aprende la política, los productos y las excepciones de Alurí y explica cada decisión. Coordina tres componentes:
- M.A.T.I.A.S. Credit Score: score y perfiles de riesgo PR1 a PR5 construidos para el mercado de Alurí.
- Matías Flows: la política de crédito convertida en un flujo automático. Recorrido: solicitud, validaciones iniciales, consulta a DataCrédito Experian o TransUnion, políticas duras, endeudamiento, validación de ingresos, capacidad de pago, Credit Score, perfil PR1–PR5, garantía, LTV y decisión. Reglas trazables, versionables y auditables.
- M.A.T.I.A.S. Platform: Credit Dashboard, Solicitudes Entrantes, Mesa de Análisis, Indicadores de Crédito, Credit Score, Data BI, el asistente Matías y soporte con trazabilidad.

## Cómo decide en cada solicitud
- Credit Score sin historia propia: Alurí aún no tiene historia suficiente para un modelo supervisado. Akaike construye una población sintética con las proporciones reales de sus clientes (por ejemplo, si el 80 % son independientes, el modelo lo refleja) y la complementa con su experiencia en crédito de consumo. En la primera etapa los perfiles PR1–PR5 son segmentadores de riesgo relativo, no probabilidades de incumplimiento calibradas. Con el desempeño real de Alurí el modelo evoluciona a supervisado.
- Perfiles: PR1 riesgo muy bajo, PR2 bajo, PR3 moderado, PR4 alto o revisión, PR5 muy alto.
- Centrales de riesgo: DataCrédito Experian o TransUnion, según la que contrate Alurí: score de buró, obligaciones y cuotas, saldos, moras actuales e históricas, cartera castigada, reestructuraciones, consultas recientes, endeudamiento por sector, experiencia crediticia y alertas. Las reglas específicas se definen en la implementación.
- Income & Capacity: cruza desprendibles de nómina, certificados laborales, extractos bancarios, declaración de renta, RUT, certificaciones de ingresos, contratos de prestación de servicios y documentación del negocio para separar el ingreso declarado del ingreso reconocido para crédito; calcula ingresos, gastos, cuotas existentes, flujo disponible, capacidad máxima de pago, cuota máxima recomendada y monto compatible.
- Garantía y LTV: lee y resume certificado de tradición y libertad, avalúo comercial, escritura, impuesto predial, estudio de títulos, paz y salvos y soportes de propiedad horizontal. LTV = monto solicitado ÷ valor reconocido del inmueble, con descuentos de estrés (ejemplo ilustrativo: inmueble de $260 millones y monto de $80 millones da LTV de 30,8 %; con 15 % de descuento, 36,2 %; con 30 %, 44,0 %). No reemplaza el avalúo profesional ni el estudio jurídico de títulos.
- Caminos de decisión: rechazo si incumple una política crítica; PR1 o PR2 con capacidad y garantía continúan automáticamente; PR3 puede pedir documentos adicionales; PR4 o inconsistencias van a revisión manual en la Mesa de Análisis; una operación aprobada en revisión vuelve al flujo; sin documentación suficiente queda condicionada.

## Lo que recibe Alurí por cada solicitud
Un expediente consolidado: perfil PR1–PR5, Credit Score M.A.T.I.A.S., resultado de centrales, ingreso declarado e ingreso reconocido, endeudamiento, capacidad de pago, cuota máxima, monto solicitado, valor del inmueble, LTV, alertas, documentos analizados, condiciones pendientes y una recomendación final: Recomendado, Recomendado con condiciones, Revisión manual o No recomendado. Sirve para presentar cada operación al inversionista de forma estructurada, homogénea y trazable.

## Cronograma (8 semanas desde la firma y el pago de la implementación)
- S1: arranque y entendimiento de la operación. S1–S2: caracterización del mercado y datos históricos. S2–S4: población sintética y Credit Score PR1–PR5. S2–S3: política de crédito, reglas y alertas. S3–S5: Matías Flows y central de riesgo. S4–S6: Income & Capacity, documentos, garantía y LTV. S5–S6: configuración de la plataforma. S6–S7: pruebas y validación conjunta con Alurí. S8: capacitación y salida a producción.
- Hitos: arranque (S1), score aprobado (S4), flujo en pruebas (S6), producción (S8).
- Alurí aporta: histórico de solicitudes y operaciones, política actual, documentos tipo y un líder de proyecto con disponibilidad semanal. Akaike entrega: modelo, flujo, plataforma configurada, pruebas con escenarios sintéticos, capacitación y acompañamiento. Seguimiento: comité semanal y aprobación de Alurí en cada hito.

## Inversión
- Implementación: USD 5.450, pago único. Incluye Credit Score y población sintética, segmentación PR1–PR5, política inicial, Matías Flows, integración con una central de riesgo, Income & Capacity, parametrización documental inicial, garantía y LTV, configuración de la plataforma, pruebas y capacitación.
- Licencia M.A.T.I.A.S. Starter: USD 990 al mes, incluye 2.000 AKUs al mes, permanencia mínima de 12 meses.
- Valores en dólares, antes de impuestos. La facturación en Colombia se hace en pesos a la TRM del día de la factura.
- No incluido: consultas de DataCrédito Experian o TransUnion, avalúos profesionales, estudios de títulos, gastos notariales y de registro, y servicios de terceros contratados por Alurí.

## AKUs para Alurí (crédito con garantía hipotecaria)
- Los Akaike Units (AKUs) son la moneda única de consumo de M.A.T.I.A.S.; el mismo saldo mensual se usa en todos los productos y el consumo se ve en la plataforma. No son dinero ni saldo redimible.
- Una solicitud con garantía hipotecaria consume el doble que una de consumo de persona natural, por el volumen de documentos y verificaciones: Credit Score 8 AKUs por calificación (frente a 4) y Matías Flows 2 AKUs por ejecución completa (frente a 1). Total: 10 AKUs por solicitud.
- Con Starter (2.000 AKUs) alcanzan hasta 200 solicitudes al mes solo con Credit Score + Flows.
- Con el volumen actual (20 a 30 solicitudes): se usan 200 a 300 AKUs (10 % a 15 % del cupo) y quedan 1.700 a 1.800 AKUs para análisis documental, Data BI y reportes; con 30 solicitudes quedan unos 56 AKUs por expediente.
- Otros consumos: reporte armado por Matías con IA 2 AKUs; Data BI consulta o pivote nuevo 0,1 AKU; ver tableros y reportes y preguntarle a Matías 0 AKUs; el análisis documental del expediente se mide según uso.
- Si Alurí crece: puede comprar AKUs adicionales en cualquier momento sin cambiar de plan (el valor se cotiza con Akaike), o pasar al plan Expert (USD 1.490 al mes, 5.200 AKUs, hasta 520 solicitudes con garantía hipotecaria) o al plan Pro (USD 2.490 al mes, 12.000 AKUs, hasta 1.200 solicitudes).

## Evolución del modelo
Cada solicitud, decisión, condición, pago, mora, incumplimiento, recuperación y ejecución de garantía alimenta la muestra propia de Alurí. Con historia suficiente, el score se recalibra como modelo supervisado sobre sus propios clientes.

## Aceptación y siguientes pasos
- Se acepta con el botón «Aceptar oferta» de la página: se leen los términos, se marca «He leído y acepto los términos de la oferta» y se confirma. Llega un correo de confirmación de Akaike.
- Para elaborar el contrato Akaike pide: certificado de existencia y representación legal de la Cámara de Comercio (no mayor a 30 días), RUT, fotocopia de la cédula del representante legal y el correo de facturación electrónica.
- La aceptación expresa la intención de contratar; las partes firman después un contrato de prestación de servicios tecnológicos que regula obligaciones, propiedad intelectual, confidencialidad, protección de datos y niveles de servicio. Si algo difiere, prevalece el contrato.
- También puede agendar una sesión con Oscar: https://calendar.app.google/9L3paRWXnsMjkXKU7
