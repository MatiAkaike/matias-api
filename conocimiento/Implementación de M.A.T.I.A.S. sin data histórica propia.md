Implementación de M.A.T.I.A.S. sin data 
histórica propia 
 
Guía técnica paso a paso (Modelo Experto → Híbrido → Propio) 
 
1) Principio base: sí se puede modelar riesgo sin data 
histórica propia 
 
Cuando una entidad no tiene historial de cartera (o es insuficiente), podemos implementar 
M.A.T.I.A.S. y comenzar con un Modelo de Riesgo Experto, diseñado con metodología 
de IA/analítica, que permita estimar probabilidad de incumplimiento (PD) y tomar 
decisiones de crédito desde el día 1. 
A medida que la entidad origina y recolecta pagos reales, el modelo se refina y migra en 
dos saltos controlados: 
1. Modelo Experto (0 a 3–6 meses): reglas/score experto con arquitectura analítica 
formal (variables, funciones, objetivo). 
2. Modelo Híbrido (3–12 meses): mezcla de conocimiento experto + calibración 
estadística con pagos reales iniciales. 
3. Modelo Propio (≥ 12 meses): modelo estadístico/ML entrenado principalmente con 
data real de la entidad, con validaciones completas. 
 
2) Fase 0 — Preparación y definición de alcance (Semana 
0–2) 
 
2.1 Definición del producto y del “default” operativo 
 
Se define exactamente qué significa incumplimiento para el producto (ejemplos):

---

• 
FPD (First Payment Default) / primer pago no realizado. 
• 
Mora 30+ / 60+ / 90+ a cierto “mes en libros” (MOB). 
• 
Castigo o “charge-off” si aplica. 
 
Esta definición es crítica porque determina la función objetivo y cómo 
se medirá la calidad del modelo. 
 
2.2 Definición de segmentos y políticas iniciales 
• 
Segmentos de clientes (nuevo vs recurrente, empleado vs independiente, etc.). 
• 
Productos (monto, plazo, tasa, garantías). 
• 
Apetito de riesgo inicial (cut-offs y límites). 
 
3) Fase 1 — Construcción del  
Modelo de Credit Score Experto 
 (Semana 2–6) 
 
Aquí replicamos el enfoque “como hicimos en la fintech de Brasil”: un modelo experto con 
metodología de IA, pero sin necesidad de historial propio. 
 
3.1 Diseño técnico del modelo (formal, defendible) 
 
(a) Variables explicativas (X) 
Se construye un set de variables “expertas” por fuentes, por ejemplo: 
1. Identidad / KYC / antifraude: consistencia de datos, señales de suplantación. 
2. Perfil socio-demográfico: edad/rango, estabilidad, ubicación. 
3. Capacidad de pago proxy: ingresos declarados vs gasto, comportamiento de pagos 
de servicios (si existe).

---

4. Comportamiento crediticio externo: atributos y scores de buró cuando se utilicen. 
5. Datos alternativos (si se integran): telco, aportes, billeteras, etc. 
 
(b) Función de entrada (f_in) 
Transforma variables crudas a señales comparables (normalización, bins, reglas de 
consistencia, flags). 
 
(c) Función de respuesta / score (f_score) 
Agrega señales con pesos expertos, por ejemplo: 
• 
Score aditivo por puntos (tipo scorecard experto), o 
• 
Ensamble de reglas (árbol experto), o 
• 
Fórmula híbrida (puntos + penalizaciones + overrides). 
 
(d) Función objetivo (J) 
En un modelo experto, no optimizamos “por gradiente” con data real aún, pero sí 
definimos la función objetivo para que la arquitectura sea “entrenable” después. Ejemplos: 
• 
Minimizar pérdida esperada: EL = PD × LGD × EAD (si aplica). 
• 
Maximizar margen ajustado al riesgo (pricing). 
• 
Minimizar defaults tempranos (FPD) para originación. 
 
3.2 Construcción de una  
base sintética de default 
 (Y_synthetic) 
 
Como no hay pagos reales, se construye una distribución sintética de incumplimiento 
coherente con: 
• 
Perfil del mercado objetivo, 
• 
Políticas iniciales,

---

• 
Benchmarks razonables (y conservadores), 
• 
Segmentación por variables clave (ej. rangos de score experto). 
 
Objetivo: asignar una PD inicial por rangos/segmentos, consistente con un apetito de 
riesgo inicial. 
 
Importante: esto no pretende “adivinar la realidad”, sino habilitar 
decisiones iniciales y permitir que el sistema comience a aprender y 
corregirse con data real. 
 
4) Fase 2 — Integración de fuentes externas (opcional 
pero recomendado) 
 
Para fortalecer el modelo experto y mejorar la estimación inicial de riesgo, se puede 
integrar información externa: 
 
4.1 Burós / Centrales de riesgo 
• 
Datacrédito (Historia de Crédito+ REST): el consumo se hace vía endpoints con 
token y cabeceras definidas por el proveedor.   
• 
TransUnion (Información Comercial WS): típicamente SOAP/HTTPS con 
autenticación y estructura XML de respuesta.   
 
4.2 Terceros adicionales (según país y disponibilidad) 
• 
Telco (antigüedad de línea, patrón de recargas/pospago). 
• 
Pagos de aportes/seguridad social (señales de formalidad). 
• 
Fuentes de verificación empresarial (si aplica a Pymes). 
• 
Señales transaccionales propias desde el día 1 (dispositivo, hora, canal, etc.).

---

