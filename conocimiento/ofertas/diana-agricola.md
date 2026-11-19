# Oferta comercial M.A.T.I.A.S. para Diana Agrícola (confidencial)

Fuente única de verdad del asistente de esta oferta. Emitida por Akaike Credit Risk Solutions S.A.S. (NIT 901.943.344-3, Bogotá) para Diana Agrícola, empresa del Grupo Diana, atención Jenny Ruiz, directora de Crédito y Cartera (jmry.ruiz@gmail.com). Presentada por Oscar G. Gutiérrez M., CEO y Fundador de Akaike (oscar@akaike.co, +57 313 412 4795, www.akaike.co).

## Vigencia
- Emisión: 19 de noviembre de 2026. Vence: 19 de diciembre de 2026 a las 11:59 p. m., hora de Bogotá. Plazo: 30 días calendario.
- La página de la oferta muestra los días que quedan. Si vence sin aceptación, Akaike actualiza la propuesta con las condiciones vigentes en ese momento.

## Lo que entendimos de Diana Agrícola
- Diana Agrícola vende a crédito insumos (fertilizantes y otros) a agricultores, en su mayoría productores de arroz (cerca del 80 %), solo en sus propios puntos. El crédito es de destinación específica, sobre un cupo por cultivo, y se paga en un solo pago a los 3 o 4 meses, con la cosecha.
- El molino del grupo (que transforma el arroz paddy) también da crédito a parte de los mismos clientes. Hoy son dos procesos con documentos y análisis distintos; está definido que van a quedar en un solo proceso.
- Volumen: unos 1.500 clientes y unos 2.000 créditos al año. Casanare: cerca de 750 clientes (unos 500 de Diana Agrícola y 250 del molino), medianos y grandes productores, cupo cercano a $ 500 millones, operación muy estacional con pico de febrero a abril. Tolima y Huila: cerca de 750 clientes (unos 600 de Diana Agrícola y 150 del molino), pequeños y medianos, cupo cercano a $ 100 millones, siembra todo el año y 2 o 3 créditos por cliente al año. Meta tiene una operación particular (maíz, arroz y soya, con pago en especie) que no entra en el score de la primera etapa; sus solicitudes pueden pasar por el flujo e ir a comité.
- Cartera vencida: en Casanare llega a 96 % fuera de temporada porque toda la cartera vence en la misma fecha; en Tolima y Huila está entre 30 y 35 %. El indicador tradicional de banco no sirve; se necesitan indicadores por cosecha.
- Dolores: documentos recibidos en campo, en la agencia o por el comercial sin registro; cupos aprobados con la imagen del pagaré cuando el original no llegó a custodia; digitación manual de DataCrédito y de estados financieros; Techambits (plataforma actual) no muestra etapa, tiempos ni devoluciones; no hay vector de pagos interno; el score actual es de juicio experto y solo informativo; las aprobaciones se apoyan mucho en la relación de largo plazo con el cliente.
- Diana Agrícola ya avanza en una validación documental con IA con otro proveedor y en un web service con DataCrédito; ambos se conectan como pasos del flujo de M.A.T.I.A.S.
- Lo que busca: un solo workflow de crédito con custodia, etapas, indicadores y reportería, que deje los datos listos para modelos de otorgamiento y cobranza, implementado por fases.

## La solución
M.A.T.I.A.S. como analista de crédito con IA de Diana Agrícola. Matías Brain es el cerebro: aprende la política, los manuales y las excepciones de Diana Agrícola en una instancia privada (sin compartir datos con modelos públicos) y explica cada decisión. Coordina cuatro componentes:
- Matías Flows: el workflow del crédito, con etapas, devoluciones y reglas; se pueden tener flujos distintos por zona. Se arma con nodos o en lenguaje natural. No se cobra por número de flujos, sino por ejecución.
- Credit Score: score y perfiles PR1 a PR5 con el incumplimiento medido contra la fecha de cosecha.
- Data BI: tableros en tiempo real (tiempo por solicitud, devoluciones, aprobación, cosechas, mora por zona, agencia y asesor), con arrastrar y soltar o pidiéndoselos a Matías, y envío automático por correo.
- Matías Agent: agentes con IA para análisis y, en una fase posterior, para cobranza y para atender al agricultor por WhatsApp.
- Recorrido de cada solicitud: solicitud del comercial o la agencia, registro único Diana y molino, validación documental con IA, pagaré firmado y en custodia, DataCrédito o TransUnion, listas restrictivas, políticas duras, análisis financiero y capacidad, Credit Score por cosecha, perfil PR1–PR5, comité o Mesa de Análisis, y decisión: aprobada, devuelta o negada.

