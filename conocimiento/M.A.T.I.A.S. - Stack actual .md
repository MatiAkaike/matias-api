M.A.T.I.A.S. ​
Stack actual: Python 3.13 - FastAPI - AWS Serverless - PostgreSQL - DataCrédito 
Experian 
 
I. Carga, Calidad de Datos y Análisis Financiero 
1.1 Cargue Masivo, Validación y Checklist de 
Documentos 
Arquitectura propuesta: 
              Cliente / Oficial →  Frontend (Next.js) 
                          ↓ 
                  API Gateway + S3 Presigned URLs 
                          ↓ 
               AWS S3 (almacenamiento documentos) 
                          ↓ 
            AWS Textract (OCR + IDP) + Lambda de procesamiento 
                          ↓ 
               Motor de validación (checklist por tipo de crédito) 
                          ↓ 
                  PostgreSQL (estado del expediente) 
 
Tecnologías: 
Componente 
Tecnología 
Justificación 
Almacenamiento 
docs 
AWS S3 (AES-256, KMS) 
Escalable, seguro, 
integración nativa 
Lambda 
OCR / IDP 
AWS Textract 
Extracción automática 
de campos en PDFs, 
imágenes 
Validación 
estructural 
JSON Schema (ya 
implementado por cliente) 
Extensible al nivel de 
campo 
Checklist 
dinámico 
PostgreSQL tabla 
document_requirements 
Configurable por tipo 
de crédito/cliente

---

Carga masiva 
AWS S3 Batch Operations + 
SQS 
Procesamiento 
asíncrono de lotes 
Notificaciones 
AWS SNS / WebSockets 
Alertas en tiempo real 
de completitud 
 
 
1.2 Vaciado Automatizado de EEFF, Reclasificación y 
Ratios Financieros 
Tecnologías: 
Componente 
Tecnología 
Extracción de tablas 
financieras 
AWS Textract (AnalyzeDocument + tablas) 
Procesamiento numérico 
pandas + numpy 
Plantillas EEFF 
JSON Schema / YAML configurable por 
cliente 
Cálculo de ratios 
Módulo Python financial_analysis/ 
Almacenamiento resultados 
PostgreSQL + JSON columns 
Módulo financial_analysis/ propuesto: 
 
Plantillas EEFF personalizables: cada cliente puede cargar su propio 
eeff_template_{client_id}.yaml en S3, que mapea nombres de cuentas 
locales a la clasificación estándar del motor. 
 
1.3 IA / Machine Learning - IDP, Patrones y Alertas 
Tempranas 
Arquitectura ML: 
Datos históricos (requests/responses/EEFF) 
          ↓ 
  AWS SageMaker Feature Store 
          ↓ 
  Entrenamiento (SageMaker Training Jobs)

---

↓ 
  Registro de modelos (SageMaker Model Registry) 
          ↓ 
  Endpoint de inferencia (SageMaker Endpoint / Lambda) 
          ↓ 
  Motor de decisión M.A.T.I.A.S. 
 
Tecnologías: 
Capacidad 
Tecnología 
IDP (extracción 
inteligente) 
AWS Textract + Amazon Comprehend 
Modelos de scoring 
scikit-learn / XGBoost en SageMaker 
Detección de anomalías 
Amazon SageMaker Random Cut 
Forest 
Alertas tempranas 
AWS Lambda + SNS (reglas de 
umbral) 
MLOps / versionado 
SageMaker Pipelines + MLflow 
NLP para análisis de 
notas 
Amazon Bedrock (Claude) 
 
 
II. Evaluación de Riesgo y Capacidad de Pago 
2.1 Información de Industria / Sector 
Tecnologías: 
Fuente 
Integración 
Buro de credito (Colombia) 
API REST → Lambda de enriquecimiento 
Superintendencia 
Financiera 
Descarga periódica → S3 → PostgreSQL 
Benchmark sectorial propio 
PostgreSQL tabla sector_benchmarks 
CIIU / ISIC clasificación 
Tabla de referencia + validación al 
ingreso

---

2.2 Modelos de Riesgo y Clasificación (Scoring, Rating, 
PD/LGD) 
 
Modelo 
Variables clave 
Scoring Personas Naturales 
Score buró, ingresos, relación cuota/ingreso, 
antigüedad laboral, historial de pagos 
Scoring PYME 
EBITDA, leverage, cobertura de deuda, años 
de operación, sector CIIU, score DataCrédito 
Rating Interno (1–10) 
Factores cuantitativos (60%) + cualitativos 
(40%) 
PD (Probabilidad de Default) 
Score transformado a probabilidad, ajustado 
por ciclo económico 
LGD (Pérdida dado Default) 
Tipo de garantía, LTV, sector, antigüedad 
colateral 
EL (Pérdida Esperada) 
Calculado automáticamente 
Variables clave del motor de decisión actual (ampliado): 
Variables del buró:      score_datacredito, nivel_endeudamiento, 
                         mora_maxima, num_obligaciones_vigentes 
