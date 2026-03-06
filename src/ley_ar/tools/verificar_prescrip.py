from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

_PLAZOS = {
    "despido": {
        "anos": 2,
        "fundamento": "Art. 256 LCT",
        "nota": "El plazo se computa desde la fecha de extincion del vinculo laboral.",
    },
    "diferencias_salariales": {
        "anos": 2,
        "fundamento": "Art. 256 LCT",
        "nota": "El plazo se computa desde que cada credito salarial es exigible.",
    },
    "accidente": {
        "anos": 2,
        "fundamento": "Art. 44 LRT",
        "nota": "El plazo se computa desde que la victima tuvo conocimiento de la incapacidad. El momento exacto de inicio puede variar segun jurisprudencia. Verificar con abogado.",
    },
    "multas_registro": {
        "anos": 2,
        "fundamento": "Art. 256 LCT",
        "nota": "El plazo se computa desde la fecha de extincion del vinculo laboral.",
    },
}


def verificar_prescripcion(
    tipo_reclamo: str,
    fecha_hecho: str,
    fecha_consulta: str = None,
) -> dict:
    """Verifica si una accion laboral esta prescripta segun la legislacion argentina.

    Args:
        tipo_reclamo: Tipo de accion. Valores: "despido", "diferencias_salariales", "accidente", "multas_registro"
        fecha_hecho: Fecha del hecho que origina el reclamo (YYYY-MM-DD)
        fecha_consulta: Fecha de consulta (YYYY-MM-DD). Default: hoy
    """
    if tipo_reclamo not in _PLAZOS:
        return {
            "error": f"Tipo de reclamo no reconocido: {tipo_reclamo}. Valores validos: {list(_PLAZOS.keys())}"
        }

    hecho = date.fromisoformat(fecha_hecho)
    consulta = date.fromisoformat(fecha_consulta) if fecha_consulta else date.today()

    plazo = _PLAZOS[tipo_reclamo]
    fecha_limite = hecho + relativedelta(years=plazo["anos"])
    dias_restantes = (fecha_limite - consulta).days

    advertencia = plazo["nota"]
    if 0 < dias_restantes < 180:
        advertencia = (
            f"Quedan menos de 6 meses ({dias_restantes} dias). "
            f"Considerar iniciar accion judicial con urgencia. {plazo['nota']}"
        )

    return {
        "prescripto": dias_restantes <= 0,
        "plazo_total": f"{plazo['anos']} anos",
        "fecha_limite": fecha_limite.isoformat(),
        "dias_restantes": max(0, dias_restantes),
        "fundamento": plazo["fundamento"],
        "advertencia": advertencia,
    }
