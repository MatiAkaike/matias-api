M.A.T.I.A.S. Credit Score – Descripción Técnica del 
Producto 
 
 
1. Definición general del producto 
M.A.T.I.A.S. Credit Score 
Modelo Analítico Transformador en Inteligencias Artificiales Scoring. 
Es el producto core de Akaike Credit Risk Solutions para calcular el riesgo de 
crédito de un solicitante mediante un API. 
Detrás del API hay un modelo de IA entrenado con: 
1. Datos históricos de comportamiento de pago de la entidad cliente (core del 
modelo). 
2. Fuentes externas de información: 
o Burós de crédito: TransUnion, Experian, otros. 
API
Request
Variables de entrada:
- ID Solicitante
- Apellidos
- Demográficas
- Financieras
- Internas de la entidad
- Otras del solicitante
AWS
Experian
Transunion
Bank
M.A.T.I.A.S. 
Credit Score
Response
Variables de Salida:
- Credit Score
- Aprobación / Rechazo
- Tasa de Interés
- Cupo / Monto
- Colaterales / Garantías
- Sugerencias IA
Claro
Movistar
Procredito
Otras
AWS

---

o Telcos: Claro, Movistar. 
o Otras fuentes como Procrédito u otras que se integren a futuro. 
 
El servicio devuelve: 
• 
Un Credit Score (numérico). 
• 
Una decisión sugerida: Aprobación / Rechazo. 
• 
Una estrategia de aprobación: 
o Tasa de interés sugerida. 
o Cupo / monto máximo recomendado. 
o Plazo máximo recomendado. 
o Requerimiento de garantías / colaterales. 
• 
Sugerencias adicionales de IA (ej. segmentación de riesgo, alertas, 
recomendaciones de política). 
 
Todo esto se entrega a través de un API / webhook para ser consumido en línea por 
la plataforma donde el solicitante está haciendo su proceso de crédito (app web, 
móvil, core, etc.).   
 
2. Objetivo funcional 
Exponer un servicio centralizado de calificación de riesgo que: 
1. Reciba un request de evaluación de crédito con datos del solicitante 
(internos + declarados). 
2. Orqueste la consulta a las fuentes externas necesarias (burós, telcos, otros 
nodos). 
3. Envíe toda la información consolidada al modelo personalizado de 
M.A.T.I.A.S. de ese cliente. 
4. Devuelva una respuesta estructurada con: 
o Credit Score 
o Decisión sugerida (approve/decline) 
o Condiciones sugeridas (tasa, monto, plazo, colateral) 
o Sugerencias IA (segmento de riesgo, banderas, etc.) 
 
El modelo es personalizado por entidad:

---

Cada cliente de Akaike tiene su propio algoritmo entrenado con su data, su propio 
nodo M.A.T.I.A.S. y su propio flujo de fuentes de información. 
 
3. Arquitectura lógica de alto nivel 
Basado en el diagrama de flujo que tienes:   
3.1 Componentes principales 
1. API Gateway (AWS API Gateway) 
o Exposición del endpoint público/privado de M.A.T.I.A.S. 
o Autenticación y autorización (API keys / JWT / OAuth2 según se defina). 
o Validación básica de schema de entrada. 
2. Orquestador de flujo por nodos (lógica de negocio) 
o Puede ser implementado con: 
§ 
AWS Lambda + Step Functions, o 
§ 
Un microservicio orquestador (por ejemplo en Python/FastAPI) 
desplegado en ECS/Fargate. 
o Encargado de: 
§ 
Recibir la solicitud. 
§ 
Determinar qué nodos/fuentes debe consultar para ese cliente 
específico. 
§ 
Llamar a los adaptadores de cada fuente (TransUnion, Experian, 
Claro, Movistar, Procrédito, etc.). 
§ 
Unificar y normalizar los datos. 
§ 
Construir el vector de features de entrada para el modelo de 
ese cliente. 
§ 
Llamar al modelo M.A.T.I.A.S. del cliente. 
§ 
Armar la respuesta final del API. 
3. Nodos de integración de datos externos (Fuentes alternativas) 
Cada fuente se modela como un nodo independiente: 
o Nodo TransUnion 
o Nodo Experian 
o Nodo Claro 
o Nodo Movistar 
o Nodo Procrédito 
o Otros nodos futuros 
Cada nodo:

---