## Cómo decide en cada solicitud
- Credit Score: sin historia estructurada, Akaike parte del scorecard de juicio experto de Diana Agrícola y de una población sintética con la mezcla real de zonas y productores. El incumplimiento se define contra la fecha de cosecha, no a 90 días como en un banco. En la primera etapa los perfiles PR1–PR5 son segmentadores de riesgo relativo, no probabilidades calibradas; con el desempeño real, el modelo evoluciona a supervisado y permite calcular cupos preaprobados para la siguiente cosecha.
- Perfiles: PR1 riesgo muy bajo, PR2 bajo, PR3 moderado, PR4 alto o revisión, PR5 muy alto.
- Centrales y listas: consulta automática a DataCrédito Experian o TransUnion y a listas OFAC y ONU. Si el cliente se consultó hace poco (15, 30 o 60 días, según la política), el flujo reutiliza la consulta.
- Análisis financiero: Matías lee los estados financieros y soportes que hoy se digitan. Como el flujo de caja del arrocero casi nunca da positivo, el análisis mira la cosecha esperada, el respaldo y el comportamiento, para que el comité decida con información.
- Pagaré y custodia: el flujo no deja aprobar un cupo si el pagaré no está firmado y en custodia. Se conecta con el proveedor de pagaré desmaterializado que elija Diana Agrícola (por ejemplo, Deceval), con un solo pagaré por cliente. Un pagaré desmaterializado es válido si garantiza trazabilidad, integridad y no repudio; el área jurídica de Diana Agrícola lo confirma.
- Caminos de decisión: negada si incumple una política crítica; aprobada para PR1 y PR2 con documentos y pagaré; devuelta para PR3 o si faltan documentos; comité para PR4 o casos especiales.

## Hoy y con la propuesta
Procesos separados pasan a un solo flujo y expediente (nuevo). Recepción sin registro pasa a registro por el comercial en el flujo (mejora). Pagaré custodiado después de aprobar pasa a no aprobar sin pagaré en custodia (nuevo). Centrales digitadas pasan a consulta automática leída por Matías (mejora). Estados financieros digitados pasan a lectura automática (mejora). Trámite sin etapa visible pasa a etapa, tiempo y devoluciones por solicitud (nuevo). Indicadores de banco pasan a cosechas, aprobación y mora por zona, agencia y asesor (nuevo). Datos dispersos pasan a una base única para otorgamiento y cobranza (nuevo).

## Fases
- Fase 1 (esta propuesta): digital, de la mano del comercial y la agencia, sin depender de la conectividad del agricultor.
- Fase 2 (cuando Diana Agrícola decida): el agricultor pide por WhatsApp con fotos y notas de voz, atendido por Matías Agent. Se dimensiona y cotiza aparte.
- El portal de cara al agricultor (agendamiento de citas en ventanilla, carga unificada de documentos) no lo hace Akaike; Akaike puede presentar a BioCredit, que desarrolla ese tipo de portales y se integra con M.A.T.I.A.S. Es una cotización aparte.

## Cronograma (8 semanas desde la firma y el pago de la implementación)
- S1–S2: arranque y levantamiento de los dos procesos. S2–S3: proceso unificado y política de crédito. S2–S4: DataCrédito o TransUnion y listas. S2–S5: población sintética y Credit Score por cosecha. S3–S6: Matías Flows con etapas, devoluciones y custodia. S4–S5: Matías Brain con política y manuales. S5–S7: tableros de Data BI. S6–S7: pruebas con comerciales, agencias y analistas. S8: capacitación y salida a producción.
- Hitos: arranque (S1), proceso aprobado (S3), flujo en pruebas (S6), producción (S8).
- Diana Agrícola aporta: procesos y formatos de las dos empresas, histórico de clientes y cartera, credenciales de las centrales y un líder del proyecto con apoyo de Tecnología. Akaike entrega: flujo unificado, score, tableros y plataforma configurada, con pruebas, capacitación y acompañamiento. Seguimiento: comité semanal y aprobación en cada hito.
- Con firma en diciembre de 2026, el flujo estaría en producción a finales de enero de 2027, antes del pico de Casanare.

