# ley-ar

> **Infraestructura open source de legislación laboral argentina para agentes de IA.**

[![npm version](https://img.shields.io/npm/v/ley-ar.svg)](https://www.npmjs.com/package/ley-ar)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![MCP compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io)

---

<!-- TODO: Agregar GIF de demo mostrando Claude Desktop usando calcular_indemnizacion -->

## Quick Start

Instalá y conectá con Claude Desktop en 30 segundos:

```bash
npx ley-ar
```

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "ley-ar": {
      "command": "npx",
      "args": ["ley-ar"]
    }
  }
}
```

Reiniciá Claude Desktop. Ahora podés preguntar:

```
Vos:    "Me despidieron sin causa después de 3 años. Cobraba $1.200.000
         brutos. ¿Cuánto me corresponde?"

Claude: Usando ley-ar, calculé tu indemnización:

        Indemnización por antigüedad (Art. 245 LCT):  $3.600.000
        Preaviso - 2 meses (Arts. 231-232 LCT):       $2.400.000
        Integración mes de despido (Art. 233 LCT):       $840.000
        SAC proporcional (Art. 123 LCT):                 $198.333
        Vacaciones proporcionales (Art. 156 LCT):        $276.164
        SAC sobre preaviso (Art. 121 LCT):               $200.000
        ─────────────────────────────────────────────────────────
        TOTAL:                                         $7.514.497

        ⚠️ No se aplicó tope del CCT — verificar manualmente.
        ⚠️ No incluye intereses — aplicar tasa activa BNA desde la fecha de egreso.
```

Cada monto es determinístico. No hay alucinación. Las fórmulas son las de la LCT.

---

## ¿Qué es esto?

`ley-ar` es un servidor [MCP (Model Context Protocol)](https://modelcontextprotocol.io) que expone legislación laboral argentina como herramientas que cualquier LLM puede usar directamente.

Cuando conectás `ley-ar` a un agente de IA, el modelo puede:

- Buscar artículos de la LCT, LRT y leyes complementarias por tema en lenguaje natural
- Consultar jurisprudencia laboral relevante a un caso específico
- Calcular con precisión determinística todos los rubros indemnizatorios de un despido
- Verificar si una acción laboral está prescripta
- Recuperar el texto exacto de cualquier artículo

**No existe infraestructura equivalente para legislación latinoamericana.** Este proyecto es el primero.

---

## El problema que resuelve

Los LLMs tienen conocimiento general sobre derecho laboral argentino, pero ese conocimiento es:

- **Impreciso en los montos**: las fórmulas del art. 245 LCT requieren cálculo exacto, no estimación
- **No actualizado**: la legislación cambia (el art. 275 LCT fue sustituido por el Decreto 70/2023)
- **No verificable**: cuando un modelo cita un artículo, no hay forma de saber si es correcto

`ley-ar` resuelve esto separando responsabilidades:

```
LLM               →  entiende el caso, conversa, redacta
ley-ar (MCP)      →  busca artículos reales, calcula montos, verifica plazos
```

El LLM nunca inventa datos legales. Los datos legales vienen de una fuente determinística y verificable.

---

## Tools disponibles

| Tool | Qué hace | Usa IA | Determinístico |
|------|----------|--------|----------------|
| `buscar_articulos` | Búsqueda híbrida en legislación laboral | Sí (embeddings locales) | Parcial |
| `jurisprudencia` | Búsqueda de fallos por descriptores del caso | No | Sí |
| `calcular_indemnizacion` | Calcula todos los rubros de un despido | No | Sí |
| `verificar_prescripcion` | Verifica si una acción laboral está prescripta | No | Sí |
| `norma_vigente` | Recupera el texto exacto de un artículo | No | Sí |

4 de 5 tools son 100% locales, sin API externa, sin modelo de IA. `buscar_articulos` usa embeddings pre-generados localmente — el único costo de IA es el embedding de la query entrante.

---

### `buscar_articulos`

Búsqueda híbrida que combina keyword matching (descriptores SAIJ con stemming en español) y búsqueda semántica (embeddings con modelo legal fine-tuned). Cada método cubre las debilidades del otro.

**Input:**
```typescript
{
  tema: string,           // "despido sin causa", "embarazo", etc.
  ley?: "LCT" | "LRT",   // opcional — filtra por ley específica
  max_resultados?: number // default: 5
}
```

**Output:**
```typescript
{
  articulos: [
    {
      ley: "Ley 20.744 - Ley de Contrato de Trabajo",
      articulo: "245",
      titulo: "Indemnización por antigüedad o despido",
      texto: "En los casos de despido dispuesto por el empleador...",
      capitulo: "Título XII: De la extinción del contrato de trabajo",
      relevancia: 0.91
    }
  ],
  total_encontrados: 3
}
```

**Cómo funciona internamente** — la búsqueda tiene dos capas que corren en paralelo:

```
Query del usuario
       │
       ├──────────────────────────────┐
       ▼                              ▼
