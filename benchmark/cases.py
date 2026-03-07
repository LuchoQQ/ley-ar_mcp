"""
Casos de benchmark para evaluar calidad de retrieval.

Cada caso define:
- query: lo que el usuario/agente pediría
- expected_articles: artículos que DEBEN aparecer en el top N (por ID)
- expected_descriptors: descriptores que DEBERÍAN matchear (al menos algunos)
- juris_min_results: mínimo de fallos que jurisprudencia debería devolver
- juris_expected_terms: términos que deberían aparecer en los descriptores de los fallos

Para agregar un caso:
1. Pensá en un caso real que un abogado consultaría
2. Determiná manualmente qué artículos aplican
3. Corré el benchmark, mirá qué devuelve, ajustá expected si el resultado es correcto
"""

ARTICULOS_CASES = [
    {
        "id": "despido_sin_causa_basico",
        "query": "despido sin causa indemnización",
        "top_k": 7,
        "expected_articles": ["LCT_245", "LCT_232", "LCT_233"],
        "expected_any_of": ["LCT_231", "LCT_247"],
    },
    {
        "id": "despido_embarazo",
        "query": "despido durante embarazo protección maternidad",
        "top_k": 7,
        "expected_articles": ["LCT_178", "LCT_182"],
        "expected_any_of": ["LCT_177", "LCT_183"],
    },
    {
        "id": "trabajo_no_registrado",
        "query": "trabajo no registrado empleo clandestino",
        "top_k": 7,
        "expected_articles": ["LdE_8"],
        "expected_any_of": ["LdE_9", "LdE_10", "LdE_11", "LdE_15"],
    },
    {
        "id": "preaviso",
        "query": "preaviso extinción contrato de trabajo plazos",
        "top_k": 5,
        "expected_articles": ["LCT_231", "LCT_232"],
        "expected_any_of": ["LCT_233"],
    },
    {
        "id": "jornada_trabajo",
        "query": "jornada de trabajo horas extras límite horario",
        "top_k": 5,
        "expected_articles": [],
        "expected_any_of": ["LJT_1", "LJT_2", "LJT_3", "LCT_196", "LCT_197", "LCT_201"],
    },
    {
        "id": "accidente_trabajo",
        "query": "accidente de trabajo incapacidad riesgos laborales",
        "top_k": 7,
        "expected_articles": [],
        "expected_any_of": ["LRT_6", "LRT_8", "LRT_11", "LRT_14"],
    },
    {
        "id": "periodo_prueba",
        "query": "período de prueba contrato de trabajo",
        "top_k": 5,
        "expected_articles": ["LCT_92"],
        "expected_any_of": [],
    },
    {
        "id": "vacaciones",
        "query": "vacaciones licencia anual ordinaria",
        "top_k": 5,
        "expected_articles": ["LCT_150"],
        "expected_any_of": ["LCT_151", "LCT_152", "LCT_153", "LCT_155", "LCT_156"],
    },
    {
        "id": "despido_causa",
        "query": "despido con justa causa injuria laboral",
        "top_k": 5,
        "expected_articles": ["LCT_242", "LCT_243"],
        "expected_any_of": [],
    },
    {
        "id": "remuneracion",
        "query": "remuneración salario concepto sueldo",
        "top_k": 5,
        "expected_articles": ["LCT_103"],
        "expected_any_of": ["LCT_104", "LCT_105", "LCT_106"],
    },
    {
        "id": "despido_discriminatorio",
        "query": "despido discriminatorio actividad sindical represalia",
        "top_k": 7,
        "expected_articles": [],
        "expected_any_of": ["LCT_17", "LCT_47", "LCT_52"],
    },
    {
        "id": "sac_aguinaldo",
        "query": "sueldo anual complementario aguinaldo",
        "top_k": 5,
        "expected_articles": ["LCT_121", "LCT_122"],
        "expected_any_of": ["LCT_123"],
    },
]

JURISPRUDENCIA_CASES = [
    {
        "id": "juris_despido_no_registrado",
        "query": "despido sin causa trabajador no registrado indemnización agravada",
        "max_resultados": 5,
        "min_results": 2,
        "expected_descriptor_overlap": ["despido sin justa causa", "empleo no registrado"],
    },
    {
        "id": "juris_despido_embarazo",
        "query": "despido durante embarazo presunción protección maternidad",
        "max_resultados": 5,
        "min_results": 1,
        "expected_descriptor_overlap": [],
    },
    {
        "id": "juris_accidente",
        "query": "accidente de trabajo incapacidad riesgos indemnización",
        "max_resultados": 5,
        "min_results": 1,
        "expected_descriptor_overlap": [],
    },
    {
        "id": "juris_despido_basico",
        "query": "despido sin causa antigüedad indemnización",
        "max_resultados": 5,
        "min_results": 2,
        "expected_descriptor_overlap": ["despido sin justa causa"],
    },
    {
        "id": "juris_horas_extras",
        "query": "horas extras jornada trabajo diferencias salariales",
        "max_resultados": 5,
        "min_results": 1,
        "expected_descriptor_overlap": [],
    },
]
