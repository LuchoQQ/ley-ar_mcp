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
    "enfermedad_profesional": {
        "anos": 2,
        "fundamento": "Art. 44 LRT",
        "nota": "El plazo se computa desde la toma de conocimiento de la enfermedad y su relacion con el trabajo. La determinacion del dies a quo es materia de prueba.",
    },
    "acoso_laboral": {
        "anos": 2,
        "fundamento": "Art. 256 LCT (por analogia) y legislacion local aplicable",
        "nota": "El plazo se computa desde el ultimo acto de acoso o desde la extincion del vinculo. Verificar legislacion provincial aplicable (ej: Ley 1225 CABA).",
    },
}

# Plazos procesales (no son prescripcion, sino caducidad o plazos de ejercicio)
_PLAZOS_PROCESALES = {
    "intimacion_registro": {
        "dias": 30,
        "tipo_dias": "corridos",
        "fundamento": "Art. 11 Ley 24.013",
        "descripcion": "Plazo que tiene el empleador para registrar la relacion laboral tras recibir el telegrama de intimacion.",
        "desde": "recepcion del telegrama por el empleador",
    },
    "certificados_art80": {
        "dias": 30,
        "tipo_dias": "habiles",
        "fundamento": "Art. 80 LCT + Dec. 146/01",
        "descripcion": "Plazo que tiene el empleador para entregar certificados de trabajo tras ser intimado. Vencido sin entrega, nace el derecho a la multa de 3 sueldos.",
        "desde": "intimacion fehaciente al empleador",
    },
    "pago_indemnizacion": {
        "dias": 4,
        "tipo_dias": "habiles",
        "fundamento": "Art. 149 LCT (por analogia jurisprudencial)",
        "descripcion": "Plazo razonable para que el empleador pague las indemnizaciones tras ser intimado. Vencido sin pago, se activa el recargo del art. 2 Ley 25.323.",
        "desde": "recepcion de la carta documento reclamando pago",
    },
    "seclo_audiencia": {
        "dias": 10,
        "tipo_dias": "habiles",
        "fundamento": "Ley 24.635 y Res. 899/04",
        "descripcion": "Plazo tipico para la primera audiencia en SECLO desde la presentacion del reclamo.",
        "desde": "presentacion del formulario de reclamo en SECLO",
    },
    "contestacion_demanda": {
        "dias": 10,
        "tipo_dias": "habiles",
        "fundamento": "Art. 71 Ley 18.345 (Procedimiento Laboral CABA)",
        "descripcion": "Plazo para contestar demanda en fuero laboral de CABA. Verificar ley procesal de la jurisdiccion aplicable.",
        "desde": "notificacion de la demanda",
    },
    "apelacion": {
        "dias": 6,
        "tipo_dias": "habiles",
        "fundamento": "Art. 116 Ley 18.345 (Procedimiento Laboral CABA)",
        "descripcion": "Plazo para apelar sentencia definitiva en fuero laboral de CABA. Verificar ley procesal de la jurisdiccion aplicable.",
        "desde": "notificacion de la sentencia",
    },
    "copia_telegrama_afip": {
        "dias": 24,
        "tipo_dias": "horas",
        "fundamento": "Art. 11 Ley 24.013",
        "descripcion": "Plazo para remitir copia del telegrama de intimacion de registro a la AFIP. Requisito para la procedencia de las multas de la Ley 24.013.",
        "desde": "envio del telegrama al empleador",
    },
}


def verificar_prescripcion(
    tipo_reclamo: str,
    fecha_hecho: str,
    fecha_consulta: str = None,
) -> dict:
    """Verifica si una accion laboral esta prescripta segun la legislacion argentina.

    Args:
        tipo_reclamo: Tipo de accion. Valores: "despido", "diferencias_salariales", "accidente", "multas_registro", "enfermedad_profesional", "acoso_laboral"
        fecha_hecho: Fecha del hecho que origina el reclamo (YYYY-MM-DD)
        fecha_consulta: Fecha de consulta (YYYY-MM-DD). Default: hoy
    """
    if tipo_reclamo not in _PLAZOS:
        return {
            "error": f"Tipo de reclamo no reconocido: {tipo_reclamo}. Valores validos: {list(_PLAZOS.keys())}"
        }

    try:
        hecho = date.fromisoformat(fecha_hecho)
    except (ValueError, TypeError):
        return {"error": f"fecha_hecho invalida: '{fecha_hecho}'. Formato esperado: YYYY-MM-DD"}

    try:
        consulta = date.fromisoformat(fecha_consulta) if fecha_consulta else date.today()
    except (ValueError, TypeError):
        return {"error": f"fecha_consulta invalida: '{fecha_consulta}'. Formato esperado: YYYY-MM-DD"}

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


def consultar_plazos_procesales(tipo_plazo: str = None) -> dict:
    """Consulta plazos procesales laborales (caducidad, intimaciones, terminos judiciales).

    Estos NO son plazos de prescripcion, sino plazos de ejercicio para acciones
    especificas dentro de un caso laboral.

    Args:
        tipo_plazo: Tipo de plazo. Si se omite, lista todos los disponibles.
            Valores: "intimacion_registro", "certificados_art80", "pago_indemnizacion",
            "seclo_audiencia", "contestacion_demanda", "apelacion", "copia_telegrama_afip"
    """
    if tipo_plazo:
        if tipo_plazo not in _PLAZOS_PROCESALES:
            return {
                "error": f"Tipo de plazo no reconocido: {tipo_plazo}. Valores validos: {list(_PLAZOS_PROCESALES.keys())}"
            }
        plazo = _PLAZOS_PROCESALES[tipo_plazo]
        return {
            "tipo": tipo_plazo,
            **plazo,
        }

    return {
        "plazos": [
            {"tipo": k, **v}
            for k, v in _PLAZOS_PROCESALES.items()
        ],
        "total": len(_PLAZOS_PROCESALES),
        "nota": "Estos son plazos procesales de referencia. Los plazos judiciales pueden variar segun la jurisdiccion y la ley procesal aplicable. Verificar siempre con la normativa local.",
    }
