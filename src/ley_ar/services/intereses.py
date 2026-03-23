"""
Calculo de intereses sobre rubros laborales.
Tasa activa BNA (Banco Nacion Argentina) - tabla historica por semestre.

Los valores son promedios semestrales de la tasa activa BNA para operaciones
de descuento a 30 dias. Fuente: BCRA / BNA.
"""

from __future__ import annotations

from datetime import date
from typing import Dict

# Tasa nominal anual promedio por semestre (TNA %).
# Cada entry: (ano, semestre) -> tasa_anual_promedio
# Semestre 1 = ene-jun, semestre 2 = jul-dic
TASAS_BNA: Dict[tuple, float] = {
    (2018, 1): 29.0,
    (2018, 2): 48.0,
    (2019, 1): 55.0,
    (2019, 2): 65.0,
    (2020, 1): 38.0,
    (2020, 2): 34.0,
    (2021, 1): 38.0,
    (2021, 2): 40.0,
    (2022, 1): 48.0,
    (2022, 2): 72.0,
    (2023, 1): 78.0,
    (2023, 2): 100.0,
    (2024, 1): 80.0,
    (2024, 2): 50.0,
    (2025, 1): 37.0,
    (2025, 2): 35.0,
    (2026, 1): 33.0,
}

# Tasa por defecto si no hay dato para un semestre
TASA_DEFAULT = 37.0


def _tasa_semestre(year: int, month: int) -> float:
    """Retorna la TNA para un mes dado."""
    semestre = 1 if month <= 6 else 2
    return TASAS_BNA.get((year, semestre), TASA_DEFAULT)


def calcular_intereses(
    monto_base: float,
    fecha_desde: str,
    fecha_hasta: str = None,
) -> dict:
    """Calcula intereses a tasa activa BNA sobre un monto base.

    Metodo: interes simple, calculado mes a mes con la tasa vigente de cada periodo.

    Args:
        monto_base: Monto sobre el que se calculan intereses
        fecha_desde: Fecha de inicio del devengamiento (YYYY-MM-DD), tipicamente fecha de egreso
        fecha_hasta: Fecha de calculo (YYYY-MM-DD). Default: hoy
    """
    desde = date.fromisoformat(fecha_desde)
    hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else date.today()

    if hasta <= desde:
        return {
            "monto_intereses": 0,
            "monto_con_intereses": round(monto_base, 2),
            "dias": 0,
            "detalle_periodos": [],
            "metodo": "Tasa activa BNA - interes simple por semestre",
            "advertencia": "Fecha de calculo anterior o igual a fecha de inicio.",
        }

    total_dias = (hasta - desde).days
    intereses_acumulados = 0.0
    detalle = []

    current = desde
    while current < hasta:
        if current.month == 12:
            fin_mes = date(current.year + 1, 1, 1)
        else:
            fin_mes = date(current.year, current.month + 1, 1)

        fin_periodo = min(fin_mes, hasta)
        dias_periodo = (fin_periodo - current).days

        tna = _tasa_semestre(current.year, current.month)
        interes_periodo = monto_base * (tna / 100) / 365 * dias_periodo
        intereses_acumulados += interes_periodo

        detalle.append({
            "periodo": f"{current.isoformat()} a {fin_periodo.isoformat()}",
            "dias": dias_periodo,
            "tna": tna,
            "interes": round(interes_periodo, 2),
        })

        current = fin_periodo

    return {
        "monto_base": round(monto_base, 2),
        "monto_intereses": round(intereses_acumulados, 2),
        "monto_con_intereses": round(monto_base + intereses_acumulados, 2),
        "dias_totales": total_dias,
        "fecha_desde": fecha_desde,
        "fecha_hasta": hasta.isoformat(),
        "detalle_periodos": detalle,
        "metodo": "Tasa activa BNA - interes simple mensual",
        "advertencia": "Tasas promedio semestrales. Verificar tasa exacta aplicable segun jurisdiccion y juzgado. Algunos tribunales aplican capitalizacion.",
    }