Variables financieras:   ebitda_margin, current_ratio, debt_service_coverage, 
                         deuda_ebitda, roe 
Variables de solicitud:  monto, plazo, tasa_solicitada, tipo_garantia 
Variables de contexto:   sector_ciiu, region, vintage_empresa 
Variables macro:         tasa_referencia_banrep, ipc, pib_sector 
 
 
2.3 Cálculo de Capacidad de Pago, Flujos de Caja y 
Simulación de Escenarios 
Módulo capacity/:

---

Simulación de escenarios: permitirá al analista modificar variables (ventas, 
márgenes, tasas) y recalcular en tiempo real contra el motor vía API. 
 
2.4 Motor de Decisiones y Verificación de Políticas de 
Crédito 
Arquitectura del motor de reglas: 
JSON Schema validation  
          + 
Política Engine (Python rules / OPA) 
          + 
ML Scoring (SageMaker) 
          + 
Capacity Calculator 
          ↓ 
Decision Aggregator 
          ↓ 
{APROBADO | RECHAZADO | CONDICIONADO | ESCALADO A COMITÉ} 
 
Tecnología: Open Policy Agent (OPA) embebido en Lambda para reglas de 
negocio configurables sin redespliegue, complementado con lógica Python para 
cálculos numéricos. 
 
III. Usabilidad, Gestión Operativa y Reportería 
3.1 Experiencia de Usuario (Frontend) 
Stack frontend: 
Componente 
Tecnología 
Framework 
Next.js 15 (App Router) 
Hosting 
AWS Amplify / CloudFront + S3 
Roles y vistas: 
Rol 
Vista principal 
Acciones 
Oficial de 
Crédito 
Bandeja de solicitudes, 
formulario de ingreso 
Crear, subir documentos, 
enviar a análisis

---

Analista de 
Riesgo 
Expediente completo + 
EEFF + ratios + score 
Revisar, comentar, 
aprobar/rechazar/escalar 
Comité de 
Crédito 
Vista consolidada 
multi-solicitud 
Votar, condicionar, aprobar con 
garantías 
Administrador 
Configuración de 
políticas, clientes, 
esquemas 
CRUD completo, auditoría 
 
3.2 Gestión de Garantías 
Módulo de garantías — modelo de datos: 
class Guarantee(Base): 
    __tablename__ = 'guarantees' 
     
    request_id = Column(String, ForeignKey('requests.request_id')) 
    guarantee_type = Column(String)  # HIPOTECA, PRENDA, AVAL, FNG, FIDUCIA 
    description = Column(Text) 
    appraised_value = Column(Numeric(18, 2)) 
    appraiser_name = Column(String) 
    appraisal_date = Column(Date) 
    appraisal_expiry = Column(Date)      # alerta 90 días antes 
    ltv_ratio = Column(Numeric(5, 4))   # valor_credito / valor_garantia 
    coverage_percentage = Column(Numeric(5, 4)) 
    registry_number = Column(String)     # matrícula inmobiliaria / folio 
    insurance_policy = Column(String) 
    insurance_expiry = Column(Date)      # alerta 60 días antes 
    status = Column(String)  # VIGENTE / VENCIDA / EN_RENOVACION 
 
Automatización: Lambda con EventBridge (cron diario) que detecta garantías 
próximas a vencer y genera alertas en SNS → email/portal al oficial 
responsable. 
 
3.3 Reportería y Analítica 
Stack de reportería: 
Componente 
Tecnología 
Dashboards 
operativos 
Amazon QuickSight (conectado a Aurora) 
Reportes regulatorios 
Lambda programada → S3 → PDF

---

Exportación 
CSV/Excel vía API  
Analítica avanzada 
Amazon Athena sobre S3 data lake 
Alertas automáticas 
CloudWatch Alarms + SNS 
KPIs disponibles: 
●​ Tiempo de ciclo promedio (ingreso → decisión) por oficial y tipo de crédito 
●​ Funnel de originación (ingresados → analizados → aprobados → 
desembolsados) 
●​ Tasa de aprobación/rechazo por segmento, región, oficial 
●​ Distribución de scores y PDFs de la cartera 
●​ Cartera aprobada vs. rechazada vs. condicionada 
●​ Productividad por analista (solicitudes procesadas/día) 
 
