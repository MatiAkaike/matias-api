M.A.T.I.A.S. y M.A.T.I.A.S. COPILOT 
 
Cómo construimos un Credit Score con IA a la medida y cómo lo volvemos 
explicable, operativo y útil para el analista 
 
1) ¿Qué es M.A.T.I.A.S.? 
 
M.A.T.I.A.S. es el Modelo Analítico Transformador en Inteligencias Artificiales 
Scoring de Akaike: un Credit Score con IA personalizado, construido desde cero para 
cada entidad usando técnicas estadísticas y de ciencia de datos aplicadas al historial real 
de comportamiento de pago de su propia cartera. 
 
En términos simples: 
• 
cada entidad tiene su propia cartera, su propio perfil de clientes, sus propias 
políticas y su propia dinámica de mora, 
por lo tanto su modelo ideal de riesgo no puede ser genérico. 
M.A.T.I.A.S. se entrena con el comportamiento histórico (buenos y malos pagos) de 
la entidad para capturar la realidad de su negocio y convertirla en un score 
predictivo y accionable. 
 
¿Qué produce M.A.T.I.A.S.? 
 
Dependiendo del alcance, M.A.T.I.A.S. genera: 
• 
Un puntaje de riesgo (score) (p. ej., 0–1.000 o el rango que defina la entidad) 
• 
Una banda o perfil de riesgo (A, B, C… o percentiles) 
• 
Una probabilidad de incumplimiento (PD) o una medida equivalente de riesgo 
• 
Drivers/razones (reason codes) y variables clave que explican el resultado 
• 
Reglas y umbrales para decisión automática (aprobación/rechazo) o zona gris 
(revisión humana)

---

• 
Insumos para pricing por riesgo (monto, plazo, tasa, cupo, garantías, etc.), cuando 
aplique 
 
2) Nuestros 5 pasos para construir modelos 
de Credit Score con IA (metodología 
Akaike) 
 
A continuación están los 5 pasos que seguimos para construir M.A.T.I.A.S. con rigor 
estadístico, control y enfoque de negocio. (La idea no es “probar algoritmos”, sino construir 
un modelo estable, gobernable y rentable.) 
 
Paso 1. Diagnóstico y entendimiento del portafolio 
(negocio + datos) 
 
Aquí buscamos responder: ¿cómo se comporta realmente la cartera? y qué definición de 
“malo” debe usarse para el modelo. 
 
Incluye típicamente: 
• 
Segmentación inicial del portafolio (productos, canales, montos, perfiles, 
antigüedad) 
• 
Definición de: 
o Ventana de observación y ventana de desempeño 
o Evento de incumplimiento (ej. 30+, 60+, 90+ DPD; castigo; 
reestructuración, según el caso) 
• 
Identificación de sesgos operativos: 
o Cambios de política, campañas, reestructuraciones masivas, migraciones de 
core, etc. 
• 
Mapa de variables disponibles: 
o Internas (comportamiento, historial, capacidad de pago, relación con la 
entidad) 
o Buró

---

o Alternativas (si aplica) 
 
Salida: documento de entendimiento del portafolio + reglas del “target” (qué es 
malo/bueno) + alcance final de variables. 
 
Paso 2. Auditoría y preparación de datos (calidad, 
consistencia, trazabilidad) 
 
Un modelo de riesgo es tan bueno como sus datos. En este paso: 
• 
Validamos calidad: faltantes, outliers, duplicados, inconsistencias 
• 
Trazamos el linaje: origen del dato, transformaciones, periodicidad 
• 
Homologamos definiciones: por ejemplo “mora”, “saldo”, “antigüedad”, “cupos” 
• 
Diseñamos el dataset modelable: 
o Universo: quién entra y quién no (y por qué) 
o Muestras: train/test/out-of-time (cuando aplica) 
o Tratamiento de variables: bines, estandarizaciones, imputaciones 
• 
Documentamos supuestos y decisiones 
 
