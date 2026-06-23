Documento de Arquitectura de Seguridad 
– M.A.T.I.A.S. COPILOT (LLM Zero-PII) 
 
1. Objetivo 
 
Diseñar e implementar una arquitectura donde: 
1. El LLM (M.A.T.I.A.S. COPILOT) no recibe, no almacena y no infiere PII 
(nombre, cédula, dirección, teléfonos) ni detalle crudo del buró (obligaciones, 
entidades, números de cuenta, montos exactos, fechas exactas). 
2. El analista autorizado obtiene una experiencia “wow”: respuestas conversacionales 
que incluyen datos exactos y referencias del buró, pero esas cifras/datos exactos 
se insertan fuera del LLM (render seguro). 
3. Se reduzca el riesgo de fuga por prompt injection, errores del modelo, logging y/o 
integraciones inseguras, siguiendo prácticas recomendadas para apps con LLM 
(OWASP Top 10 LLM) y gestión de riesgos de IA (NIST AI RMF).   
 
2. Alcance y definiciones 
 
2.1 Datos sensibles (prohibidos para el LLM) 
• 
PII: nombre completo, documento (cédula/NIT), fecha nacimiento, teléfonos, 
emails, direcciones. 
• 
Buró crudo: XML/JSON/estructura completa del reporte, detalle de obligaciones, 
identificadores de cuentas, entidades reportantes si se considera sensible, historial 
detallado con montos/fechas exactas. 
• 
Identificadores persistentes: customer_id del cliente si es reversible a identidad 
sin control. 
 
2.2 Datos permitidos para el LLM (contexto sanitizado)

---

• 
Features/atributos: valores agregados o categorizados (rangos/bins) y métricas no 
identificables. 
• 
Resultados analíticos: score, PD band, reason codes, reglas disparadas, 
recomendaciones de condiciones. 
• 
Esquema disponible (metadatos): lista de campos que existen para placeholders, 
sin valores. 
 
Principio de minimización: “El LLM solo necesita lo mínimo para 
razonar; lo exacto lo pone el renderer”. 
 
3. Amenazas y modelo de riesgo (resumen) 
 
Las amenazas más relevantes en aplicaciones con LLM incluyen: 
1. Prompt Injection (LLM01): el usuario intenta que el sistema “revele” datos o 
ignore instrucciones.   
2. Sensitive Information Disclosure (LLM02): el modelo o la app termina 
exponiendo información sensible en la salida.   
3. Insecure Output Handling (LLM02/LLMxx según versión): el texto del LLM se 
usa sin validación, provocando exfiltración o acciones no autorizadas.   
4. Riesgos de gobernanza/privacidad: uso indebido de datos, retención, auditoría 
insuficiente. NIST AI RMF enfatiza privacidad/seguridad de datos y controles de 
gestión.   
 
Respuesta de diseño: tratar al LLM como componente “no confiable” para datos sensibles; 
diseñar un sistema donde, incluso si el LLM es manipulado, no tenga acceso al buró ni PII 
(principio de least privilege y segregation of duties). 
 
4. Arquitectura objetivo (Zero-PII LLM + 
respuesta exacta) 
 
4.1 Componentes (alto nivel)

---

1. UI del Analista (Web/App) 
o Búsqueda/selección del cliente fuera del chat (selector). 
o Panel “visor” (si aplica) para detalle con controles. 
2. API Gateway + AuthN/AuthZ (Tenant-aware) 
o Autenticación (SSO/OIDC) y autorización por roles (RBAC/ABAC) y por 
entidad (tenant). 
3. Bureau Connector Service (AWS Secure Server) 
o Realiza la consulta al buró con credenciales y controles de red. 
o (Tu idea base se mantiene) Se recibe respuesta y se parsea. 
4. Bureau Vault (Datos sensibles) 
o Almacén cifrado (KMS) con partición por tenant. 
o Contiene: 
▪ 
Raw (si es necesario) con acceso ultra-restringido. 
▪ 
Parsed exacto (campos exactos). 
▪ 
Feature store (agregados / bins). 
5. Copilot Orchestrator (Servicio de Orquestación) 
o Prepara contexto sanitizado para el LLM. 
o Ejecuta DLP en entrada/salida. 
o Gestiona plantillas y placeholders. 
o Realiza auditoría (sin payload sensible). 
6. LLM Runtime (M.A.T.I.A.S. COPILOT) 
o Solo recibe CopilotContext sanitizado. 
o Genera respuesta en formato plantilla (placeholders) + “plan de datos”. 
7. Secure Renderer (backend o UI de confianza) 
o Resuelve placeholders solicitando al Vault solo campos permitidos por rol. 
o Inserta datos exactos (montos, fechas, identificaciones) y produce la 
respuesta final al analista. 
 