IV. Cumplimiento Normativo y Tecnología 
4.1 Normatividad Bancaria (Basilea, Reportes 
Regulatorios) 
Módulo de cumplimiento: 
Requerimiento 
Implementación 
Basilea III — 
Cálculo RWA 
TBD 
Grandes 
Exposiciones (CE 
100) 
TBD 
Reporte COLGAAP 
→ NIIF 
TBD 
Circular Básica 
Contable (SFC) 
TBD 
SARLAFT 
Integración con listas OFAC, ONU, PEP vía API externa 
Adaptabilidad regulatoria: OPA (Open Policy Agent) permite actualizar reglas de 
negocio vía archivos .rego sin redespliegue de Lambda. Cambios regulatorios = 
actualizar política + make deploy.

---

4.2 SARAS / ESG en Evaluación de Crédito 
Integración ESG: TBD 
 
4.3 Arquitectura e Integración — Diagrama Completo 
┌─────────────────────────────────────────────────────────────────┐ 
│                        INTERNET / WAN                           │ 
└─────────────────┬───────────────────────────────────────────────┘ 
                  │ HTTPS TLS 1.3 
┌─────────────────▼───────────────────────────────────────────────┐ 
│                    AWS CLOUD (us-east-2)                        │ 
│                                                                 │ 
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │ 
│  │  CloudFront  │    │         AWS WAF + Shield             │   │ 
│  │  (Frontend)  │    │   (DDoS, OWASP Top 10, Rate limit)   │   │ 
│  └──────┬───────┘    └──────────────┬───────────────────────┘   │ 
│         │                           │                           │ 
│  ┌──────▼───────────────────────────▼───────────────────────┐   │ 
│  │              API Gateway (Regional, TLS 1.2+)            │   │ 
│  │         Throttling: 50 rps / burst 100                   │   │ 
│  └──────────────────────┬───────────────────────────────────┘   │ 
│                          │                                      │ 
│  ┌───────────────────────▼───────────────────────────────────┐  │ 
│  │                    AWS VPC                                │  │ 
│  │                                                           │  │ 
│  │  ┌─────────────────────────────────────────────────────┐  │  │ 
│  │  │               Lambda Functions                      │  │  │ 
│  │  │  ┌────────────┐ ┌──────────────┐ ┌──────────────┐   │  │  │ 
│  │  │  │credit-     │ │ eeff-        │ │ ml-scoring   │   │  │  │ 
│  │  │  │decision    │ │ processor    │ │ (SageMaker   │   │  │  │ 
│  │  │  │(FastAPI+   │ │ (Textract +  │ │  invoke)     │   │  │  │ 
│  │  │  │ Mangum)    │ │  pandas)     │ │              │   │  │  │ 
│  │  │  └─────┬──────┘ └──────┬───────┘ └──────┬───────┘   │  │  │ 
│  │  └────────┼───────────────┼────────────────┼───────────┘  │  │ 
│  │           │               │                │              │  │ 
│  │  ┌────────▼───────────────▼────────────────▼───────────┐  │  │ 
│  │  │        RDS Aurora PostgreSQL (Multi-AZ)             │  │  │ 
│  │  │   clients · api_keys · requests · responses         │  │  │ 
│  │  │   audit_logs · models · documents · guarantees      │  │  │ 
│  │  │   financial_statements · sector_benchmarks          │  │  │ 
│  │  └─────────────────────────────────────────────────────┘  │  │ 
│  │                                                           │  │ 
│  └───────────────────────────────────────────────────────────┘  │ 
│                                                                 │ 
│  ┌───────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐   │ 
│  │    S3     │ │AWS Secrets   │ │  AWS KMS   │ │CloudWatch  │   │ 
│  │(Documentos│ │  Manager     │ │ (CMK cifra-│ │  Logs +    │   │

---

│  │  + EEFF)  │ │(DB + API     │ │  do BD,    │ │  Metrics   │   │ 
│  │           │ │ credentials) │ │  Secrets)  │ │            │   │ 
│  └───────────┘ └──────────────┘ └────────────┘ └────────────┘   │ 
│                                                                 │ 
│  ┌───────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐   │ 
│  │SageMaker  │ │   Cognito    │ │  QuickSight│ │EventBridge │   │ 
│  │(ML models)│ │(AuthN + MFA  │ │(Dashboards)│ │(Scheduler) │   │ 
│  │           │ │ + AD Fed.)   │ │            │ │            │   │ 
│  └───────────┘ └──────────────┘ └────────────┘ └────────────┘   │ 
└──────────────────────────────────────────────────────────────┬──┘ 
                                                               │ 
              Integraciones externas (HTTPS mTLS)              │ 
    ┌──────────────────────────────────────────────────────┐   │ 
    │  DataCrédito Experian · Transunion · SARLAFT/LISTAS  │◄──┘ 
    │  Core Bancario (T24/Flexcube) · CRM                  │ 
    │  DANE/SFC · DIAN (NIT validation) · FNG              │ 
    └──────────────────────────────────────────────────────┘ 
 