o Recibe un payload estándar desde el orquestador (ID, documento, 
nombre, etc.). 
o Gestiona la llamada al proveedor (REST/XML/SOAP, según el caso). 
o Normaliza la respuesta a un formato interno estándar de Akaike. 
o Maneja errores, timeouts y políticas de reintento. 
4. Nodos de datos internos de la entidad 
o Conectores a bases internas del cliente (core, CRM, histórico de pagos, 
etc.), ya sea: 
§ 
vía APIs del cliente, 
§ 
vía replicación de datos a un Data Lake / Feature Store en AWS, 
§ 
o vía batch precargado (según el acuerdo con cada entidad). 
o Su salida también se normaliza al formato interno estándar. 
5. Nodo de modelo M.A.T.I.A.S. por cliente (Modelo personalizado) 
o Servicio de inferencia del modelo entrenado para ese cliente. 
o Implementado típicamente en Python (PyTorch, scikit-learn, etc.). 
o Desplegado en: 
§ 
AWS Lambda (si el modelo es ligero y la latencia lo permite). 
§ 
AWS ECS/Fargate o SageMaker para modelos más pesados o 
con necesidad de GPU. 
o Uno por cliente: 
§ 
matias_model_cliente_A 
§ 
matias_model_cliente_B 
§ 
etc. 
o Cada uno recibe un vector de features normalizado, genera: 
§ 
PD / riesgo, 
§ 
score estandarizado, 
§ 
sugerencias de condiciones (o señales para una capa de reglas). 
6. Capa de reglas de negocio y estrategia (opcional pero recomendable) 
o Puede ser embebida en el mismo servicio del modelo o en un motor de 
reglas separado. 
o Traduce la salida del modelo (PD, score, segmento) en: 
§ 
Aprobación / Rechazo sugerido. 
§ 
Tasa recomendada. 
§ 
Monto máximo. 
§ 
Plazo máximo. 
§ 
Requerimiento de garantías. 
o Debe ser parametrizable por cliente (tablas de pricing, rangos de 
score, etc.). 
7. Almacenamiento y logging 
o S3 / Data Lake: guarda requests, respuestas, logs de inferencia, para: 
§ 
auditoría, 
§ 
análisis posterior, 
§ 
re-entrenamiento. 
o CloudWatch / OpenSearch: logs técnicos, métricas de uso, errores.

---

o Base de datos relacional / NoSQL para seguimiento de transacciones 
y versionado de modelos. 
 
4. Flujo detallado de petición / respuesta 
4.1 Variables de entrada (según diagrama y descripción)   
Del cliente de Akaike hacia el API de M.A.T.I.A.S.: 
• 
id_solicitud / id_solicitante 
• 
Datos personales: 
o nombres, apellidos 
o tipo y número de documento 
o fecha de nacimiento 
o información demográfica: ciudad, departamento, país, estrato, estado 
civil, etc. 
• 
Información financiera: 
o ingresos, egresos, tipo de empleo, antigüedad laboral, etc. 
o información interna de la entidad (si el cliente la envía en el request: 
número de productos activos, mora histórica interna, etc.) 
• 
Información de la operación: 
o tipo de producto, monto solicitado, plazo solicitado, tipo de garantía 
ofrecida, etc. 
 
Importante: La arquitectura debe soportar que parte de la data interna no venga en el 
request, sino que se consulte vía nodos internos conectados al core/CRM del cliente. 
 
4.2 Flujo secuencial 
1. Recepción de la solicitud (API Gateway → Orquestador) 
o Valida estructura básica del request. 
o Identifica al cliente (tenant) mediante API key / header / path 
(/api/v1/matias/{cliente_id}/score). 
2. Determinación de nodos a usar (por cliente) 
o A partir de la configuración del cliente: 
§ 
Cliente A: requiere TransUnion + Experian + Claro. 
§ 
Cliente B: solo TransUnion. 
§ 
Cliente C: Experian + Procrédito.

---

o El orquestador construye el plan de ejecución de nodos. 
3. Consulta a fuentes externas / internas 
o Para cada nodo requerido: 
§ 
Construye el payload necesario (por ejemplo, para TransUnion: 
tipo doc, número doc, nombre, etc.). 
§ 
Llama al servicio del nodo (Lambda / microservicio). 
§ 
Recibe la respuesta del proveedor externo. 
§ 
Normaliza campos a un esquema común de features de buró / 
telco. 
4. Construcción del vector de features 
o Se juntan: 
§ 
variables del request original, 
§ 
variables internas del cliente (si se obtienen vía nodo), 
§ 
variables de burós, 
§ 
variables de telcos, 
§ 
cualquier otra fuente configurada. 
o Se aplican transformaciones: 
§ 
imputación de faltantes, 
§ 
codificación de categóricas (one-hot, target encoding, etc.) 
según el modelo, 
§ 
escalado o normalización si el modelo lo requiere. 
5. Llamado al modelo M.A.T.I.A.S. del cliente 
o El orquestador llama al endpoint de inferencia del modelo: 
§ 
POST /internal/matias/{cliente_id}/predict 
o El modelo devuelve: 
§ 
score_bruto o PD, 
§ 
score_normalizado (ej. 0–1.000), 
§ 
segmento_riesgo (ej. A–E, PR1–PR5), 
§ 
métricas auxiliares (probabilidades, etc., si se quieren loguear). 
6. Aplicación de estrategia de crédito 
o Capa de reglas transforma el score en: 
§ 
decision: APPROVE / REJECT / REVIEW. 
§ 
tasa_interes_sugerida. 
§ 
monto_maximo_aprobado. 
§ 
plazo_maximo_meses. 
§ 
garantias_requeridas (ej. codeudor, garantía real, sin garantía). 
o Se pueden incluir estrategias diferenciales para: 
§ 
clientes nuevos vs recurrentes, 
§ 
canales (digital vs físico), 
§ 
tipo de producto. 
7. Construcción de la respuesta y devolución vía API / webhook 
Respuesta estandarizada al cliente:

---