Salida: dataset listo para modelación + bitácora de transformaciones + reporte de calidad 
de datos. 
 
Paso 3. Construcción estadística del modelo (IA + 
estabilidad + explicabilidad) 
 
Aquí construimos el corazón de M.A.T.I.A.S. 
 
Dependiendo del caso, el enfoque puede incluir:

---

• 
Modelos estadísticos base (ej. regresión logística) para una línea sólida, 
interpretable y comparable 
• 
Modelos de machine learning (si aplica) como segundo nivel para capturar no 
linealidades 
• 
Selección de variables: 
o poder discriminante (AUC, Gini, KS) 
o estabilidad (PSI / drift) 
o coherencia económica (signos esperados, monotonicidad) 
• 
Control de sobreajuste 
• 
Reason codes: identificación de variables que “explican” el score 
• 
Calibración (si aplica): para que PD/score sea consistente en tiempo 
 
Salida: modelo final + especificación técnica + performance + variables + 
interpretabilidad. 
 
Paso 4. Estrategia de decisión y política (automático vs 
zona gris) 
 
Aquí convertimos el score en decisiones operativas. 
 
Se define: 
• 
Umbrales de aprobación y rechazo 
• 
Segmento “zona gris”: 
o casos cercanos al umbral 
o casos con señales contradictorias 
o casos con alertas específicas 
• 
Reglas complementarias (policy rules): 
o hard rules (no negociables) 
o soft rules (condicionables) 
• 
Condiciones por riesgo: 
o monto/plazo/tasa/cupo/garantías 
• 
Flujo operativo: 
o qué va a automático 
o qué va a analista 
o qué va a comité

---

Salida: matriz de decisión + cutoffs + reglas + tabla de condiciones por banda. 
 
Paso 5. Implementación, monitoreo y gobierno del 
modelo 
 
Un score sin monitoreo no es un score serio. 
 
En este paso: 
• 
Integración al flujo de originación / core / motor 
• 
Pruebas de punta a punta (calidad, latencia, consistencia) 
• 
Definición de monitoreo: 
o desempeño (bad rate por banda, lift, AUC, KS) 
o drift (PSI, cambios en distribuciones) 
o estabilidad del portafolio y alertas tempranas 
• 
Gobierno: 
o quién ajusta umbrales 
o cómo se recalibra o reentrena 
o periodicidad de reportes y comités 
• 
Documentación y trazabilidad para auditoría 
 
Salida: modelo productivo + tablero de monitoreo + protocolo de gobierno. 
 
3) ¿Y entonces qué es M.A.T.I.A.S. 
COPILOT? 
 
Una vez M.A.T.I.A.S. está entrenado, calibrado y operando, aparece la segunda capa:

---

M.A.T.I.A.S. COPILOT es el modelo conversacional que permite a los analistas y a los 
comités interactuar en lenguaje natural con los resultados del score, reglas, políticas y 
evidencia disponible, para: 
• 
Entender por qué M.A.T.I.A.S. aprobó o rechazó 
• 
Documentar decisiones 
• 
Profundizar casos de “zona gris” 
• 
Soportar decisiones más complejas (comité) 
• 
Mejorar consistencia, productividad y aprendizaje del equipo 
 
En pocas palabras: 
• 
M.A.T.I.A.S. = motor de score y decisión (cuando aplica). 
• 
M.A.T.I.A.S. COPILOT = motor de explicación y apoyo conversacional. 
 
4) Diferencias clave (explicadas como lo 
vive el negocio) 
 
4.1 Qué “hace” cada uno 
 
M.A.T.I.A.S. (Credit Score IA) 
• 
Calcula score / banda / riesgo 
• 
Aplica umbrales y políticas 
• 
Puede decidir automáticamente: 
o aprobar 
o rechazar 
o enviar a revisión (zona gris) 
• 
Entrega reason codes y drivers 
 