Integración con Core Bancario: 
●​ Protocolo: REST/JSON o SOAP (según Core) vía API Gateway privado 
●​ Patrón: Adapter dentro del Provider Pattern existente 
●​ Datos recibidos: Saldos actuales, historial interno, límites 
●​ Datos enviados: Decisión crediticia, condiciones aprobadas 
 
V. Tecnología - Respuestas Detalladas 
5.1 Arquitectura Completa . Resumen Ejecutivo 
Capa 
Tecnología 
Modalidad 
Frontend 
Next.js 15 + shadcn/ui 
Cloud (AWS Amplify) 
API 
FastAPI + Python 3.13 + 
Mangum 
Serverless (AWS 
Lambda) 
Base de 
datos 
AWS Aurora PostgreSQL 
(Multi-AZ) 
Cloud managed 
ML/Scoring 
AWS SageMaker 
Cloud managed 
Documentos 
AWS S3 + Textract 
Cloud managed 
Secretos 
AWS Secrets Manager 
Cloud managed 
Cifrado 
AWS KMS (CMK propias) 
Cloud managed

---

Auth 
AWS Cognito + SAML (AD) 
Cloud managed 
IaC 
AWS SAM + GitHub Actions 
Cloud (CI/CD) 
Monitoreo 
CloudWatch + X-Ray 
Cloud managed 
WAF 
AWS WAF v2 + Shield Standard 
Cloud managed 
100% Cloud — AWS (región us-east-2 Ohio) 
 
5.2 Tecnología de los Motores 
Motor de Decisión: 
├── Validación estructural:    JSON Schema (por cliente) 
├── Motor de políticas:        Open Policy Agent (OPA) — reglas Rego 
├── Scoring estadístico:       scikit-learn / XGBoost via SageMaker 
├── Análisis financiero:       pandas + numpy (módulo EEFF) 
├── Capacidad de pago:         Python puro (módulo capacity/) 
├── Integración bureaus:       Provider Pattern + DataCrédito OAuth2 
└── Orquestación:              FastAPI async + SQLAlchemy 2.x 
 
 
5.3 Interoperabilidad 
El sistema expone y consume: 
Protocolo 
Uso 
REST/JSON sobre 
HTTPS 
API principal 
OAuth2 Client 
Credentials 
Autenticación máquina-a-máquina con bureaus 
SAML 2.0 
Federación con Active Directory corporativo 
(Cognito) 
WebSockets 
Notificaciones en tiempo real al frontend 
S3 Events 
Integración desacoplada con procesamiento 
documental 
SQS 
Cola de mensajería para procesamiento asíncrono

---

5.4 Manejo de Datos, Colas y Herramientas para Fábricas 
de Crédito 
Flujo asíncrono completo: 
Solicitud API → SQS FIFO (garantiza orden) 
                     ↓ 
              Lambda Worker (procesamiento) 
                     ↓ 
         S3 (documentos) + RDS (datos) + SageMaker (score) 
                     ↓ 
              SNS → Email/Portal (notificación) 
 
Herramientas para fábricas de crédito: 
Necesidad 
Herramienta 
Procesamiento batch 
masivo 
AWS Batch + SQS 
Carga masiva de 
solicitudes 
API /batch-decision + S3 CSV upload 
Monitoreo de producción 
CloudWatch Dashboards + Alarms 
Trazabilidad completa 
audit_logs + CloudWatch X-Ray (trazas 
distribuidas) 
Gestión de errores 
DLQ (Dead Letter Queue) en SQS 
 
5.5 Modelo Comercial: SaaS 
La arquitectura es nativamente multi-tenant SaaS: 
●​ Cada cliente tiene su client_id, su api_key, su JSON Schema propio y su 
configuración de políticas 
●​ El aislamiento de datos se garantiza a nivel de fila (client_id en todas las 
tablas sensibles) 
●​ Facturación por volumen de decisiones (tabla requests como fuente de 
verdad) 
●​ Onboarding de nuevos clientes: make db-seed + carga de schema JSON 
 
5.6 Seguridad Bancaria — Controles Completos

---

