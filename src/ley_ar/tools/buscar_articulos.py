from __future__ import annotations

from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.legislation_store import LegislationStore


def buscar_articulos(
    retriever: HybridRetriever,
    store: LegislationStore,
    tema: str,
    ley: str = None,
    max_resultados: int = 5,
    mod_service=None,
) -> dict:
    """Busqueda hibrida de articulos de legislacion laboral por tema en lenguaje natural.

    Args:
        tema: Descripcion del tema en lenguaje natural. Ej: "despido durante embarazo"
        ley: Filtro opcional por ley. Valores: "LCT", "LRT", "LdE", "LJT"
        max_resultados: Cantidad maxima de articulos a devolver. Default: 5
    """
    result = retriever.search(tema, top_k=max_resultados * 2)

    articles_raw = result["articles"]

    # Filtrar por ley si se especifico
    if ley:
        code = store._resolve_law(ley)
        articles_raw = [a for a in articles_raw if a["id"].startswith(code + "_")]

    # Enriquecer con texto completo
    articulos = []
    for art_info in articles_raw[:max_resultados]:
        art_data = store.get_by_id(art_info["id"])
        if not art_data:
            continue
        entry = {
            "ley": art_data["codigo_nombre"],
            "codigo": art_data["codigo"],
            "articulo": str(art_data["numero"]),
            "texto": art_data["contenido"],
            "capitulo": art_data["capitulo"],
            "seccion": art_data["seccion"],
            "relevancia": art_info["weighted_score"],
            "descriptores": [d["descriptor"] for d in art_info["from_descriptors"]],
        }
        if mod_service:
            art_id = art_info["id"]
            ann = mod_service.annotate(art_id)
            if ann:
                entry["modificaciones"] = ann
        articulos.append(entry)

    return {
        "articulos": articulos,
        "total_encontrados": len(articulos),
        "descriptores_usados": result["descriptors_matched"],
    }