M.A.T.I.A.S. COPILOT (Conversacional) 
• 
Responde preguntas del analista en formato chat 
• 
Explica el resultado con claridad

---

• 
Prioriza señales relevantes 
• 
Sugiere qué revisar en zona gris 
• 
Estructura argumentos para comité 
• 
Ayuda a estandarizar criterios y reducir errores 
 
4.2 Cuándo se usa cada uno (momentos del flujo) 
 
Caso A: Decisión automática (aprobado / rechazado) 
1. M.A.T.I.A.S. decide automáticamente. 
2. El analista pregunta a COPILOT: 
o “¿Cuáles fueron los factores principales?” 
o “¿Qué cambió frente al último crédito?” 
o “Resume el caso para dejarlo en expediente” 
3. COPILOT entrega explicación y evidencia resumida. 
 
Resultado: mayor confianza en la automatización y mejor trazabilidad. 
 
Caso B: Zona gris (no hay decisión automática) 
1. M.A.T.I.A.S. entrega score cercano a umbral o señales mixtas. 
2. El caso pasa a analista (human-in-the-loop). 
3. El analista usa COPILOT para: 
o entender los drivers del score 
o identificar alertas y contradicciones 
o pedir escenarios: 
▪ 
“¿Qué condiciones mitigarían el riesgo?” 
▪ 
“¿Qué variable revisarías primero y por qué?” 
4. El analista toma la decisión final, con soporte. 
 
Resultado: el analista decide más rápido, con más consistencia y con mejor evidencia. 
 
Caso C: Comité de crédito (decisiones no estándar)

---

COPILOT también apoya en: 
• 
Refinanciaciones 
• 
Reestructuraciones 
• 
Ampliaciones de cupo 
• 
Excepciones 
• 
Revisiones por deterioro o alertas tempranas 
 
Ejemplos: 
• 
“¿Qué señales de estrés financiero aparecen?” 
• 
“¿Qué alternativa reduce más el riesgo: ampliar plazo o bajar cupo?” 
• 
“Resume el historial y plantea una recomendación para comité” 
 
Resultado: reuniones más eficientes y decisiones mejor justificadas. 
 
5) Qué vuelve a COPILOT realmente 
poderoso (y útil en el día a día) 
 
5.1 Traduce analítica a lenguaje operativo 
 
Convierte métricas y variables en algo entendible: 
• 
“Alta utilización” 
• 
“Consultas recientes” 
• 
“Historial corto” 
• 
“Mora reciente” 
y explica impacto en la decisión.

---

5.2 Estandariza el criterio 
 
En equipos grandes, la variación de criterio es un problema. COPILOT: 
• 
reduce interpretación subjetiva 
• 
ayuda a que todos expliquen decisiones de manera similar 
• 
mejora entrenamiento de analistas junior 
 
5.3 Acelera tiempos sin sacrificar control 
• 
Automático donde es seguro 
• 
Humano donde es necesario 
• 
Conversacional para cerrar la brecha 
 
6) Mensaje final (muy importante para 
que no haya confusión) 
• 
M.A.T.I.A.S. es el Credit Score con IA personalizado entrenado desde cero con 
el comportamiento histórico de pago de la cartera de la entidad, construido con 
metodología estadística rigurosa en 5 pasos. 
• 
M.A.T.I.A.S. COPILOT es el asistente conversacional que permite a los usuarios 
autorizados explicar, profundizar y operar las decisiones del score, especialmente en 
zonas grises y en comités. 
 
Si quieres, te lo adapto en 3 versiones listas para usar: 
1. Versión web (más corta, bullets, fácil de leer) 
2. Versión comercial / pitch (1 minuto + 3 minutos) 
3. Versión técnica (para TI y seguridad, incluyendo el concepto de “wow sin exponer 
PII al LLM”, pero sin revelar arquitectura interna)