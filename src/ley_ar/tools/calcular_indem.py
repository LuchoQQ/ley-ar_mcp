from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta

from ley_ar.tools.consultar_cct import _load_ccts


def _get_tope_cct(cct_id: str) -> dict | None:
    """Busca el tope indemnizatorio para un CCT."""
    return _load_ccts().get(cct_id)


def _validate_inputs(
    fecha_ingreso: str,
    fecha_egreso: str,
    mejor_remuneracion: float,
    causa: str,
    fecha_intimacion: Optional[str],
    fecha_registro_falsa: Optional[str],
) -> dict | tuple[date, date, Optional[date], Optional[date]]:
    """Valida inputs y retorna dates parseados, o dict de error."""
    _CAUSAS_VALIDAS = ("sin_causa", "con_causa", "indirecto")
    if causa not in _CAUSAS_VALIDAS:
        return {"error": f"Causa no valida: '{causa}'. Valores validos: {list(_CAUSAS_VALIDAS)}"}

    try:
        ingreso = date.fromisoformat(fecha_ingreso)
    except (ValueError, TypeError):
        return {"error": f"fecha_ingreso invalida: '{fecha_ingreso}'. Formato esperado: YYYY-MM-DD"}

    try:
        egreso = date.fromisoformat(fecha_egreso)
    except (ValueError, TypeError):
        return {"error": f"fecha_egreso invalida: '{fecha_egreso}'. Formato esperado: YYYY-MM-DD"}

    if egreso <= ingreso:
        return {"error": "fecha_egreso debe ser posterior a fecha_ingreso"}

    if mejor_remuneracion <= 0:
        return {"error": "mejor_remuneracion debe ser mayor a 0"}

    try:
        intimacion = date.fromisoformat(fecha_intimacion) if fecha_intimacion else None
    except (ValueError, TypeError):
        return {"error": f"fecha_intimacion invalida: '{fecha_intimacion}'. Formato esperado: YYYY-MM-DD"}

    registro_falsa = None
    if fecha_registro_falsa:
        try:
            registro_falsa = date.fromisoformat(fecha_registro_falsa)
        except (ValueError, TypeError):
            return {"error": f"fecha_registro_falsa invalida: '{fecha_registro_falsa}'. Formato esperado: YYYY-MM-DD"}

    return ingreso, egreso, intimacion, registro_falsa


def _calcular_antiguedad(ingreso: date, egreso: date) -> dict:
    """Calcula antiguedad, periodos indemnizatorios y periodo de prueba."""
    delta = relativedelta(egreso, ingreso)
    anos = delta.years
    meses_restantes = delta.months
    dias_restantes_delta = delta.days

    periodos = anos
    if meses_restantes > 3 or (meses_restantes == 3 and dias_restantes_delta > 0):
        periodos += 1
    periodos = max(periodos, 1)

    total_meses = anos * 12 + meses_restantes
    en_periodo_prueba = total_meses < 3

    return {
        "anos": anos,
        "meses_restantes": meses_restantes,
        "dias_restantes_delta": dias_restantes_delta,
        "periodos": periodos,
        "en_periodo_prueba": en_periodo_prueba,
    }