Control 
Tecnología 
Estado 
WAF OWASP 
Top 10 
AWS WAF v2 
Por implementar 
sobre API GW 
existente 
DDoS Protection 
AWS Shield Standard 
Incluido en API 
Gateway 
Autenticación 
API Keys 
SHA-256 hash + expiración 
Implementado 
MFA para 
usuarios UI 
AWS Cognito MFA (TOTP/SMS) 
Con frontend 
Federación AD 
Cognito + SAML 2.0 
Por implementar 
Cifrado en 
reposo 
AWS KMS CMK 
RDS + Secrets 
Manager 
Cifrado en 
tránsito 
TLS 1.2+ (API GW managed) 
Implementado 
Mascaramiento 
PII 
Función _mask_sensitive_fields 
Implementado 
Audit trail 
Tabla audit_logs + CloudWatch 
Implementado 
Rate limiting 
API GW Throttling (50 rps) 
Implementado 
IAM Least 
Privilege 
Roles Lambda acotados 
Implementado 
VPC Isolation 
VPC + SGs + Subnets privadas 
Implementado 
SAST 
bandit (make security) 
Implementado 
Dependency 
CVE scan 
safety (make deps-audit) 
Implementado 
Secrets rotation 
Secrets Manager auto-rotation 
Por configurar 
SIEM 
AWS Security Hub + GuardDuty 
Por implementar 
 
5.7 Soporte y Mantenimiento

---

Nivel 
Descripción 
SLA 
L1 (operativo) 
Monitoreo CloudWatch, alertas, 
reintentos 
24/7 automático 
L2 (funcional) 
Soporte a usuarios, ajuste de 
políticas/esquemas 
8h hábiles 
L3 (técnico) 
Bugs, parches, actualizaciones de 
seguridad 
24h crítico / 72h 
normal 
Ventanas de 
mantenimiento 
Actualizaciones Lambda (sin 
downtime - rolling) 
Domingos 
02:00-04:00 
Parches Aurora 
AWS Managed - automáticos en 
ventana configurada 
Sin acción 
manual 
 
5.8 Roles y Perfiles de Usuarios (Implementación 
Completa) 
class UserRole(Enum): 
    SUPER_ADMIN     = "super_admin"      # CRUD total + configuración 
    CREDIT_OFFICER  = "credit_officer"   # Crear/ingresar solicitudes 
    RISK_ANALYST    = "risk_analyst"     # Analizar + recomendar 
    COMMITTEE       = "committee"        # Aprobar/rechazar 
    AUDITOR         = "auditor"          # Solo lectura + reportes 
    API_CLIENT      = "api_client"       # Integración máquina-a-máquina 
 
Segregación de funciones (4-eyes principle): 
●​ Un oficial NO puede aprobar su propia solicitud 
●​ Analista y aprobador deben ser personas distintas 
●​ Auditor tiene acceso solo de lectura a todo, incluyendo logs 
Implementación: Cognito Groups + OPA para autorización por endpoint. 
 
VI. Seguridad de la Información, Ciberseguridad y 
Continuidad de Negocio 
6.1 Gestión de Riesgos Operacionales del Software 
Proceso DevSecOps:

---

Desarrollo → GitHub PR 
                ↓ 
        GitHub Actions CI: 
        ├── make lint          (ruff) 
        ├── make security      (bandit — SAST) 
        ├── make deps-audit    (safety — CVE check) 
        ├── make test-cov      (pytest ≥80% coverage) 
        └── make migrate-check (schema drift) 
                ↓ 
        Code Review obligatorio  
                ↓ 
        Deploy DEV automático → pruebas integración 
                ↓ 
        Deploy STAGING manual → pruebas E2E + UAT 
                ↓ 
        Deploy PROD con aprobación explícita 
 
 
6.2 Gestión de Riesgo de Terceros y Subcontratistas 
Proveedor 
Riesgo 
Control 
AWS 
(infraestructura) 
Concentración 
cloud 
Multi-AZ, SLA 99.99%, BAA 
disponible 
DataCrédito 
Experian 
Disponibilidad buró 
Fallback a Buros + caché de 
últimas consultas 
GitHub (CI/CD) 
Pipeline 
comprometido 
Branch protection, secrets en 
GitHub Encrypted Secrets 
SageMaker (ML) 
Inferencia 
indisponible 
Fallback a modelo regla simple 
(score DataCrédito) 
 
6.3 Logs de Auditoría - Operaciones Críticas 
Todas las operaciones críticas generan registro en audit_logs + CloudWatch: 
Operación 
Log generado 
Autenticación (éxito/fallo) 
action: AUTH_SUCCESS / AUTH_FAILED 
Solicitud de crédito ingresada 
action: REQUEST_CREATED 
Decisión emitida 
action: DECISION_ISSUED

---

