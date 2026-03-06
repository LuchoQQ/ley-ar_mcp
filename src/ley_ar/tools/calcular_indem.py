from __future__ import annotations

import calendar
from datetime import date
from dateutil.relativedelta import relativedelta


def calcular_indemnizacion(
    fecha_ingreso: str,
    fecha_egreso: str,
    mejor_remuneracion: float,
    causa: str = "sin_causa",
    registrado: bool = True,
    preaviso_otorgado: bool = False,
) -> dict:
    """Calcula todos los rubros indemnizatorios de un despido laboral argentino.

    100% deterministico. Aplica las formulas exactas de la LCT.

    Args:
        fecha_ingreso: Fecha de inicio de la relacion laboral (YYYY-MM-DD)
        fecha_egreso: Fecha de despido (YYYY-MM-DD)
        mejor_remuneracion: Mejor remuneracion mensual normal y habitual (bruta)
        causa: Tipo de despido: "sin_causa", "con_causa", "indirecto"
        registrado: Si la relacion laboral estaba registrada
        preaviso_otorgado: Si el empleador otorgo preaviso
    """
    ingreso = date.fromisoformat(fecha_ingreso)
    egreso = date.fromisoformat(fecha_egreso)
    rem = mejor_remuneracion

    # Antiguedad
    delta = relativedelta(egreso, ingreso)
    anos = delta.years
    meses_restantes = delta.months
    dias_restantes_delta = delta.days

    # Periodos indemnizatorios (Art. 245 LCT):
    # Cada ano completo = 1 periodo.
    # Fraccion > 3 meses = 1 periodo adicional.
    # Minimo: 1 periodo.
    periodos = anos
    if meses_restantes > 3 or (meses_restantes == 3 and dias_restantes_delta > 0):
        periodos += 1
    periodos = max(periodos, 1)

    rubros = {}

    # 1. Indemnizacion por antiguedad (Art. 245 LCT)
    indem_antiguedad = rem * periodos
    rubros["indemnizacion_antiguedad"] = {
        "monto": round(indem_antiguedad, 2),
        "calculo": f"{periodos} periodos x ${rem:,.0f}",
        "fundamento": "Art. 245 LCT",
    }

    # 2. Preaviso (Arts. 231-232 LCT)
    meses_preaviso = 0
    texto_preaviso = "Preaviso otorgado - no corresponde"
    if not preaviso_otorgado and causa != "con_causa":
        total_meses = anos * 12 + meses_restantes
        if total_meses < 3:
            meses_preaviso = 0.5  # 15 dias
            texto_preaviso = "15 dias (periodo de prueba)"
        elif anos < 5:
            meses_preaviso = 1
            texto_preaviso = f"1 mes x ${rem:,.0f} (antiguedad < 5 anos)"
        else:
            meses_preaviso = 2
            texto_preaviso = f"2 meses x ${rem:,.0f} (antiguedad >= 5 anos)"

    monto_preaviso = rem * meses_preaviso
    rubros["preaviso"] = {
        "monto": round(monto_preaviso, 2),
        "calculo": texto_preaviso,
        "fundamento": "Arts. 231-232 LCT",
    }

    # 3. Integracion mes de despido (Art. 233 LCT)
    dias_en_mes = calendar.monthrange(egreso.year, egreso.month)[1]
    dias_restantes_mes = dias_en_mes - egreso.day
    monto_integracion = 0.0
    texto_integracion = "Despido al ultimo dia del mes - no corresponde"
    if dias_restantes_mes > 0 and not preaviso_otorgado and causa != "con_causa":
        monto_integracion = (rem / 30) * dias_restantes_mes
        texto_integracion = f"{dias_restantes_mes} dias x (${rem:,.0f} / 30)"

    rubros["integracion_mes"] = {
        "monto": round(monto_integracion, 2),
        "calculo": texto_integracion,
        "fundamento": "Art. 233 LCT",
    }

    # 4. SAC proporcional (Art. 123 LCT)
    if egreso.month <= 6:
        inicio_semestre = date(egreso.year, 1, 1)
    else:
        inicio_semestre = date(egreso.year, 7, 1)
    dias_semestre = (egreso - inicio_semestre).days
    sac_prop = (rem / 2) * (dias_semestre / 180)

    rubros["sac_proporcional"] = {
        "monto": round(sac_prop, 2),
        "calculo": f"(${rem:,.0f} / 2) x ({dias_semestre} dias / 180)",
        "fundamento": "Art. 123 LCT",
    }

    # 5. Vacaciones proporcionales (Art. 156 LCT)
    if anos >= 20:
        dias_vac = 35
    elif anos >= 10:
        dias_vac = 28
    elif anos >= 5:
        dias_vac = 21
    else:
        dias_vac = 14

    inicio_anio = date(egreso.year, 1, 1)
    dias_trabajados_anio = (egreso - inicio_anio).days
    vac_prop = (dias_vac * dias_trabajados_anio / 365) * (rem / 25)

    rubros["vacaciones_proporcionales"] = {
        "monto": round(vac_prop, 2),
        "calculo": f"({dias_vac} dias x {dias_trabajados_anio}/365) x (${rem:,.0f} / 25)",
        "fundamento": "Art. 156 LCT",
    }

    # 6. SAC sobre preaviso (Art. 121 LCT)
    sac_preaviso = monto_preaviso / 12
    rubros["sac_sobre_preaviso"] = {
        "monto": round(sac_preaviso, 2),
        "calculo": f"${monto_preaviso:,.0f} / 12",
        "fundamento": "Art. 121 LCT",
    }

    # 7. Multas por no registro (si aplica)
    if not registrado:
        multa_25323 = (indem_antiguedad + monto_preaviso + monto_integracion) * 0.5
        rubros["multa_ley25323_art2"] = {
            "monto": round(multa_25323, 2),
            "calculo": f"50% x (${indem_antiguedad:,.0f} + ${monto_preaviso:,.0f} + ${monto_integracion:,.0f})",
            "fundamento": "Art. 2 Ley 25.323",
        }
    else:
        rubros["multa_ley25323_art2"] = {
            "monto": 0,
            "calculo": "No aplica (relacion registrada)",
            "fundamento": "Art. 2 Ley 25.323",
        }

    # Total
    total = sum(r["monto"] for r in rubros.values())

    # Advertencias
    advertencias = [
        "No se aplico tope del CCT (art. 245 LCT) - verificar manualmente segun convenio colectivo aplicable",
        "No incluye intereses - aplicar tasa activa BNA desde fecha de egreso",
    ]
    if causa == "con_causa":
        advertencias.append(
            "Despido con causa: si la causa no es valida, corresponden las indemnizaciones de despido sin causa"
        )

    return {
        "rubros": rubros,
        "total": round(total, 2),
        "total_formateado": f"${total:,.0f}",
        "antiguedad": {
            "anos": anos,
            "meses_restantes": meses_restantes,
            "periodos_indemnizatorios": periodos,
        },
        "advertencias": advertencias,
    }
