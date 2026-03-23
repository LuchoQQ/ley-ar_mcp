# ley-ar

Servidor [MCP](https://modelcontextprotocol.io) (Model Context Protocol) de legislacion laboral argentina. Expone herramientas que cualquier LLM compatible con MCP puede usar para buscar articulos, calcular indemnizaciones, consultar jurisprudencia y verificar plazos de prescripcion.

Toda la busqueda y el calculo corren localmente — sin llamadas a APIs externas.

Publicado en [PyPI](https://pypi.org/project/ley-ar/).

## Instalacion

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/).

### Claude Desktop

En el archivo de configuracion de Claude Desktop:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

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

Reiniciar Claude Desktop. La primera vez descarga automaticamente los datos pesados (~55MB).

### Claude Code

```bash
claude mcp add ley-ar -- uvx ley-ar
```

### Otros clientes MCP

Cualquier cliente compatible con MCP puede usar ley-ar. El comando es `uvx ley-ar` (stdio transport).

## Tools

| Tool | Que hace | Tipo |
|------|----------|------|
| `buscar_articulos` | Busqueda hibrida (keyword + semantica) por tema en lenguaje natural | Busqueda |
| `jurisprudencia` | Fallos laborales relevantes a un caso | Busqueda |
| `analizar_caso` | Estadisticas de jurisprudencia: tasa de exito, tendencia temporal, costo-beneficio | Analisis |
| `calcular_indemnizacion` | Rubros indemnizatorios de un despido con trazabilidad legal completa | Deterministica |
| `verificar_prescripcion` | Verifica si una accion laboral esta prescripta | Deterministica |
| `norma_vigente` | Texto exacto de un articulo por ley + numero | Lookup |
| `generar_documento` | Genera telegramas, cartas documento y liquidaciones desde templates | Generacion |

### buscar_articulos

Busqueda hibrida que combina keyword matching (stemming espanol + 955 descriptores SAIJ) con busqueda semantica (modelo legal fine-tuned + FAISS). Devuelve articulos con texto completo ordenados por relevancia.

```
Input:  tema="despido durante embarazo"
```
```json
{
  "articulos": [
    {
      "ley": "Ley de Contrato de Trabajo",
      "numero": "178",
      "texto": "Se presume, salvo prueba en contrario, que el despido...",
      "capitulo": "De la proteccion de la maternidad",
      "relevancia": 0.85,
      "descriptores": ["despido discriminatorio", "proteccion de la maternidad"]
    }
  ],
  "descriptores_usados": [...]
}
```

### jurisprudencia

Busca fallos laborales por overlap de descriptores SAIJ. Prioriza fallos recientes (boost por recencia). Corpus de 57,349 fallos.

```
Input:  caso="despido durante embarazo", jurisdiccion="Buenos Aires"
```
```json
{
  "fallos": [
    {
      "caratula": "Rodriguez c/ Empresa S.A. s/ despido",
      "sumario": "Se hace lugar al reclamo de la actora...",
      "fecha": "2023-05-15",
      "provincia": "Buenos Aires",
      "descriptores_comun": ["despido discriminatorio", "proteccion de la maternidad"],
      "score": 0.72
    }
  ]
}
```

### calcular_indemnizacion

Calculo 100% deterministico. Cada monto es trazable a un articulo y una formula. Los rubros se clasifican segun su exigibilidad procesal.

```
Input:  fecha_ingreso="2020-03-01", fecha_egreso="2024-09-15",
        mejor_remuneracion=500000, causa="sin_causa",
        registrado=false, preaviso_otorgado=false
```
```json
{
  "rubros_inmediatos": {
    "indemnizacion_antiguedad": { "monto": 2500000, "articulo": "245 LCT", "calculo": "500000 x 5 periodos" },
    "preaviso": { "monto": 500000, "articulo": "231-232 LCT" },
    "integracion_mes": { "monto": 250000, "articulo": "233 LCT" },
    "sac_proporcional": { "monto": 208333, "articulo": "123 LCT" },
    "vacaciones_proporcionales": { "monto": 140000, "articulo": "156 LCT" },
    "sac_sobre_preaviso": { "monto": 41667, "articulo": "121 LCT" },
    "duplicacion_no_registro": { "monto": 2500000, "articulo": "1 Ley 25.323" }
  },
  "rubros_requiere_intimacion": { "...": "arts. 8, 9, 10, 15 Ley 24.013" },
  "rubros_apercibimiento": { "...": "art. 2 Ley 25.323" },
  "total": 6140000,
  "advertencias": ["No se aplico tope del CCT (art. 245)", "No incluye intereses"]
}
```

Parametros opcionales: `fecha_intimacion`, `remuneracion_registrada`, `fecha_registro_falsa` (para calcular multas por deficiente registracion).

### verificar_prescripcion

Plazos por tipo de reclamo: despido, diferencias salariales, accidente, multas por no registro. Alerta si quedan menos de 6 meses.

```
Input:  tipo_reclamo="despido", fecha_hecho="2024-09-01"
```
```json
{
  "prescripto": false,
  "fecha_limite": "2026-09-01",
  "dias_restantes": 162,
  "fundamento": "Art. 256 LCT - plazo de 2 anos desde extincion del vinculo"
}
```

### norma_vigente

Lookup directo al texto de un articulo. Acepta aliases: "LCT", "20744", "ley 20.744", etc.

```
Input:  ley="LCT", articulo="245"
Output: texto completo del articulo, capitulo, seccion
```

## Datos incluidos

| Ley | Nombre | Articulos |
|-----|--------|-----------|
| Ley 20.744 | Ley de Contrato de Trabajo (LCT) | 270 |
| Ley 24.557 | Ley de Riesgos del Trabajo (LRT) | 51 |
| Ley 24.013 | Ley Nacional de Empleo (LdE) | 159 |
| Ley 11.544 | Ley de Jornada de Trabajo (LJT) | 12 |
| Ley 25.323 | Incremento indemnizatorio | 2 |
| Ley 23.345 | Asociaciones sindicales | 52 |
| Ley 25.551 | Compre trabajo argentino | 65 |

Ademas: indice de 955 descriptores SAIJ con 5,490 sinonimos, 57,349 fallos de jurisprudencia laboral (prioridad CABA y Buenos Aires), y vectores pre-generados con modelo legal fine-tuned.

## Limitaciones

- Tope del CCT (art. 245): soportado si se informa el convenio colectivo, pero no todos los CCT estan cargados.
- Intereses: se calculan internamente (tasa activa BNA por semestre) pero no se exponen como tool independiente.
- Jurisprudencia prioriza CABA y Buenos Aires.
- Legislacion vigente al momento de la ultima actualizacion del paquete.

## Desarrollo local

```bash
git clone https://github.com/LuchoQQ/ley-ar_mcp
cd ley-ar_mcp
pip install -e .

# Los datos pesados se descargan automaticamente al primer uso.

# Tests
pytest tests/ -v
```

## Licencia

MIT