o credit_score 
o decision 
o tasa_interes 
o monto_maximo 
o plazo_maximo 
o garantias 
o sugerencias_ia (texto / códigos de recomendación) 
o metadata_modelo (versión del modelo, timestamp, etc.) 
8. Persistencia y logging 
o Se guarda todo el ciclo de inferencia (request limpiecito, features, 
salida del modelo, respuesta) en repositorios para: 
§ 
auditoría regulatoria, 
§ 
monitoreo de performance del modelo, 
§ 
futuros re-entrenamientos. 
 
5. Diseño “por nodos” y multi-fuente 
5.1 Concepto de nodos 
Cada fuente de información se modela como un nodo independiente y 
reutilizable: 
• 
Nodo = componente que: 
o Recibe un objeto estándar (por ejemplo {id_solicitante, documento, 
nombres, apellidos, ...}). 
o Llama a un servicio externo o interno. 
o Devuelve un subconjunto de variables ya normalizadas. 
Esto permite: 
• 
Habilitar o deshabilitar nodos por cliente. 
• 
Agregar nuevas fuentes a futuro sin romper la arquitectura: 
o Nuevo nodo “Open Banking”. 
o Nuevo nodo “Score alternativo X”. 
• 
Reusar la misma lógica de orquestación con diferente combinación de nodos. 
 
5.2 Configuración por cliente

---

Debe existir una configuración por cliente, por ejemplo: 
{ 
  "cliente_id": "crediantioquia", 
  "nodos_activos": [ 
    "interno_core", 
    "transunion", 
    "experian", 
    "claro" 
  ], 
  "modelo_matias_endpoint": 
"https://internal.aws/crediantioquia/matias/predict", 
  "estrategias_credito": { 
    "segmento_A": {"tasa_min": 18, "tasa_max": 22, "plazo_max": 36}, 
    "segmento_B": {"tasa_min": 22, "tasa_max": 26, "plazo_max": 24}, 
    "segmento_C": {"tasa_min": 26, "tasa_max": 30, "plazo_max": 18} 
  } 
} 
El orquestador lee esta configuración al inicio o la cachea para determinar: 
• 
qué nodos ejecutar, 
• 
a qué endpoint de modelo llamar, 
• 
qué reglas de estrategia aplicar. 
 
6. Modelo de datos del API (propuesta) 
Nota: esto es una guía para los equipos, los nombres concretos pueden ajustarse 
pero la estructura conceptual debe mantenerse. 
 
6.1 Request (ejemplo JSON) 
{ 
  "cliente_id": "fondetodos", 
  "canal": "digital", 
  "id_solicitud": "SOL-2025-000123", 
  "solicitante": { 
    "tipo_documento": "CC", 
    "numero_documento": "123456789", 
    "nombres": "JUAN", 
    "apellidos": "PEREZ LOPEZ", 
    "fecha_nacimiento": "1990-05-10", 
    "genero": "M", 
    "estado_civil": "SOLTERO", 
    "ciudad": "MEDELLIN", 
    "departamento": "ANTIOQUIA", 
    "estrato": 3 
  },

---

"informacion_financiera": { 
    "ingreso_mensual": 2500000, 
    "egreso_mensual": 1500000, 
    "tipo_contrato": "INDEFINIDO", 
    "antiguedad_laboral_meses": 36 
  }, 
  "operacion": { 
    "tipo_producto": "CONSUMO", 
    "monto_solicitado": 5000000, 
    "plazo_solicitado_meses": 24, 
    "destino": "LIBRE_INVERSION" 
  }, 
  "metadata": { 
    "origen": "APP_MOVIL", 
    "ip": "191.168.X.X" 
  } 
} 
6.2 Response (ejemplo JSON) 
{ 
  "id_solicitud": "SOL-2025-000123", 
  "cliente_id": "fondetodos", 
  "credit_score": 782, 
  "probabilidad_incumplimiento": 0.035, 
  "segmento_riesgo": "PR2", 
  "decision_sugerida": "APPROVE", 
  "condiciones_sugeridas": { 
    "tasa_interes_anual": 24.5, 
    "plazo_maximo_meses": 24, 
    "monto_maximo_aprobado": 5200000, 
    "garantias": "SIN_GARANTIA" 
  }, 
  "sugerencias_ia": [ 
    "CLIENTE_RECOMENDABLE_PARA_CAMPANAS_CROSS_SELL", 
    "RIESGO_BAJO_SEGUN_PATRONES_HISTORICOS" 
  ], 
  "metadata_modelo": { 
    "version_modelo": "matias_fondetodos_v1.3", 
    "fecha_ejecucion": "2025-11-08T18:30:45Z", 
    "tiempo_respuesta_ms": 430 
  } 
} 
 
7. Consideraciones de infraestructura en AWS 
7.1 Componentes sugeridos 
• 
AWS API Gateway: front del API. 
• 
AWS Lambda / ECS Fargate: 
o Orquestador.

---

