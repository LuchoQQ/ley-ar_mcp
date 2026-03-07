# ley-ar

Servidor MCP de legislacion laboral argentina. Expone 5 herramientas que cualquier LLM compatible con [Model Context Protocol](https://modelcontextprotocol.io) puede usar para buscar articulos, calcular indemnizaciones, consultar jurisprudencia y verificar plazos de prescripcion.

Publicado en [PyPI](https://pypi.org/project/ley-ar/).

## Instalacion

Requiere [uv](https://docs.astral.sh/uv/getting-started/installation/).

En `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

## Tools

| Tool | Que hace | Deterministica |
|------|----------|----------------|
| `norma_vigente` | Texto exacto de un articulo por ley + numero | Si |
| `buscar_articulos` | Busqueda hibrida (keyword + semantica) por tema en lenguaje natural | Parcial (usa embeddings locales) |
| `jurisprudencia` | Fallos laborales relevantes a un caso | Si |
| `calcular_indemnizacion` | Rubros indemnizatorios de un despido (7 rubros + multas) | Si |
| `verificar_prescripcion` | Verifica si una accion laboral esta prescripta | Si |

### norma_vigente

Lookup directo al texto de un articulo. Acepta aliases: "LCT", "20744", "ley 20.744", etc.

```
Input:  ley="LCT", articulo="245"
Output: texto completo del articulo, capitulo, seccion
```

### buscar_articulos

Busqueda hibrida que combina keyword matching (stemming espanol + 955 descriptores SAIJ) con busqueda semantica (modelo `bge-m3-es-legal` + FAISS). Devuelve articulos con texto completo ordenados por relevancia.

```
Input:  tema="despido durante embarazo"
Output: LCT_245, LCT_178, LCT_182 con texto, capitulo y descriptores
```

### jurisprudencia

Busca fallos por overlap de descriptores SAIJ. Prioriza fallos recientes (boost por recencia). Corpus de 57,349 fallos laborales.

```
Input:  caso="despido durante embarazo", jurisdiccion="Buenos Aires"
Output: fallos con caratula, sumario, fecha, provincia y score
```

### calcular_indemnizacion

Aplica las formulas de la LCT. Cada monto es trazable a un articulo.

```
Input:  fecha_ingreso, fecha_egreso, mejor_remuneracion, causa, registrado, preaviso_otorgado
Output: 7 rubros desglosados con monto, calculo y fundamento legal + total + advertencias
```

Rubros: indemnizacion por antiguedad (art. 245), preaviso (arts. 231-232), integracion mes (art. 233), SAC proporcional (art. 123), vacaciones proporcionales (art. 156), SAC sobre preaviso (art. 121), multa ley 25.323 art. 2 (si no registrado).

### verificar_prescripcion

Plazos por tipo de reclamo: despido, diferencias salariales, accidente, multas por no registro. Alerta si quedan menos de 6 meses.

```
Input:  tipo_reclamo="despido", fecha_hecho="2024-09-01"
Output: prescripto (bool), dias_restantes, fecha_limite, fundamento
```

## Datos incluidos

| Ley | Nombre | Articulos |
|-----|--------|-----------|
| Ley 20.744 | Ley de Contrato de Trabajo (LCT) | 270 |
| Ley 24.557 | Ley de Riesgos del Trabajo (LRT) | 51 |
| Ley 24.013 | Ley Nacional de Empleo (LdE) | 159 |
| Ley 11.544 | Ley de Jornada de Trabajo (LJT) | 12 |
| Ley 25.323 | Incremento indemnizatorio | 2 |

Ademas: indice de 955 descriptores SAIJ con 5,490 sinonimos, 57,349 fallos de jurisprudencia laboral (prioridad CABA y Buenos Aires), y vectores pre-generados con modelo legal fine-tuned.

## Limitaciones

- No calcula tope del CCT (art. 245). El output advierte.
- No calcula intereses.
- Jurisprudencia prioriza CABA y Buenos Aires.
- Legislacion vigente al momento de la ultima actualizacion del paquete.

## Desarrollo local

```bash
git clone https://github.com/LuchoQQ/ley-ar_mcp
cd ley-ar_mcp
pip install -e .

# Los datos pesados se descargan automaticamente al primer uso.
# Para desarrollo, copiar manualmente a src/ley_ar/data/

# Tests
pytest tests/ -v
```

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para detalles tecnicos del sistema de busqueda, formulas de calculo y flujo de datos.

## Licencia

MIT
