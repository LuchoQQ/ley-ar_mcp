from __future__ import annotations

from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.juris_search import JurisprudenciaSearch


def jurisprudencia(
    retriever: HybridRetriever,
    juris: JurisprudenciaSearch,
    caso: str = None,
    caratula: str = None,
    jurisdiccion: str = None,
    max_resultados: int = 3,
) -> dict:
    """Busca jurisprudencia laboral relevante a un caso.

    Dos modos de busqueda:
    - Por caso (lenguaje natural): usa descriptores tematicos para encontrar fallos relevantes.
      Funciona mejor con descripciones conceptuales del caso.
    - Por caratula (nombre del caso): busca por texto en el nombre del fallo.
      Util para fallos emblematicos (ej: "Vizzoti", "Aquino", "Madorrán").

    Debe informarse al menos uno de los dos: caso o caratula.

    Args:
        caso: Descripcion del caso en lenguaje natural
        caratula: Texto a buscar en el nombre del fallo
        jurisdiccion: Filtro opcional. Ej: "Buenos Aires", "CABA"
        max_resultados: Cantidad maxima de fallos a devolver. Default: 3
    """
    if not caso and not caratula:
        return {"error": "Debe informarse al menos 'caso' (busqueda tematica) o 'caratula' (busqueda por nombre del fallo)."}

    if caratula:
        fallos = juris.search_by_caratula(
            caratula,
            top_k=max_resultados,
            jurisdiccion=jurisdiccion,
        )
        return {
            "fallos": fallos,
            "total_encontrados": len(fallos),
            "modo_busqueda": "caratula",
        }

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
        "modo_busqueda": "descriptores",
    }