o Nodos de integración (TransUnion, Experian, etc.). 
o Servicios de modelo M.A.T.I.A.S. por cliente (o SageMaker si se quiere). 
• 
AWS Step Functions (opcional): 
para orquestar flujos complejos de nodos, reintentos, timeouts, etc. 
• 
Amazon S3: 
o Almacenamiento de data de entrenamiento y logs de inferencia. 
o Versionado de modelos. 
• 
Amazon RDS / DynamoDB: 
o Configuraciones por cliente. 
o Historial de consultas. 
• 
Amazon CloudWatch: 
o Logs. 
o Métricas de rendimiento. 
• 
AWS IAM / Secret Manager / Parameter Store: 
o Credenciales de burós. 
o Llaves API. 
o Configuraciones sensibles. 
 
7.2 Escalabilidad 
• 
El diseño debe ser serverless-first (Lambda) siempre que sea posible, para: 
o escalar automáticamente con el tráfico, 
o pagar solo por uso. 
• 
Para modelos más pesados, usar ECS/Fargate con auto-scaling. 
 
8. Requerimientos no funcionales clave 
1. Latencia 
o Meta: tiempo total de respuesta (request → response) típico: 
§ 
Entre 300 ms y 2 segundos, dependiendo de los tiempos de 
respuesta de burós. 
o Deben definirse timeouts para cada nodo (ej. 1–2 s) y estrategia de qué 
hacer si un buró no responde (fallback). 
2. Disponibilidad 
o Objetivo ≥ 99.5% uptime para el endpoint de scoring. 
3. Seguridad 
o Encriptación en tránsito (HTTPS/TLS). 
o Gestión de secretos en AWS Secrets Manager.

---

o Autenticación / autorizaciones robustas por cliente. 
o Logs sin exponer datos sensibles de forma directa (cumplimiento de 
normas locales de protección de datos). 
4. Multi-tenant con aislamiento lógico fuerte 
o Cada cliente: 
§ 
tiene su propio modelo, 
§ 
su configuración de nodos, 
§ 
sus reglas de negocio, 
§ 
y, si se requiere, sus recursos separados (bases y buckets con 
separación de prefijos o cuentas). 
5. Observabilidad 
o Métricas: 
§ 
número de requests por cliente, 
§ 
latencia promedio, 
§ 
tasa de error, 
§ 
distribución del score por cliente (para monitorear drift). 
o Alarmas: 
§ 
caídas de servicios, 
§ 
errores en consultas a burós, 
§ 
anomalías en la distribución de scores (ej. PSI). 
6. Versionamiento del modelo 
o Soportar versiones de modelo por cliente, por ejemplo: 
§ 
matias_cliente_X_v1.0, v1.1, etc. 
o Permitir: 
§ 
A/B testing si se quiere (enrutando cierta proporción de tráfico). 
§ 
rollback rápido si una versión nueva se comporta mal. 
 
9. Resumen de desarrollo 
Lo que se debe construir, en esencia, es: 
1. Un API de calificación de crédito multi-tenant expuesto por AWS API 
Gateway. 
2. Un orquestador que, dado un cliente_id y una solicitud de crédito: 
o sepa qué nodos de fuentes externas/internas debe invocar, 
o consolide y normalice la data, 
o llame al modelo M.A.T.I.A.S. correspondiente a ese cliente, 
o aplique las reglas de estrategia de crédito, 
o y arme la respuesta estándar. 
3. Un sistema de nodos modulares para integrarse con: 
o burós (TransUnion, Experian, etc.), 
o telcos (Claro, Movistar),

---

o Procrédito y otras fuentes, 
de forma que sea fácil activar/desactivar por cliente. 
4. Servicios de modelo por cliente, donde cada modelo: 
o está entrenado con la data histórica real de ese cliente, 
o se puede actualizar (re-entrenar) y versionar, 
o y expone un endpoint de inferencia con un contrato claro. 
5. Infraestructura en AWS que sea: 
o escalable, 
o segura, 
o observable, 
o preparada para auditar y reentrenar modelos con base en los datos de 
inferencia. 
 
10. N8N como motor de flujo por cliente (estilo BPM) 
10.1 Rol de N8N en la arquitectura 
En la arquitectura de M.A.T.I.A.S. Credit Score, N8N es la capa de orquestación de 
procesos, es decir, el “motor BPM” que: 
1. Recibe la solicitud de evaluación de crédito (ya sea directamente o a través de 
un API Gateway que llame a N8N). 
2. Ejecuta un flujo (workflow) específico por cliente, donde: 
o se consultan las diferentes fuentes de información (burós, telcos, 
sistemas internos), 
o se limpia y transforma la información, 
o se arma el payload hacia M.A.T.I.A.S. Credit Score, 
o se recibe la respuesta de M.A.T.I.A.S., 
o y se construye la respuesta final para la plataforma del cliente. 
3. Permite que Akaike y la entidad visualicen y ajusten el flujo como si fuera un 
diagrama BPM, basado en nodos arrastrar-y-soltar. 
En términos simples: 
AWS (Lambda/ECS/SageMaker) aloja los modelos y servicios core de M.A.T.I.A.S., 
mientras que N8N es el “director de orquesta” que arma el flujo de principio a fin 
para cada cliente.

---

