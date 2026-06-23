M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 1 de 18 
M.A.T.I.A.S. 
API REST — Documentación Técnica de Integración 
Modelo Analítico Transformador en Inteligencias Artificiales de Scoring 
Akaike Credit Risk Solutions S.A.S. 
NIT 901.943.344-3   ·   Bogotá, Colombia 
Versión del documento: v1.0 
Versión del API: v1 
Fecha: 15 de abril de 2026 
Estado: Producción 
Documento confidencial — uso exclusivo de clientes autorizados

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 2 de 18 
Tabla de Contenido

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 3 de 18 
1. Introducción 
M.A.T.I.A.S. es el motor analítico de scoring crediticio desarrollado por Akaike Credit Risk 
Solutions. Expone una API REST que permite a entidades crediticias (cooperativas, fondos de 
empleados, fintechs, bancos y otras entidades del sector solidario y financiero) evaluar 
solicitudes de crédito en tiempo real. 
La API entrega, a partir de las variables del solicitante: 
• 
M.A.T.I.A.S. Credit Score (escala 0–1000) 
• 
Decisión automatizada: APPROVED / REJECTED / MANUAL_REVIEW 
• 
Monto máximo aprobado y plazo máximo en meses 
• 
Tasa de interés sugerida (Efectiva Anual y Nominal Mensual) 
• 
Garantías y colaterales recomendados 
• 
Probabilidad de Default (PD) y Pérdida Esperada (EL) a 12 meses 
 
El API está diseñado bajo principios REST, responde en formato JSON, opera bajo 
HTTPS/TLS 1.3 y cumple con arquitectura Zero-PII: los modelos de Machine Learning nunca 
reciben información personal identificable en claro. 
 
2. Conceptos Clave 
Término 
Descripción 
Evaluación 
Operación atómica que recibe variables del solicitante y devuelve un 
resultado de scoring + decisión. 
evaluation_id 
Identificador único (UUID v4) de cada evaluación. Inmutable y trazable. 
Score 
Valor entero entre 0 y 1000 (a mayor score, menor riesgo). 
PD 
Probabilidad de Default a 12 meses (0.0 – 1.0). 
EL 
Pérdida Esperada (Expected Loss) en moneda local. 
Decisión 
APPROVED · REJECTED · MANUAL_REVIEW 
Producto 
CONSUMO · LIBRANZA · MICROCREDITO · VIVIENDA · COMERCIAL 
Tenant 
Entidad cliente que consume el API (identificada por su API Key). 
 
3. Entornos y URL Base

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 4 de 18 
Entorno 
URL Base 
Uso 
Sandbox 
https://sandbox.api.akaike.co/matias/v1 
Pruebas e integración. Datos 
sintéticos. 
Producción 
https://api.akaike.co/matias/v1 
Tráfico real con datos 
productivos. 
 
Importante: todas las llamadas deben realizarse sobre HTTPS. Conexiones HTTP serán 
rechazadas con 426 Upgrade Required. 
 
4. Autenticación 
M.A.T.I.A.S. soporta dos esquemas de autenticación, que pueden usarse de forma combinada. 
4.1 API Key (obligatoria) 
Cada tenant recibe una API Key única, enviada en el header HTTP: 
X-Akaike-Api-Key: ak_live_8f3a92d1c47b6e0a5f1b9d2e3c8a7f4b 
 
• 
Llaves de sandbox: prefijo ak_test_ 
• 
Llaves de producción: prefijo ak_live_ 
• 
Rotación cada 12 meses (notificación 30 días antes) 
4.2 Bearer Token (JWT) — opcional, recomendado para Enterprise 
Para clientes con múltiples usuarios, M.A.T.I.A.S. emite un JWT de corta duración (15 minutos) 
vía OAuth2 Client Credentials. 
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9... 
 
5. Convenciones Generales 
5.1 Formato 
• 
Content-Type: application/json; charset=utf-8 
• 
Accept: application/json 
• 
Encoding: UTF-8 
• 
Timezone: UTC, formato ISO 8601 (2026-04-15T14:30:00Z) 
• 
Moneda por defecto: COP. Configurable: USD, MXN, EUR, etc.

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 5 de 18 
5.2 Headers obligatorios 
Header 
Ejemplo 
Descripción 
X-Akaike-Api-Key 
ak_live_... 
Llave de autenticación 
Content-Type 
application/json 
Tipo de contenido 
X-Request-ID 
req-7f2e3a91-... 
UUID generado por el cliente para 
trazabilidad 
X-Idempotency-Key 
idem-2026-04-15-... 
Garantiza idempotencia en POST 
5.3 Paginación 
Endpoints de listado usan paginación basada en cursor: 
GET /evaluations?limit=50&cursor=eyJpZCI6... 
 