5) Fase 3 — Implementación en M.A.T.I.A.S. + 
M.A.T.I.A.S. COPILOT (Semana 6–8) 
 
5.1 Publicación del modelo experto en M.A.T.I.A.S. 
• 
Se parametriza el modelo (features, transformaciones, reglas, score final). 
• 
Se expone en API para originación 1 a 1. 
• 
Se habilita trazabilidad: qué variables influyeron, qué reglas dispararon, qué 
versión del modelo. 
 
5.2 Habilitación en M.A.T.I.A.S. COPILOT 
• 
COPILOT responde sobre resultados del modelo, explicaciones operativas, y 
recomendaciones de decisión, basado en la data disponible (incluyendo 
buró/terceros si fueron consultados). 
• 
Queda listo para que un analista pregunte: “¿por qué salió alto riesgo?”, “¿qué 
variable pegó?”, “¿qué condición sugerida aplica?”. 
 
6) Fase 4 — Estrategias de decisión y  
pricing por riesgo 
 (Semana 8–10) 
 
Con la PD sintética inicial + score experto, definimos políticas accionables: 
 
6.1 Matriz de decisión (policy grid) 
 
Por rangos de score/PD: 
• 
Aprobación / Rechazo 
• 
Monto (cupo) máximo

---

• 
Plazo 
• 
Tasa 
• 
Garantías / codeudor / anticipo 
• 
Reglas de excepción (override) y banderas antifraude. 
 
6.2 Pricing (ejemplo conceptual) 
• 
Tasa mínima para cubrir pérdida esperada + costos + margen. 
• 
Ajustes por tramo de riesgo, plazo y monto. 
 
7) Fase 5 — Producción con arquitectura escalable 
(Semana 10–12) 
 
Se despliega una arquitectura que soporte evolución: 
• 
Registro de cada solicitud (features, score, decisión, condiciones). 
• 
Registro de eventos de pago (calendario, mora, abonos, refinanciaciones). 
• 
Versionamiento de modelos: Modelo v1 (experto), v2 (híbrido), v3 (propio). 
• 
Monitoreo continuo: estabilidad, performance, drift. 
 
8) Fase 6 — Migración a  
Modelo Híbrido 
 (a los 3–6 meses) 
 
El gatillo típico: 3 meses (productos de muy corto plazo) o 6 meses 
(productos con ciclos más largos), cuando ya existen señales de pago. 
 
8.1 Construcción de la base real inicial (Y_real)

---

• 
Se cruzan originaciones vs comportamiento real: 
o pagos a tiempo, mora, FPD, 30+, etc. 
• 
Se define etiqueta real (default/no default) según la política del producto. 
 
8.2 Unión: sintético + real (controlado) 
• 
Se combinan datos: 
o Base sintética (para estabilidad en segmentos con pocos casos), 
o Base real (para calibración a la realidad del portafolio). 
• 
Se evalúa consistencia: 
o ¿Los tramos de score experto se comportan como se esperaba? 
o ¿Dónde hay sesgo o sub/ sobre-estimación? 
 
8.3 Ajuste y publicación de versión 
• 
Se recalibran pesos, bins y reglas. 
• 
Se publica como Modelo v2 (Híbrido) en M.A.T.I.A.S. 
• 
Se documentan cambios (changelog): qué cambió, por qué, impacto esperado. 
 
9) Fase 7 — Migración a  
Modelo Propio 
 (≥ 12 meses) 
 
Cuando ya hay suficiente volumen y eventos de pago: 
 
9.1 Entrenamiento estadístico/ML con data real 
 
Se entrenan modelos candidatos (ejemplos): 
• 
Logit / scorecard estadístico (baseline explicable). 
• 
Árboles / gradient boosting (si aplica).

---

• 
Más adelante, redes neuronales (cuando haya madurez de data y gobierno). 
 
9.2 Validación técnica completa 
 
Se calculan métricas y pruebas, por ejemplo: 
• 
AUC/ROC, GINI, KS (capacidad discriminante). 
• 
PSI (estabilidad poblacional entre entrenamiento vs producción). 
• 
Bad rate por deciles, lift, calibración (PD vs observado). 
• 
Comparación contra el híbrido: ¿mejora significativa? ¿se mantiene estable? 
 
9.3 Publicación como versión v3 y evolución continua 
• 
Se despliega el modelo propio en M.A.T.I.A.S. 
• 
COPILOT se actualiza para explicar el modelo nuevo (variables clave, razones, 
reglas operativas). 
 
10) Resultado: evolución “IA débil → IA fuerte” 
(controlada y auditable) 
• 
IA débil (Experto): arranque inmediato sin data propia, decisiones operativas 
desde el día 1. 
• 
IA intermedia (Híbrido): aprende con pagos reales temprano, sin perder 
estabilidad. 
• 
IA fuerte (Propio/ML avanzado): con data suficiente, se maximiza precisión, 
calibración y automatización. 
 
11) Respuesta corta lista para el GPT (si te preguntan 
“¿se puede sin data?”) 
 
Sí. Implementamos M.A.T.I.A.S. con un Modelo Experto (variables + funciones + 
objetivo) y una PD inicial basada en default sintético, reforzada con fuentes externas

---

(buró/terceros). Entramos a producción con políticas y pricing por riesgo. A los 3–6 meses 
calibramos con pagos reales y migramos a Modelo Híbrido. A partir de 12 meses, si hay 
volumen suficiente, entrenamos un Modelo Propio y lo validamos con métricas (GINI, KS, 
ROC, PSI) antes de publicar la nueva versión en M.A.T.I.A.S. y COPILOT.