10.2 Flujo por cliente en N8N (visión general) 
Para cada cliente de Akaike Credit Risk Solutions se define un (o varios) workflows 
en N8N. Ejemplo: 
• 
WF_MATIAS_CREDIANTIOQUIA_ORIGINACION 
• 
WF_MATIAS_FONDETODOS_ORIGINACION 
• 
WF_MATIAS_FINTECH_X_RECURRENTE 
Cada workflow en N8N tiene la siguiente lógica general: 
1. Trigger de Entrada 
o Puede ser: 
§ 
Webhook Node de N8N (endpoint público tipo 
/webhook/matias/cliente_x). 
§ 
O una llamada desde un API Gateway de AWS que a su vez 
consuma este webhook. 
o Recibe el JSON con la solicitud de crédito (datos del solicitante, 
operación, etc.). 
2. Validación y Normalización de Datos 
o Function / Code Node: 
§ 
Valida campos obligatorios. 
§ 
Estandariza formatos (fechas, tipos de documento, mayúsculas, 
etc.). 
§ 
Aplica reglas básicas (ej. si falta un dato crítico → devolver error 
controlado). 
3. Ruteo a Fuentes de Información (nodos por buró / telco / interno) 
o N8N implementa exactamente el concepto de “nodos” que 
mencionaste, pero ahora de forma visual: 
§ 
HTTP Request Node – TransUnion 
Llama al API de TransUnion, recibe la respuesta, la mapea. 
§ 
HTTP Request Node – Experian 
§ 
HTTP Request Node – Procrédito 
§ 
HTTP Request Node – Claro / Movistar 
§ 
HTTP Request Node – Servicios internos del cliente (core, 
CRM, etc.) 
o Cada nodo: 
§ 
recibe el contexto actual del workflow (datos del solicitante), 
§ 
llama al servicio correspondiente, 
§ 
adjunta las variables resultantes al “contexto” (items) que se 
van propagando por el workflow. 
4. Configuración condicional según cliente

---