Respuesta: 
{ 
  "data": [ ... ], 
  "pagination": { 
    "next_cursor": "eyJpZCI6...", 
    "has_more": true, 
    "limit": 50 
  } 
} 
 
6. Endpoints 
6.1 Health Check 
Verifica disponibilidad del servicio. No requiere autenticación. 
GET /health 
 
Response 200: 
{ 
  "status": "ok", 
  "version": "1.4.2", 
  "timestamp": "2026-04-15T14:30:00Z", 
  "uptime_seconds": 1842933 
} 
6.2 Generar Token de Sesión (OAuth2)

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 6 de 18 
POST /auth/token 
 
Request Body: 
{ 
  "grant_type": "client_credentials", 
  "client_id": "akaike_client_xxxxxxxx", 
  "client_secret": "akaike_secret_xxxxxxxxxxxxxxxx", 
  "scope": "evaluations:read evaluations:write" 
} 
 
Response 200: 
{ 
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...", 
  "token_type": "Bearer", 
  "expires_in": 900, 
  "scope": "evaluations:read evaluations:write" 
} 
6.3 Evaluación Crediticia (Scoring + Decisión) 
Endpoint principal del API. Recibe las variables del solicitante y devuelve el resultado de la 
evaluación crediticia en tiempo real. 
POST /evaluations 
 
Request Body 
{ 
  "request_metadata": { 
    "request_id": "req-7f2e3a91-4c2b-4a8e-9b1f-2d3c4e5f6a7b", 
    "channel": "WEB", 
    "branch_code": "BOG-001", 
    "agent_id": "AG-2045" 
  }, 
  "applicant": { 
    "document_type": "CC", 
    "document_number": "1020304050", 
    "first_name": "JUAN CARLOS", 
    "last_name": "RODRIGUEZ MARTINEZ", 
    "birth_date": "1988-03-15", 
    "gender": "M", 
    "marital_status": "MARRIED", 
    "nationality": "CO", 
    "email": "juan.rodriguez@example.com", 
    "phone": "+573001234567" 
  }, 
  "demographics": { 
    "education_level": "UNIVERSITY", 
    "dependents": 2,

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 7 de 18 
    "city_residence": "BOGOTA", 
    "department_residence": "CUNDINAMARCA", 
    "country_residence": "CO", 
    "years_in_current_address": 5, 
    "housing_type": "OWNED_PAID", 
    "vehicle_owned": true 
  }, 
  "employment": { 
    "employment_type": "EMPLOYEE", 
    "occupation": "INGENIERO", 
    "employer_name": "EMPRESA EJEMPLO S.A.S.", 
    "employer_sector": "TECHNOLOGY", 
    "years_in_current_job": 4, 
    "contract_type": "INDEFINITE" 
  }, 
  "financials": { 
    "monthly_income": 8500000, 
    "additional_income": 1200000, 
    "monthly_expenses": 4300000, 
    "current_debt_total": 18000000, 
    "current_debt_monthly_payment": 950000, 
    "savings_balance": 12000000, 
    "currency": "COP" 
  }, 
  "credit_request": { 
    "product_type": "CONSUMO", 
    "requested_amount": 25000000, 
    "requested_term_months": 36, 
    "purpose": "REMODELACION_VIVIENDA", 
    "currency": "COP" 
  }, 
  "bureau_data": { 
    "include_bureau": true, 
    "bureau_provider": "DATACREDITO", 
    "consent_id": "consent-2026-04-15-abc123" 
  }, 
  "model_config": { 
    "model_version": "matias-v3.2-cooperativas", 
    "explainability": true, 
    "policy_set": "POL-COOP-2026-Q2" 
  } 
} 
 