┌──────────────┐              ┌────────────────┐
│   KEYWORD    │              │   SEMÁNTICO    │
│              │              │                │
│ Tokeniza     │              │ Embedding con  │
│ + stemming   │              │ bge-m3-es-     │
│ español      │              │ legal          │
│ + match vs   │              │ + FAISS        │
│ descriptores │              │ similitud      │
│ SAIJ +       │              │ coseno vs      │
│ sinónimos    │              │ 5,490 vectores │
└──────┬───────┘              └───────┬────────┘
       │                              │
       │  {descriptor: score}         │  {descriptor: score}
       │                              │
       └──────────┬───────────────────┘
                  ▼
         ┌───────────────┐
         │    MERGE      │
         │               │
         │ Por cada       │
         │ descriptor:   │
         │ max(kw, sem)  │
         └───────┬───────┘
                 ▼
         ┌───────────────┐
         │  PONDERACIÓN  │
         │  POR RAMA     │
         │               │
         │ Cada rama     │
         │ SAIJ tiene    │
         │ su propia     │
         │ ancla (no     │
         │ global)       │
         └───────┬───────┘
                 ▼
         Top N artículos
         con texto completo
```

**¿Por qué híbrido y no solo uno?**

El keyword matching es preciso cuando hay coincidencia exacta de frases pero no entiende semántica. El semántico conecta conceptos sin match exacto pero con queries cortas produce resultados absurdos. La combinación de ambos resuelve los dos problemas.

Detalle de la ponderación por rama: antes de la versión híbrida, el sistema tomaba el descriptor con mayor score como "ancla" global y penalizaba todo lo que no estuviera en su misma rama jerárquica SAIJ. Eso provocaba que queries multi-concepto como "despido durante embarazo" perdieran los artículos de embarazo (rama distinta a la de despido). Ahora agrupamos por rama y cada rama tiene su propia ancla, lo que permite capturar artículos de múltiples áreas del derecho laboral.

**Resultados medidos en 10 casos de prueba:**

| Caso | Keyword solo | Semántico solo | Híbrido |
|------|-------------|----------------|---------|
| "me despidieron estando embarazada" | ✅ LCT_178 top | ✅ LCT_178 top | ✅ LCT_178 top |
| "despido sin causa durante embarazo" | ❌ pierde embarazo | ✅ LCT_178 top | ✅ LCT_245 + LCT_178 + LCT_182 |
| "despido sin causa" | ✅ LCT_245 top | ❌ "mensajería en moto" | ✅ LCT_245 top |
| "trabajo en negro" | ✅ LdE_8 top | ✅ LdE_8 top | ✅ LdE_8 top |
| "horas extras" | ✅ LCT_201 top | ✅ LCT_201 top | ✅ LCT_201 top |
| "accidente de trabajo" | ❌ solo "trabajo" genérico | ❌ "mensajería en moto" | ✅ LRT_39, LRT_46, LRT_6 |
| "sindicato" | ⚠️ solo reincorporación | ❌ "despido por riña" | ⚠️ agrega discriminatorio + afiliado |
| "licencia por enfermedad" | ⚠️ 1 descriptor | ❌ "estatuto bancario" | ✅ despido + licencia combinados |
| "aguinaldo" | ✅ SAC top | ❌ "falta de aumento" | ✅ SAC top |
| "acoso laboral" | ✅ mobbing top | ❌ "bonificación emergencia" | ✅ mobbing top |

**Resumen: keyword solo 6/10 — semántico solo 4/10 — híbrido 9/10.**

El caso que motivó todo el rediseño ("despido sin causa durante embarazo") ahora devuelve los 3 artículos clave: LCT_245 (indemnización por despido), LCT_178 (presunción por embarazo), LCT_182 (indemnización agravada).

---

### `jurisprudencia`

Busca fallos por overlap de descriptores SAIJ extraídos del caso. 100% local.

**Input:**
```typescript
{
  caso: string,              // descripción del caso en lenguaje natural
  jurisdiccion?: string,     // "CABA" | "PBA" | "nacional"
  max_resultados?: number    // default: 3
}
```

**Output:**
```typescript
{
  fallos: [
    {
      tribunal: "Cámara Nacional de Apelaciones del Trabajo, Sala VII",
      caratula: "González, María c/ Transportes SA s/ despido",
      fecha: "2023-05-15",
      descriptores: ["DESPIDO INJUSTIFICADO"],
      sintesis: "Se confirmó la condena al pago de indemnización...",
      relevancia: 0.87
    }
  ]
}
```

---

### `calcular_indemnizacion`

**100% determinístico.** Calcula los rubros de un despido aplicando las fórmulas exactas de la LCT. No usa IA. Cada monto es trazable a un artículo y una fórmula.

**Input:**
```typescript
{
  fecha_ingreso: string,                          // "2020-03-15"
  fecha_egreso: string,                           // "2025-01-20"
  mejor_remuneracion: number,                     // remuneración mensual bruta
  causa: "sin_causa" | "con_causa" | "indirecto",
  registrado: boolean,
  preaviso_otorgado?: boolean
}
```

**Output:**
```typescript
{
  rubros: {
    indemnizacion_antiguedad: {
      monto: 5000000,
      calculo: "5 períodos × $1.000.000",
      fundamento: "Art. 245 LCT"
    },
    preaviso: {
      monto: 2000000,
      calculo: "2 meses × $1.000.000 (antigüedad ≥ 5 años)",
      fundamento: "Arts. 231-232 LCT"
    },
    integracion_mes: {
      monto: 400000,
      calculo: "12 días × ($1.000.000 / 30)",
      fundamento: "Art. 233 LCT"
    },
    sac_proporcional: { ... },
    vacaciones_proporcionales: { ... },
    sac_sobre_preaviso: { ... }
  },
  total: 8122223,
  total_formateado: "$8.122.223",
  antiguedad: {
    años: 4,
    meses_restantes: 10,
    periodos_indemnizatorios: 5
  },
  advertencias: [
    "No se aplicó tope del CCT — verificar manualmente",
    "No incluye intereses — aplicar tasa activa BNA desde fecha de egreso"
  ]
}
```

**Fórmulas implementadas:**

| Rubro | Fórmula | Artículo |
|-------|---------|----------|
| Indemnización por antigüedad | `mejor_rem × períodos` (fracción > 3 meses = 1 período) | Art. 245 LCT |
| Preaviso | 15 días (<3 meses), 1 mes (<5 años), 2 meses (≥5 años) | Arts. 231-232 LCT |
| Integración mes | `(mejor_rem / 30) × días_restantes_del_mes` | Art. 233 LCT |
| SAC proporcional | `(mejor_rem / 2) × (días_semestre / 180)` | Art. 123 LCT |
| Vacaciones proporcionales | según antigüedad: 14/21/28/35 días | Art. 156 LCT |
| SAC sobre preaviso | `preaviso / 12` | Art. 121 LCT |

---

### `verificar_prescripcion`

**Input:**
```typescript
{
  tipo_reclamo: "despido" | "diferencias_salariales" | "accidente" | "multas_registro",
  fecha_hecho: string,     // "2023-06-15"
  fecha_consulta?: string  // default: hoy
}
```

**Output:**
```typescript
{
  prescripto: false,
  plazo_total: "2 años",
  fecha_limite: "2025-06-15",
  dias_restantes: 120,
  fundamento: "Art. 256 LCT",
  advertencia: "⚠️ Quedan menos de 6 meses. Considerar iniciar acción judicial."
}
```

**Plazos implementados:**

| Tipo de reclamo | Plazo | Artículo | Nota |
|----------------|-------|----------|------|
| Despido | 2 años desde extinción del vínculo | Art. 256 LCT | |
| Diferencias salariales | 2 años desde que el crédito es exigible | Art. 256 LCT | |
| Accidente / enfermedad profesional | 2 años desde conocimiento de la incapacidad | Art. 44 LRT | Plazo con matices jurisprudenciales; el cómputo del inicio puede variar según el caso. Verificar con abogado. |
| Multas por no registro | 2 años desde extinción del vínculo | Art. 256 LCT | |

---

### `norma_vigente`

Lookup directo al texto de un artículo. Sin procesamiento, sin IA.

**Input:**
```typescript
{
  ley: "LCT" | "LRT" | "24013" | "25323",
  articulo: string   // "245", "231", etc.
}
```

**Output:**
```typescript
{
  ley: "Ley 20.744 - Ley de Contrato de Trabajo",
  articulo: "245",
  titulo: "Indemnización por antigüedad o despido",
  texto: "En los casos de despido dispuesto por el empleador sin justa causa...",
  capitulo: "Título XII: De la extinción del contrato de trabajo",
  vigente: true,
  ultima_modificacion: "Decreto 70/2023 B.O. 21/12/2023"
}
```

---

## Arquitectura interna

### Estructura del repositorio

```
ley-ar/
├── src/
│   ├── index.ts                   # Entry point — inicia el servidor MCP
│   ├── server.ts                  # Registro de las 5 tools con Zod schemas
│   ├── tools/
│   │   ├── buscar-articulos.ts    # Búsqueda híbrida (keyword + semántica)
│   │   ├── jurisprudencia.ts      # Búsqueda por descriptores SAIJ
│   │   ├── calcular-indem.ts      # Fórmulas LCT — 100% determinístico
│   │   ├── verificar-prescrip.ts  # Lógica de plazos por tipo de reclamo
│   │   └── norma-vigente.ts       # Lookup directo por ley + artículo
│   ├── services/
│   │   ├── hybrid-retriever.ts    # Orquesta keyword + semántico + merge
│   │   ├── keyword-matcher.ts     # Stemming español + match vs descriptores
│   │   ├── semantic-search.ts     # FAISS + embeddings bge-m3-es-legal
│   │   ├── legislation-store.ts   # Acceso a los JSONs de artículos
│   │   └── juris-search.ts        # Búsqueda en JSONL de jurisprudencia
│   └── data/
│       ├── legislacion/           # JSONs de leyes
│       ├── jurisprudencia/        # JSONL con fallos indexados por descriptores
│       ├── descriptores/          # Índice SAIJ (955 descriptores, 5,490 sinónimos)
│       └── embeddings/            # Vectores pre-generados (FAISS index)
├── scripts/
│   └── generate-embeddings.ts     # Genera vectores offline (corre una vez)
├── package.json
└── tsconfig.json
```

### Flujo de datos en runtime

Cuando un cliente MCP llama una tool, esto es lo que pasa:

```
Cliente MCP (Claude Desktop, tu app, etc.)
       │
       │  tool_call: "calcular_indemnizacion"
       │  args: { fecha_ingreso: "2020-03-15", ... }
       ▼
