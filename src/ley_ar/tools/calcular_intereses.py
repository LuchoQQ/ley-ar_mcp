from __future__ import annotations

from ley_ar.services.intereses import calcular_intereses as _calc_intereses


def calcular_intereses(
    monto_base: float,
    fecha_desde: str,
    fecha_hasta: str = None,
) -> dict:
    """Calcula intereses a tasa activa del Banco Nacion Argentina sobre un monto.

    Usa interes simple, calculado mes a mes con la tasa vigente de cada periodo.
    Util para actualizar montos adeudados entre la fecha de despido y la fecha
    de liquidacion o sentencia.

    Args:
        monto_base: Capital sobre el que se calculan intereses
        fecha_desde: Fecha de inicio del devengamiento (YYYY-MM-DD)
        fecha_hasta: Fecha de calculo (YYYY-MM-DD). Default: hoy
    """
    return _calc_intereses(monto_base, fecha_desde, fecha_hasta)