Response 200 — Evaluación aprobada 
{ 
  "evaluation_id": "eval-9b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e", 
  "timestamp": "2026-04-15T14:30:42Z", 
  "model_version": "matias-v3.2-cooperativas", 
  "status": "COMPLETED", 
  "result": { 
    "decision": "APPROVED", 
    "matias_credit_score": 782, 
    "score_band": "A", 
    "probability_of_default": 0.0234, 
    "expected_loss": 187200, 
    "approved_amount": 22000000, 
    "approved_term_months": 36,

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 8 de 18 
    "interest_rate_ea": 0.1850, 
    "interest_rate_nm": 0.01428, 
    "monthly_payment": 794500, 
    "currency": "COP", 
    "collateral": { 
      "required": false, 
      "type": null, 
      "coverage_ratio": null 
    }, 
    "guarantees": [ 
      { "type": "PAGARE_EN_BLANCO", "mandatory": true }, 
      { "type": "CODEUDOR", "mandatory": false, "recommended": true } 
    ] 
  }, 
  "risk_factors": { 
    "positive": [ 
      { "factor": "STABLE_EMPLOYMENT", "weight": 0.18 }, 
      { "factor": "LOW_DEBT_TO_INCOME", "weight": 0.22 }, 
      { "factor": "CLEAN_BUREAU_HISTORY", "weight": 0.31 } 
    ], 
    "negative": [ 
      { "factor": "HIGH_REQUESTED_AMOUNT_VS_INCOME", "weight": -0.08 } 
    ] 
  }, 
  "policy_evaluation": { 
    "policy_set": "POL-COOP-2026-Q2", 
    "rules_passed": 14, 
    "rules_failed": 0, 
    "rules_warning": 1 
  }, 
  "recommendations": { 
    "suggested_action": "DESEMBOLSAR", 
    "review_required": false, 
    "notes": "Solicitante con perfil solido. Se sugiere monto inferior al solicitado por 
capacidad de pago." 
  }, 
  "audit": { 
    "request_id": "req-7f2e3a91-4c2b-4a8e-9b1f-2d3c4e5f6a7b", 
    "tenant_id": "tenant-akaike-coop-001", 
    "processing_time_ms": 287 
  } 
} 
 
Response 200 — Decisión de rechazo 
{ 
  "evaluation_id": "eval-1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d", 
  "result": { 
    "decision": "REJECTED", 
    "matias_credit_score": 412, 
    "score_band": "E", 
    "probability_of_default": 0.2841, 
    "approved_amount": 0, 
    "rejection_reasons": [ 
      { "code": "R-101", "description": "Capacidad de pago insuficiente" }, 
      { "code": "R-205", "description": "Reportes negativos vigentes en buro" } 
    ] 
  }

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 9 de 18 
} 
 
Response 200 — Revisión manual 
{ 
  "evaluation_id": "eval-2b3c4d5e-...", 
  "result": { 
    "decision": "MANUAL_REVIEW", 
    "matias_credit_score": 615, 
    "score_band": "C", 
    "review_reasons": [ 
      { "code": "M-301", "description": "Score en zona gris, requiere comite" }, 
      { "code": "M-402", "description": "Monto solicitado excede politica automatica" } 
    ], 
    "suggested_committee_level": "COMITE_REGIONAL" 
  } 
} 
6.4 Consulta de Evaluación por ID 
GET /evaluations/{evaluation_id} 
 
Path Parameters: 
Parámetro 
Tipo 
Descripción 
evaluation_id 
string (UUID) 
ID retornado por POST /evaluations 
 
Response 404: 
{ 
  "error": { 
    "code": "EVALUATION_NOT_FOUND", 
    "message": "No existe evaluacion con ID eval-xxx para el tenant actual.", 
    "request_id": "req-..." 
  } 
} 
6.5 Re-evaluación con nuevas variables 
Permite recalcular una evaluación existente cambiando uno o varios parámetros (monto, plazo, 
garantías). Útil para simulaciones. 
POST /evaluations/{evaluation_id}/reevaluate 
 
Request Body: 
{

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 10 de 18 
  "overrides": { 
    "credit_request": { 
      "requested_amount": 18000000, 
      "requested_term_months": 24 
    } 
  } 
} 
 
Response 200: nueva evaluación con referencia al original. 
{ 
  "evaluation_id": "eval-new-...", 
  "parent_evaluation_id": "eval-9b2c3d4e-...", 
  "result": { ... } 
} 
6.6 Listado de Evaluaciones 
GET /evaluations?from=2026-04-01&to=2026-04-15&decision=APPROVED&limit=50 
 