┌──────────────────────────────────────────┐
│  index.ts → server.ts                    │
│  Routing: identifica la tool y valida    │
│  el input contra el Zod schema          │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  tools/calcular-indem.ts                 │
│  Tool handler: ejecuta la lógica         │
│  específica de la tool                   │
│                                          │
│  Para calcular_indemnizacion:            │
│  → Aplica fórmulas del art. 245,        │
│    231, 232, 233, 123, 156 LCT          │
│  → Pura aritmética, cero IA             │
│                                          │
│  Para buscar_articulos:                  │
│  → Llama a hybrid-retriever.ts          │
│  → Keyword + semántico en paralelo      │
│  → Merge + ponderación por rama         │
│  → Enriquece con texto desde            │
│    legislation-store.ts                  │
└──────────────┬───────────────────────────┘
               ▼
┌──────────────────────────────────────────┐
│  services/ (capa de datos)               │
│                                          │
│  legislation-store.ts                    │
│    └── Lee JSONs de data/legislacion/    │
│                                          │
│  juris-search.ts                         │
│    └── Lee JSONL de data/jurisprudencia/ │
│                                          │
│  Datos cargados en memoria al iniciar    │
│  el servidor. Sin DB, sin filesystem     │
│  reads en cada request.                  │
└──────────────┬───────────────────────────┘
               ▼
       Respuesta JSON estructurada
       devuelta al cliente MCP