o Mediante Switch Node / IF Node, se puede definir: 
§ 
Si el cliente X requiere TransUnion y Experian → se ejecutan 
ambos nodos. 
§ 
Si el cliente Y solo requiere TransUnion → se salta Experian. 
o Esto permite tener un único workflow parametrizado o uno por 
cliente, según lo que se prefiera: 
§ 
Opción A: un workflow genérico con cliente_id y nodos 
condicionales. 
§ 
Opción B: un workflow dedicado por cliente, totalmente 
adaptado a su lógica. 
5. Construcción del payload hacia M.A.T.I.A.S. 
o Nuevamente con Function / Code Nodes: 
§ 
Se consolidan todas las variables (input + burós + telcos + 
internos). 
§ 
Se mapean a la estructura esperada por el endpoint del modelo 
M.A.T.I.A.S. (por cliente). 
§ 
Se aplica la lógica de features que el equipo de ciencia de datos 
defina. 
6. Llamado al modelo M.A.T.I.A.S. Credit Score 
o HTTP Request Node – M.A.T.I.A.S.: 
§ 
URL del endpoint de modelo para ese cliente (por ejemplo, 
https://matias.api.aws/crediantioquia/predict). 
§ 
Método POST. 
§ 
Body = vector de features / JSON definido para el modelo. 
o Recibe: 
§ 
score, 
§ 
probabilidad de incumplimiento, 
§ 
segmento de riesgo, 
§ 
condiciones sugeridas. 
7. Aplicación de lógica de negocio adicional (si hace falta) 
o IF / Switch Nodes para: 
§ 
redondear tasas, 
§ 
aplicar límites de monto por política, 
§ 
marcar casos “en revisión manual” si ciertas condiciones se 
cumplen (fraude, inconsistencias, etc.). 
8. Construcción de la respuesta final 
o Function Node: 
§ 
arma la respuesta estándar que se devolverá al sistema del 
cliente (app, core, etc.). 
§ 
Ejemplo: JSON con credit_score, decision_sugerida, tasa, 
monto_maximo, plazo_maximo, etc. 
9. Salida del flujo 
o El Webhook Node de respuesta devuelve el JSON al consumidor.

---

o Si el flujo se activa desde API Gateway de AWS, N8N responde al 
Gateway, y el Gateway a la entidad. 
10. Logging y auditoría 
 
• 
Se pueden usar HTTP Request Nodes adicionales o integraciones para: 
o enviar logs a un endpoint de Akaike en AWS (que guarde en 
S3/DynamoDB), 
o generar registros en una base de datos que lleve el histórico de 
decisiones, 
o disparar notificaciones si hay errores. 
 
10.3 Ventajas concretas de usar N8N como BPM 
1. Flexibilidad extrema por cliente 
o Ajustar nodos, reglas, conectores y condiciones sin tocar el código del 
modelo M.A.T.I.A.S. 
o Cada cliente puede tener: 
§ 
su propio workflow, 
§ 
o una variante del workflow estándar. 
2. Enfoque “low-code” pero enterprise 
o Los ingenieros pueden implementar lógica compleja (HTTP, JS, 
condicionales, loops) sin montar toda la orquestación a mano. 
o Menor tiempo de desarrollo y de cambios. 
3. Visibilidad completa del proceso 
o Desde N8N se ve de forma gráfica: 
§ 
por dónde pasó una solicitud, 
§ 
qué nodos se ejecutaron, 
§ 
en qué paso falló, 
§ 
qué respuesta entregó cada servicio externo. 
o Esto es oro para: 
§ 
soporte, 
§ 
auditoría, 
§ 
pruebas con áreas de riesgo. 
4. Multi-tenant controlado 
o Se pueden agrupar workflows por cliente. 
o Se manejan credenciales por cliente (API keys de burós, tokens, etc.) 
utilizando la gestión de credenciales de N8N + AWS Secrets si se 
integra.

---

10.4 Detalles técnicos para desplegar N8N 
Recomendación de despliegue: 
• 
N8N self-hosted sobre infraestructura de Akaike (no SaaS público), por temas 
de: 
o datos sensibles, 
o cumplimiento regulatorio, 
o control de red y seguridad. 
• 
Opciones: 
1. Docker / Docker Compose en una instancia EC2 de AWS. 
2. ECS Fargate corriendo el contenedor de N8N. 
• 
Base de datos: PostgreSQL (recomendado por N8N) para guardar: 
o definiciones de workflows, 
o credenciales (encriptadas), 
o ejecuciones históricas (al menos metadata). 
• 
Integración con la capa AWS: 
o N8N puede consumir: 
§ 
APIs de M.A.T.I.A.S. en Lambda/ECS, 
§ 
endpoints de logging en API Gateway, 
§ 
servicios internos de las entidades (si se exponen por 
HTTPS/VPN/etc.). 
Seguridad: 
• 
Poner N8N detrás de: 
o un reverse proxy, 
o o un ALB en AWS, 
o con acceso restringido por IP/VPN o SSO (para que solo el equipo de 
Akaike acceda a la consola). 
• 
Manejar las credenciales de burós y entidades: 
o dentro de N8N como “Credentials” encriptadas, 
o o integrando con AWS Secrets Manager. 
 
10.5 Cómo encaja N8N con la idea de “nodos por cliente” 
“la estructura y lógica de consumo de información que llegará a M.A.T.I.A.S. Credit 
Score, debe ser por nodos y por cliente…”

---

Con N8N queda literalmente así: 
• 
Cada nodo de N8N representa un “nodo de información”: 
o Nodo TransUnion, 
o Nodo Experian, 
o Nodo Claro, 
o Nodo datos internos, 
o Nodo M.A.T.I.A.S., 
o Nodo de reglas, etc. 
• 
Para cada cliente: 
o se arma un diagrama de nodos que define la ruta de su evaluación de 
crédito. 
o el nodo de M.A.T.I.A.S. es siempre el núcleo, pero rodeado de nodos 
de fuentes específicas de ese cliente. 
• 
El nodo M.A.T.I.A.S. en N8N: 
o es simplemente un HTTP Request Node apuntando al endpoint del 
modelo de ese cliente, 
o y el payload que se le envía ya viene “cocinadito” por todo el flujo. 
 
10.6 Resumen técnico (N8N + M.A.T.I.A.S.) 
Se debe entender muy claramente lo siguiente: 
1. M.A.T.I.A.S. Credit Score es el motor de scoring / IA (modelo entrenado + API 
en AWS). 
2. N8N es el motor de orquestación/BPM, donde: 
o entra la solicitud del cliente, 
o se consultan las fuentes, 
o se construyen features, 
o se llama a M.A.T.I.A.S., 
o se arma la respuesta final. 
3. Cada cliente de Akaike tiene: 
o su modelo M.A.T.I.A.S. propio, 
o y su workflow N8N propio o específico, 
lo que implementa la personalización “full stack”: 
modelo + flujo + fuentes + reglas de negocio.

---

11. Cumplimiento normativo – Superintendencia Financiera de 
Colombia 
La arquitectura e implementación de M.A.T.I.A.S. Credit Score debe alinearse con 
los lineamientos de la Superintendencia Financiera de Colombia (SFC), en 
particular con: 
• 
Capítulo XXXI – Sistema Integral de Administración de Riesgos (SIAR). 
• 
Reglas de SARC / Riesgo de Crédito de la Circular Básica Contable y 
Financiera. 
• 
Requisitos de gobernanza de modelos, trazabilidad y auditoría. 
A nivel de diseño técnico se deben garantizar, como mínimo, los siguientes puntos: 
 
11.1 Trazabilidad y auditoría de decisiones 
Cada evaluación realizada por M.A.T.I.A.S. (vía API o vía interfaz tipo chat) debe dejar 
un rastro completo: 
• 
Identificadores: 
o id_solicitud, id_solicitante, cliente_id, usuario/analista que hizo la 
consulta (si aplica). 
• 
Información de entrada: 
o Request original recibido por el flujo (variables de entrada). 
o Fuentes consultadas (burós, telcos, core, etc.) y respuestas obtenidas. 
• 
Transformaciones: 
o Versión del pipeline de features usado. 
o Variables finales entregadas al modelo (vector de features). 
• 
Modelo: 
o Identificador y versión del modelo (matias_cliente_X_v1.3). 
o Parámetros relevantes (si aplica). 
• 
Resultado: 
o Score, probabilidad de incumplimiento, segmento de riesgo. 
o Decisión sugerida (Aprobado/Rechazado/Revisión). 
o Condiciones sugeridas (tasa, monto, plazo, garantías). 
• 
Metadatos: 
o Timestamp de la evaluación. 
o Latencia total y latencia por nodo. 
o Usuario/analista que consultó (en el modo copiloto).

---

Esto se debe persistir en repositorios en AWS (por ejemplo, S3 + base 
relacional/NoSQL) con: 
• 
Control de acceso por rol (oficial de riesgo, analista, auditor interno/externo). 
• 
Capacidad de reconstruir ex post cómo se tomó una decisión concreta, 
como exige la SFC. 
 
11.2 Gestión del ciclo de vida de modelos (model risk) 
• 
Cada modelo M.A.T.I.A.S. por cliente debe tener: 
o Documentación técnica y metodológica (desarrollada por Akaike, pero 
referenciable desde el sistema). 
o Versionamiento y registro de fecha de entrada en producción, dataset 
de entrenamiento y validación. 
o Indicadores de performance en producción (KS, Gini, tasa de 
incumplimiento por banda de score, etc.). 
• 
La infraestructura debe soportar: 
o Monitoreo de drift (cambios en distribución de variables y score). 
o Reentrenamientos programados. 
o Posibilidad de mantener dos versiones en paralelo (A/B testing) y hacer 
rollback. 
 
11.3 Seguridad, conﬁdencialidad y segregación 
• 
Todo el tráfico debe ir sobre HTTPS/TLS. 
• 
Gestión de secretos y credenciales (burós, telcos, entidades) con: 
o AWS Secrets Manager / Parameter Store. 
o Credentials encriptadas en N8N. 
• 
Segregación lógica multi-tenant: 
o Datos de cada entidad (cliente) deben estar aislados a nivel de: 
§ 
buckets/prefijos de S3, 
§ 
esquemas/tablas de BD, 
§ 
permisos IAM. 
• 
Acceso a la consola de N8N y a herramientas de monitoreo sólo para usuarios 
autorizados (VPN, IP allowlist, SSO, etc.).

---

11.4 SIAR / SARC – Roles y responsabilidades 
La arquitectura debe permitir que la entidad vigilada pueda demostrar frente a la 
SFC: 
• 
Que tiene control y supervisión sobre: 
o parametrización del motor de decisiones, 
o estrategias de crédito, 
o uso de M.A.T.I.A.S. como herramienta de apoyo (no “caja negra 
incontrolada”). 
• 
Que existe: 
o un responsable interno de riesgo de crédito que aprueba la puesta en 
producción de nuevos modelos, 
o una bitácora de cambios (modelos, reglas, flujos en N8N), 
o evidencia de pruebas y validaciones. 
Esto se traduce técnicamente en: 
• 
Módulos de configuración por cliente auditables (quién cambió qué y 
cuándo). 
• 
Logs de cambios de workflows en N8N (versionado de workflows). 
• 
Reportes descargables para: 
o comités de crédito, 
o comités de riesgo, 
o auditorías. 
 
12. Módulo opcional: M.A.T.I.A.S. Copiloto para Analistas 
(interfaz tipo ChatGPT) 
Para clientes que no cuentan con capacidad tecnológica para integrar APIs o no 
tienen un portal de solicitudes de crédito, M.A.T.I.A.S. incluirá un módulo opcional: 
M.A.T.I.A.S. Copiloto – Interfaz web tipo ChatGPT para analistas de crédito.

---

12.1 Objetivo funcional 
Permitir que el analista de crédito: 
1. Ingrese los datos de un solicitante de forma manual (formulario estructurado). 
2. Pida ayuda a M.A.T.I.A.S. usando lenguaje natural (“analizar crédito 123456”, 
“calcular score para este cliente”, etc.). 
3. Reciba: 
o el score M.A.T.I.A.S. y la recomendación de crédito, 
o explicaciones sobre el caso, 
o respuestas a preguntas puntuales sobre el reporte de buró, niveles de 
mora, productos castigados, etc. 
4. Todo dentro de una sesión de chat que queda guardada como evidencia y 
soporte de la decisión.

---

12.2 Componentes técnicos del módulo Copiloto 
1. Front-end Web (tipo app chat) 
o Aplicación web (HTML/JS/React) con: 
§ 
Panel de chat (como en tus capturas): 
“Hola, soy M.A.T.I.A.S., tu asistente de Credit Scoring con IA…”. 
§ 
Tarjeta de “Análisis de Crédito – Ingresa los datos”: 
§ 
Calificación de buró. 
§ 
Moras > 30 días. 
§ 
% utilización de crédito. 
§ 
Ingresos mensuales (COP). 
§ 
% capacidad de pago. 
§ 
indicador de crédito reestructurado. 
§ 
número de cuentas activas, edad, dependientes, etc. 
§ 
Botón “Calcular Score”. 
§ 
Tarjeta de resultado tipo: 
§ 
“Resultado M.A.T.I.A.S.: 640 – Riesgo Moderado”. 
§ 
Top variables que más impactaron (opcional). 
§ 
Input de texto para prompts libres (parte inferior, estilo 
ChatGPT). 
o Este front no llama directamente a OpenAI ni a los burós. 
Todo pasa por un backend de Akaike. 
2. Backend del Copiloto (servicio de orquestación de chat) 
El backend del Copiloto debe: 
o Recibir mensajes del analista (prompt) y contexto actual del caso (id de 
cliente, datos del solicitante, score calculado, etc.). 
o Orquestar llamadas a: 
§ 
N8N para: 
§ 
ejecutar el flujo de scoring cuando el analista pida 
“calcular score”, 
§ 
recuperar/actualizar datos del caso. 
§ 
Modelo M.A.T.I.A.S. (vía API estándar, el mismo que usan los 
flujos API). 
§ 
LLM de OpenAI (u otro proveedor) para generar respuesta en 
lenguaje natural. 
o Mantener el historial de la conversación: 
§ 
prompts del analista, 
§ 
respuestas de la IA,

---

§ 
decisiones / scores generados. 
o Guardar todo esto en una base de datos para trazabilidad y reportes. 
Arquitectura típica: 
o Backend en Python/FastAPI o Node.js, desplegado en ECS o Lambda. 
o Integración con OpenAI a través de un endpoint interno (las API keys 
nunca se exponen al front). 
3. Integración con N8N 
o Cuando el analista pide algo como: 
§ 
“analizar crédito 123456” 
§ 
“calcular el score con estos datos” 
o El backend del Copiloto: 
§ 
construye el payload estructurado, 
§ 
llama al Webhook de N8N correspondiente al flujo de ese 
cliente, 
§ 
N8N ejecuta los nodos (burós, internos, etc.) y M.A.T.I.A.S., 
§ 
N8N retorna el resultado al backend, 
§ 
el backend actualiza la interfaz (tarjeta con score + detalles), 
§ 
y prepara un prompt de sistema/contexto para el LLM de OpenAI 
con: 
§ 
datos relevantes del caso, 
§ 
resultados del modelo, 
§ 
reglas de negocio. 
De esta forma, el LLM nunca consulta directamente burós; sólo “lee” el 
resumen estructurado que el backend le entrega, cumpliendo con control y 
seguridad. 
4. Módulo de Reportes y Supervisión 
Para cumplir con lo que pides de que un gerente o supervisor pueda ver 
estadísticas: 
o Se construye un módulo de reportes (web o embebido en el mismo 
front) que consuma una base de datos donde se almacenan: 
§ 
Número de consultas por analista, por día/mes. 
§ 
Distribución de scores y decisiones (cuántos 
aprobados/rechazados). 
§ 
Tiempo promedio desde el inicio de la conversación hasta la 
decisión. 
§ 
Principales motivos de rechazo (si se codifican o se extraen de la 
respuesta del modelo/reglas). 
§ 
Volumen por tipo de producto / canal.

---

o Este módulo debe permitir: 
§ 
filtrado por fecha, analista, cliente final, tipo de producto, 
§ 
exportar reportes (CSV/Excel) para comités de riesgo o 
auditoría. 
Todo esto se integra con los logs y almacenamiento que mencionamos en la 
sección de cumplimiento SFC. 
 
12.3 Flujo típico de uso del Copiloto 
1. El analista abre la app de M.A.T.I.A.S. Copiloto y selecciona “Nuevo Chat”. 
2. M.A.T.I.A.S. saluda: 
“Hola, soy M.A.T.I.A.S., tu asistente de Credit Scoring con IA. ¿En qué te 
ayudo?” 
3. El analista: 
o llena el formulario con los datos del solicitante, o 
o escribe: “analizar crédito 123456” (si ya existe una solicitud cargada en 
el sistema de la entidad). 
4. El backend llama a N8N → N8N ejecuta el flujo → M.A.T.I.A.S. calcula score y 
estrategia. 
5. El front muestra: 
o tarjeta de “Análisis de Crédito – Ingresa los datos” (con la info), 
o tarjeta de “Resultado M.A.T.I.A.S.: 640 – Riesgo Moderado”. 
6. El analista puede seguir preguntando en lenguaje natural: 
o “En el reporte de burós, ¿cuántas obligaciones tiene por encima de 
1.000.000?” 
o “¿Ha tenido cartera castigada?” 
o “¿Por qué lo catalogas como riesgo moderado?” 
7. El backend: 
o usa la información estructurada (resumen de buró + variables internas), 
o llama al LLM de OpenAI con un prompt de sistema que obliga a: 
§ 
responder sólo con base en los datos presentes, 
§ 
respetar lineamientos de riesgo de crédito, 
§ 
no inventar datos. 
o devuelve la explicación al analista. 
8. Al final, cuando el analista toma una decisión (ej. “Aprobado por el comité”), 
esa decisión se puede registrar explícitamente en el sistema, asociada a la 
evaluación de M.A.T.I.A.S. y a la conversación.

---

12.4 Normativa y Copiloto 
Para cumplir SFC: 
• 
Cada conversación con el Copiloto es parte del expediente de crédito: 
o queda asociada a la solicitud, 
o se puede consultar en auditorías, 
o muestra qué información usó el analista y qué le respondió la IA. 
• 
El LLM no sustituye la responsabilidad del analista ni del comité: 
o se presenta explícitamente como una herramienta de apoyo, 
o las políticas internas de la entidad deben definir cómo usar sus 
recomendaciones. 
• 
Toda la data sensible se procesa y se almacena dentro de la infraestructura 
controlada de Akaike/cliente; el LLM sólo recibe resúmenes/atributos 
necesarios, no datos de identificación innecesarios.