Query Parameters: 
Parámetro 
Tipo 
Descripción 
from 
date 
Fecha inicial (YYYY-MM-DD) 
to 
date 
Fecha final (YYYY-MM-DD) 
decision 
enum 
APPROVED · REJECTED · MANUAL_REVIEW 
product_type 
enum 
CONSUMO · LIBRANZA · etc. 
min_score 
int 
Score mínimo 
max_score 
int 
Score máximo 
limit 
int 
1–200 (default 50) 
cursor 
string 
Cursor de paginación 
6.7 Webhook de Notificación Asíncrona 
Para evaluaciones con procesamiento extendido (>2 segundos, p. ej. consulta a múltiples 
burós), M.A.T.I.A.S. notifica el resultado a un webhook configurado por el cliente. 
Configuración: Panel administrativo → Webhooks → Endpoint URL. 
Payload entregado a tu webhook: 
POST https://tu-dominio.com/webhooks/matias 
X-Akaike-Signature: sha256=8f3a92d1c47b6e0a... 
Content-Type: application/json

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 11 de 18 
 
{ 
  "event": "evaluation.completed", 
  "evaluation_id": "eval-...", 
  "timestamp": "2026-04-15T14:30:42Z", 
  "result": { ... } 
} 
 
Verificación de firma (HMAC-SHA256): 
import hmac, hashlib 
expected = hmac.new( 
    key=WEBHOOK_SECRET.encode(), 
    msg=request.body, 
    digestmod=hashlib.sha256 
).hexdigest() 
assert hmac.compare_digest(f"sha256={expected}", request.headers["X-Akaike-Signature"]) 
 
7. Esquemas de Datos 
7.1 Catálogo: document_type 
Código 
Descripción 
CC 
Cédula de Ciudadanía (Colombia) 
CE 
Cédula de Extranjería 
TI 
Tarjeta de Identidad 
PA 
Pasaporte 
NIT 
NIT (persona jurídica) 
RUT 
RUT 
DNI 
DNI (otros países) 
7.2 Catálogo: education_level 
PRIMARY · SECONDARY · TECHNICAL · TECHNOLOGICAL · UNIVERSITY · 
POSTGRADUATE · NONE 
7.3 Catálogo: housing_type 
OWNED_PAID · OWNED_MORTGAGE · RENTED · FAMILY · OTHER 
7.4 Catálogo: employment_type

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 12 de 18 
EMPLOYEE · SELF_EMPLOYED · BUSINESS_OWNER · RETIRED · STUDENT · 
UNEMPLOYED 
7.5 Catálogo: product_type 
CONSUMO · LIBRANZA · MICROCREDITO · VIVIENDA · COMERCIAL · ROTATIVO · 
TARJETA_CREDITO 
7.6 Bandas de Score 
Banda 
Rango 
Riesgo 
A+ 
850–1000 
Muy bajo 
A 
750–849 
Bajo 
B 
650–749 
Moderado 
C 
550–649 
Medio 
D 
450–549 
Alto 
E 
0–449 
Muy alto 
 
8. Códigos de Error 
Todos los errores siguen el formato: 
{ 
  "error": { 
    "code": "STRING_CODE", 
    "message": "Descripcion legible del error.", 
    "details": [ ... ], 
    "request_id": "req-..." 
  } 
} 
8.1 Errores HTTP estándar 
HTTP 
Código interno 
Descripción 
400 
INVALID_REQUEST 
Body malformado o variables faltantes 
401 
UNAUTHORIZED 
API Key ausente o inválida 
403 
FORBIDDEN 
Sin permisos sobre el recurso 
404 
NOT_FOUND 
Recurso no existe 
409 
CONFLICT 
Idempotency key reutilizada con body distinto

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 13 de 18 
HTTP 
Código interno 
Descripción 
422 
VALIDATION_ERROR 
Datos válidos sintácticamente pero inválidos 
semánticamente 
429 
RATE_LIMIT_EXCEEDED 
Límite de peticiones superado 
500 
INTERNAL_ERROR 
Error interno (reintentar) 
503 
SERVICE_UNAVAILABLE 
Mantenimiento o sobrecarga 
8.2 Errores de negocio 
Código 
Descripción 
BUREAU_TIMEOUT 
El buró no respondió a tiempo 
BUREAU_CONSENT_INVALID 
El consent_id no es válido o expiró 
MODEL_VERSION_NOT_FOUND 
La versión del modelo solicitada no existe 
POLICY_SET_NOT_FOUND 
El set de políticas no existe 
INSUFFICIENT_DATA 
Variables insuficientes para evaluar 
DOCUMENT_FORMAT_INVALID 
Formato de documento incorrecto 
 
