Seguridad, Privacidad y Uso Responsable 
de la Información 
 
M.A.T.I.A.S. COPILOT – Akaike Credit Risk Solutions 
 
Versión para clientes y áreas de Seguridad / Riesgo / TI 
 
1. Principio fundamental de seguridad 
 
En Akaike Credit Risk Solutions, la seguridad y confidencialidad de la información de 
nuestros clientes y de sus usuarios finales es prioritaria. 
 
Por diseño, M.A.T.I.A.S. COPILOT no recibe, no procesa ni almacena información 
sensible de personas naturales, tales como: 
• 
Nombres completos 
• 
Números de identificación (cédula, NIT, etc.) 
• 
Direcciones, teléfonos o correos electrónicos 
• 
Reportes crudos de buró de crédito 
 
El sistema ha sido construido bajo los principios de minimización de datos, segregación de 
funciones y privilegio mínimo, alineados con buenas prácticas internacionales de seguridad 
de la información. 
 
2. Separación clara de responsabilidades (diseño seguro)

---

La solución está diseñada con una separación estricta de capas, donde cada componente 
tiene un rol claramente definido: 
• 
Capa de datos sensibles: 
La información de identificación y los reportes de buró se gestionan en entornos 
seguros, controlados y cifrados, accesibles únicamente por servicios autorizados. 
• 
Capa analítica y conversacional (M.A.T.I.A.S. COPILOT): 
El motor conversacional trabaja exclusivamente con: 
o Resultados analíticos 
o Indicadores agregados 
o Variables categorizadas 
o Conclusiones de riesgo y reglas de decisión 
  Nunca con datos personales ni con reportes detallados de buró. 
Esta separación garantiza que, incluso en escenarios de error o uso indebido, la información 
sensible no queda expuesta al modelo de lenguaje. 
 
3. Cómo M.A.T.I.A.S. COPILOT responde sin acceder a 
datos sensibles 
Cuando un analista autorizado interactúa con M.A.T.I.A.S. COPILOT: 
1. El sistema identifica previamente el caso y valida permisos del usuario. 
2. El motor conversacional recibe únicamente un contexto anonimizado y no sensible, 
suficiente para: 
o Explicar decisiones 
o Justificar recomendaciones 
o Sugerir condiciones de crédito 
3. La información exacta que ve el analista (si aplica) se incorpora fuera del modelo, 
desde sistemas seguros, bajo control de acceso. 
De esta forma: 
• 
El analista obtiene respuestas claras y precisas. 
• 
El modelo no conoce la identidad del cliente ni sus datos personales.

---

4. Protección de la información (cifrado y control) 
La información gestionada por Akaike cumple con estándares robustos de protección: 
• 
Cifrado en tránsito 
Toda la comunicación entre sistemas se realiza mediante protocolos seguros 
(TLS/HTTPS). 
• 
Cifrado en reposo 
Los datos almacenados se mantienen cifrados utilizando mecanismos estándar de la 
industria. 
• 
Gestión segura de credenciales 
Las credenciales y accesos se gestionan mediante servicios especializados y nunca se 
exponen en código o interfaces. 
• 
Control de accesos 
El acceso a la información está restringido por: 
o Rol del usuario 
o Entidad (tenant) 
o Caso específico 
aplicando el principio de need-to-know. 
 
5. Prevención de fugas de información 
Para reducir riesgos operativos y humanos, la solución incorpora controles adicionales: 
• 
Prevención de fuga de datos (DLP) 
El sistema bloquea o restringe el envío de información sensible a canales no 
autorizados. 
• 
Validación de entradas y salidas 
Se aplican controles para evitar que información sensible sea enviada o generada por 
error en respuestas conversacionales.

---

• 
Aislamiento por cliente 
Cada entidad opera en un entorno lógico separado, evitando accesos cruzados o 
contaminación de datos. 
 
6. Uso responsable de Inteligencia Artificial 
M.A.T.I.A.S. COPILOT ha sido diseñado bajo un enfoque de IA responsable, donde: 
• 
La IA asiste, pero no sustituye, la toma de decisiones humanas. 
• 
Las decisiones de crédito se basan en modelos gobernados y reglas definidas por cada 
entidad. 
• 
El modelo conversacional no aprende ni memoriza información de clientes 
finales. 
Esto asegura trazabilidad, explicabilidad y control en los procesos de riesgo de crédito. 
 
7. Cumplimiento y alineación con buenas prácticas 
La arquitectura y los procesos de Akaike se alinean con: 
• 
Principios de ISO/IEC 27001 e ISO/IEC 27002: 
o Control de accesos 
o Protección de la información 
o Gestión de riesgos 
o Registro y auditoría de eventos 
• 
Buenas prácticas de seguridad para soluciones basadas en IA 
• 
Enfoques de Privacy by Design y Security by Design 
 
8. Mensaje clave para clientes 
La información de sus clientes no viaja al modelo de IA. 
 
M.A.T.I.A.S. COPILOT opera únicamente con información anonimizada y 
resultados analíticos, mientras que los datos sensibles permanecen 
protegidos, cifrados y bajo control exclusivo de sistemas seguros y 
usuarios autorizados.

---

9. Conclusión 
Akaike Credit Risk Solutions ha diseñado M.A.T.I.A.S. COPILOT para ofrecer los 
beneficios de la inteligencia artificial sin comprometer la confidencialidad, integridad ni 
disponibilidad de la información. 
Esta arquitectura permite a las entidades aprovechar capacidades avanzadas de análisis y 
explicación de riesgo, manteniendo los más altos estándares de seguridad y privacidad 
exigidos por el sector financiero.