def _calcular_rubros_inmediatos(
    rem: float,
    ingreso: date,
    egreso: date,
    causa: str,
    registrado: bool,
    preaviso_otorgado: bool,
    certificados_entregados: Optional[bool],
    cct: Optional[str],
    ant: dict,
) -> tuple[dict, list]:
    """Calcula rubros exigibles desde el momento del despido."""
    periodos = ant["periodos"]
    anos = ant["anos"]
    meses_restantes = ant["meses_restantes"]
    en_periodo_prueba = ant["en_periodo_prueba"]

    rubros = {}
    notas = []

    # 1. Indemnizacion por antiguedad (Art. 245 LCT)
    rem_245 = rem
    tope_info = None
    if cct:
        tope_info = _get_tope_cct(cct)
        if tope_info:
            tope_3x = tope_info["tope_245"] * 3
            if rem > tope_3x:
                rem_245 = tope_3x
                piso_67 = rem * 0.67
                if rem_245 < piso_67:
                    rem_245 = piso_67

    if en_periodo_prueba:
        indem_antiguedad = 0
        calculo_245 = "No corresponde - periodo de prueba (art. 92 bis LCT)"
    else:
        indem_antiguedad = rem_245 * periodos
        calculo_245 = f"{periodos} periodos x ${rem_245:,.0f}"
    if tope_info and rem > tope_info["tope_245"] * 3 and not en_periodo_prueba:
        tope_3x = tope_info["tope_245"] * 3
        piso_67 = rem * 0.67
        if rem_245 == piso_67 and piso_67 > tope_3x:
            calculo_245 += f" (tope CCT {cct}: ${tope_3x:,.0f}, piso 67% Vizzoti aplicado: ${piso_67:,.0f})"
        else:
            calculo_245 += f" (tope CCT {cct} aplicado: ${rem:,.0f} reducido a ${rem_245:,.0f})"
    rubros["indemnizacion_antiguedad"] = {
        "monto": round(indem_antiguedad, 2),
        "calculo": calculo_245,
        "fundamento": "Art. 245 LCT" if not en_periodo_prueba else "Art. 92 bis LCT - periodo de prueba, no corresponde art. 245",
    }
    if tope_info and not en_periodo_prueba:
        tope_3x = tope_info["tope_245"] * 3
        piso_67 = rem * 0.67
        rubros["indemnizacion_antiguedad"]["tope_cct"] = {
            "cct": cct,
            "nombre": tope_info["nombre"],
            "tope_valor": tope_info["tope_245"],
            "aplicado": rem > tope_3x,
            "piso_vizzoti_aplicado": rem > tope_3x and piso_67 > tope_3x,
            "monto_sin_tope": round(rem * periodos, 2),
        }

    # 2. Preaviso (Arts. 231-232 LCT)
    meses_preaviso = 0
    texto_preaviso = "Preaviso otorgado - no corresponde"
    if not preaviso_otorgado and causa != "con_causa":
        if en_periodo_prueba:
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
    if not preaviso_otorgado and causa != "con_causa" and anos == 4 and meses_restantes > 3:
        monto_alternativo = rem * 2
        preaviso_entry["nota"] = (
            f"Antiguedad: {anos} anios y {meses_restantes} meses. "
            f"Art. 245 computa {periodos} periodos (redondea fraccion > 3 meses), "
            f"pero art. 231 usa tiempo calendario (< 5 anios = 1 mes de preaviso). "
            f"Algunos tribunales aplican criterio distinto. Verificar jurisprudencia local."
        )
        preaviso_entry["monto_alternativo"] = round(monto_alternativo, 2)
        preaviso_entry["calculo_alternativo"] = f"2 meses x ${rem:,.0f} (si se interpreta antiguedad >= 5 anios por redondeo art. 245)"
        preaviso_entry["diferencia"] = round(monto_alternativo - monto_preaviso, 2)
    rubros["preaviso"] = preaviso_entry

    # 3. Integracion mes de despido (Art. 233 LCT)
    dias_en_mes = calendar.monthrange(egreso.year, egreso.month)[1]
    dias_restantes_mes = dias_en_mes - egreso.day
    monto_integracion = 0.0
    texto_integracion = "Despido al ultimo dia del mes - no corresponde"
    if en_periodo_prueba:
        texto_integracion = "No corresponde - periodo de prueba (art. 92 bis LCT)"
    elif dias_restantes_mes > 0 and not preaviso_otorgado and causa != "con_causa":
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
    inicio_computo_sac = max(ingreso, inicio_semestre)
    dias_semestre = (egreso - inicio_computo_sac).days + 1
    sac_prop = (rem / 2) * (dias_semestre / 180)

    rubros["sac_proporcional"] = {
        "monto": round(sac_prop, 2),
        "calculo": f"(${rem:,.0f} / 2) x ({dias_semestre} dias / 180)",
        "fundamento": "Art. 123 LCT",
    }

    # 5. Vacaciones proporcionales (Art. 156 LCT)
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
    vac_prop = dias_vac_proporcional * (rem / 25)

    rubros["vacaciones_proporcionales"] = {
        "monto": round(vac_prop, 2),
        "calculo": f"{dias_trabajados_anio} dias trabajados / 20 = {dias_vac_proporcional:.1f} dias vac. x (${rem:,.0f} / 25)",
        "fundamento": "Art. 156 LCT (1 dia de vacacion por cada 20 dias de trabajo efectivo, valor dia art. 155)",
    }

    # 6. SAC sobre preaviso (Art. 121 LCT)
    sac_preaviso = monto_preaviso / 12
    rubros["sac_sobre_preaviso"] = {
        "monto": round(sac_preaviso, 2),
        "calculo": f"${monto_preaviso:,.0f} / 12",
        "fundamento": "Art. 121 LCT",
    }

    # 7. Duplicacion Ley 25.323 art. 1 (no requiere intimacion)
    if not registrado:
        duplicacion_25323 = indem_antiguedad
        rubros["duplicacion_ley25323_art1"] = {
            "monto": round(duplicacion_25323, 2),
            "calculo": f"100% de indemnizacion por antiguedad (${indem_antiguedad:,.0f})",
            "fundamento": "Art. 1 Ley 25.323 - duplicacion por empleo no registrado al momento del despido",
        }

    # 8. Multa art. 80 LCT — Certificados de trabajo
    if certificados_entregados is False:
        multa_art80 = rem * 3
        rubros["multa_art80_certificados"] = {
            "monto": round(multa_art80, 2),
            "calculo": f"3 x ${rem:,.0f}",
            "fundamento": "Art. 80 LCT - multa por falta de entrega de certificados de trabajo",
            "requisito_previo": "Dec. 146/01: requiere intimacion previa al empleador + 30 dias HABILES de espera. Si no se intimo, incluir intimacion en la carta documento y reclamar la multa una vez vencido el plazo.",
        }
    elif certificados_entregados is None and causa != "con_causa":
        rubros["multa_art80_certificados"] = {
            "monto": 0,
            "calculo": "No se informo si se entregaron certificados",
            "fundamento": "Art. 80 LCT",
            "accion_requerida": "Intimar al empleador a entregar certificados de trabajo (art. 80 LCT). Plazo para cumplir: 30 dias HABILES (Dec. 146/01). Vencido el plazo sin entrega, corresponde multa de 3 sueldos.",
        }

    # Notas sobre tope CCT
    if not cct:
        notas.append("Tope CCT no aplicado: no se informo convenio colectivo")
    elif tope_info and not (rem > tope_info["tope_245"] * 3):
        notas.append(f"Tope CCT {cct} ({tope_info['nombre']}): remuneracion no excede el tope, no se aplica reduccion")
    elif tope_info and rem > tope_info["tope_245"] * 3:
        notas.append(f"Tope CCT {cct} aplicado: remuneracion reducida de ${rem:,.0f} a ${rem_245:,.0f}")

    if en_periodo_prueba:
        notas.append(
            "Periodo de prueba (art. 92 bis LCT): no corresponde indemnizacion por antiguedad "
            "(art. 245) ni integracion mes (art. 233). Solo corresponde preaviso de 15 dias."
        )

    return rubros, notas