## Inversión
- Implementación: $ 20.000.000 más IVA, pago único. Incluye levantamiento y unificación de los dos procesos, política inicial, Matías Flows, integración con una central de riesgo y listas restrictivas, conexión con la validación documental y con el proveedor de pagaré, Credit Score por cosecha y PR1–PR5, Matías Brain, tableros de Data BI, pruebas y capacitación.
- Licencia M.A.T.I.A.S. Starter: $ 4.000.000 más IVA al mes, incluye 2.000 AKUs al mes, permanencia mínima de 12 meses, se cobra desde la salida a producción. Con la licencia quedan habilitados todos los módulos; se paga por consumo de AKUs.
- Valores en pesos colombianos, más IVA.
- No incluido: consultas a DataCrédito Experian o TransUnion, emisión y custodia de pagarés desmaterializados, la validación documental del proveedor que contrate Diana Agrícola, el portal de cara al agricultor y la fase 2 por WhatsApp.

## AKUs para Diana Agrícola
- Los Akaike Units (AKUs) son la moneda única de consumo de M.A.T.I.A.S.; el mismo saldo mensual sirve para todos los módulos y el consumo se ve en la plataforma. No son dinero ni saldo redimible.
- Cada solicitud con Credit Score (4 AKUs) y Matías Flows (1 AKU) consume 5 AKUs. Con Starter alcanzan hasta 400 solicitudes al mes.
- Mes promedio de Diana Agrícola: unas 170 solicitudes, 850 AKUs (43 % del cupo); quedan unos 1.150 AKUs para Data BI, reportes con IA, análisis documental y Matías Agent. En el pico de Casanare (febrero a abril): unas 350 solicitudes, 1.750 AKUs; siguen cabiendo en el plan y, si hace falta más, se compran AKUs adicionales solo para esos meses.
- Otros consumos: reporte armado por Matías con IA 2 AKUs; Data BI consulta o pivote nuevo 0,1 AKU; ver tableros y preguntarle a Matías 0 AKUs; análisis documental y Matías Agent según uso.
- Si crece: AKUs adicionales en cualquier momento sin cambiar de plan; plan Expert con 5.200 AKUs al mes (hasta 1.040 solicitudes) o plan Pro con 12.000 AKUs al mes (hasta 2.400 solicitudes). Los precios de los AKUs adicionales y de los planes Expert y Pro se cotizan con Akaike; el asistente no los da.

## Lo que el asistente no debe hacer
- No dar precios de AKUs adicionales, de los planes Expert o Pro, de la fase 2 ni del portal de BioCredit: se cotizan con Oscar.
- No ofrecer descuentos ni cambiar la permanencia, el IVA o el cronograma.
- No prometer tiempos de respuesta por solicitud que no estén medidos.

## Aceptación y siguientes pasos
- Se acepta con el botón «Aceptar oferta» de la página: se leen los términos, se marca «He leído y acepto los términos de la oferta» y se confirma. Llega un correo de confirmación de Akaike.
- Para elaborar el contrato Akaike pide: certificado de existencia y representación legal de la Cámara de Comercio (no mayor a 30 días), RUT, fotocopia de la cédula del representante legal y el correo de facturación electrónica.
- La aceptación expresa la intención de contratar; las partes firman después un contrato de prestación de servicios tecnológicos que regula obligaciones, propiedad intelectual, confidencialidad, protección de datos y niveles de servicio. Si algo difiere, prevalece el contrato.
- El siguiente paso propuesto es revisar la propuesta con el equipo de Tecnología de Diana Agrícola. Agenda con Oscar: https://calendar.app.google/9L3paRWXnsMjkXKU7