Cambio de política/esquema 
action: POLICY_UPDATED 
Acceso a datos sensibles 
action: SENSITIVE_DATA_ACCESSED 
Error de sistema 
action: SYSTEM_ERROR 
Retención: 
●​ CloudWatch Logs: 13 meses (configurable, mínimo regulatorio Circular 052) 
●​ PostgreSQL audit_logs: 5 años (respaldo en S3 Glacier para largo plazo) 
●​ Logs inmutables: S3 Object Lock (WORM) para evidencia forense 
 
6.4 Controles Antifraude 
Control 
Implementación 
Rate limiting por cliente 
API GW Throttling + tabla 
api_keys.rate_limit 
Detección de duplicados 
Hash del payload + ventana de 5 min 
Listas restrictivas SARLAFT 
Integración CIFIN/Listas ONU en 
ESGProvider 
Anomalías en patrones de 
consulta 
CloudWatch Anomaly Detection 
IP allowlisting 
API GW Resource Policy por cliente 
Validación cruzada de 
identidad 
DataCrédito + (NIT) + (CC) 
 
6.5 Gestión de Cambios y Actualizaciones 
Feature Branch → PR → CI Gates → Code Review 
       → DEV auto-deploy → QA → STAGING → PROD 
 
Hotfix: rama `hotfix/` → PR expedito → CI Gates → deploy con aprobación 
Parches de seguridad: SLA 4h para críticos, 24h para altos 
 
AWS Lambda: actualizaciones sin downtime (traffic shifting canary/linear). 
Aurora: parches en ventana de mantenimiento configurada (downtime < 30s en 
failover Multi-AZ).

---

6.6 Ambientes Aislados para Pruebas 
Ambiente 
Propósito 
Datos 
Local 
Desarrollo individual (make 
run-mock) 
Datos ficticios, proveedor 
Mock 
DEV 
Integración continua (make deploy 
ENV=dev) 
Datos anonimizados 
STAGING 
UAT, pruebas de carga 
Copia anonimizada de 
producción 
PROD 
Producción real 
Datos reales, acceso 
restringido 
Todos los ambientes usan stacks SAM independientes con parámetros 
distintos. Nunca se comparten credenciales entre ambientes. 
 
6.8 BCP / DRP - Continuidad del Negocio 
Parámetro 
Valor 
Mecanismo 
RTO (Recovery 
Time Objective) 
< 15 minutos 
Lambda multi-AZ + Aurora 
failover automático 
RPO (Recovery 
Point Objective) 
< 5 minutos 
Aurora continuous backup + 
point-in-time recovery 
Disponibilidad 
objetivo 
99.9% (< 8.7h/año) 
SLA compuesto AWS 
Backup BD 
Diario automático 
Aurora automated backups 
Backup documentos 
S3 
Replicación 
cross-region 
(us-west-2) 
S3 CRR 
Pruebas DRP 
Simulacro semestral 
documentado 
Runbook en docs/DRP.md 
Sitio alterno: AWS permite activar región secundaria en < 25 minutos con Route 
53 health checks + DNS failover automático.

---

6.9 Estándares y Certificaciones 
Estándar 
Estado en AWS 
Acción requerida 
ISO 27001 
AWS certificado 
Adoptar controles en procesos 
internos 
SOC 2 Type II 
AWS certificado 
Disponible en AWS Artifact 
ISO 22301 (BCP) 
AWS certificado 
Implementar BCP 
organizacional 
PCI DSS (si hay 
pagos) 
AWS Level 1 
Alcance limitado si no procesa 
tarjetas 
Circular 052 SFC 
Responsabilidad 
compartida 
Implementar controles 
descritos en este doc 
Ley 1581 
(HABEAS DATA) 
Controles técnicos en 
código 
Requiere DPO + políticas 
organizacionales 
 
6.10 Control de Acceso, MFA y Gestión de Identidades 
Usuario (navegador) 
       ↓ 
  AWS Cognito User Pool 
  ├── MFA obligatorio (TOTP / SMS) 
  ├── Federación SAML con Active Directory corporativo 
  ├── Política de contraseñas: 12 chars, mayúsc, nums, especiales 
  └── Sesiones: JWT con expiración 8h 
       ↓ 
  API Gateway (valida JWT Cognito) 
       ↓ 
  Lambda (verifica rol via OPA) 
       ↓ 
  Acción autorizada o 403 Forbidden 
 
Superusuarios: acceso via IAM con MFA, sesiones de rol IAM con duración 
máxima 1 hora, todas las acciones registradas en CloudTrail. 
 
6.11 Cifrado en Reposo, Tránsito y Uso 
Capa 
Mecanismo 
En reposo (BD) 
AWS KMS CMK (AES-256) — RDS Aurora

---

