# Grafo de conocimiento y voz — agente comercial M.A.T.I.A.S.

## Arquitectura

El sistema separa estrictamente dos capas:

1. Hechos: corpus público con procedencia, derivado de documentos propios de M.A.T.I.A.S. y del wiki sintetizado de Credit Risk Papers.
2. Voz: estadísticas agregadas de las intervenciones de Oscar en Fathom. La producción usa ritmo, conjugaciones y marcadores discursivos; el léxico y las combinaciones completas quedan únicamente en SQLite privado y nunca se usan como fuente factual.

Los nombres, correos, teléfonos, identificadores y ejemplos literales de reuniones no se despliegan. Las fuentes restringidas quedan representadas únicamente en el grafo privado local.

## Artefactos

- Grafo privado SQLite: `~/.local/share/matias-oscar-graph/oscar_knowledge_graph.sqlite`
- Manifest de fuentes: `~/.local/share/matias-oscar-graph/source_manifest.json`
- Snapshot privado de Fathom: `~/.local/share/matias-oscar-graph/raw/fathom_meetings.json`
- Corpus público: `oscar_graph/public_corpus.jsonl`
- Grafo público: `oscar_graph/knowledge_graph.json`
- Perfil lingüístico agregado: `oscar_graph/style_profile.json`
- Runtime: `oscar_graph_runtime.py`

## Actualización

```bash
python3 scripts/sync_fathom.py
python3 scripts/build_oscar_graph.py
python3 -m pytest -q
```

`sync_fathom.py` pagina hasta `next_cursor = null`, conserva checkpoints y respeta el rate limit. `build_oscar_graph.py` reconstruye el snapshot completo, clasifica acceso, cuenta todas las palabras de Oscar y exporta únicamente contenido permitido para producción.

## Guardrails

- Fathom y actas comerciales: voz privada, no hechos públicos.
- Credit Risk Papers: fuente teórica.
- Documentos de M.A.T.I.A.S.: fuente de producto.
- Fuentes sensibles: nodo y hash local, sin copiar contenido.
- Consultas fuera de riesgo de crédito, Akaike o M.A.T.I.A.S.: abstención.
- Demo/contacto: únicamente el calendario oficial.
- Salida pública: texto plano, máximo dos párrafos, sin HTML, Markdown ni PII.

## Verificación del snapshot inicial

- 201 reuniones Fathom desde el 19 de enero de 2026; 198 con transcripción.
- 254 actas, resúmenes o bloques de acciones indexados en el grafo privado.
- 84.878 intervenciones totales; 51.760 de Oscar.
- 854.437 palabras de Oscar; vocabulario de 20.164 formas, 211.464 bigramas y 524.294 trigramas únicos.
- 11.894 formas verbales superficiales preservadas en el grafo privado.
- 1.026 archivos inventariados en Akaike CRS.
- 686 documentos con texto extraído; 3.425.515 palabras documentales.
- 66 chunks públicos de 59 fuentes autorizadas, 72 nodos públicos y 292 relaciones públicas.