4.2 Flujo de datos seguro (secuencia) 
 
Fase A: Consulta y almacenamiento 
1. UI → API: “Consultar buró” con identificador (cédula) solo hacia backend. 
2. Bureau Connector → Buró: petición (TLS) y recibe respuesta. 
3. Parser → Vault: 
o Guarda “exacto parseado” + features + hash/index para búsqueda. 
4. Auditoría: registra who/when/tenant/case_id (sin raw). 
 
Fase B: Conversación del analista sin exponer PII al LLM

---

Patrón recomendado: “Case-bound chat” 
1. Analista selecciona cliente en UI (o pega cédula en un campo de búsqueda no chat). 
2. Backend resuelve identidad y permisos → emite case_id y abre sesión de chat atada 
al caso. 
3. Cuando analista pregunta en chat, la solicitud llega al Orchestrator: 
o Extrae datos del Vault 
o Construye contexto sanitizado (no PII) 
4. Orchestrator → LLM: 
o Envía features/bins/score/reason codes + schema de placeholders. 
5. LLM devuelve: 
o Plantilla con placeholders (sin PII) 
o Data plan: lista de campos a renderizar y formato requerido 
6. Renderer: 
o Valida que los placeholders estén en allowlist según rol/política. 
o Consulta Vault por esos campos exactos. 
o Hace merge (formato moneda/fechas) y devuelve respuesta final al analista. 
 
  Resultado: el analista ve datos exactos, pero el LLM jamás los recibe. 
 
5. Contratos técnicos: “CopilotContext”, 
Plantilla y Data Plan 
 
5.1  
CopilotContext 
 (solo sanitizado) 
 
Campos típicos: 
• 
tenant_id, case_id, analyst_role 
• 
score, risk_band, pd_band, decision_recommendation

---

• 
reason_codes[] (texto controlado, no libre) 
• 
features: 
o max_dpd_24m_bin: {0, 1-30, 31-60, 61-90, 90+} 
o utilization_bin: {0-20, 20-40, 40-60, 60-80, 80-100} 
o inquiries_6m_bin: {0, 1-2, 3-5, 6+} 
o open_trades_bin: {0, 1-2, 3-5, 6-10, 10+} 
• 
policy_results[]: reglas disparadas (IDs o nombres internos) 
• 
available_placeholders_schema: lista de campos disponibles sin valores 
o Ej: cliente.nombre, cliente.doc_tipo, cliente.doc_numero, obligaciones[ 
].saldo, etc. 
 
El esquema permite al LLM “saber qué se puede pedir” sin ver el dato. 
 
5.2 Plantilla (output del LLM) 
 
El LLM debe responder siempre usando placeholders para cualquier dato sensible o 
exacto, por ejemplo: 
 
“El cliente {{cliente.nombre}} con documento {{cliente.doc_tipo}} 
{{cliente.doc_numero}} presenta una mora máxima de {{mora.max_dias}} 
días en {{mora.periodo}}…” 
 
5.3 Data Plan (output del LLM) 
 
Objeto estructurado: 
• 
placeholders[]: lista de campos a rellenar 
• 
format_rules: moneda, fecha, redondeo 
• 
evidence_links: opcional, referencias internas de auditoría (IDs), no PII

---

6. Controles de seguridad críticos (market 
best practices + ISO 27001/27002) 
 
6.1 Controles “anti fuga” específicos para LLM 
 
Alineados a OWASP Top 10 para LLM Apps: 
1. Mitigación de Prompt Injection (LLM01) 
o Chat case-bound: el usuario no “elige” el caso por texto en prompt. 
o El LLM no tiene herramientas con acceso a PII. 
o Separar instrucciones vs datos; nunca pasar documentos crudos al modelo.   
2. Prevención de Sensitive Info Disclosure / Insecure Output Handling 
o Validación de salida: si el LLM “imprime” números tipo cédula o patrones 
sensibles, bloquear y re-generar en modo plantilla.   
3. DLP Gateway (entrada y salida) 
o Bloqueo/redacción de: 
▪ 
IDs (cédula, NIT), emails, teléfonos, direcciones 
▪ 
XML/JSON del buró o textos masivos 
o ISO/IEC 27002 incluye control explícito de Data Leakage Prevention 
(8.12) como práctica recomendada.   
4. Allowlist estricta de placeholders 
o El renderer solo reemplaza placeholders permitidos por rol/tenant. 
o Cualquier placeholder no permitido → se deja vacío o se reemplaza por “No 
autorizado”. 
 
