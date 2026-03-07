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
    fecha_intimacion: str = None,
    remuneracion_registrada: float = None,
    fecha_registro_falsa: str = None,
) -> dict:
    """Calcula todos los rubros indemnizatorios de un despido laboral argentino.

    100% deterministico. Aplica las formulas exactas de la LCT y leyes complementarias.

    Args:
        fecha_ingreso: Fecha de inicio de la relacion laboral (YYYY-MM-DD)
        fecha_egreso: Fecha de despido (YYYY-MM-DD)
        mejor_remuneracion: Mejor remuneracion mensual normal y habitual (bruta)
        causa: Tipo de despido: "sin_causa", "con_causa", "indirecto"
        registrado: Si la relacion laboral estaba registrada
        preaviso_otorgado: Si el empleador otorgo preaviso
        fecha_intimacion: Fecha del telegrama intimando registro (YYYY-MM-DD). Requerido para multas Ley 24.013. Si no se envio, omitir.
        remuneracion_registrada: Remuneracion que figuraba en recibos (si habia registro parcial). Omitir si no estaba registrado en absoluto.
        fecha_registro_falsa: Fecha de ingreso que figuraba en recibos si era distinta a la real (YYYY-MM-DD). Omitir si no aplica.
    """
    ingreso = date.fromisoformat(fecha_ingreso)
    egreso = date.fromisoformat(fecha_egreso)
    rem = mejor_remuneracion

    intimacion = date.fromisoformat(fecha_intimacion) if fecha_intimacion else None

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

    rubros_inmediatos = {}
    rubros_requiere_intimacion = {}
    rubros_apercibimiento = {}

    # ── RUBROS INMEDIATOS (exigibles desde el despido) ──

    # 1. Indemnizacion por antiguedad (Art. 245 LCT)
    indem_antiguedad = rem * periodos
    rubros_inmediatos["indemnizacion_antiguedad"] = {
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
    preaviso_entry = {
        "monto": round(monto_preaviso, 2),
        "calculo": texto_preaviso,
        "fundamento": "Arts. 231-232 LCT",
    }
    # Advertir cuando la antiguedad esta cerca del umbral de 5 anios
    # Art. 245 redondea fracciones > 3 meses, pero art. 231 usa tiempo calendario.
    # Un trabajador con 4a10m tiene 5 periodos (art. 245) pero < 5 anios (art. 231) → preaviso 1 mes.
    if not preaviso_otorgado and causa != "con_causa" and anos == 4 and meses_restantes > 3:
        preaviso_entry["nota"] = (
            f"Antiguedad: {anos} anios y {meses_restantes} meses. "
            f"Art. 245 computa {periodos} periodos (redondea fraccion > 3 meses), "
            f"pero art. 231 usa tiempo calendario (< 5 anios = 1 mes de preaviso). "
            f"Algunos tribunales aplican criterio distinto. Verificar jurisprudencia local."
        )
    rubros_inmediatos["preaviso"] = preaviso_entry

    # 3. Integracion mes de despido (Art. 233 LCT)
    dias_en_mes = calendar.monthrange(egreso.year, egreso.month)[1]
    dias_restantes_mes = dias_en_mes - egreso.day
    monto_integracion = 0.0
    texto_integracion = "Despido al ultimo dia del mes - no corresponde"
    if dias_restantes_mes > 0 and not preaviso_otorgado and causa != "con_causa":
        monto_integracion = (rem / 30) * dias_restantes_mes
        texto_integracion = f"{dias_restantes_mes} dias x (${rem:,.0f} / 30)"

    rubros_inmediatos["integracion_mes"] = {
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

    rubros_inmediatos["sac_proporcional"] = {
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

    rubros_inmediatos["vacaciones_proporcionales"] = {
        "monto": round(vac_prop, 2),
        "calculo": f"({dias_vac} dias x {dias_trabajados_anio}/365) x (${rem:,.0f} / 25)",
        "fundamento": "Art. 156 LCT",
    }

    # 6. SAC sobre preaviso (Art. 121 LCT)
    sac_preaviso = monto_preaviso / 12
    rubros_inmediatos["sac_sobre_preaviso"] = {
        "monto": round(sac_preaviso, 2),
        "calculo": f"${monto_preaviso:,.0f} / 12",
        "fundamento": "Art. 121 LCT",
    }

    # ── RUBROS POR NO REGISTRO — Art. 1 Ley 25.323 (no requiere intimacion previa) ──

    if not registrado:
        # Art. 1 Ley 25.323: duplica la indemnizacion del art. 245 LCT
        # cuando al momento del despido la relacion no estaba registrada
        duplicacion_25323 = indem_antiguedad
        rubros_inmediatos["duplicacion_ley25323_art1"] = {
            "monto": round(duplicacion_25323, 2),
            "calculo": f"100% de indemnizacion por antiguedad (${indem_antiguedad:,.0f})",
            "fundamento": "Art. 1 Ley 25.323 - duplicacion por empleo no registrado al momento del despido",
        }

    # ── RUBROS QUE REQUIEREN INTIMACION PREVIA (arts. 8, 9, 10 Ley 24.013) ──
    # El trabajador debe intimar al empleador a registrar dentro de 30 dias (art. 11 Ley 24.013).
    # Sin esa intimacion previa, no se generan estas multas.

    if not registrado:
        if intimacion:
            # Art. 8 Ley 24.013: empleo totalmente no registrado
            # 25% de las remuneraciones devengadas desde inicio hasta intimacion
            meses_devengados = (intimacion.year - ingreso.year) * 12 + (intimacion.month - ingreso.month)
            meses_devengados = max(meses_devengados, 1)
            multa_art8 = rem * meses_devengados * 0.25
            rubros_requiere_intimacion["multa_ley24013_art8"] = {
                "monto": round(multa_art8, 2),
                "calculo": f"25% x {meses_devengados} meses x ${rem:,.0f}",
                "fundamento": "Art. 8 Ley 24.013 - empleo no registrado. Requiere intimacion previa (art. 11)",
            }

            # Art. 15 Ley 24.013: si el despido ocurre dentro de los 2 anos
            # posteriores a la intimacion, se duplican las multas de arts. 8/9/10
            meses_desde_intimacion = (egreso.year - intimacion.year) * 12 + (egreso.month - intimacion.month)
            if meses_desde_intimacion <= 24:
                rubros_requiere_intimacion["duplicacion_ley24013_art15"] = {
                    "monto": round(multa_art8, 2),
                    "calculo": f"Duplicacion de art. 8 (${multa_art8:,.0f}) por despido dentro de 2 anos de intimacion",
                    "fundamento": "Art. 15 Ley 24.013 - presuncion de despido represalia",
                }
        else:
            rubros_requiere_intimacion["multa_ley24013_art8"] = {
                "monto": 0,
                "calculo": "No se informo fecha de intimacion. Para reclamar esta multa, el trabajador debe enviar telegrama intimando registro (art. 11 Ley 24.013) y esperar 30 dias.",
                "fundamento": "Art. 8 Ley 24.013",
                "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la relacion dentro de 30 dias corridos (art. 11 Ley 24.013)",
            }

    # Art. 9 Ley 24.013: registro con remuneracion inferior a la real
    if remuneracion_registrada is not None and remuneracion_registrada < rem:
        diferencia = rem - remuneracion_registrada
        if intimacion:
            meses_devengados_9 = (intimacion.year - ingreso.year) * 12 + (intimacion.month - ingreso.month)
            meses_devengados_9 = max(meses_devengados_9, 1)
            multa_art9 = diferencia * meses_devengados_9 * 0.25
            rubros_requiere_intimacion["multa_ley24013_art9"] = {
                "monto": round(multa_art9, 2),
                "calculo": f"25% x {meses_devengados_9} meses x ${diferencia:,.0f} (diferencia salarial)",
                "fundamento": "Art. 9 Ley 24.013 - remuneracion registrada inferior a la real. Requiere intimacion previa (art. 11)",
            }
        else:
            rubros_requiere_intimacion["multa_ley24013_art9"] = {
                "monto": 0,
                "calculo": "No se informo fecha de intimacion.",
                "fundamento": "Art. 9 Ley 24.013",
                "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la remuneracion real (art. 11 Ley 24.013)",
            }

    # Art. 10 Ley 24.013: fecha de ingreso registrada posterior a la real
    if fecha_registro_falsa:
        registro_falsa = date.fromisoformat(fecha_registro_falsa)
        if intimacion:
            meses_diferencia = (registro_falsa.year - ingreso.year) * 12 + (registro_falsa.month - ingreso.month)
            meses_diferencia = max(meses_diferencia, 1)
            multa_art10 = rem * meses_diferencia * 0.25
            rubros_requiere_intimacion["multa_ley24013_art10"] = {
                "monto": round(multa_art10, 2),
                "calculo": f"25% x {meses_diferencia} meses x ${rem:,.0f} (diferencia de fechas de ingreso)",
                "fundamento": "Art. 10 Ley 24.013 - fecha de ingreso registrada posterior a la real. Requiere intimacion previa (art. 11)",
            }
        else:
            rubros_requiere_intimacion["multa_ley24013_art10"] = {
                "monto": 0,
                "calculo": "No se informo fecha de intimacion.",
                "fundamento": "Art. 10 Ley 24.013",
                "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la fecha de ingreso real (art. 11 Ley 24.013)",
            }

    # ── RUBROS APERCIBIMIENTO (solo si el empleador no paga tras intimacion) ──

    # Art. 2 Ley 25.323: 50% sobre arts. 232, 233 y 245
    # Se devenga recien despues de intimar al pago y que el empleador no pague.
    multa_25323_art2 = (indem_antiguedad + monto_preaviso + monto_integracion) * 0.5
    if not registrado or causa in ("sin_causa", "indirecto"):
        rubros_apercibimiento["multa_ley25323_art2"] = {
            "monto": round(multa_25323_art2, 2),
            "calculo": f"50% x (${indem_antiguedad:,.0f} + ${monto_preaviso:,.0f} + ${monto_integracion:,.0f})",
            "fundamento": "Art. 2 Ley 25.323",
            "nota": "Se devenga solo si el empleador no paga las indemnizaciones dentro del plazo de intimacion. Incluir como apercibimiento en la carta documento, no como monto adeudado.",
        }

    # Totales por categoria
    total_inmediatos = sum(r["monto"] for r in rubros_inmediatos.values())
    total_requiere_intimacion = sum(r["monto"] for r in rubros_requiere_intimacion.values())
    total_apercibimiento = sum(r["monto"] for r in rubros_apercibimiento.values())
    total_general = total_inmediatos + total_requiere_intimacion + total_apercibimiento

    # Advertencias
    advertencias = [
        "No se aplico tope del CCT (art. 245 LCT) - verificar manualmente segun convenio colectivo aplicable",
        "No incluye intereses - aplicar tasa activa BNA desde fecha de egreso",
    ]
    if causa == "con_causa":
        advertencias.append(
            "Despido con causa: si la causa no es valida, corresponden las indemnizaciones de despido sin causa"
        )
    if not registrado and not intimacion:
        advertencias.append(
            "IMPORTANTE: Para reclamar las multas de la Ley 24.013, el trabajador debe PRIMERO enviar telegrama "
            "intimando al empleador a registrar la relacion dentro de 30 dias (art. 11 Ley 24.013). "
            "Sin ese paso previo, se pierden esas multas. Consultar con abogado la secuencia correcta."
        )

    return {
        "rubros_inmediatos": rubros_inmediatos,
        "rubros_requiere_intimacion": rubros_requiere_intimacion,
        "rubros_apercibimiento": rubros_apercibimiento,
        "totales": {
            "inmediatos": round(total_inmediatos, 2),
            "requiere_intimacion": round(total_requiere_intimacion, 2),
            "apercibimiento": round(total_apercibimiento, 2),
            "general": round(total_general, 2),
            "general_formateado": f"${total_general:,.0f}",
        },
        "antiguedad": {
            "anos": anos,
            "meses_restantes": meses_restantes,
            "periodos_indemnizatorios": periodos,
        },
        "advertencias": advertencias,
    }
