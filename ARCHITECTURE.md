# Arquitectura de ley-ar

Detalles tecnicos del MCP server: como se ejecuta cada tool, flujo de datos, formulas y sistema de busqueda.

## Estructura del codigo

```
src/ley_ar/
├── server.py                      # Entry point FastMCP, registra las 5 tools
├── __main__.py                    # python -m ley_ar
├── data_manager.py                # Descarga automatica de datos pesados
├── services/
│   ├── legislation_store.py       # Carga JSONs de leyes en memoria
│   ├── hybrid_retriever.py        # Keyword + semantico + merge + ponderacion
│   └── juris_search.py            # Busqueda de fallos por overlap de descriptores
├── tools/
│   ├── norma_vigente.py           # Lookup de articulos
│   ├── buscar_articulos.py        # Busqueda hibrida -> articulos
│   ├── jurisprudencia.py          # Descriptores -> fallos
│   ├── calcular_indem.py          # Formulas LCT
│   └── verificar_prescrip.py      # Plazos de prescripcion
└── data/
    ├── legislacion/               # JSONs de leyes (en el paquete, 1.7MB)
    ├── descriptores/              # descriptor_index.json (en el paquete, 1MB)
    ├── embeddings/                # FAISS + mappings (descarga automatica, 22MB)
    └── jurisprudencia/            # JSONL de fallos (descarga automatica, 194MB)
```

## Flujo de datos en runtime

Al iniciar el servidor:

1. `data_manager.ensure_data_ready()` verifica que existan los datos pesados. Si faltan, los descarga del GitHub Release como zips y los extrae.
2. `LegislationStore` carga los 7 JSONs de legislacion en un dict en memoria (663 articulos).
3. `HybridRetriever` carga el indice de descriptores SAIJ, el modelo de embeddings (`bge-m3-es-legal`), y el indice FAISS.
4. `JurisprudenciaSearch` carga el JSONL de fallos en memoria y construye un indice invertido por descriptor.

Todo queda en memoria. No hay lecturas a disco ni llamadas a APIs externas en cada request.

Cuando un cliente MCP llama una tool:

```
Cliente MCP (Claude Desktop, etc.)
       │
       │  tool_call + args (JSON via stdio)
       ▼
   server.py
       │  valida args, despacha a la tool
       ▼
   tools/*.py
       │  ejecuta logica (llama a services si necesita)
       ▼
   services/*.py
       │  accede a datos en memoria
       ▼
   Respuesta JSON via stdio
```

## norma_vigente — Lookup de articulos

El mas simple. `LegislationStore` tiene un dict `{art_id: data}` donde `art_id` es `"{CODIGO}_{NUMERO}"` (ej: `LCT_245`).

1. Recibe `ley` y `articulo`.
2. `_resolve_law(ley)` normaliza aliases: `"20744"` -> `"LCT"`, `"ley 20.744"` -> `"LCT"`, etc.
3. `_normalize_article_num(articulo)` limpia caracteres (`"245°"` -> `245`).
4. Busca `f"{code}_{num}"` en el dict.
5. Devuelve texto, capitulo, seccion.

Aliases soportados: ver `_LAW_ALIASES` en `legislation_store.py`.

## buscar_articulos — Busqueda hibrida

El componente mas complejo. Dos capas de busqueda corren en secuencia (no en paralelo porque comparten el modelo):

### Capa 1: Keyword matching

En `HybridRetriever._match_keywords()`:

1. Tokeniza el input en palabras.
2. Para cada palabra, genera stems con un stemmer casero para espanol (lista de sufijos: `-acion`, `-imiento`, `-ado`, `-ido`, etc.).
3. Para cada descriptor SAIJ y sus sinonimos, calcula `matched_words / total_words`.
4. Match exacto de frase completa = score 1.0.
5. Match de palabra unica = score * 0.3 (penaliza para evitar falsos positivos).
6. Umbral minimo: 0.4.

### Capa 2: Busqueda semantica

En `HybridRetriever._match_semantic()`:

1. Genera embedding de la query con `sentence-transformers` (modelo `dariolopez/bge-m3-es-legal-tmp-6`).
2. Busca los 15 vectores mas cercanos en el indice FAISS (similitud coseno, vectores normalizados).
3. Cada vector mapea a un descriptor SAIJ via `descriptor_mappings.json`.
4. Umbral minimo de similitud: 0.55.

### Merge

En `HybridRetriever.match_descriptors()`:

Para cada descriptor encontrado por cualquiera de los dos metodos:
```
score_final = max(score_keyword, score_semantico)
```

### Ponderacion por rama SAIJ

En `HybridRetriever._apply_hierarchy_weighting()`:

Los descriptores SAIJ estan organizados en un arbol jerarquico (ej: `DERECHO LABORAL / CONTRATO DE TRABAJO / DESPIDO`). La ponderacion funciona asi:

1. Agrupa los descriptores encontrados por rama (primeros 3 niveles del path).
2. Dentro de cada rama, el descriptor con mayor score es el "ancla".
3. Los demas descriptores de la rama se ponderan por similitud jerarquica con el ancla.

Esto permite que queries multi-concepto como "despido durante embarazo" mantengan articulos de ambas ramas (despido + maternidad) sin que una aplaste a la otra.

### De descriptores a articulos

En `HybridRetriever.get_articles()`:

Cada descriptor en `descriptor_index.json` tiene una lista de articulos con cantidad de citas en jurisprudencia. El score de un articulo es:
```
weighted_score = sum(citas * desc_score for each descriptor que lo referencia)
```

Articulos con mas "signals" (referenciados por mas descriptores) rankean mas alto.

### Enriquecimiento

`buscar_articulos` toma los IDs de articulos rankeados y busca el texto completo en `LegislationStore`. Opcionalmente filtra por ley.

## jurisprudencia — Busqueda de fallos

En `JurisprudenciaSearch.search()`:

1. Recibe descriptores ponderados del `HybridRetriever`.
2. Expande descriptores con equivalentes jerarquicos (un descriptor puede tener sinonimos en el arbol SAIJ).
3. Para cada fallo candidato, calcula overlap:
   ```
   score = sum(score_descriptor for each descriptor compartido) * recency_boost
   ```
4. `recency_boost`: 2020+ = 1.5x, 2015-2019 = 1.2x, 2010-2014 = 1.0x, 2000-2009 = 0.8x, pre-2000 = 0.5x.
5. Minimo 2 descriptores en comun para que un fallo aparezca.
6. Deduplica por caratula.

Solo carga fallos con materia "LABORAL" (campo `materia` del JSONL).

## calcular_indemnizacion — Formulas LCT

100% deterministico. Las formulas:

### Antiguedad (Art. 245 LCT)
```
periodos = anos_completos
if meses_fraccion > 3: periodos += 1
periodos = max(periodos, 1)
monto = mejor_remuneracion * periodos
```

### Preaviso (Arts. 231-232 LCT)
```
if antiguedad < 3 meses:    0.5 meses (15 dias)
if antiguedad < 5 anos:     1 mes
if antiguedad >= 5 anos:    2 meses
monto = mejor_remuneracion * meses_preaviso
```
No aplica si preaviso otorgado o despido con causa.

### Integracion mes de despido (Art. 233 LCT)
```
dias_restantes = dias_en_mes - dia_del_despido
monto = (mejor_remuneracion / 30) * dias_restantes
```
Si el despido es el ultimo dia del mes, es 0. No aplica si preaviso otorgado.

### SAC proporcional (Art. 123 LCT)
```
dias_semestre = dias desde inicio del semestre (ene-jun o jul-dic) hasta egreso
monto = (mejor_remuneracion / 2) * (dias_semestre / 180)
```

### Vacaciones proporcionales (Art. 156 LCT)
```
dias_vacaciones segun antiguedad: <5a=14, 5-10=21, 10-20=28, >20=35
dias_trabajados_anio = dias desde 1/ene hasta egreso
monto = (dias_vacaciones * dias_trabajados_anio / 365) * (mejor_remuneracion / 25)
```

### SAC sobre preaviso (Art. 121 LCT)
```
monto = monto_preaviso / 12
```

### Multa ley 25.323 art. 2 (si no registrado)
```
monto = (antiguedad + preaviso + integracion) * 0.5
```

### Advertencias
Siempre incluye:
- No se aplico tope del CCT (art. 245)
- No incluye intereses (aplicar tasa activa BNA)

## verificar_prescripcion — Plazos

Tabla de plazos:

| Tipo | Anos | Fundamento | Computo desde |
|------|------|------------|---------------|
| despido | 2 | Art. 256 LCT | extincion del vinculo |
| diferencias_salariales | 2 | Art. 256 LCT | exigibilidad del credito |
| accidente | 2 | Art. 44 LRT | conocimiento de la incapacidad |
| multas_registro | 2 | Art. 256 LCT | extincion del vinculo |

Si quedan menos de 180 dias, agrega advertencia de urgencia.

## Distribucion de datos

El paquete en PyPI (~1.7MB) incluye:
- Legislacion (7 JSONs, 668KB)
- Descriptores SAIJ (1MB)

Los datos pesados se descargan al primer uso desde GitHub Releases:
- `embeddings.zip` (16MB) -> FAISS index + mappings
- `jurisprudencia.zip` (39MB) -> JSONL de 57,349 fallos

La descarga la maneja `data_manager.py` con `urllib` (sin dependencias extra).
