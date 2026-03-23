from __future__ import annotations

from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch
from ley_ar.services.case_analytics import CaseAnalytics


def analizar_caso(
    retriever: HybridRetriever,
    juris: JurisprudenciaSearch,
    caso: str,
    jurisdiccion: str = None,
    monto_inmediatos: float = None,
    monto_intereses: float = None,
    honorarios_pct: float = 20.0,
) -> dict:
    """Analiza estadisticamente la jurisprudencia relevante a un caso.

    Args:
        caso: Descripcion del caso en lenguaje natural
        jurisdiccion: Filtro opcional por provincia
        monto_inmediatos: Total de rubros inmediatos (de calcular_indemnizacion)
        monto_intereses: Intereses calculados. Default: 0.
        honorarios_pct: Porcentaje de honorarios del abogado. Default: 20.
    """
    result = retriever.search(caso)
    descriptor_scores = [
        (d["descriptor"], d["score"]) for d in result["descriptors_matched"]
    ]

    analytics = CaseAnalytics(juris)
    stats = analytics.analizar_caso(
        descriptor_scores,
        jurisdiccion=jurisdiccion,
    )

    stats["descriptores_usados"] = result["descriptors_matched"]

    if monto_inmediatos is not None:
        stats["costo_beneficio"] = CaseAnalytics.costo_beneficio(
            monto_inmediatos=monto_inmediatos,
            monto_intereses=monto_intereses or 0,
            tasa_exito=stats.get("tasa_exito_general"),
            honorarios_pct=honorarios_pct,
            jurisdiccion=jurisdiccion,
        )

    return stats