Ejemplo de error de validación: 
{ 
  "error": { 
    "code": "VALIDATION_ERROR", 
    "message": "El campo 'monthly_income' debe ser mayor a 0.", 
    "details": [ 
      { 
        "field": "financials.monthly_income", 
        "issue": "must_be_positive", 
        "received": -1000 
      } 
    ], 
    "request_id": "req-7f2e3a91-..." 
  } 
} 
 
9. Rate Limiting 
Cada API Key tiene límites por defecto, configurables por plan: 
Plan 
Requests/segundo 
Requests/día 
Starter 
10 
5.000

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 14 de 18 
Plan 
Requests/segundo 
Requests/día 
Scale 
50 
50.000 
Corporate 
200 
250.000 
Enterprise 
Configurable 
Configurable 
 
Headers de respuesta: 
X-RateLimit-Limit: 50 
X-RateLimit-Remaining: 47 
X-RateLimit-Reset: 1745335842 
 
Al exceder el límite: 429 Too Many Requests + header Retry-After: 12. 
 
10. Seguridad y Privacidad (Zero-PII) 
M.A.T.I.A.S. opera bajo arquitectura Zero-PII: 
• 
Toda PII (nombres, documentos, contactos) se tokeniza al ingresar al sistema. 
• 
Los modelos de ML nunca procesan PII en claro; trabajan con vectores numéricos y 
tokens hash. 
• 
Datos en reposo cifrados con AES-256-GCM; en tránsito con TLS 1.3. 
• 
Llaves gestionadas en AWS KMS con rotación automática. 
• 
Acceso auditado bajo logs inmutables (CloudTrail + S3 Object Lock). 
• 
Cumplimiento: Ley 1581 de 2012 (Colombia), GDPR (UE), SOC 2 Type II (en proceso). 
10.1 Buenas prácticas para el cliente 
• 
Nunca envíes la API Key desde el frontend; úsala desde tu backend. 
• 
Almacena las llaves en gestores de secretos (AWS Secrets Manager, HashiCorp Vault, 
Azure Key Vault). 
• 
Usa X-Idempotency-Key para evitar duplicados en reintentos. 
• 
Implementa verificación de firma HMAC-SHA256 en webhooks. 
• 
Configura IP whitelisting desde el panel administrativo. 
 
11. Ejemplos de Integración 
11.1 cURL

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 15 de 18 
curl -X POST https://api.akaike.co/matias/v1/evaluations \ 
  -H "X-Akaike-Api-Key: ak_live_xxxxxxxxxxxxxxxx" \ 
  -H "Content-Type: application/json" \ 
  -H "X-Request-ID: req-$(uuidgen)" \ 
  -d @evaluation_request.json 
11.2 Python (requests) 
import os 
import requests 
import uuid 
 
API_BASE = "https://api.akaike.co/matias/v1" 
API_KEY = os.environ["AKAIKE_API_KEY"] 
 
payload = { 
    "applicant": { 
        "document_type": "CC", 
        "document_number": "1020304050", 
        "first_name": "JUAN CARLOS", 
        "last_name": "RODRIGUEZ MARTINEZ", 
        "birth_date": "1988-03-15" 
    }, 
    "demographics": { 
        "education_level": "UNIVERSITY", 
        "housing_type": "OWNED_PAID", 
        "dependents": 2 
    }, 
    "employment": { 
        "employment_type": "EMPLOYEE", 
        "years_in_current_job": 4 
    }, 
    "financials": { 
        "monthly_income": 8500000, 
        "monthly_expenses": 4300000, 
        "current_debt_monthly_payment": 950000, 
        "currency": "COP" 
    }, 
    "credit_request": { 
        "product_type": "CONSUMO", 
        "requested_amount": 25000000, 
        "requested_term_months": 36, 
        "currency": "COP" 
    } 
} 
 
