# CLAUDE.md — Instrucciones de desarrollo

## Contexto del proyecto

Estamos construyendo dos proyectos que forman un ecosistema:

1. **ley-ar** — MCP Server de legislación laboral argentina (infraestructura open source, Python)
2. **demanda-lab** — Generador de borradores de demandas laborales (producto, primer cliente del MCP)

El objetivo final es aplicar a Puentes by Antigravity Capital (Cohorte #3, mayo 2026) con ambos proyectos como evidencia de capacidad técnica y tracción real.

Restricción de tiempo: 10-15 horas semanales. Deadline: mayo 2026.

---

## Estado actual — lo que YA está hecho

### Búsqueda híbrida (COMPLETA ✅)

El sistema de búsqueda de artículos ya está construido y validado. Es el componente más complejo del MCP server y **ya funciona**:

- **Keyword matching** — Tokenización + stemming en español + match contra 955 descriptores SAIJ y 5,490 sinónimos. Preciso con frases exactas.
- **Búsqueda semántica** — Modelo `dariolopez/bge-m3-es-legal-tmp-6` (fine-tuned en texto legal español) + índice FAISS con 5,490 vectores pre-generados. Conecta conceptos sin match literal.
- **Merge híbrido** — Ejecuta ambos en paralelo, toma `max(keyword_score, semantic_score)` por descriptor, aplica ponderación jerárquica **por rama** SAIJ (cada rama tiene su propia ancla, no global).
- **Resultado validado:** 9/10 en 10 casos de prueba. El caso motivador ("despido sin causa durante embarazo") devuelve los 3 artículos clave: LCT_245, LCT_178, LCT_182.

Archivos relevantes:
- `topic_retriever.py` — Keyword matching contra descriptores SAIJ
- Búsqueda semántica con FAISS integrada
- Merge + ponderación por rama implementada

### `buscar_articulos` (COMPLETA ✅)

La tool de búsqueda de artículos ya funciona encima del sistema híbrido:
- Recibe tema en lenguaje natural + filtro opcional por ley
- Ejecuta búsqueda híbrida → obtiene descriptores rankeados
- Enriquece con texto completo de artículos
- Devuelve artículos con ley, número, título, texto, capítulo, relevancia

### `jurisprudencia` (COMPLETA ✅)

La búsqueda de jurisprudencia ya funciona:
- `jurisprudencia_search.py` — Busca fallos en JSONL por overlap de descriptores
- Score ponderado por cantidad de descriptores en común
- Filtro por jurisdicción disponible

### Datos (COMPLETOS ✅)

- `descriptor_index.json` — 955 descriptores SAIJ con 5,490 sinónimos
- JSONs de legislación: LCT, LRT, Ley de Empleo, Ley de Jornada de Trabajo, Ley 25.323
- JSONL de jurisprudencia con fallos taggeados por descriptores SAIJ
- Vectores de embeddings pre-generados para FAISS
- `legislation_store.py` — Carga JSONs y devuelve texto completo por ID
- `build_index.py` — Script que construye el índice de descriptores

### Agente conversacional (PARCIAL ⚠️)

- `agent.py` — Agente con GPT-4o que entiende el caso antes de buscar (se reutiliza para demanda-lab)
- `api.py` — Retriever como servicio FastAPI en puerto 8001 (se reemplaza por MCP)

---

## Lo que FALTA construir para el MCP server

| Componente | Estado | Esfuerzo estimado |
|-----------|--------|-------------------|
| `calcular_indemnizacion` | ❌ No existe | 4-6 horas (fórmulas definidas, falta código) |
| `verificar_prescripcion` | ❌ No existe | 1-2 horas (lógica mecánica) |
| `norma_vigente` | ❌ No existe | ~30 min (lookup directo, 20 líneas) |
| Scaffolding del servidor MCP | ❌ No existe | 2-3 horas (conectar tools + schemas + transport) |
| README actualizado | ❌ Borrador existe, necesita ajustes | 1-2 horas |

**Total estimado para completar el MCP: ~10-14 horas = ~1 semana de trabajo.**

---

## DECISIÓN: MCP en Python (no TypeScript)

El MCP server se construye **en Python** usando el SDK oficial (`mcp` en PyPI). Razones:

- Todo el código existente (retriever, legislation store, jurisprudencia search, búsqueda semántica) ya es Python. Migrar a TypeScript duplicaría el trabajo sin beneficio.
- El SDK oficial de Python es igual de completo que el de TypeScript.
- La instalación sigue siendo simple: `uvx ley-ar` o `pipx install ley-ar`.
- FAISS, el modelo de embeddings, y el stemmer en español ya funcionan en Python. En TS habría que resolver dependencias de binarios nativos.

**El messaging del README cambia:** en vez de "paquete npm, `npx ley-ar`", es "paquete Python, `uvx ley-ar`". El valor del proyecto es el mismo.

---

## FASE 1: Completar el MCP Server — ~1 semana

### Paso 1: Implementar `norma_vigente` (~30 min)

La tool más simple. Lookup directo al `LegislationStore`.

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ley-ar")

@mcp.tool()
def norma_vigente(ley: str, articulo: str) -> dict:
    """Recupera el texto exacto de un artículo de legislación laboral argentina.

    Args:
        ley: Nombre o número de la ley. Valores: "LCT", "LRT", "24013", "25323", "11544"
        articulo: Número del artículo. Ej: "245", "231"
    """
    resultado = legislation_store.get_articulo(ley, articulo)
    if not resultado:
        return {"error": f"No se encontró el artículo {articulo} de la ley {ley}"}

    return {
        "ley": resultado["metadata"]["code"],
        "articulo": articulo,
        "titulo": resultado["metadata"].get("title", ""),
        "texto": resultado["content"],
        "capitulo": resultado["metadata"].get("chapter", ""),
        "vigente": True,
        "ultima_modificacion": resultado["metadata"].get("last_modified", None)
    }
```

**Testear:** Llamar con `("LCT", "245")` y verificar que devuelve el texto correcto del artículo.

---

### Paso 2: Implementar `calcular_indemnizacion` (4-6 horas)

La tool más valiosa y la más testeable. 100% determinística, cero IA.

```python
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

@mcp.tool()
def calcular_indemnizacion(
    fecha_ingreso: str,
    fecha_egreso: str,
    mejor_remuneracion: float,
    causa: str = "sin_causa",
    registrado: bool = True,
    preaviso_otorgado: bool = False
) -> dict:
    """Calcula todos los rubros indemnizatorios de un despido laboral argentino.

    100% determinístico. Aplica las fórmulas exactas de la LCT.
    No usa IA. Cada monto es trazable a un artículo y una fórmula.

    Args:
        fecha_ingreso: Fecha de inicio de la relación laboral (YYYY-MM-DD)
        fecha_egreso: Fecha de despido (YYYY-MM-DD)
        mejor_remuneracion: Mejor remuneración mensual normal y habitual (bruta)
        causa: Tipo de despido: "sin_causa", "con_causa", "indirecto"
        registrado: Si la relación laboral estaba registrada
        preaviso_otorgado: Si el empleador otorgó preaviso
    """
    ingreso = date.fromisoformat(fecha_ingreso)
    egreso = date.fromisoformat(fecha_egreso)
    rem = mejor_remuneracion

    # ── Antigüedad ──
    delta = relativedelta(egreso, ingreso)
    anos = delta.years
    meses_restantes = delta.months
    dias_restantes_delta = delta.days

    # Períodos indemnizatorios (Art. 245 LCT):
    # Cada año completo = 1 período.
    # Fracción > 3 meses = 1 período adicional.
    # Mínimo: 1 período.
    periodos = anos
    if meses_restantes > 3 or (meses_restantes == 3 and dias_restantes_delta > 0):
        periodos += 1
    periodos = max(periodos, 1)

    rubros = {}

    # ── 1. Indemnización por antigüedad (Art. 245 LCT) ──
    # mejor_remuneración × períodos
    # NOTA: No se aplica tope CCT en esta versión.
    indem_antiguedad = rem * periodos
    rubros["indemnizacion_antiguedad"] = {
        "monto": round(indem_antiguedad, 2),
        "calculo": f"{periodos} períodos × ${rem:,.0f}",
        "fundamento": "Art. 245 LCT"
    }

    # ── 2. Preaviso (Arts. 231-232 LCT) ──
    # Si no se otorgó preaviso:
    #   Antigüedad en período de prueba (< 3 meses): 15 días
    #   Antigüedad >= 3 meses y < 5 años: 1 mes
    #   Antigüedad >= 5 años: 2 meses
    meses_preaviso = 0
    texto_preaviso = "Preaviso otorgado — no corresponde"
    if not preaviso_otorgado and causa != "con_causa":
        total_meses = anos * 12 + meses_restantes
        if total_meses < 3:
            meses_preaviso = 0.5  # 15 días
            texto_preaviso = "15 días (período de prueba)"
        elif anos < 5:
            meses_preaviso = 1
            texto_preaviso = f"1 mes × ${rem:,.0f} (antigüedad < 5 años)"
        else:
            meses_preaviso = 2
            texto_preaviso = f"2 meses × ${rem:,.0f} (antigüedad ≥ 5 años)"

    monto_preaviso = rem * meses_preaviso
    rubros["preaviso"] = {
        "monto": round(monto_preaviso, 2),
        "calculo": texto_preaviso,
        "fundamento": "Arts. 231-232 LCT"
    }

    # ── 3. Integración mes de despido (Art. 233 LCT) ──
    # Días que faltan para completar el mes del despido.
    # (mejor_rem / 30) × días_restantes_del_mes
    import calendar
    dias_en_mes = calendar.monthrange(egreso.year, egreso.month)[1]
    dias_restantes_mes = dias_en_mes - egreso.day
    monto_integracion = 0
    texto_integracion = "Despido al último día del mes — no corresponde"
    if dias_restantes_mes > 0 and not preaviso_otorgado and causa != "con_causa":
        monto_integracion = (rem / 30) * dias_restantes_mes
        texto_integracion = f"{dias_restantes_mes} días × (${rem:,.0f} / 30)"

    rubros["integracion_mes"] = {
        "monto": round(monto_integracion, 2),
        "calculo": texto_integracion,
        "fundamento": "Art. 233 LCT"
    }

    # ── 4. SAC proporcional (Art. 123 LCT) ──
    # (mejor_rem / 2) × (días_trabajados_en_semestre / 180)
    # Semestre: enero-junio o julio-diciembre
    if egreso.month <= 6:
        inicio_semestre = date(egreso.year, 1, 1)
    else:
        inicio_semestre = date(egreso.year, 7, 1)
    dias_semestre = (egreso - inicio_semestre).days
    sac_prop = (rem / 2) * (dias_semestre / 180)

    rubros["sac_proporcional"] = {
        "monto": round(sac_prop, 2),
        "calculo": f"(${rem:,.0f} / 2) × ({dias_semestre} días / 180)",
        "fundamento": "Art. 123 LCT"
    }

    # ── 5. Vacaciones proporcionales (Art. 156 LCT) ──
    # Días de vacaciones según antigüedad:
    #   < 5 años: 14 días
    #   5-10 años: 21 días
    #   10-20 años: 28 días
    #   > 20 años: 35 días
    # Fórmula: (días_vac × días_trabajados_en_año / 365) × (mejor_rem / 25)
    if anos >= 20:
        dias_vac = 35
    elif anos >= 10:
        dias_vac = 28
    elif anos >= 5:
        dias_vac = 21
    else:
        dias_vac = 14

    inicio_anio = date(egreso.year, 1, 1)
    dias_trabajados_anio = (egreso - inicio_anio).days
    vac_prop = (dias_vac * dias_trabajados_anio / 365) * (rem / 25)

    rubros["vacaciones_proporcionales"] = {
        "monto": round(vac_prop, 2),
        "calculo": f"({dias_vac} días × {dias_trabajados_anio}/365) × (${rem:,.0f} / 25)",
        "fundamento": "Art. 156 LCT"
    }

    # ── 6. SAC sobre preaviso (Art. 121 LCT) ──
    sac_preaviso = monto_preaviso / 12
    rubros["sac_sobre_preaviso"] = {
        "monto": round(sac_preaviso, 2),
        "calculo": f"${monto_preaviso:,.0f} / 12",
        "fundamento": "Art. 121 LCT"
    }

    # ── 7. Multas por no registro (si aplica) ──
    if not registrado:
        # Art. 8 Ley 24.013: 25% de remuneraciones devengadas
        # Art. 2 Ley 25.323: 50% sobre arts. 232, 233 y 245
        multa_25323 = (indem_antiguedad + monto_preaviso + monto_integracion) * 0.5
        rubros["multa_ley25323_art2"] = {
            "monto": round(multa_25323, 2),
            "calculo": f"50% × (${indem_antiguedad:,.0f} + ${monto_preaviso:,.0f} + ${monto_integracion:,.0f})",
            "fundamento": "Art. 2 Ley 25.323"
        }
    else:
        rubros["multa_ley25323_art2"] = {
            "monto": 0,
            "calculo": "No aplica (relación registrada)",
            "fundamento": "Art. 2 Ley 25.323"
        }

    # ── Total ──
    total = sum(r["monto"] for r in rubros.values())

    # ── Advertencias ──
    advertencias = [
        "No se aplicó tope del CCT (art. 245 LCT) — verificar manualmente según convenio colectivo aplicable",
        "No incluye intereses — aplicar tasa activa BNA desde fecha de egreso"
    ]
    if causa == "con_causa":
        advertencias.append("Despido con causa: si la causa no es válida, corresponden las indemnizaciones de despido sin causa")

    return {
        "rubros": rubros,
        "total": round(total, 2),
        "total_formateado": f"${total:,.0f}",
        "antiguedad": {
            "anos": anos,
            "meses_restantes": meses_restantes,
            "periodos_indemnizatorios": periodos
        },
        "advertencias": advertencias
    }
```

**Tests unitarios obligatorios** — Escribir tests para al menos estos 6 casos:

```python
# test_calcular_indem.py

def test_despido_menos_1_anio():
    """Antigüedad 8 meses → 1 período (fracción > 3 meses)"""
    r = calcular_indemnizacion("2024-06-01", "2025-02-15", 1000000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 1
    assert r["rubros"]["indemnizacion_antiguedad"]["monto"] == 1000000
    assert r["rubros"]["preaviso"]["monto"] == 1000000  # 1 mes (>= 3 meses, < 5 años)

def test_despido_exacto_5_anios():
    """Antigüedad exacta 5 años → 5 períodos, preaviso 2 meses"""
    r = calcular_indemnizacion("2020-01-15", "2025-01-15", 1200000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 5
    assert r["rubros"]["preaviso"]["monto"] == 2400000  # 2 meses × $1.200.000

def test_despido_10_anios():
    """Antigüedad 10 años → 10 períodos, vacaciones 21 días"""
    r = calcular_indemnizacion("2015-03-01", "2025-03-01", 900000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 10
    # Vacaciones: 21 días (5-10 años) — verificar monto

def test_despido_inicio_mes():
    """Despido el día 3 → integración mes grande (27-28 días restantes)"""
    r = calcular_indemnizacion("2020-01-01", "2025-01-03", 1000000, "sin_causa", True, False)
    assert r["rubros"]["integracion_mes"]["monto"] > 0
    # 28 días restantes × ($1.000.000 / 30) ≈ $933.333

def test_despido_fin_mes():
    """Despido el día 31 → integración mes = 0"""
    r = calcular_indemnizacion("2020-01-01", "2025-01-31", 1000000, "sin_causa", True, False)
    assert r["rubros"]["integracion_mes"]["monto"] == 0

def test_despido_no_registrado():
    """Relación no registrada → multa art. 2 ley 25.323 = 50%"""
    r = calcular_indemnizacion("2022-01-01", "2025-01-15", 800000, "sin_causa", False, False)
    assert r["rubros"]["multa_ley25323_art2"]["monto"] > 0

def test_con_preaviso_otorgado():
    """Preaviso otorgado → preaviso = 0, integración = 0, SAC s/preaviso = 0"""
    r = calcular_indemnizacion("2020-01-01", "2025-06-15", 1000000, "sin_causa", True, True)
    assert r["rubros"]["preaviso"]["monto"] == 0
    assert r["rubros"]["integracion_mes"]["monto"] == 0
    assert r["rubros"]["sac_sobre_preaviso"]["monto"] == 0
```

**Validación externa:** Contrastar resultados contra calculadoras online de indemnización que usan abogados (ej: liquidacioneslaborales.com.ar). Si los montos no coinciden, revisar las fórmulas.

---

### Paso 3: Implementar `verificar_prescripcion` (1-2 horas)

```python
@mcp.tool()
def verificar_prescripcion(
    tipo_reclamo: str,
    fecha_hecho: str,
    fecha_consulta: str = None
) -> dict:
    """Verifica si una acción laboral está prescripta según la legislación argentina.

    Args:
        tipo_reclamo: Tipo de acción. Valores: "despido", "diferencias_salariales", "accidente", "multas_registro"
        fecha_hecho: Fecha del hecho que origina el reclamo (YYYY-MM-DD)
        fecha_consulta: Fecha de consulta (YYYY-MM-DD). Default: hoy
    """
    hecho = date.fromisoformat(fecha_hecho)
    consulta = date.fromisoformat(fecha_consulta) if fecha_consulta else date.today()

    plazos = {
        "despido": {
            "anos": 2,
            "fundamento": "Art. 256 LCT",
            "nota": "El plazo se computa desde la fecha de extinción del vínculo laboral."
        },
        "diferencias_salariales": {
            "anos": 2,
            "fundamento": "Art. 256 LCT",
            "nota": "El plazo se computa desde que cada crédito salarial es exigible."
        },
        "accidente": {
            "anos": 2,
            "fundamento": "Art. 44 LRT",
            "nota": "El plazo se computa desde que la víctima tuvo conocimiento de la incapacidad. El momento exacto de inicio puede variar según jurisprudencia. Verificar con abogado."
        },
        "multas_registro": {
            "anos": 2,
            "fundamento": "Art. 256 LCT",
            "nota": "El plazo se computa desde la fecha de extinción del vínculo laboral."
        }
    }

    if tipo_reclamo not in plazos:
        return {"error": f"Tipo de reclamo no reconocido: {tipo_reclamo}. Valores válidos: {list(plazos.keys())}"}

    plazo = plazos[tipo_reclamo]
    fecha_limite = hecho + relativedelta(years=plazo["anos"])
    dias_restantes = (fecha_limite - consulta).days

    advertencia = plazo["nota"]
    if 0 < dias_restantes < 180:
        advertencia = f"⚠️ Quedan menos de 6 meses ({dias_restantes} días). Considerar iniciar acción judicial con urgencia. " + plazo["nota"]

    return {
        "prescripto": dias_restantes <= 0,
        "plazo_total": f"{plazo['anos']} años",
        "fecha_limite": fecha_limite.isoformat(),
        "dias_restantes": max(0, dias_restantes),
        "fundamento": plazo["fundamento"],
        "advertencia": advertencia
    }
```

---

### Paso 4: Scaffolding del servidor MCP (2-3 horas)

Conectar todas las tools al servidor MCP usando el SDK oficial de Python.

**Instalar dependencias:**

```bash
pip install mcp python-dateutil
```

**Estructura del proyecto:**

```
ley-ar/
├── src/
│   └── ley_ar/
│       ├── __init__.py
│       ├── server.py              # Entry point del MCP server
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── buscar_articulos.py    # ✅ Ya existe (migrar handler)
│       │   ├── jurisprudencia.py      # ✅ Ya existe (migrar handler)
│       │   ├── calcular_indem.py      # 🆕 Código del Paso 2
│       │   ├── verificar_prescrip.py  # 🆕 Código del Paso 3
│       │   └── norma_vigente.py       # 🆕 Código del Paso 1
│       ├── services/
│       │   ├── __init__.py
│       │   ├── hybrid_retriever.py    # ✅ Ya existe
│       │   ├── keyword_matcher.py     # ✅ Ya existe (topic_retriever.py)
│       │   ├── semantic_search.py     # ✅ Ya existe
│       │   ├── legislation_store.py   # ✅ Ya existe
│       │   └── juris_search.py        # ✅ Ya existe (jurisprudencia_search.py)
│       └── data/
│           ├── legislacion/           # ✅ JSONs ya existen
│           ├── jurisprudencia/        # ✅ JSONL ya existe
│           ├── descriptores/          # ✅ descriptor_index.json ya existe
│           └── embeddings/            # ✅ Vectores FAISS ya existen
├── tests/
│   ├── test_calcular_indem.py         # 🆕 Tests del Paso 2
│   └── test_verificar_prescrip.py     # 🆕
├── pyproject.toml
└── README.md
```

**Entry point del servidor (`server.py`):**

```python
from mcp.server.fastmcp import FastMCP
from ley_ar.services.legislation_store import LegislationStore
from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch

# Inicializar servicios (cargan datos en memoria)
legislation_store = LegislationStore("data/legislacion/")
hybrid_retriever = HybridRetriever("data/descriptores/", "data/embeddings/")
juris_search = JurisprudenciaSearch("data/jurisprudencia/")

# Crear servidor MCP
mcp = FastMCP(
    "ley-ar",
    description="Infraestructura de legislación laboral argentina para agentes de IA"
)

# Registrar tools
# (importar los handlers de cada tool y decorarlos con @mcp.tool())

@mcp.tool()
def norma_vigente(ley: str, articulo: str) -> dict:
    """Recupera el texto exacto de un artículo de legislación laboral argentina."""
    # ... (ver Paso 1)

@mcp.tool()
def buscar_articulos(tema: str, ley: str = None, max_resultados: int = 5) -> dict:
    """Búsqueda híbrida de artículos de legislación laboral por tema en lenguaje natural."""
    descriptores = hybrid_retriever.buscar(tema)
    articulos = legislation_store.buscar_por_descriptores(descriptores, ley_filtro=ley, limit=max_resultados)
    return {"articulos": articulos, "total_encontrados": len(articulos)}

@mcp.tool()
def jurisprudencia(caso: str, jurisdiccion: str = None, max_resultados: int = 3) -> dict:
    """Busca jurisprudencia laboral relevante a un caso descrito en lenguaje natural."""
    descriptores = hybrid_retriever.buscar(caso)
    fallos = juris_search.buscar(descriptores, jurisdiccion=jurisdiccion, limit=max_resultados)
    return {"fallos": fallos}

@mcp.tool()
def calcular_indemnizacion(...) -> dict:
    """Calcula todos los rubros indemnizatorios de un despido laboral argentino."""
    # ... (ver Paso 2)

@mcp.tool()
def verificar_prescripcion(...) -> dict:
    """Verifica si una acción laboral está prescripta."""
    # ... (ver Paso 3)
```

**`pyproject.toml`:**

```toml
[project]
name = "ley-ar"
version = "0.1.0"
description = "MCP server de legislación laboral argentina para agentes de IA"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "python-dateutil>=2.8.0",
    "faiss-cpu>=1.7.0",
    "sentence-transformers>=2.0.0",
]

[project.scripts]
ley-ar = "ley_ar.server:mcp.run"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Instalación y uso:**

```bash
# Desde PyPI (cuando esté publicado)
uvx ley-ar

# Desarrollo local
pip install -e .
ley-ar
```

**Configuración en Claude Desktop:**

```json
{
  "mcpServers": {
    "ley-ar": {
      "command": "uvx",
      "args": ["ley-ar"]
    }
  }
}
```

---

### Paso 5: Testing completo del MCP (1-2 horas)

Probar las 5 tools desde Claude Desktop con estos casos:

```
Caso 1 (norma_vigente):
"¿Qué dice el artículo 245 de la LCT?"
→ Debe devolver texto exacto del art. 245.

Caso 2 (buscar_articulos):
"Buscame artículos sobre despido durante embarazo"
→ Debe devolver LCT_245, LCT_178, LCT_182 en el top 5.

Caso 3 (calcular_indemnizacion):
"Me despidieron sin causa con 3 años de antigüedad y sueldo de $1.200.000"
→ Debe devolver rubros desglosados con montos exactos.

Caso 4 (jurisprudencia):
"Me despidieron estando embarazada. ¿Hay fallos relevantes?"
→ Debe devolver fallos sobre presunción de despido por embarazo.

Caso 5 (verificar_prescripcion):
"Me despidieron hace 18 meses. ¿Todavía puedo reclamar?"
→ Debe decir que no está prescripto, con X días restantes.

Caso 6 (multi-tool):
"Me despidieron sin causa después de 7 años con sueldo de $900.000. ¿Cuánto me corresponde y qué artículos me protegen?"
→ Debe usar calcular_indemnizacion + buscar_articulos.
```

---

### Paso 6: Actualizar el README (1-2 horas)

Cambios necesarios en el README existente:

1. **Instalación:** Cambiar `npx ley-ar` por `uvx ley-ar`. Cambiar la config de Claude Desktop para usar `uvx`.
2. **La tabla de tools ya es correcta** con la columna "Usa IA" y "Determinístico" separadas.
3. **Búsqueda híbrida:** Ya está documentada correctamente en el README actual. El messaging es: "búsqueda local con modelo de embeddings fine-tuned en texto legal español + keyword matching. Sin APIs externas, cero costo en runtime."
4. **Quick Start:** Actualizar el ejemplo de conversación con `uvx` en vez de `npx`.
5. **Arquitectura:** Actualizar estructura de carpetas a Python (no TS).
6. **Desarrollo local:** Cambiar instrucciones de npm a pip/uv.
7. **Autor:** Completar con nombre real + Twitter/X + LinkedIn.
8. **GIF de demo:** Grabar y agregar cuando las 5 tools funcionen.

---

## FASE 2: Generador de demandas (demanda-lab) — Semanas 2 a 7

> Esta fase comienza DESPUÉS de que el MCP server esté completo y publicado.

### Semana 2-3: Setup + Fase 1 (entrevista guiada)

**Objetivo:** Chat funcional donde el agente entrevista al usuario y extrae los datos del caso.

**Paso 1 — Inicializar el repo:**

```bash
npx create-next-app@latest demanda-lab --typescript --tailwind --app --src-dir
cd demanda-lab
npm install ai @ai-sdk/openai
```

**Paso 2 — Implementar el endpoint de chat (`/api/chat/route.ts`):**

Usar Vercel AI SDK con streaming. El system prompt del agente entrevistador debe:
- Actuar como abogado laboralista argentino experimentado
- Hacer 1-2 preguntas por mensaje (nunca más)
- Extraer: datos del trabajador, del empleador, de la relación laboral, del despido, prueba disponible
- Interpretar lenguaje coloquial ("me echaron", "cobraba en mano", "hace 2 meses")
- Cuando tenga TODOS los datos, emitir `<caso_completo>{...JSON...}</caso_completo>`

Reutilizar la lógica conversacional del `agent.py` existente como referencia para el system prompt.

**Paso 3 — Implementar el frontend del chat (`/nueva/page.tsx`):**

Layout de dos columnas:
- Izquierda: interfaz de chat (mensajes + input)
- Derecha: panel "Resumen del caso" que se va completando en tiempo real
- Barra de progreso que indica % de datos completos
- Detectar `<caso_completo>` para transicionar a la siguiente fase

### Semana 4: Fase 2 (conexión con MCP server)

**Objetivo:** Cuando la entrevista termina, el sistema llama al MCP server y obtiene liquidación + artículos + jurisprudencia.

Implementar el MCP client en Python que consume ley-ar. Las 3 llamadas pueden correr en paralelo. La UI muestra progreso paso a paso.

### Semana 5: Fase 3 (generación del escrito)

**Objetivo:** GPT-4o genera el borrador de demanda usando los datos reales.

**REGLA CRÍTICA:** El LLM NO inventa datos legales. Los artículos vienen del MCP server (datos reales), la liquidación viene del calculador determinístico, la jurisprudencia viene de la base de fallos. El LLM solo redacta y conecta las piezas en lenguaje jurídico.

Estructura del escrito: Encabezado → Hechos → Derecho → Liquidación → Jurisprudencia → Prueba → Petitorio.

### Semana 6: Fase 4 (editor + export DOCX)

**Objetivo:** El usuario puede ver, editar y exportar el borrador.

Cada sección editable. Export a DOCX con formato oficio judicial argentino (21.59cm × 35.56cm, Times New Roman 12pt, márgenes de oficio). Usar librería `docx` de npm o `python-docx`.

### Semana 7: Testing con abogados + pulido

**Objetivo:** 3-5 abogados laboralistas prueban la herramienta.

Conseguirlos en grupos de Facebook/LinkedIn de abogados laboralistas, colegios de abogados, facultades de derecho. Ofrecer acceso gratuito a cambio de feedback.

Iterar basado en feedback real. Pulir UI. Deploy final. Postear en redes sociales.

---

## Scope del MVP (INAMOVIBLE)

- SOLO despido sin causa
- SOLO relación registrada (las multas por no registro se incluyen en `calcular_indemnizacion` pero el generador de demandas no las aborda en v1)
- SOLO CABA y Provincia de Buenos Aires
- SOLO demandas individuales (no colectivas)

No expandir hasta que 3+ abogados validen que el MVP funciona bien. La tentación de agregar más tipos de despido, más jurisdicciones, más ramas del derecho va a matar el proyecto. Resistir.

---

## Cómo presentarlo en la aplicación a Puentes

NO decir "hice un chatbot legal".

DECIR:

"Construí la primera infraestructura open source de legislación argentina para agentes de IA (ley-ar, publicado en PyPI como MCP server), y encima construí demanda-lab, un producto que genera borradores de demandas laborales con fundamento legal verificable. Lo están probando X abogados en Buenos Aires."

Linkear ambos repos. READMEs impecables. GIF de demo en ambos.

---

## Recursos útiles

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — SDK oficial de Python
- [FastMCP docs](https://gofastmcp.com/) — Documentación del framework FastMCP
- [MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) — Para testear MCP servers
- [Vercel AI SDK](https://sdk.vercel.ai/docs) — Para el chat con streaming en demanda-lab
- [python-docx](https://python-docx.readthedocs.io/) — Para generar DOCX desde Python
- [SAIJ](https://www.saij.gob.ar/) — Sistema Argentino de Información Jurídica