from __future__ import annotations

from ley_ar.services.legislation_store import LegislationStore


def norma_vigente(store: LegislationStore, ley: str, articulo: str, mod_service=None) -> dict:
    """Recupera el texto exacto de un articulo de legislacion laboral argentina.

    Args:
        ley: Nombre o numero de la ley. Valores: "LCT", "LRT", "24013", "25323", "11544"
        articulo: Numero del articulo. Ej: "245", "231"
    """
    resultado = store.get(ley, articulo)
    if not resultado:
        return {"error": f"No se encontro el articulo {articulo} de la ley {ley}"}

    result = {
        "ley": resultado["codigo_nombre"],
        "articulo": str(resultado["numero"]),
        "texto": resultado["contenido"],
        "capitulo": resultado["capitulo"],
        "seccion": resultado["seccion"],
    }
    if mod_service:
        mod = mod_service.annotate(resultado["id"])
        if mod:
            result["modificaciones"] = mod
    return result