response = requests.post( 
    f"{API_BASE}/evaluations", 
    json=payload, 
    headers={ 
        "X-Akaike-Api-Key": API_KEY, 
        "X-Request-ID": f"req-{uuid.uuid4()}", 
        "Content-Type": "application/json" 
    }, 
    timeout=10 
)

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 16 de 18 
response.raise_for_status() 
result = response.json() 
 
print(f"Decision: {result['result']['decision']}") 
print(f"Score: {result['result']['matias_credit_score']}") 
print(f"Monto aprobado: ${result['result']['approved_amount']:,}") 
print(f"Tasa E.A.: {result['result']['interest_rate_ea']*100:.2f}%") 
11.3 Node.js / TypeScript (axios) 
import axios from "axios"; 
import { v4 as uuidv4 } from "uuid"; 
 
const API_BASE = "https://api.akaike.co/matias/v1"; 
const API_KEY = process.env.AKAIKE_API_KEY!; 
 
interface EvaluationResult { 
  evaluation_id: string; 
  result: { 
    decision: "APPROVED" | "REJECTED" | "MANUAL_REVIEW"; 
    matias_credit_score: number; 
    approved_amount: number; 
    approved_term_months: number; 
    interest_rate_ea: number; 
  }; 
} 
 
async function evaluateCredit(payload: object): Promise<EvaluationResult> { 
  const { data } = await axios.post<EvaluationResult>( 
    `${API_BASE}/evaluations`, 
    payload, 
    { 
      headers: { 
        "X-Akaike-Api-Key": API_KEY, 
        "X-Request-ID": `req-${uuidv4()}`, 
        "Content-Type": "application/json" 
      }, 
      timeout: 10000 
    } 
  ); 
  return data; 
} 
11.4 n8n 
• 
Nodo: HTTP Request 
• 
Method: POST 
• 
URL: https://api.akaike.co/matias/v1/evaluations 
• 
Authentication: Header Auth → Name: X-Akaike-Api-Key → Value: 
{{$credentials.akaikeApiKey}} 
• 
Body Content Type: JSON 
• 
Body: mapeado desde nodos previos

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 17 de 18 
 
12. Versionado y Deprecación 
• 
El API sigue versionado en URL (/v1, /v2, ...). 
• 
Cambios no breaking (nuevos campos, nuevos endpoints) se publican sin nueva 
versión. 
• 
Cambios breaking generan nueva versión con soporte mínimo de 18 meses a la versión 
anterior. 
• 
Notificación de deprecación: header X-Akaike-Deprecation: 2027-10-01 + email + panel 
administrativo. 
 
13. Anexos 
13.1 Glosario 
Sigla 
Significado 
PD 
Probability of Default — probabilidad de incumplimiento a 12 meses 
EL 
Expected Loss — pérdida esperada (EL = PD × LGD × EAD) 
LGD 
Loss Given Default — severidad de la pérdida 
EAD 
Exposure At Default — exposición al momento del incumplimiento 
MPE 
Modelo de Pérdida Esperada (Circular Externa 93/2025 Supersolidaria) 
E.A. 
Tasa Efectiva Anual 
N.M. 
Tasa Nominal Mensual 
13.2 Recursos 
• 
Postman Collection: https://akaike.co/api/postman/matias_v1.json 
• 
OpenAPI 3.1 Spec: https://akaike.co/api/openapi/matias_v1.yaml 
• 
SDK Python: pip install akaike-matias 
• 
SDK Node.js: npm install @akaike/matias 
• 
Status page: https://status.akaike.co 
• 
Changelog: https://akaike.co/api/changelog 
13.3 Contacto 
Canal 
Detalle 
Email técnico 
hola@akaike.co

---

M.A.T.I.A.S. API v1   ·   Akaike Credit Risk Solutions 
Documento confidencial — Akaike CRS   ·   Página 18 de 18 
Canal 
Detalle 
Soporte 
https://akaike.co/soporte 
WhatsApp Business 
+57 320 475 6752 
Sitio web 
www.akaike.co 
 
 
© 2026 Akaike Credit Risk Solutions S.A.S. — NIT 901.943.344-3 
Akaike Holding Group LLC (Delaware, USA) 
Documento confidencial — uso interno y de clientes autorizados