def _calcular_rubros_ley24013(
    rem: float,
    ingreso: date,
    egreso: date,
    intimacion: Optional[date],
    registrado: bool,
    remuneracion_registrada: Optional[float],
    registro_falsa: Optional[date],
    indem_antiguedad: float,
    monto_preaviso: float,
    monto_integracion: float,
) -> tuple[dict, list]:
    """Calcula multas de Ley 24.013 (arts. 8, 9, 10, 15) y Ley 25.323 art. 2."""
    _FECHA_DEROGACION_24013 = date(2024, 7, 8)
    ley_24013_vigente = egreso < _FECHA_DEROGACION_24013

    rubros_intimacion: dict = {}
    notas: list = []

    if not registrado:
        if ley_24013_vigente:
            if intimacion:
                meses_devengados = (intimacion.year - ingreso.year) * 12 + (intimacion.month - ingreso.month)
                meses_devengados = max(meses_devengados, 1)
                multa_art8 = rem * meses_devengados * 0.25
                rubros_intimacion["multa_ley24013_art8"] = {
                    "monto": round(multa_art8, 2),
                    "calculo": f"25% x {meses_devengados} meses x ${rem:,.0f}",
                    "fundamento": "Art. 8 Ley 24.013 - empleo no registrado. Requiere intimacion previa (art. 11)",
                }

                meses_desde_intimacion = (egreso.year - intimacion.year) * 12 + (egreso.month - intimacion.month)
                if meses_desde_intimacion <= 24:
                    monto_art15 = indem_antiguedad + monto_preaviso + monto_integracion
                    rubros_intimacion["duplicacion_ley24013_art15"] = {
                        "monto": round(monto_art15, 2),
                        "calculo": f"Arts. 245 (${indem_antiguedad:,.0f}) + 232 (${monto_preaviso:,.0f}) + 233 (${monto_integracion:,.0f}) por despido dentro de 2 anos de intimacion",
                        "fundamento": "Art. 15 Ley 24.013 - duplicacion de indemnizaciones por despido (arts. 232, 233, 245 LCT)",
                    }
            else:
                meses_potenciales = (egreso.year - ingreso.year) * 12 + (egreso.month - ingreso.month)
                meses_potenciales = max(meses_potenciales, 1)
                monto_potencial_art8 = rem * meses_potenciales * 0.25
                monto_potencial_art15 = indem_antiguedad + monto_preaviso + monto_integracion
                rubros_intimacion["multa_ley24013_art8"] = {
                    "monto": 0,
                    "monto_potencial": round(monto_potencial_art8, 2),
                    "calculo": f"Potencial: 25% x {meses_potenciales} meses x ${rem:,.0f} = ${monto_potencial_art8:,.0f}. No exigible sin intimacion previa.",
                    "fundamento": "Art. 8 Ley 24.013",
                    "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la relacion dentro de 30 dias corridos (art. 11 Ley 24.013)",
                }
                rubros_intimacion["duplicacion_ley24013_art15"] = {
                    "monto": 0,
                    "monto_potencial": round(monto_potencial_art15, 2),
                    "calculo": f"Potencial: arts. 245 (${indem_antiguedad:,.0f}) + 232 (${monto_preaviso:,.0f}) + 233 (${monto_integracion:,.0f}) si despido dentro de 2 anos de intimacion.",
                    "fundamento": "Art. 15 Ley 24.013 - duplicacion de indemnizaciones por despido (arts. 232, 233, 245 LCT)",
                    "accion_requerida": "Requiere intimacion previa (art. 11 Ley 24.013)",
                }
        else:
            notas.append(
                "Arts. 8-15 Ley 24.013 derogados por Ley 27.742 (B.O. 8/7/2024). "
                "No se calculan multas bajo estos articulos para despidos posteriores a esa fecha."
            )

    # Art. 9 Ley 24.013: registro con remuneracion inferior a la real
    if remuneracion_registrada is not None and remuneracion_registrada < rem:
        if ley_24013_vigente:
            diferencia = rem - remuneracion_registrada
            if intimacion:
                meses_devengados_9 = (intimacion.year - ingreso.year) * 12 + (intimacion.month - ingreso.month)
                meses_devengados_9 = max(meses_devengados_9, 1)
                multa_art9 = diferencia * meses_devengados_9 * 0.25
                rubros_intimacion["multa_ley24013_art9"] = {
                    "monto": round(multa_art9, 2),
                    "calculo": f"25% x {meses_devengados_9} meses x ${diferencia:,.0f} (diferencia salarial)",
                    "fundamento": "Art. 9 Ley 24.013 - remuneracion registrada inferior a la real. Requiere intimacion previa (art. 11)",
                }
            else:
                rubros_intimacion["multa_ley24013_art9"] = {
                    "monto": 0,
                    "calculo": "No se informo fecha de intimacion.",
                    "fundamento": "Art. 9 Ley 24.013",
                    "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la remuneracion real (art. 11 Ley 24.013)",
                }
        else:
            notas.append(
                "Art. 9 Ley 24.013 derogado por Ley 27.742 (B.O. 8/7/2024). "
                "No se calcula multa por remuneracion inferior para despidos posteriores a esa fecha."
            )

    # Art. 10 Ley 24.013: fecha de ingreso registrada posterior a la real
    if registro_falsa:
        if ley_24013_vigente:
            if intimacion:
                meses_diferencia = (registro_falsa.year - ingreso.year) * 12 + (registro_falsa.month - ingreso.month)
                meses_diferencia = max(meses_diferencia, 1)
                multa_art10 = rem * meses_diferencia * 0.25
                rubros_intimacion["multa_ley24013_art10"] = {
                    "monto": round(multa_art10, 2),
                    "calculo": f"25% x {meses_diferencia} meses x ${rem:,.0f} (diferencia de fechas de ingreso)",
                    "fundamento": "Art. 10 Ley 24.013 - fecha de ingreso registrada posterior a la real. Requiere intimacion previa (art. 11)",
                }
            else:
                rubros_intimacion["multa_ley24013_art10"] = {
                    "monto": 0,
                    "calculo": "No se informo fecha de intimacion.",
                    "fundamento": "Art. 10 Ley 24.013",
                    "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la fecha de ingreso real (art. 11 Ley 24.013)",
                }
        else:
            notas.append(
                "Art. 10 Ley 24.013 derogado por Ley 27.742 (B.O. 8/7/2024). "
                "No se calcula multa por fecha de ingreso falsa para despidos posteriores a esa fecha."
            )

    # Art. 132 bis LCT — Retencion de aportes no depositados
    if not registrado:
        rubros_intimacion["sancion_art132bis"] = {
            "monto": 0,
            "monto_potencial_mensual": round(rem, 2),
            "calculo": f"${rem:,.0f} por mes desde intimacion hasta acreditacion de deposito de aportes retenidos",
            "fundamento": "Art. 132 bis LCT - sancion conminatoria por retencion de aportes no depositados",
            "accion_requerida": "Intimar al empleador a acreditar deposito de aportes retenidos. La sancion se devenga mensualmente desde la intimacion. En empleo totalmente no registrado, los aportes nunca fueron depositados.",
            "nota": "Monto se acumula mensualmente hasta que el empleador acredite el deposito. No es un monto fijo sino una sancion conminatoria.",
        }

    return rubros_intimacion, notas


