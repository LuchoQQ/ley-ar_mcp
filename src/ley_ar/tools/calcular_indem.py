from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path
from dateutil.relativedelta import relativedelta

CCT_PATH = Path(__file__).parent.parent / "data" / "cct" / "topes.json"

_cct_cache = None


def _get_tope_cct(cct_id: str) -> dict | None:
    """Busca el tope indemnizatorio para un CCT."""
    global _cct_cache
    if _cct_cache is None:
        if CCT_PATH.exists():
            with open(CCT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            _cct_cache = {k: v for k, v in data.items() if not k.startswith("_")}
        else:
            _cct_cache = {}
    return _cct_cache.get(cct_id)


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
    # Aplicar tope CCT si se informo convenio colectivo
    rem_245 = rem
    tope_info = None
    if cct:
        tope_info = _get_tope_cct(cct)
        if tope_info:
            tope_valor = tope_info["tope_245"]
            # Art. 245: base no puede exceder 3 veces el promedio CCT
            tope_3x = tope_valor * 3
            if rem > tope_3x:
                rem_245 = tope_3x

    indem_antiguedad = rem_245 * periodos
    calculo_245 = f"{periodos} periodos x ${rem_245:,.0f}"
    if tope_info and rem > tope_info["tope_245"] * 3:
        calculo_245 += f" (tope CCT {cct} aplicado: ${rem:,.0f} reducido a ${rem_245:,.0f})"
    rubros_inmediatos["indemnizacion_antiguedad"] = {
        "monto": round(indem_antiguedad, 2),
        "calculo": calculo_245,
        "fundamento": "Art. 245 LCT",
    }
    if tope_info:
        rubros_inmediatos["indemnizacion_antiguedad"]["tope_cct"] = {
            "cct": cct,
            "nombre": tope_info["nombre"],
            "tope_valor": tope_info["tope_245"],
            "aplicado": rem > tope_info["tope_245"] * 3,
            "monto_sin_tope": round(rem * periodos, 2),
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
    dias_semestre = (egreso - inicio_semestre).days + 1  # conteo inclusivo: primer y ultimo dia trabajados
    sac_prop = (rem / 2) * (dias_semestre / 180)

    rubros_inmediatos["sac_proporcional"] = {
        "monto": round(sac_prop, 2),
        "calculo": f"(${rem:,.0f} / 2) x ({dias_semestre} dias / 180)",
        "fundamento": "Art. 123 LCT",
    }

    # 5. Vacaciones proporcionales (Art. 156 LCT)
    # Escala de dias de licencia segun antiguedad (art. 150 LCT):
    if anos >= 20:
        dias_vac_anual = 35
    elif anos >= 10:
        dias_vac_anual = 28
    elif anos >= 5:
        dias_vac_anual = 21
    else:
        dias_vac_anual = 14

    # Art. 156: 1 dia de vacacion por cada 20 dias de trabajo efectivo
    inicio_anio = date(egreso.year, 1, 1)
    dias_trabajados_anio = (egreso - inicio_anio).days + 1  # conteo inclusivo
    dias_vac_proporcional = dias_trabajados_anio / 20
    # Tope: no puede exceder la proporcion del periodo anual
    dias_vac_proporcional = min(dias_vac_proporcional, dias_vac_anual * dias_trabajados_anio / 365)
    # Valor del dia de vacacion: art. 155 LCT -> rem / 25
    vac_prop = dias_vac_proporcional * (rem / 25)

    rubros_inmediatos["vacaciones_proporcionales"] = {
        "monto": round(vac_prop, 2),
        "calculo": f"{dias_trabajados_anio} dias trabajados / 20 = {dias_vac_proporcional:.1f} dias vac. x (${rem:,.0f} / 25)",
        "fundamento": "Art. 156 LCT (1 dia de vacacion por cada 20 dias de trabajo efectivo, valor dia art. 155)",
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
            # posteriores a la intimacion, el trabajador percibe el doble de las
            # indemnizaciones por despido (arts. 232, 233, 245 LCT).
            # Es decir: un monto adicional igual a la suma de antiguedad + preaviso + integracion.
            meses_desde_intimacion = (egreso.year - intimacion.year) * 12 + (egreso.month - intimacion.month)
            if meses_desde_intimacion <= 24:
                monto_art15 = indem_antiguedad + monto_preaviso + monto_integracion
                rubros_requiere_intimacion["duplicacion_ley24013_art15"] = {
                    "monto": round(monto_art15, 2),
                    "calculo": f"Arts. 245 (${indem_antiguedad:,.0f}) + 232 (${monto_preaviso:,.0f}) + 233 (${monto_integracion:,.0f}) por despido dentro de 2 anos de intimacion",
                    "fundamento": "Art. 15 Ley 24.013 - duplicacion de indemnizaciones por despido (arts. 232, 233, 245 LCT)",
                }
        else:
            # Calcular monto potencial usando fecha de egreso como referencia
            meses_potenciales = (egreso.year - ingreso.year) * 12 + (egreso.month - ingreso.month)
            meses_potenciales = max(meses_potenciales, 1)
            monto_potencial_art8 = rem * meses_potenciales * 0.25
            # Art. 15 duplica indemnizaciones por despido (arts. 232+233+245), no art. 8
            monto_potencial_art15 = indem_antiguedad + monto_preaviso + monto_integracion
            rubros_requiere_intimacion["multa_ley24013_art8"] = {
                "monto": 0,
                "monto_potencial": round(monto_potencial_art8, 2),
                "calculo": f"Potencial: 25% x {meses_potenciales} meses x ${rem:,.0f} = ${monto_potencial_art8:,.0f}. No exigible sin intimacion previa.",
                "fundamento": "Art. 8 Ley 24.013",
                "accion_requerida": "Enviar telegrama laboral intimando al empleador a registrar la relacion dentro de 30 dias corridos (art. 11 Ley 24.013)",
            }
            rubros_requiere_intimacion["duplicacion_ley24013_art15"] = {
                "monto": 0,
                "monto_potencial": round(monto_potencial_art15, 2),
                "calculo": f"Potencial: arts. 245 (${indem_antiguedad:,.0f}) + 232 (${monto_preaviso:,.0f}) + 233 (${monto_integracion:,.0f}) si despido dentro de 2 anos de intimacion.",
                "fundamento": "Art. 15 Ley 24.013 - duplicacion de indemnizaciones por despido (arts. 232, 233, 245 LCT)",
                "accion_requerida": "Requiere intimacion previa (art. 11 Ley 24.013)",
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

    # ── MULTA ART. 80 LCT — Certificados de trabajo ──
    # Dec. 146/01: para que proceda la multa, el trabajador debe intimar al empleador
    # a entregar los certificados y esperar 30 dias HABILES. Si el empleador no los
    # entrega dentro de ese plazo, recien entonces nace el derecho a la multa.

    if certificados_entregados is False:
        multa_art80 = rem * 3
        rubros_inmediatos["multa_art80_certificados"] = {
            "monto": round(multa_art80, 2),
            "calculo": f"3 x ${rem:,.0f}",
            "fundamento": "Art. 80 LCT - multa por falta de entrega de certificados de trabajo",
            "requisito_previo": "Dec. 146/01: requiere intimacion previa al empleador + 30 dias HABILES de espera. Si no se intimo, incluir intimacion en la carta documento y reclamar la multa una vez vencido el plazo.",
        }
    elif certificados_entregados is None and causa != "con_causa":
        rubros_inmediatos["multa_art80_certificados"] = {
            "monto": 0,
            "calculo": "No se informo si se entregaron certificados",
            "fundamento": "Art. 80 LCT",
            "accion_requerida": "Intimar al empleador a entregar certificados de trabajo (art. 80 LCT). Plazo para cumplir: 30 dias HABILES (Dec. 146/01). Vencido el plazo sin entrega, corresponde multa de 3 sueldos.",
        }

    # ── ART. 132 BIS LCT — Retencion de aportes no depositados ──
    # Cuando el empleador retuvo aportes del trabajador (jubilacion, obra social)
    # y no los deposito, debe pagar una sancion conminatoria mensual equivalente
    # a la remuneracion del trabajador, devengada desde la intimacion hasta el
    # efectivo deposito o acreditacion en ANSES.
    # En empleo no registrado, nunca se depositaron aportes.

    if not registrado:
        rubros_requiere_intimacion["sancion_art132bis"] = {
            "monto": 0,
            "monto_potencial_mensual": round(rem, 2),
            "calculo": f"${rem:,.0f} por mes desde intimacion hasta acreditacion de deposito de aportes retenidos",
            "fundamento": "Art. 132 bis LCT - sancion conminatoria por retencion de aportes no depositados",
            "accion_requerida": "Intimar al empleador a acreditar deposito de aportes retenidos. La sancion se devenga mensualmente desde la intimacion. En empleo totalmente no registrado, los aportes nunca fueron depositados.",
            "nota": "Monto se acumula mensualmente hasta que el empleador acredite el deposito. No es un monto fijo sino una sancion conminatoria.",
        }

    # Totales por categoria
    total_inmediatos = sum(r["monto"] for r in rubros_inmediatos.values())
    total_requiere_intimacion = sum(r["monto"] for r in rubros_requiere_intimacion.values())
    total_apercibimiento = sum(r["monto"] for r in rubros_apercibimiento.values())

    # Advertencias
    advertencias = []
    if not cct:
        advertencias.append(
            "No se aplico tope del CCT (art. 245 LCT) - informar convenio colectivo para calculo preciso"
        )
    elif tope_info and not (rem > tope_info["tope_245"] * 3):
        advertencias.append(
            f"Tope CCT {cct} ({tope_info['nombre']}): remuneracion no excede el tope, no se aplica reduccion"
        )
    if causa == "con_causa":
        advertencias.append(
            "Despido con causa: si la causa no es valida, corresponden las indemnizaciones de despido sin causa"
        )

    # ── RESUMEN PRE-FORMATEADO (para que el LLM copie, no recalcule) ──

    def _format_rubros(rubros: dict) -> list:
        lineas = []
        for key, rubro in rubros.items():
            if rubro["monto"] > 0:
                nombre = key.replace("_", " ").title()
                lineas.append(f"- {nombre} ({rubro['fundamento']}): ${rubro['monto']:,.0f}")
        return lineas

    resumen = {
        "rubros_reclamables": _format_rubros(rubros_inmediatos),
        "subtotal_reclamable": f"${total_inmediatos:,.0f}",
    }
    if rubros_apercibimiento:
        resumen["apercibimientos"] = _format_rubros(rubros_apercibimiento)
        resumen["subtotal_apercibimiento"] = f"${total_apercibimiento:,.0f}"
    if any(r.get("monto_potencial", 0) > 0 for r in rubros_requiere_intimacion.values()):
        potenciales = []
        for key, rubro in rubros_requiere_intimacion.items():
            mp = rubro.get("monto_potencial", 0)
            if mp > 0:
                nombre = key.replace("_", " ").title()
                potenciales.append(f"- {nombre} ({rubro['fundamento']}): ${mp:,.0f}")
        resumen["rubros_potenciales_requieren_intimacion"] = potenciales
        resumen["nota_potenciales"] = "Estos montos NO son exigibles todavia. Requieren intimacion previa (telegrama art. 11 Ley 24.013). No sumarlos al subtotal reclamable."

    # ── SECUENCIA DE DOCUMENTOS (logica deterministica) ──
    # Verificar si los arts. 11 y 15 de la Ley 24.013 estan derogados
    arts_24013_derogados = False
    if mod_service:
        arts_24013_derogados = mod_service.fue_derogado("LdE_11") and mod_service.fue_derogado("LdE_15")

    documentos = []
    if not registrado and not intimacion and not arts_24013_derogados:
        # Secuencia clasica pre-Ley 27.742: telegrama de registro primero
        documentos.append({
            "orden": 1,
            "tipo": "telegrama_registro",
            "descripcion": "Telegrama intimando registro (art. 11 Ley 24.013)",
            "contenido": "SOLO intimacion de registro. NO mencionar despido, NO reclamar indemnizaciones, NO mencionar rubros. El unico objetivo es intimar al empleador a registrar la relacion laboral.",
            "motivo": "Si se reclaman indemnizaciones en el mismo acto que se intima el registro, el empleador puede argumentar que la intimacion de registro fue instrumental y no genuina, debilitando el art. 15 Ley 24.013.",
            "plazo_espera": "30 dias corridos desde recepcion",
        })
        documentos.append({
            "orden": 2,
            "tipo": "carta_documento",
            "descripcion": "Carta documento reclamando indemnizacion y rubros",
            "contenido": "Enviar DESPUES de los 30 dias del telegrama de registro. Incluir todos los rubros inmediatos.",
            "rubros_a_incluir": list(rubros_inmediatos.keys()),
            "subtotal": f"${total_inmediatos:,.0f}",
            "apercibimientos_a_incluir": list(rubros_apercibimiento.keys()),
        })
        advertencias.append(
            "SECUENCIA OBLIGATORIA: enviar telegrama de registro (documento 1) ANTES que la carta documento (documento 2). "
            "Enviarlos juntos o en orden inverso debilita el reclamo del art. 15 Ley 24.013."
        )
    elif not registrado and not intimacion and arts_24013_derogados:
        # Post-Ley 27.742: arts. 11 y 15 derogados, carta documento directa
        documentos.append({
            "orden": 1,
            "tipo": "carta_documento",
            "descripcion": "Carta documento reclamando indemnizacion y rubros",
            "contenido": "Reclamar todos los rubros inmediatos. Arts. 11 y 15 Ley 24.013 derogados por Ley 27.742 — no se requiere telegrama de registro previo bajo la nueva normativa.",
            "rubros_a_incluir": list(rubros_inmediatos.keys()),
            "subtotal": f"${total_inmediatos:,.0f}",
            "apercibimientos_a_incluir": list(rubros_apercibimiento.keys()),
        })
        advertencias.append(
            "Arts. 11 y 15 Ley 24.013 derogados por Ley 27.742 (B.O. 8/7/2024). "
            "Bajo la nueva normativa no se requiere telegrama de registro previo. "
            "Sin embargo, para hechos anteriores a la derogacion, algunos tribunales pueden aplicar ultraactividad. "
            "Evaluar con el abogado si conviene enviar igualmente el telegrama de registro como cautela."
        )
    elif not registrado and intimacion:
        documentos.append({
            "orden": 1,
            "tipo": "carta_documento",
            "descripcion": "Carta documento reclamando indemnizacion y rubros",
            "contenido": "Telegrama de registro ya fue enviado. Reclamar todos los rubros.",
            "rubros_a_incluir": list(rubros_inmediatos.keys()),
            "subtotal": f"${total_inmediatos:,.0f}",
            "apercibimientos_a_incluir": list(rubros_apercibimiento.keys()),
        })
    else:
        documentos.append({
            "orden": 1,
            "tipo": "carta_documento",
            "descripcion": "Carta documento reclamando indemnizacion y rubros",
            "rubros_a_incluir": list(rubros_inmediatos.keys()),
            "subtotal": f"${total_inmediatos:,.0f}",
            "apercibimientos_a_incluir": list(rubros_apercibimiento.keys()),
        })

    # ── MODIFICACIONES NORMATIVAS ──
    # Adjuntar hechos de modificaciones a los articulos usados en el calculo

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

    # ── INTERESES ──
    intereses_info = None
    try:
        from ley_ar.services.intereses import calcular_intereses
        fecha_calc = fecha_calculo if fecha_calculo else date.today().isoformat()
        intereses_info = calcular_intereses(total_inmediatos, fecha_egreso, fecha_calc)
    except ImportError:
        advertencias.append("Modulo de intereses no disponible")

    result = {
        "rubros_inmediatos": rubros_inmediatos,
        "rubros_requiere_intimacion": rubros_requiere_intimacion,
        "rubros_apercibimiento": rubros_apercibimiento,
        "totales": {
            "inmediatos": round(total_inmediatos, 2),
            "inmediatos_formateado": f"${total_inmediatos:,.0f}",
            "requiere_intimacion": round(total_requiere_intimacion, 2),
            "apercibimiento": round(total_apercibimiento, 2),
            "nota": "Cada categoria tiene un estatus legal distinto. NO sumar categorias entre si. Los rubros_inmediatos son exigibles ahora. Los rubros_requiere_intimacion dependen de pasos previos. Los apercibimientos son condicionales.",
        },
        "antiguedad": {
            "anos": anos,
            "meses_restantes": meses_restantes,
            "periodos_indemnizatorios": periodos,
        },
        "resumen": resumen,
        "documentos": documentos,
        "advertencias": advertencias,
    }
    if modificaciones_normativas:
        result["modificaciones_normativas"] = modificaciones_normativas
    if intereses_info and intereses_info.get("monto_intereses", 0) > 0:
        result["intereses"] = intereses_info
    return result
