# M.A.T.I.A.S. explicado simple: respuestas de referencia para el chat público

Esta es la fuente principal del chat de la web. Cada respuesta está escrita como debe entenderla un gerente o un analista de crédito sin conocimientos técnicos. Si otra referencia lo dice de forma más técnica o confusa, manda esta.

## Qué es Akaike y qué es M.A.T.I.A.S.

Akaike construye M.A.T.I.A.S., una inteligencia artificial especializada en crédito para bancos, cooperativas, fondos de empleados, financieras y fintechs. En una frase: le ayuda a una entidad a decidir mejor a quién prestar, a hacerlo más rápido y a controlar su cartera.

Lo más conocido es el modelo de calificación de riesgo (Credit Score). Además hay herramientas para el analista, para los procesos y para los reportes. Cuando alguien pregunta en general, se explica primero lo central (el score hecho a la medida) y solo se nombran los demás productos si los pide.

## ¿Hacen modelos de scoring?

Sí. Es nuestro producto principal: M.A.T.I.A.S. Credit Score. Construimos un modelo de calificación de riesgo hecho a la medida de cada entidad, entrenado con la forma en que han pagado sus propios clientes. No es un score genérico igual para todos.

## ¿Cómo construyen el modelo de score?

Con la información histórica que la entidad ya tiene. No hace falta ninguna API para construirlo. Los pasos son:

1. La entidad nos entrega su historial: solicitudes, créditos otorgados y cómo pagaron sus clientes. Sirve en el formato en que lo tenga (Excel, CSV o una exportación de su sistema), aunque esté desordenado.
2. El equipo de científicos de datos de Akaike entiende esa información y entrena con IA un modelo propio para esa entidad.
3. Validamos el modelo con la entidad y definimos juntos desde qué calificación se aprueba, se rechaza o se revisa.
4. El modelo queda listo para calificar cada nueva solicitud en segundos.

Si la entidad no tiene historial suficiente, arrancamos con un modelo experto desde el primer día. A medida que llegan pagos reales, se convierte en un modelo propio.

## ¿Se conectan a mis datos? ¿Necesito una API? ¿Quién pone la API?

Para construir el modelo no hay que conectar nada: basta con entregarnos los archivos del historial.

Para usar el modelo en el día a día, la API es nuestra: M.A.T.I.A.S. tiene su propia API. La entidad no tiene que construir ninguna. Su sistema de solicitudes solo le envía a la API de M.A.T.I.A.S. los datos de cada solicitante y recibe la calificación de vuelta. Le damos las llaves de acceso y un ambiente de pruebas.

Si la entidad no tiene equipo de sistemas, no necesita integrarse: puede usar M.A.T.I.A.S. desde su plataforma web, ingresando la solicitud o cargando un archivo con varias solicitudes.

## ¿Cómo lo usaríamos en el día a día?

Hay tres formas, según lo que tenga la entidad:

- **Desde la plataforma web de M.A.T.I.A.S.:** el analista ingresa la solicitud y ve la calificación. No requiere equipo técnico.
- **Conectando su sistema a nuestra API:** cada solicitud se califica automáticamente.
- **Con M.A.T.I.A.S. Flows:** se arma el proceso completo (consultas, reglas y aprobación) y también se pueden procesar archivos con muchas solicitudes a la vez.

## ¿Qué información necesitan? ¿Qué variables?

No pedimos una lista fija de variables. Partimos de lo que la entidad ya tiene:

- los datos de la solicitud;
- lo que consulta en centrales de riesgo;
- y, sobre todo, cómo han pagado sus clientes.

Entender esa información es trabajo de Akaike, no un requisito previo de la entidad. Un consejo: no limpien ni reorganicen los datos antes de entregarlos, porque se pueden perder señales valiosas.

## Mi información está en Excel o desordenada

No es problema. Es lo normal, y ordenarla y entenderla es parte de nuestro trabajo.

## No tenemos historial (entidad nueva)

Sí sirve. Se arranca con un modelo experto que califica desde el primer día. Con los primeros meses de pagos reales se ajusta, y después se vuelve un modelo propio entrenado con los datos de la entidad.

## ¿Trabajan en mi país?

Akaike trabaja con entidades de crédito de Latinoamérica. Las centrales de riesgo y las reglas de cada país se revisan para cada caso.

## ¿Tengo que cambiar mi software o sistema de cartera?

No. M.A.T.I.A.S. funciona junto a los sistemas que la entidad ya tiene, sin reemplazarlos.

## ¿Cuánto se demora?

Depende del estado de la información y de cómo se vaya a usar, así que el plan exacto se arma al revisar el caso. Como referencia, la preparación toma las primeras semanas, y un modelo experto suele quedar listo entre la semana 2 y la 6. No prometas fechas exactas.

## ¿El modelo decide solo si aprueba o rechaza?

No. El modelo califica y recomienda aprobar, rechazar o revisar, siguiendo los puntos de corte y la política que define la entidad. Los casos dudosos pasan a un analista. La decisión y las reglas siempre son de la entidad.

## ¿Consultan centrales de riesgo (DataCrédito, Experian, TransUnion)?

Sí, M.A.T.I.A.S. puede consultarlas dentro del proceso. Se hace con el contrato de la propia entidad con la central o según se acuerde. Esas consultas las cobra la central y no están incluidas en la suscripción.

## ¿Mis datos están seguros? ¿Los ven otros clientes?

Sí, están protegidos:

- Cada entidad tiene su información separada de las demás y nadie más la ve.
- Los datos viajan y se guardan cifrados.
- El acceso es por usuario y por rol.
- El asistente conversacional no recibe datos personales ni reportes de centrales en bruto.

La IA apoya, pero no reemplaza, la decisión de las personas.

## ¿Funciona para mi tipo de crédito? (libranza, consumo, microcrédito, pyme, vehículo, hipotecario)

Sí. El modelo y los procesos se arman para cada línea de crédito de la entidad. No se aplica un método único para todas.

## Los otros productos, en una línea cada uno (solo si preguntan)

- **Copilot:** un asistente para el analista. Le explica reportes de centrales, capacidad de pago y políticas, y le prepara el resumen para el comité.
- **Credit Agent:** va un paso más allá que Copilot: hace tareas completas que se le autorizan, por ejemplo pedir documentos faltantes o preparar un estudio. Siempre lo hace con permisos y supervisión.
- **Flows:** arma visualmente el proceso de crédito: qué se consulta, qué reglas se aplican y quién aprueba. Funciona con el score de M.A.T.I.A.S. o con el score propio de la entidad.
- **Data B.I.:** tableros e informes de originación, cartera, mora y cobranza.
- **Signals:** muestra cómo se comporta el solicitante en el formulario web (dónde abandona, cuánto tarda) para mejorar la conversión. No se usa por sí solo para rechazar a nadie.
- **Brain y Training Center:** la entidad le enseña a M.A.T.I.A.S. sus manuales y políticas, y así responde según sus propias reglas.

Ningún producto obliga a contratar otro.

## Planes y costos

- Hay una suscripción con cuatro planes: Starter, Expert, Pro y Corporate. Cada uno trae un saldo mensual de AKUs, que miden el uso de la plataforma; el detalle está en el documento de suscripción.
- Habla de planes y AKUs solo si la persona pregunta por planes, consumo o costos.
- El setup del modelo a la medida se estima aparte para cada entidad.
- Nunca se dan precios: los valores se revisan en una reunión.
