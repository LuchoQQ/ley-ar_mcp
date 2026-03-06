from __future__ import annotations

from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch


def jurisprudencia(
    retriever: HybridRetriever,
    juris: JurisprudenciaSearch,
    caso: str,
    jurisdiccion: str = None,
    max_resultados: int = 3,
) -> dict:
    """Busca jurisprudencia laboral relevante a un caso descrito en lenguaje natural.

    Args:
        caso: Descripcion del caso en lenguaje natural
        jurisdiccion: Filtro opcional. Ej: "Buenos Aires", "CABA"
        max_resultados: Cantidad maxima de fallos a devolver. Default: 3
    """
    result = retriever.search(caso)
    descriptor_scores = [
        (d["descriptor"], d["score"]) for d in result["descriptors_matched"]
    ]

    fallos = juris.search(
        descriptor_scores,
        top_k=max_resultados,
        jurisdiccion=jurisdiccion,
    )

    return {
        "fallos": fallos,
        "total_encontrados": len(fallos),
        "descriptores_usados": result["descriptors_matched"],
    }
