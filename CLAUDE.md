# CLAUDE.md — Estado actual del proyecto

## Contexto

Dos proyectos que forman un ecosistema:

1. **ley-ar** (`mcp/`) — MCP Server de legislación laboral argentina. Infraestructura open source en Python.
2. **webapp** (`webapp/`) — Agente conversacional que consume ley-ar como librería directa. Frontend React + backend FastAPI + Claude Sonnet.

Deadline: mayo 2026 (Puentes by Antigravity Capital, Cohorte #3).

---

## Arquitectura actual

```
webapp/frontend (React + Vite)
    │
    POST /api/chat/stream  { session_id, message }
    │
webapp/backend
    ├── server.py          FastAPI, sesiones en memoria, SSE streaming
    └── agent.py           Agentic loop con Claude Sonnet + tool use
            │
            │  importa ley-ar como librería Python directa (no MCP protocol)
            │  sys.path.insert → mcp/src/ley_ar/
            │
            ├── Claude API (anthropic SDK)
            │     model: claude-sonnet-4-20250514
            │     system prompt + 5 tool definitions
            │     agentic loop: llama tools hasta stop_reason != "tool_use"
            │
            └── ley-ar tools (ejecución local, sin red)
                  ├── buscar_articulos    → HybridRetriever + LegislationStore
                  ├── jurisprudencia      → HybridRetriever + JurisprudenciaSearch
                  ├── calcular_indemnizacion  → determinístico, sin IA
                  ├── verificar_prescripcion  → determinístico, sin IA
                  └── norma_vigente           → lookup directo LegislationStore
```

El MCP server (`server.py` con FastMCP) también existe y funciona, pero la webapp lo consume como librería directa, no vía MCP protocol.

---

## Estructura de archivos

```
mcp/
├── src/ley_ar/
│   ├── server.py              # MCP server (FastMCP). Entry point: ley-ar CLI
│   ├── data_manager.py        # Descarga automática de archivos pesados desde GitHub Releases
│   ├── __main__.py
│   ├── tools/
│   │   ├── buscar_articulos.py    # Búsqueda semántica de artículos por tema
│   │   ├── jurisprudencia.py      # Búsqueda de fallos por overlap de descriptores
│   │   ├── calcular_indem.py      # Cálculo determinístico de indemnización
│   │   ├── verificar_prescrip.py  # Verificación de prescripción
│   │   └── norma_vigente.py       # Lookup de texto de artículo por ley+número
│   ├── services/
│   │   ├── hybrid_retriever.py    # Keyword matching + FAISS semántico + merge
│   │   ├── legislation_store.py   # Carga JSONs de legislación, lookup por ID
│   │   └── juris_search.py        # Búsqueda de fallos en JSONL por descriptores
│   └── data/
│       ├── legislacion/           # JSONs: LCT, LRT, Ley de Empleo, LJT, Ley 25.323
│       ├── descriptores/          # descriptor_index.json (955 descriptores, 5490 sinónimos)
│       ├── embeddings/            # FAISS index + mappings (se descarga al primer uso)
│       └── jurisprudencia/        # JSONL con fallos taggeados (se descarga al primer uso)
├── tests/
│   ├── test_calcular_indem.py     # 17 tests
│   ├── test_buscar_articulos.py
│   ├── test_jurisprudencia.py
│   ├── test_norma_vigente.py
│   └── test_verificar_prescrip.py
└── pyproject.toml

webapp/
├── backend/
│   ├── server.py              # FastAPI, endpoints /api/chat y /api/chat/stream
│   └── agent.py               # System prompt + tool definitions + agentic loop
└── frontend/
    └── src/App.tsx             # React chat UI
```

---

## Tools de ley-ar — qué hace cada una

### buscar_articulos
- Input: tema (lenguaje natural), ley (filtro opcional), max_resultados
- Proceso: HybridRetriever ejecuta keyword matching (stemming español + descriptores SAIJ) y búsqueda semántica (FAISS con modelo `dariolopez/bge-m3-es-legal-tmp-6`) en paralelo, mergea con `max(keyword, semantic)` por descriptor, pondera por rama SAIJ. LegislationStore enriquece con texto completo.
- Output: artículos con ley, número, título, texto, capítulo, score

### jurisprudencia
- Input: caso (lenguaje natural), jurisdicción (opcional), max_resultados
- Proceso: HybridRetriever extrae descriptores del caso. JurisprudenciaSearch busca fallos en JSONL por overlap de descriptores, con boost por recencia (2.0x post-2020, 0.3x pre-2005). min_overlap=1.
- Output: fallos con carátula, sumario (hasta 1500 chars), fecha, provincia, descriptores en común, score

### calcular_indemnizacion
- Input: fecha_ingreso, fecha_egreso, mejor_remuneracion, causa, registrado, preaviso_otorgado + opcionales: fecha_intimacion, remuneracion_registrada, fecha_registro_falsa
- Proceso: 100% determinístico. Calcula rubros según LCT y leyes 24.013 / 25.323.
- Output clasificado en 3 categorías:
  - `rubros_inmediatos`: art. 245, preaviso, integración mes, SAC, vacaciones, SAC s/preaviso, duplicación art. 1 Ley 25.323
  - `rubros_requiere_intimacion`: arts. 8, 9, 10, 15 Ley 24.013 (solo si se informó fecha_intimacion; si no, devuelve monto 0 + accion_requerida)
  - `rubros_apercibimiento`: art. 2 Ley 25.323 (nota: no es exigible directo, solo como apercibimiento)
- Incluye nota especial cuando antigüedad está cerca del umbral de 5 años (diferencia entre períodos art. 245 y tiempo calendario art. 231)
- Advertencias automáticas: tope CCT no aplicado, intereses no incluidos, telegrama pendiente si aplica

### verificar_prescripcion
- Input: tipo_reclamo (despido/diferencias_salariales/accidente/multas_registro), fecha_hecho
- Proceso: determinístico, plazos de 2 años según art. 256 LCT / art. 44 LRT
- Output: prescripto (bool), fecha_limite, dias_restantes, fundamento

### norma_vigente
- Input: ley, articulo
- Proceso: lookup directo en LegislationStore
- Output: texto completo del artículo, título, capítulo

---

## Agente conversacional (webapp/backend/agent.py)

### System prompt
El prompt define 3 fases sin hardcodear casos específicos:
1. **Recopilación**: recopilar datos del caso conversando. Los parámetros opcionales de calcular_indemnizacion guían qué preguntar.
2. **Análisis**: llamar herramientas relevantes. buscar_articulos y jurisprudencia funcionan con descriptores temáticos, no citas legales.
3. **Respuesta**: presentar resultados respetando la clasificación de rubros de la herramienta. Generar documentos según la situación procesal. Emisor = trabajador en primera persona.

### Agentic loop
- Modelo: claude-sonnet-4-20250514
- Loop: envía messages → si stop_reason == "tool_use" → ejecuta tools → agrega al historial → repite
- Streaming: SSE con eventos tool_start, tool_result, text_delta, done
- Sesiones: dict en memoria (session_id → messages)

### Tool definitions
Las 5 tools están definidas como JSON schema en agent.py. Descripciones genéricas sin ejemplos hardcodeados. El modelo razona qué preguntar y cómo formular queries basándose en su conocimiento legal + las descriptions de las tools.

---

## Datos

| Dataset | Tamaño | Distribución |
|---------|--------|--------------|
| Legislación (JSONs) | ~5 leyes | Incluido en el paquete |
| Descriptores SAIJ | 955 descriptores, 5490 sinónimos | Incluido en el paquete |
| Embeddings FAISS | ~50MB | GitHub Releases (descarga al primer uso) |
| Jurisprudencia JSONL | ~100MB | GitHub Releases (descarga al primer uso) |

`data_manager.py` descarga automáticamente los archivos pesados desde `github.com/LuchoQQ/ley-ar_mcp/releases/v0.1.0-data` al primer uso.

---

## Limitaciones conocidas

- **Tope CCT no aplicado**: art. 245 LCT tiene un tope por convenio colectivo que no se calcula (requiere datos de CCT por actividad)
- **Intereses no incluidos**: el cálculo no suma intereses (tasa activa BNA desde fecha de egreso)
- **Cobertura de descriptores**: búsquedas muy específicas (nombres de leyes, números de artículos) no matchean bien porque los descriptores SAIJ son temáticos
- **Jurisprudencia**: el dataset tiene fallos desde ~2000 hasta 2025, con boost por recencia. Fallos muy viejos pueden aparecer si tienen alto overlap de descriptores.

---

## Cómo correr

### MCP server (standalone)
```bash
pip install -e .
ley-ar
# o: uvx ley-ar (cuando esté en PyPI)
```

### Webapp
```bash
# Backend
cd webapp/backend
pip install -r requirements.txt  # anthropic, fastapi, uvicorn, python-dotenv
python server.py                 # puerto 8000

# Frontend
cd webapp/frontend
npm install && npm run dev       # puerto 5173
```

### Tests
```bash
cd mcp
python3 -m pytest tests/ -v
```
