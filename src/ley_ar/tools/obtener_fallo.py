from __future__ import annotations

from ley_ar.services.juris_search import JurisprudenciaSearch


def obtener_fallo(
    juris: JurisprudenciaSearch,
    numero_sumario: str,
) -> dict:
    """Recupera el texto completo de un fallo especifico por su numero de sumario.

    Usar cuando se necesita el detalle de un fallo previamente encontrado
    con la tool de jurisprudencia.

    Args:
        numero_sumario: Identificador del fallo (campo numero_sumario de jurisprudencia)
    """
    fallo = juris.get_by_id(numero_sumario)
    if not fallo:
        return {"error": f"Fallo con numero de sumario '{numero_sumario}' no encontrado."}
    return fallo