En reposo 
(documentos) 
S3 SSE-KMS con CMK cliente 
En reposo 
(secretos) 
Secrets Manager + KMS 
En tránsito 
TLS 1.3 (API GW → cliente), TLS 1.2+ (Lambda → 
RDS) 
En tránsito 
(bureaus) 
HTTPS + certificado pinning para DataCrédito 
API Keys 
SHA-256 hash (no almacenadas en claro)  
PII en logs 
Enmascaramiento automático 
(_mask_sensitive_fields) 
HSM 
AWS CloudHSM disponible si requerido por regulador 
 
6.12 Clasificación de Información y Protección de Datos 
Personales 
Taxonomía de datos: 
Clasificación 
Ejemplos 
Control 
PÚBLICO 
Tasas de referencia, tipos de 
crédito 
Sin restricción 
INTERNO 
Configuraciones, templates 
Acceso por rol 
CONFIDENCIA
L 
EEFF, historial crediticio 
Cifrado + audit log 
SECRETO / PII 
CC, NIT, ingresos, deudas 
Cifrado + mask + 
DLP 
Cumplimiento Ley 1581 / Habeas Data: campos de consentimiento explícito en 
formulario de solicitud, registro de consentimiento en BD, mecanismo de 
solicitud de eliminación de datos (right to erasure).

---

6.13 Pruebas de Penetración y Gestión de 
Vulnerabilidades 
Proceso: 
1.​ SAST continuo: bandit en cada PR (ya implementado en make security) 
2.​ SCA continuo: safety para CVEs en dependencias (ya implementado en make 
deps-audit) 
3.​ DAST: OWASP ZAP contra ambiente STAGING (trimestral) 
4.​ Gestión de vulnerabilidades: GitHub Dependabot (alertas automáticas) + 
parches en SLA definidos 
 
6.14 Monitoreo, Detección y Respuesta a Incidentes 
CloudWatch Logs (todos los lambdas) 
        ↓ 
CloudWatch Alarms (umbrales: error rate, latencia, 4xx/5xx) 
        ↓ 
AWS GuardDuty (amenazas en tiempo real: brute force, exfiltración) 
        ↓ 
AWS Security Hub (agregación centralizada) 
        ↓ 
SNS → PagerDuty / OpsGenie (alertas 24/7) 
        ↓ 
Runbook de respuesta a incidentes 
 
SLAs de respuesta: 
●​ Incidente crítico (brecha de datos): notificación < 2h, contención < 4h 
●​ Incidente alto (degradación servicio): resolución < 8h hábiles 
●​ Notificación a SFC (Circular 052): dentro de las 24h siguientes a confirmación 
 
6.15 Desarrollo Seguro (SDLC) 
El pipeline de CI/CD (make check) integra: 
Commit → PR → GitHub Actions: 
  1. ruff (linting, code quality) 
  2. bandit (SAST — detecta hardcoded secrets, injections) 
  3. safety (CVE en dependencias) 
  4. pytest --cov ≥80% (tests funcionales) 
  5. alembic check (integridad de schema) 
  → Merge bloqueado si cualquier gate falla 
 
Prácticas OWASP SAMM implementadas:

---

●​ Revisión de código (aprobadores requeridos en main) 
●​ Sin secretos en código (Secrets Manager + .env.example sin valores) 
●​ Validación de input en todas las fronteras (JSON Schema + Pydantic) 
●​ Manejo de errores sin exposición de stack traces en producción 
 
6.16 Integración con Active Directory 
Implementación con AWS Cognito + SAML 2.0: 
Active Directory (on-premise o Azure AD) 
        ↓ SAML 2.0 / ADFS 
AWS Cognito Identity Provider (SAML federation) 
        ↓ JWT tokens 
API Gateway + Lambda (verificación de claims) 
        ↓ 
Roles mapeados: AD Group → Cognito Group → OPA Role 
 
Los usuarios se autentican con sus credenciales corporativas de Windows. No 
se crean contraseñas adicionales. MFA heredado del AD o añadido en Cognito. 
 
6.17 Consulta en Línea de Actividades de Usuarios 
Disponible hoy: tabla audit_logs registra todas las operaciones críticas 
consultable vía API (rol AUDITOR) o directamente en QuickSight. 
Retención de logs de auditoría: 
●​ PostgreSQL audit_logs: 5 años activos 
●​ CloudWatch Logs: 13 meses (ajustable a 10 años) 
●​ S3 Glacier (archivado): 10 años (datos históricos) 
 
Resumen Ejecutivo — Implementación Completa 
Módulo 
Tecnología principal 
Prioridad 
Motor de decisión API 
 FastAPI + Lambda 
(implementado) 
P0 — Listo 
Integración DataCrédito 
OAuth2 + Provider Pattern 
(implementado) 
P0 — Listo

---