```

### El sistema de búsqueda híbrido

El componente más complejo del servidor. Explicado en detalle:

**Capa 1 — Keyword matching:**
Tokeniza el input, aplica stemming en español, y busca coincidencias contra 955 descriptores SAIJ y sus 5,490 sinónimos. Preciso con frases exactas ("despido sin causa" → match directo), pero pierde conceptos cuando las palabras no coinciden literalmente.

**Capa 2 — Búsqueda semántica:**
Usa el modelo `dariolopez/bge-m3-es-legal-tmp-6`, un modelo de embeddings fine-tuned en texto legal español. Los 5,490 textos de descriptores + sinónimos están pre-vectorizados en un índice FAISS. En cada query, solo se genera el embedding de la query entrante y se buscan los 15 vectores más cercanos por similitud coseno. Conecta conceptos sin match exacto ("accidente laboral" ≈ "riesgo de trabajo"), pero produce ruido con queries cortas.

**Capa 3 — Merge y ponderación:**
Combina ambos resultados tomando el score máximo por descriptor. Después aplica ponderación jerárquica **por rama** (no global), lo que permite que queries multi-concepto como "despido durante embarazo" devuelvan artículos de ambas ramas sin que una aplaste a la otra.

---

## Datos incluidos

| Ley | Nombre | Cobertura |
|-----|--------|-----------|
| Ley 20.744 | Ley de Contrato de Trabajo (LCT) | Artículos completos |
| Ley 24.557 | Ley de Riesgos del Trabajo (LRT) | Artículos completos |
| Ley 24.013 | Ley Nacional de Empleo | Arts. 8, 9, 10 (multas por no registro) |
| Ley 25.323 | Incremento indemnizatorio | Arts. 1, 2 |
| Ley 11.544 | Ley de Jornada de Trabajo | Artículos selectos |

Además: índice de 955 descriptores SAIJ con 5,490 sinónimos, y corpus de jurisprudencia laboral en formato JSONL con fallos taggeados por descriptores (prioridad: CABA y Provincia de Buenos Aires).

---

## Instalación y uso

### Con Claude Desktop

```json
{
  "mcpServers": {
    "ley-ar": {
      "command": "npx",
      "args": ["ley-ar"]
    }
  }
}
```

### Como cliente MCP programático

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({
  command: "npx",
  args: ["ley-ar"]
});

const client = new Client({ name: "mi-app", version: "1.0.0" });
await client.connect(transport);

// Ejemplo: calcular indemnización
const resultado = await client.callTool("calcular_indemnizacion", {
  fecha_ingreso: "2020-03-15",
  fecha_egreso: "2025-01-20",
  mejor_remuneracion: 1200000,
  causa: "sin_causa",
  registrado: true
});
```

