# CLAUDE.md

## Que es este proyecto

MCP server de legislacion laboral argentina. Expone 7 tools que cualquier LLM compatible con Model Context Protocol puede usar para buscar articulos, calcular indemnizaciones, consultar jurisprudencia, analizar casos estadisticamente, verificar prescripciones y generar documentos legales.

Publicado en PyPI como `ley-ar`. Se instala con `uvx ley-ar` o `pip install ley-ar`.

---

## Como correr

```bash
# Instalar en modo desarrollo
pip install -e .

# Correr el server MCP
ley-ar

# Tests
pytest tests/ -v
```

Los datos pesados (embeddings FAISS + jurisprudencia JSONL) se descargan automaticamente al primer uso desde GitHub Releases.

---

## Estructura del codigo

```
src/ley_ar/
├── server.py              # Entry point. Inicializa servicios y registra tools con FastMCP
├── data_manager.py        # Descarga automatica de datos pesados desde GitHub Releases
├── tools/                 # Capa de tools MCP (interfaz publica)
│   ├── norma_vigente.py
│   ├── buscar_articulos.py
│   ├── jurisprudencia.py
│   ├── calcular_indem.py
│   ├── verificar_prescrip.py
│   ├── analizar_caso.py
│   └── generar_documento.py
├── services/              # Logica de negocio y acceso a datos
│   ├── legislation_store.py       # Indice en memoria de articulos de leyes
│   ├── hybrid_retriever.py        # Busqueda keyword + semantica + merge
│   ├── juris_search.py            # Busqueda de fallos por overlap de descriptores
│   ├── case_analytics.py          # Analisis estadistico de jurisprudencia
│   ├── outcome_extractor.py       # Extraccion de resultado de fallos (regex)
│   ├── document_generator.py      # Generacion de documentos desde templates
│   ├── modificaciones_service.py  # Historial de modificaciones legislativas
│   ├── intereses.py               # Calculo de intereses (tasa activa BNA)
│   └── temporal_store.py          # Versionado temporal de datos
└── data/
    ├── legislacion/       # JSONs de leyes (incluido en el paquete)
    ├── descriptores/      # descriptor_index.json (incluido en el paquete)
    ├── embeddings/        # FAISS index + mappings (descarga automatica)
    ├── jurisprudencia/    # JSONL de fallos (descarga automatica)
    ├── templates/         # Templates de documentos legales
    ├── cct/               # Topes por convenio colectivo
    └── modificaciones.json
```

---

## Patron de arquitectura: tools → services → data

El proyecto sigue una separacion estricta en 3 capas:

### 1. Tools (`tools/`)

Funciones puras que reciben servicios ya inicializados por inyeccion de dependencias. Cada tool:
- Recibe los services que necesita como parametros (no importa ni instancia nada)
- Valida inputs
- Orquesta llamadas a services
- Formatea el output como dict

Ejemplo: `buscar_articulos(retriever, store, tema, ley, max_resultados, mod_service)`.

### 2. Services (`services/`)

Logica de negocio reutilizable. Sin conocimiento de MCP ni del protocolo de comunicacion. Cada service:
- Se instancia una vez al inicio en `server.py`
- Mantiene estado en memoria (indices, datos cargados)
- Expone metodos que las tools consumen

### 3. server.py (composicion)

Unico lugar donde se conectan las piezas:
1. `ensure_data_ready()` — descarga datos si faltan
2. Instancia los 4 services compartidos: `LegislationStore`, `HybridRetriever`, `JurisprudenciaSearch`, `ModificacionesService`
3. Registra cada tool con `@mcp.tool()`, inyectando los services en el closure

**No hay estado global ni singletons.** Todo se inyecta explicitamente.

---

## Como agregar una nueva tool

1. **Crear el service** en `services/` si necesitas logica nueva. El service no debe importar nada de `tools/` ni de `mcp`.

2. **Crear la tool** en `tools/nuevo_tool.py`:
   ```python
   def mi_nueva_tool(service_1, service_2, param_a: str, param_b: int = 5) -> dict:
       # Logica de orquestacion
       resultado = service_1.algo(param_a)
       return {"data": resultado}
   ```

3. **Registrarla** en `server.py`:
   ```python
   from ley_ar.tools.nuevo_tool import mi_nueva_tool as _mi_nueva_tool

   @mcp.tool()
   def mi_nueva_tool(param_a: str, param_b: int = 5) -> dict:
       """Descripcion clara para el LLM. Sin jerga tecnica.

       Args:
           param_a: Que significa este parametro
           param_b: Que significa este. Default: 5
       """
       return _mi_nueva_tool(service_1, service_2, param_a, param_b)
   ```