Seguridad base (KMS, 
Secrets, VPC) 
AWS (implementado) 
P0 — Listo 
Audit trail 
PostgreSQL + CloudWatch 
(implementado) 
P0 — Listo 
Análisis EEFF + ratios 
pandas + Textract 
P1 — Próximo 
sprint 
Motor de políticas 
configurable 
Open Policy Agent (OPA) 
P1 — Próximo 
sprint 
Capacidad de pago + 
escenarios 
Python módulo capacity/ 
P1 — Próximo 
sprint 
ML Scoring (PD/LGD) 
AWS SageMaker + scikit-learn 
P2 — Fase 2 
Frontend (UX multi-rol) 
Next.js 15 + AWS Cognito 
P2 — Fase 2 
Gestión documental 
S3 + Textract + SQS 
P2 — Fase 2 
Integración Core 
Bancario 
Adapter Provider Pattern 
P2 — Fase 2 
Gestión de garantías 
Módulo PostgreSQL + alertas 
P2 — Fase 2 
Reportería / 
Dashboards 
Amazon QuickSight 
P3 — Fase 3 
ESG / SARAS 
ESGScoringProvider 
P3 — Fase 3 
MFA + Active Directory 
Cognito + SAML 
P3 — Fase 3 
WAF + GuardDuty + 
Security Hub 
AWS managed services 
P1 — 
Seguridad 
BCP documentado 
(DRP formal) 
Runbook + simulacro 
P1 — 
Gobernanza 
 
 
============================================== 
 Glosario de Acrónimos Rápidos 
 
Sigla​ Significado en español 
API​
Interfaz de comunicación entre sistemas 
AWS​ Servicios en la nube de Amazon 
BCP​
Plan de Continuidad del Negocio 
CIIU​
Código de sector económico

---

CRM​ Sistema de gestión de clientes 
DSCR​ Indicador de cobertura de deuda 
DRP​
Plan de Recuperación ante Desastres 
EAD​
Monto expuesto al momento de no pago 
EBITDA​
Ganancia operativa antes de impuestos y depreciación 
EEFF​ Estados Financieros 
EL​
Pérdida esperada en un crédito 
ESG​
Criterios ambientales, sociales y de gobernanza 
FCF​
Dinero libre disponible de una empresa 
FNG​
Fondo Nacional de Garantías (Colombia) 
HCPJ​ Historia crediticia de empresas (DataCrédito) 
HCPN​ Historia crediticia de personas (DataCrédito) 
HSM​ Dispositivo físico de protección de llaves 
IaC​
Infraestructura descrita como código 
IDP​
Procesamiento inteligente de documentos con IA 
ISO​
Norma internacional de calidad/seguridad 
JWT​
Credencial digital temporal de acceso 
KMS​
Servicio de gestión de llaves de cifrado 
KPI​
Indicador clave de desempeño 
LGD​
Pérdida si el cliente no paga 
LTV​
Relación crédito / valor de garantía 
MFA​
Autenticación con múltiples factores 
NIIF​
Normas contables internacionales 
NIT​
Número de identificación tributaria (empresas) 
OFAC​ Lista de sancionados internacionales (EE.UU.) 
OPA​
Motor de reglas de negocio configurable 
PD​
Probabilidad de que el cliente no pague 
PEP​
Persona con cargo público relevante 
PII​
Datos de identificación personal 
RDS​
Base de datos en la nube de Amazon 
REST​ Estilo estándar de comunicación entre sistemas 
ROA​
Rentabilidad sobre activos 
ROE​
Rentabilidad sobre patrimonio 
RPO​
Máxima pérdida de datos aceptable en una falla 
RTO​
Tiempo máximo para restablecer el sistema 
RWA​ Capital requerido por riesgo (Basilea) 
SAML​ Protocolo de acceso único corporativo 
SARLAFT​
Sistema antilavado de activos (Colombia) 
SARAS​
Sistema de riesgo ambiental y social (Colombia) 
SAST​ Análisis de seguridad del código fuente 
SCA​
Análisis de vulnerabilidades en librerías 
SFC​
Superintendencia Financiera de Colombia 
SIC​
Superintendencia de Industria y Comercio (datos) 
SIEM​ Sistema centralizado de alertas de seguridad 
SLA​
Acuerdo de niveles de servicio 
SNS​
Servicio de notificaciones de Amazon 
SOC 2​Certificación de seguridad para empresas tech 
SQS​
Sistema de colas de mensajes de Amazon

---

TLS​
Protocolo de cifrado de comunicaciones en red 
VPC​
Red privada virtual en la nube 
WAF​
Cortafuegos de aplicaciones web 
WORM​
Almacenamiento de solo escritura (inmutable) 
XSS​
Ataque de inyección de código en sitios web