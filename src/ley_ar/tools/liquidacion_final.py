from __future__ import annotations

import calendar
from datetime import date
from dateutil.relativedelta import relativedelta


def liquidacion_final(
    fecha_ingreso: str,
    fecha_egreso: str,
    remuneracion: float,
    motivo: str = "renuncia",
    dias_vacaciones_gozadas: int = 0,
) -> dict:
    """Calcula la liquidacion final de un trabajador SIN rubros indemnizatorios.

    Para casos de renuncia, jubilacion, fin de contrato a plazo fijo, o
    acuerdo mutuo. Si el caso es un despido, usar calcular_indemnizacion
    que incluye estos rubros mas los indemnizatorios.

    Args:
        fecha_ingreso: Fecha de inicio de la relacion laboral (YYYY-MM-DD)
        fecha_egreso: Fecha de finalizacion (YYYY-MM-DD)
        remuneracion: Ultima remuneracion mensual bruta
        motivo: Motivo de egreso: "renuncia", "jubilacion", "mutuo_acuerdo",
            "fin_contrato_plazo_fijo", "fallecimiento". Default: "renuncia"
        dias_vacaciones_gozadas: Dias de vacaciones ya gozadas en el anio. Default: 0
    """
    ingreso = date.fromisoformat(fecha_ingreso)
    egreso = date.fromisoformat(fecha_egreso)
    rem = remuneracion

    delta = relativedelta(egreso, ingreso)
    anos = delta.years
    meses = delta.months
    dias_delta = delta.days

    rubros = {}

    # 1. Dias trabajados del mes de egreso (proporcional)
    dias_mes = calendar.monthrange(egreso.year, egreso.month)[1]
    dias_trabajados_mes = egreso.day
    sueldo_proporcional = (rem / 30) * dias_trabajados_mes

    rubros["dias_trabajados"] = {
        "monto": round(sueldo_proporcional, 2),
        "calculo": f"{dias_trabajados_mes} dias x (${rem:,.0f} / 30)",
        "fundamento": "Art. 137 LCT - salario proporcional al tiempo trabajado",
    }

    # 2. SAC proporcional (Art. 123 LCT)
    if egreso.month <= 6:
        inicio_semestre = date(egreso.year, 1, 1)
    else:
        inicio_semestre = date(egreso.year, 7, 1)
    dias_semestre = (egreso - inicio_semestre).days + 1
    sac_prop = (rem / 2) * (dias_semestre / 180)

    rubros["sac_proporcional"] = {
        "monto": round(sac_prop, 2),
        "calculo": f"(${rem:,.0f} / 2) x ({dias_semestre} dias / 180)",
        "fundamento": "Art. 123 LCT",
    }

    # 3. Vacaciones proporcionales (Art. 156 LCT)
    if anos >= 20:
        dias_vac_anual = 35
    elif anos >= 10:
        dias_vac_anual = 28
    elif anos >= 5:
        dias_vac_anual = 21
    else:
        dias_vac_anual = 14

    inicio_anio = max(ingreso, date(egreso.year, 1, 1))
    dias_trabajados_anio = (egreso - inicio_anio).days + 1
    dias_vac_proporcional = dias_trabajados_anio / 20
    dias_vac_proporcional = min(dias_vac_proporcional, dias_vac_anual * dias_trabajados_anio / 365)
    dias_vac_proporcional = max(dias_vac_proporcional - dias_vacaciones_gozadas, 0)
    # Art. 155 LCT: valor dia de vacacion = rem / 25
    vac_prop = dias_vac_proporcional * (rem / 25)

    rubros["vacaciones_proporcionales"] = {
        "monto": round(vac_prop, 2),
        "calculo": f"{dias_vac_proporcional:.1f} dias x (${rem:,.0f} / 25)",
        "fundamento": "Art. 156 LCT (proporcional), Art. 155 LCT (valor dia = rem/25)",
        "detalle": {
            "dias_vac_anual_por_antiguedad": dias_vac_anual,
            "dias_trabajados_anio": dias_trabajados_anio,
            "dias_vacaciones_gozadas": dias_vacaciones_gozadas,
            "dias_proporcionales_netos": round(dias_vac_proporcional, 1),
        },
    }

    # 4. SAC sobre vacaciones (Art. 121 LCT)
    sac_sobre_vac = vac_prop / 12
    rubros["sac_sobre_vacaciones"] = {
        "monto": round(sac_sobre_vac, 2),
        "calculo": f"${vac_prop:,.0f} / 12",
        "fundamento": "Art. 121 LCT",
    }

    # Rubros adicionales por motivo
    if motivo == "fallecimiento":
        # Art. 248 LCT: indemnizacion por fallecimiento = 50% de art. 245
        periodos = anos
        if meses > 3 or (meses == 3 and dias_delta > 0):
            periodos += 1
        periodos = max(periodos, 1)
        indem_fallecimiento = (rem * periodos) * 0.5

        rubros["indemnizacion_fallecimiento"] = {
            "monto": round(indem_fallecimiento, 2),
            "calculo": f"50% x ({periodos} periodos x ${rem:,.0f})",
            "fundamento": "Art. 248 LCT - indemnizacion por fallecimiento del trabajador (50% de art. 245)",
        }

    total = sum(r["monto"] for r in rubros.values())

    motivo_labels = {
        "renuncia": "Renuncia del trabajador",
        "jubilacion": "Jubilacion",
        "mutuo_acuerdo": "Acuerdo mutuo de partes",
        "fin_contrato_plazo_fijo": "Finalizacion de contrato a plazo fijo",
        "fallecimiento": "Fallecimiento del trabajador",
    }

    return {
        "motivo": motivo_labels.get(motivo, motivo),
        "antiguedad": {
            "anos": anos,
            "meses": meses,
            "dias": dias_delta,
        },
        "rubros": rubros,
        "total": round(total, 2),
        "total_formateado": f"${total:,.0f}",
        "nota": "Liquidacion final sin rubros indemnizatorios. Si corresponde indemnizacion (despido), usar calcular_indemnizacion.",
    }