4. **Agregar tests** en `tests/test_nuevo_tool.py`.

### Principios para tool descriptions

Las descriptions son lo que el LLM lee para decidir cuando y como usar la tool. Son criticas:

- Escribir en lenguaje natural, no tecnico. El LLM no necesita saber que usas FAISS.
- Describir QUE hace, no COMO lo hace internamente.
- Especificar que tipo de input funciona mejor (ej: "descripciones conceptuales, no citas legales").
- Si un parametro es opcional, explicar cuando tiene sentido usarlo.
- No incluir ejemplos hardcodeados de casos legales en la description.

---

## Sistema de busqueda (HybridRetriever)

El componente mas complejo. Combina dos estrategias:

**Keyword matching**: stemming en espanol + 955 descriptores SAIJ con 5490 sinonimos. Score por overlap de palabras.

**Busqueda semantica**: modelo `dariolopez/bge-m3-es-legal-tmp-6` + indice FAISS precalculado sobre descriptores. Cosine similarity con umbral 0.55.

**Merge**: `score_final = max(keyword, semantico)` por descriptor. Luego ponderacion por jerarquia SAIJ (ramas tematicas) para que queries multi-concepto no colapsen a un solo tema.

**De descriptores a articulos**: cada descriptor en `descriptor_index.json` tiene articulos asociados con cantidad de citas en jurisprudencia. Score de articulo = suma ponderada de citas * score_descriptor * especificidad.

Si necesitas ajustar thresholds o pesos, estan en `hybrid_retriever.py`. Usa el benchmark para medir impacto:

```bash
python3 benchmark/run.py --json > benchmark/snapshots/before.json
# hacer cambios
python3 benchmark/run.py --json > benchmark/snapshots/after.json
python3 benchmark/compare.py benchmark/snapshots/before.json benchmark/snapshots/after.json
```

---

## Datos

| Dataset | Tamanio | Distribucion | Ubicacion |
|---------|---------|--------------|-----------|
| Legislacion (7 JSONs) | ~670 KB | En el paquete PyPI | `data/legislacion/` |
| Descriptores SAIJ | ~1 MB | En el paquete PyPI | `data/descriptores/` |
| Embeddings FAISS | ~22 MB | GitHub Releases (auto) | `data/embeddings/` |
| Jurisprudencia JSONL | ~194 MB | GitHub Releases (auto) | `data/jurisprudencia/` |

`data_manager.py` descarga los datos pesados desde `github.com/LuchoQQ/ley-ar_mcp/releases/v0.1.0-data` la primera vez que se inicia el server. Usa `urllib` (sin dependencias extra).

### Para actualizar datos

- **Legislacion**: editar los JSONs en `data/legislacion/`. `LegislationStore` los carga automaticamente.
- **Descriptores**: editar `data/descriptores/descriptor_index.json`. Recalcular embeddings FAISS si se agregan descriptores nuevos.
- **Jurisprudencia**: reemplazar el JSONL y subir nuevo zip a GitHub Releases.
- **Embeddings**: regenerar con el modelo `bge-m3-es-legal` y subir nuevo zip.

---

## Limitaciones conocidas

- **Tope CCT**: art. 245 LCT tiene tope por convenio colectivo. El codigo carga datos de CCT pero no todos los convenios estan cubiertos.
- **Intereses**: el service `intereses.py` existe pero ninguna tool lo expone directamente.
- **Cobertura geografica**: jurisprudencia prioriza CABA y Buenos Aires.
- **Busqueda por numero de articulo**: los descriptores SAIJ son tematicos. Buscar "art. 245" no funciona bien; para eso usar `norma_vigente`.
- **Datos estaticos**: la legislacion se actualiza manualmente por release.

---

## Tests

```bash
pytest tests/ -v
```

Los tests estan organizados por tool. Cada archivo testea una tool con sus edge cases.

Para tests que requieren datos pesados (embeddings, jurisprudencia), asegurate de haber corrido el server al menos una vez para que se descarguen.

---

## Dependencias

```
mcp>=1.0.0              # Framework MCP
python-dateutil>=2.8.0  # Parsing de fechas
faiss-cpu>=1.7.0        # Indice de vectores
sentence-transformers   # Modelo de embeddings
```

El paquete se construye con `hatchling`. Entry point: `ley-ar = "ley_ar.server:mcp.run"`.