def _calcular_rubros_apercibimiento(
    indem_antiguedad: float,
    monto_preaviso: float,
    monto_integracion: float,
    registrado: bool,
    causa: str,
) -> dict:
    """Calcula rubros que requieren intimacion de pago previa (apercibimientos)."""
    rubros: dict = {}

    multa_25323_art2 = (indem_antiguedad + monto_preaviso + monto_integracion) * 0.5
    if not registrado or causa in ("sin_causa", "indirecto"):
        rubros["multa_ley25323_art2"] = {
            "monto": round(multa_25323_art2, 2),
            "calculo": f"50% x (${indem_antiguedad:,.0f} + ${monto_preaviso:,.0f} + ${monto_integracion:,.0f})",
            "fundamento": "Art. 2 Ley 25.323",
            "nota": "Se devenga solo si el empleador no paga las indemnizaciones dentro del plazo de intimacion. Incluir como apercibimiento en la carta documento, no como monto adeudado.",
        }

    return rubros


def _build_dependencias(
    registrado: bool,
    causa: str,
    remuneracion_registrada: Optional[float],
    rem: float,
    fecha_registro_falsa: Optional[str],
    certificados_entregados: Optional[bool],
    ant: dict,
) -> dict:
    """Construye el grafo de dependencias entre rubros."""
    periodos = ant["periodos"]
    dependencias = {
        "indemnizacion_antiguedad": {
            "requiere": [],
            "descripcion": "Exigible desde el momento del despido sin causa",
        },
        "preaviso": {
            "requiere": [],
            "descripcion": "Exigible desde el momento del despido sin preaviso",
        },
        "integracion_mes": {
            "requiere": [],
            "descripcion": "Exigible desde el momento del despido sin preaviso (si no fue el ultimo dia del mes)",
        },
        "sac_proporcional": {
            "requiere": [],
            "descripcion": "Exigible desde el momento del despido",
        },
        "vacaciones_proporcionales": {
            "requiere": [],
            "descripcion": "Exigible desde el momento del despido",
        },
        "sac_sobre_preaviso": {
            "requiere": ["preaviso"],
            "descripcion": "Accesorio al preaviso. Si preaviso = 0, este tambien = 0",
        },
    }

    if not registrado:
        dependencias["duplicacion_ley25323_art1"] = {
            "requiere": ["indemnizacion_antiguedad"],
            "descripcion": "Se duplica la indemnizacion por antiguedad. Exigible desde el despido.",
        }
        dependencias["multa_ley24013_art8"] = {
            "requiere": ["telegrama_registro"],
            "plazo": "30 dias corridos desde envio del telegrama",
            "descripcion": "Requiere telegrama de intimacion a registrar (art. 11 Ley 24.013). Sin telegrama previo, no es exigible.",
        }
        dependencias["duplicacion_ley24013_art15"] = {
            "requiere": ["multa_ley24013_art8"],
            "condicion": "Despido dentro de los 2 anos posteriores a la intimacion de registro",
            "descripcion": "Duplica arts. 232+233+245. Requiere que se haya intimado registro Y que el despido ocurra dentro de 2 anos.",
        }
        dependencias["sancion_art132bis"] = {
            "requiere": ["intimacion_deposito_aportes"],
            "plazo": "Se devenga mensualmente desde la intimacion hasta acreditacion de deposito",
            "descripcion": "Sancion conminatoria. Requiere intimar al empleador a depositar aportes retenidos.",
        }

    if remuneracion_registrada is not None and remuneracion_registrada < rem:
        dependencias["multa_ley24013_art9"] = {
            "requiere": ["telegrama_registro"],
            "plazo": "30 dias corridos desde envio del telegrama",
            "descripcion": "Requiere telegrama intimando a registrar remuneracion real.",
        }

    if fecha_registro_falsa:
        dependencias["multa_ley24013_art10"] = {
            "requiere": ["telegrama_registro"],
            "plazo": "30 dias corridos desde envio del telegrama",
            "descripcion": "Requiere telegrama intimando a registrar fecha de ingreso real.",
        }

    dependencias["multa_ley25323_art2"] = {
        "requiere": ["carta_documento_pago"],
        "plazo": "Plazo razonable (jurisprudencia: 4 dias habiles) desde intimacion de pago",
        "descripcion": "50% sobre arts. 232+233+245. Solo se devenga si el empleador no paga tras ser intimado. Incluir como APERCIBIMIENTO en la carta documento, no como monto adeudado.",
    }

    if certificados_entregados is False or certificados_entregados is None:
        dependencias["multa_art80_certificados"] = {
            "requiere": ["intimacion_certificados"],
            "plazo": "30 dias HABILES desde intimacion (Dec. 146/01)",
            "descripcion": "Intimar al empleador a entregar certificados art. 80 LCT. Si no entrega en 30 dias habiles, nace el derecho a la multa de 3 sueldos.",
        }

    return dependencias


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
    certificados_entregados: bool = None,
    mod_service=None,
    fecha_calculo: str = None,
    cct: str = None,
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
    # Validacion
    validated = _validate_inputs(
        fecha_ingreso, fecha_egreso, mejor_remuneracion, causa,
        fecha_intimacion, fecha_registro_falsa,
    )
    if isinstance(validated, dict):
        return validated
    ingreso, egreso, intimacion, registro_falsa = validated

    rem = mejor_remuneracion

    # Antiguedad
    ant = _calcular_antiguedad(ingreso, egreso)

    # Rubros inmediatos
    rubros_inmediatos, notas_inmediatos = _calcular_rubros_inmediatos(
        rem, ingreso, egreso, causa, registrado, preaviso_otorgado,
        certificados_entregados, cct, ant,
    )

    indem_antiguedad = rubros_inmediatos["indemnizacion_antiguedad"]["monto"]
    monto_preaviso = rubros_inmediatos["preaviso"]["monto"]
    monto_integracion = rubros_inmediatos["integracion_mes"]["monto"]

    # Rubros Ley 24.013
    rubros_requiere_intimacion, notas_ley24013 = _calcular_rubros_ley24013(
        rem, ingreso, egreso, intimacion, registrado,
        remuneracion_registrada, registro_falsa,
        indem_antiguedad, monto_preaviso, monto_integracion,
    )

    # Rubros apercibimiento
    rubros_apercibimiento = _calcular_rubros_apercibimiento(
        indem_antiguedad, monto_preaviso, monto_integracion, registrado, causa,
    )

    # Notas
    notas_calculo = notas_inmediatos + notas_ley24013

    # Totales
    total_inmediatos = sum(r["monto"] for r in rubros_inmediatos.values())
    total_requiere_intimacion = sum(r["monto"] for r in rubros_requiere_intimacion.values())
    total_apercibimiento = sum(r["monto"] for r in rubros_apercibimiento.values())

    # Modificaciones normativas
    modificaciones_normativas = None
    if mod_service:
        arts_usados = ["LCT_245", "LCT_231", "LCT_232", "LCT_233"]
        if not registrado:
            arts_usados.extend(["LdE_8", "LdE_9", "LdE_10", "LdE_11", "LdE_15", "LCT_132bis"])
        if certificados_entregados is not None:
            arts_usados.append("LCT_78")
        mods = mod_service.annotate_many(arts_usados)
        if mods:
            modificaciones_normativas = mods

    # Intereses
    intereses_info = None
    try:
        from ley_ar.services.intereses import calcular_intereses
        fecha_calc = fecha_calculo if fecha_calculo else date.today().isoformat()
        intereses_info = calcular_intereses(total_inmediatos, fecha_egreso, fecha_calc)
    except ImportError:
        notas_calculo.append("Modulo de intereses no disponible")

    # Dependencias
    dependencias = _build_dependencias(
        registrado, causa, remuneracion_registrada, rem,
        fecha_registro_falsa, certificados_entregados, ant,
    )

    result = {
        "rubros_inmediatos": rubros_inmediatos,
        "rubros_requiere_intimacion": rubros_requiere_intimacion,
        "rubros_apercibimiento": rubros_apercibimiento,
        "dependencias": dependencias,
        "totales": {
            "inmediatos": round(total_inmediatos, 2),
            "inmediatos_formateado": f"${total_inmediatos:,.0f}",
            "requiere_intimacion": round(total_requiere_intimacion, 2),
            "apercibimiento": round(total_apercibimiento, 2),
        },
        "antiguedad": {
            "anos": ant["anos"],
            "meses_restantes": ant["meses_restantes"],
            "periodos_indemnizatorios": ant["periodos"],
        },
        "notas_calculo": notas_calculo,
    }
    if modificaciones_normativas:
        result["modificaciones_normativas"] = modificaciones_normativas
    if intereses_info:
        result["intereses"] = intereses_info
    return result