---

## Desarrollo local

```bash
git clone https://github.com/tuusuario/ley-ar
cd ley-ar
npm install

# Generar embeddings (solo la primera vez, requiere el modelo descargado)
npm run generate-embeddings

# Iniciar en modo desarrollo
npm run dev

# Build
npm run build
```

### Agregar nueva legislación

1. Agregá el JSON de la ley en `src/data/legislacion/`:

```json
{
  "content": "texto del artículo",
  "metadata": {
    "article": "número",
    "chapter": "capítulo",
    "tags": ["descriptor1", "descriptor2"],
    "code": "nombre de la ley"
  }
}
```

2. Regenerá los embeddings:

```bash
npm run generate-embeddings
```

---

## Limitaciones conocidas

- **Tope CCT (art. 245):** No se calcula el tope indemnizatorio del convenio colectivo aplicable. El output incluye una advertencia explícita.
- **Intereses:** No se calculan intereses. El abogado debe aplicar la tasa activa del BNA desde la fecha de egreso.
- **Cobertura geográfica:** La jurisprudencia incluida prioriza CABA y Provincia de Buenos Aires.
- **Actualización de leyes:** El corpus refleja la legislación vigente al momento de la última actualización del paquete. Verificar artículos modificados por decreto.
- **Búsqueda semántica con queries cortas:** Con inputs de 1-2 palabras genéricas, la capa semántica puede producir ruido. La capa keyword compensa en esos casos.

---

## Roadmap

- [ ] v1.0 — Las 5 tools con LCT, LRT y leyes complementarias
- [ ] v1.1 — Cálculo de tope CCT por rama de actividad (convenios colectivos)
- [ ] v1.2 — Ampliación de corpus de jurisprudencia a otras jurisdicciones provinciales
- [ ] v1.3 — Soporte para despido con causa (validación de causales del art. 242 LCT)

---

## Proyectos que usan ley-ar

**[demanda-lab](https://github.com/tuusuario/demanda-lab)** — Generador de borradores de demandas laborales. El primer producto construido sobre esta infraestructura.

---

## Licencia

MIT — Libre para uso comercial y no comercial.

---

## Autor

<!-- TODO: Nombre, Twitter/X, LinkedIn -->

---

*¿Lo estás usando en producción? Abrí un issue o mandá un PR para aparecer en esta lista.*