6.2 Controles de gestión y técnicos alineados a ISO/IEC 
27001:2022 (Anexo A) 
 
ISO 27001:2022 reorganiza controles en dominios organizacionales, de personas, físicos y 
tecnológicos; el enfoque clave aquí es protección, acceso, monitoreo y prevención de fuga.   
 
Mapa de controles recomendados (nivel práctico):

---

A) Control de acceso y privilegios mínimos (Tecnológicos/Organizacionales) 
• 
RBAC/ABAC por tenant y por rol (analista, supervisor, auditor, soporte). 
• 
“Need-to-know” para vistas: resumen vs detalle del buró. 
• 
Sesiones case-bound y expiración. 
 
B) Protección de datos (Tecnológicos) 
• 
Cifrado en reposo (KMS) y en tránsito. 
• 
Vault con tablas/particiones por tenant. 
• 
Índices por hash (documento) para búsqueda sin exponer valores en logs. 
 
C) Registro y monitoreo (Tecnológicos/Organizacionales) 
• 
Auditoría de eventos: quién consultó, a qué case_id, cuándo, IP, acción. 
• 
Logs sin payload sensible (ni prompts renderizados). 
• 
Alertas DLP. 
 
D) Gestión de proveedores y servicios (Organizacionales) 
• 
Si el LLM es tercero/externo: evaluación de riesgos, acuerdos, controles de 
retención. 
• 
NIST AI RMF refuerza gobernanza y accountability para sistemas de IA.   
 
E) Gestión de incidentes (Organizacionales) 
• 
Playbooks: detección de intento de pegar buró en chat, bloqueo, notificación. 
• 
Trazabilidad para auditoría. 
 
7. Políticas operativas (para auditoría y 
cumplimiento)

---

7.1 Política de “No-PII-to-LLM” 
• 
Prohibido enviar PII o buró crudo al LLM. 
• 
El canal oficial para detalles exactos es el renderer y/o visor seguro. 
 
7.2 Retención y minimización 
• 
Retener raw del buró solo si es estrictamente necesario (y con controles reforzados). 
• 
Preferir guardar structured + features para scoring y explicación. 
 
7.3 Separación de entornos 
• 
Dev/QA: datos sintéticos o anonimizados. 
• 
Producción: controles completos, llaves separadas, accesos segregados. 
 
8. Recomendaciones AWS (implementación 
típica) 
 
(Sin casarte con servicios específicos, pero como guía) 
• 
API Gateway / ALB + WAF 
• 
Cognito/OIDC (o IdP corporativo) para SSO 
• 
Secrets Manager para credenciales buró 
• 
KMS para cifrado y llaves por tenant si aplica 
• 
RDS/PostgreSQL o DynamoDB para Vault (según modelo) 
• 
CloudWatch + SIEM para auditoría y alertas 
• 
Servicio Orchestrator (ECS/EKS/Lambda) con DLP y validadores

---

9. Pruebas y validación de seguridad (qué 
auditar) 
1. Prueba de exfiltración: prompts maliciosos intentando obtener cédula/nombre. 
2. Prueba de pegado de buró: bloquear XML/JSON y strings largos. 
3. Prueba de fuga por salida: el modelo “alucina” números → validador debe 
impedir. 
4. Prueba multi-tenant: un analista nunca puede acceder a otro tenant/caso. 
5. Revisión de logs: confirmar que no se guarda PII ni prompts renderizados. 
 
OWASP Top 10 para LLM Apps sirve como checklist de amenazas y pruebas para este tipo 
de sistemas.   
 
10. Resumen ejecutivo 
 
La arquitectura propuesta logra el objetivo con un patrón robusto: 
• 
El LLM produce lenguaje y estructura (plantilla + plan de datos), pero no ve 
PII. 
• 
El renderer, bajo controles de acceso y DLP, inserta los datos exactos desde un 
Vault cifrado. 
• 
Esto reduce drásticamente el riesgo de fuga por prompt injection y disclosure, y se 
alinea con prácticas de prevención de fuga (DLP) y controles de un ISMS bajo 
ISO 27001/27002.   
 
Siguiente paso (para dejarlo “implementable”) 
 
Si me dices si hoy estás usando RDS o DynamoDB para el Vault y si el LLM corre 
externo o dentro de AWS, te entrego: 
• 
Diagrama por componentes (con límites de confianza) 
• 
Especificación formal de CopilotContext, Plantilla y Data Plan 
• 
Matriz de permisos por rol + allowlist de placeholders

---

• 
Reglas DLP mínimas (expresiones/patrones y reglas de tamaño) 
 
(Con esto tu equipo dev lo puede construir tal cual.)