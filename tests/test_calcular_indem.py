from ley_ar.tools.calcular_indem import calcular_indemnizacion


def test_despido_menos_1_anio():
    """Antiguedad 8 meses -> 1 periodo (fraccion > 3 meses)"""
    r = calcular_indemnizacion("2024-06-01", "2025-02-15", 1000000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 1
    assert r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"] == 1000000
    assert r["rubros_inmediatos"]["preaviso"]["monto"] == 1000000


def test_despido_exacto_5_anios():
    """Antiguedad exacta 5 anos -> 5 periodos, preaviso 2 meses"""
    r = calcular_indemnizacion("2020-01-15", "2025-01-15", 1200000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 5
    assert r["rubros_inmediatos"]["preaviso"]["monto"] == 2400000


def test_despido_10_anios():
    """Antiguedad 10 anos -> 10 periodos, vacaciones 28 dias"""
    r = calcular_indemnizacion("2015-03-01", "2025-03-01", 900000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 10
    assert r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"] == 9000000


def test_despido_inicio_mes():
    """Despido el dia 3 -> integracion mes grande"""
    r = calcular_indemnizacion("2020-01-01", "2025-01-03", 1000000, "sin_causa", True, False)
    assert r["rubros_inmediatos"]["integracion_mes"]["monto"] > 0
    assert r["rubros_inmediatos"]["integracion_mes"]["monto"] > 900000


def test_despido_fin_mes():
    """Despido el dia 31 -> integracion mes = 0"""
    r = calcular_indemnizacion("2020-01-01", "2025-01-31", 1000000, "sin_causa", True, False)
    assert r["rubros_inmediatos"]["integracion_mes"]["monto"] == 0


def test_despido_no_registrado_art2_25323():
    """Relacion no registrada -> multa art. 2 ley 25.323 en apercibimiento"""
    r = calcular_indemnizacion("2022-01-01", "2025-01-15", 800000, "sin_causa", False, False)
    assert r["rubros_apercibimiento"]["multa_ley25323_art2"]["monto"] > 0
    antiguedad = r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"]
    preaviso = r["rubros_inmediatos"]["preaviso"]["monto"]
    integracion = r["rubros_inmediatos"]["integracion_mes"]["monto"]
    expected = (antiguedad + preaviso + integracion) * 0.5
    assert abs(r["rubros_apercibimiento"]["multa_ley25323_art2"]["monto"] - expected) < 1


def test_despido_no_registrado_duplicacion_art1_25323():
    """No registrado -> duplicacion art. 1 Ley 25.323 (100% del art. 245)"""
    r = calcular_indemnizacion("2022-01-01", "2025-01-15", 800000, "sin_causa", False, False)
    antiguedad = r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"]
    duplicacion = r["rubros_inmediatos"]["duplicacion_ley25323_art1"]["monto"]
    assert duplicacion == antiguedad


def test_despido_no_registrado_con_intimacion_art8():
    """No registrado + intimacion (pre-derogacion) -> multa art. 8 Ley 24.013"""
    r = calcular_indemnizacion(
        "2020-01-01", "2024-06-15", 800000, "sin_causa", False, False,
        fecha_intimacion="2024-05-01",
    )
    multa = r["rubros_requiere_intimacion"]["multa_ley24013_art8"]
    assert multa["monto"] > 0
    # 25% x 52 meses x $800.000
    meses = 52  # ene 2020 a may 2024
    expected = 800000 * meses * 0.25
    assert abs(multa["monto"] - expected) < 1


def test_despido_no_registrado_sin_intimacion_advierte():
    """No registrado sin intimacion (pre-derogacion) -> monto 0 + monto_potencial + accion requerida"""
    r = calcular_indemnizacion("2020-01-01", "2024-06-15", 800000, "sin_causa", False, False)
    multa = r["rubros_requiere_intimacion"]["multa_ley24013_art8"]
    assert multa["monto"] == 0
    assert "accion_requerida" in multa
    # Monto potencial calculado con egreso como referencia: 25% x 53 meses x $800.000
    assert multa["monto_potencial"] == 800000 * 53 * 0.25
    # Art. 15 potencial = arts. 245 + 232 + 233
    art15 = r["rubros_requiere_intimacion"]["duplicacion_ley24013_art15"]
    assert art15["monto"] == 0
    antiguedad = r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"]
    preaviso = r["rubros_inmediatos"]["preaviso"]["monto"]
    integracion = r["rubros_inmediatos"]["integracion_mes"]["monto"]
    assert abs(art15["monto_potencial"] - (antiguedad + preaviso + integracion)) < 1


def test_art15_duplicacion_por_despido_represalia():
    """Despido dentro de 2 anos de intimacion (pre-derogacion) -> art. 15 duplica arts. 232+233+245"""
    r = calcular_indemnizacion(
        "2020-01-01", "2024-06-15", 800000, "sin_causa", False, False,
        fecha_intimacion="2024-05-01",
    )
    assert "duplicacion_ley24013_art15" in r["rubros_requiere_intimacion"]
    antiguedad = r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"]
    preaviso = r["rubros_inmediatos"]["preaviso"]["monto"]
    integracion = r["rubros_inmediatos"]["integracion_mes"]["monto"]
    art15 = r["rubros_requiere_intimacion"]["duplicacion_ley24013_art15"]["monto"]
    assert abs(art15 - (antiguedad + preaviso + integracion)) < 1


def test_registro_parcial_art9():
    """Remuneracion registrada menor a la real (pre-derogacion) -> multa art. 9"""
    r = calcular_indemnizacion(
        "2020-01-01", "2024-06-15", 800000, "sin_causa", True, False,
        fecha_intimacion="2024-05-01",
        remuneracion_registrada=400000,
    )
    multa = r["rubros_requiere_intimacion"]["multa_ley24013_art9"]
    assert multa["monto"] > 0
    # 25% x 52 meses x $400.000 (diferencia)
    expected = 400000 * 52 * 0.25
    assert abs(multa["monto"] - expected) < 1


def test_fecha_registro_falsa_art10():
    """Fecha de ingreso falsa (pre-derogacion) -> multa art. 10"""
    r = calcular_indemnizacion(
        "2020-01-01", "2024-06-15", 800000, "sin_causa", True, False,
        fecha_intimacion="2024-05-01",
        fecha_registro_falsa="2021-06-01",
    )
    multa = r["rubros_requiere_intimacion"]["multa_ley24013_art10"]
    assert multa["monto"] > 0
    # 25% x 17 meses x $800.000
    expected = 800000 * 17 * 0.25
    assert abs(multa["monto"] - expected) < 1


def test_ley24013_derogada_post_20240708():
    """Despido posterior a derogacion de Ley 24.013 -> no calcula multas arts. 8-15"""
    r = calcular_indemnizacion(
        "2022-01-01", "2025-01-15", 800000, "sin_causa", False, False,
        fecha_intimacion="2024-12-01",
    )
    # No debe haber multas de Ley 24.013
    assert "multa_ley24013_art8" not in r["rubros_requiere_intimacion"]
    assert "duplicacion_ley24013_art15" not in r["rubros_requiere_intimacion"]
    # Debe advertir sobre la derogacion
    assert any("27.742" in n for n in r["notas_calculo"])


def test_con_preaviso_otorgado():
    """Preaviso otorgado -> preaviso = 0, integracion = 0, SAC s/preaviso = 0"""
    r = calcular_indemnizacion("2020-01-01", "2025-06-15", 1000000, "sin_causa", True, True)
    assert r["rubros_inmediatos"]["preaviso"]["monto"] == 0
    assert r["rubros_inmediatos"]["integracion_mes"]["monto"] == 0
    assert r["rubros_inmediatos"]["sac_sobre_preaviso"]["monto"] == 0


def test_total_es_suma_de_categorias():
    """Cada subtotal debe ser la suma de sus rubros"""
    r = calcular_indemnizacion(
        "2020-01-01", "2024-06-15", 800000, "sin_causa", False, False,
        fecha_intimacion="2024-05-01",
    )
    suma_inm = sum(rubro["monto"] for rubro in r["rubros_inmediatos"].values())
    suma_int = sum(rubro["monto"] for rubro in r["rubros_requiere_intimacion"].values())
    suma_ape = sum(rubro["monto"] for rubro in r["rubros_apercibimiento"].values())
    assert abs(r["totales"]["inmediatos"] - suma_inm) < 1
    assert abs(r["totales"]["requiere_intimacion"] - suma_int) < 1
    assert abs(r["totales"]["apercibimiento"] - suma_ape) < 1
    # No debe haber total general (evita que el LLM sume categorias incompatibles)
    assert "general" not in r["totales"]


def test_periodo_prueba():
    """Antiguedad < 3 meses -> preaviso 15 dias, no corresponde art. 245 ni integracion"""
    r = calcular_indemnizacion("2025-01-01", "2025-02-15", 1000000, "sin_causa", True, False)
    assert r["rubros_inmediatos"]["preaviso"]["monto"] == 500000
    assert r["rubros_inmediatos"]["indemnizacion_antiguedad"]["monto"] == 0
    assert r["rubros_inmediatos"]["integracion_mes"]["monto"] == 0


def test_no_registrado_sin_intimacion_accion_requerida():
    """No registrado sin intimacion (pre-derogacion) -> multa art.8 monto 0 con accion_requerida"""
    r = calcular_indemnizacion("2020-01-01", "2024-06-15", 800000, "sin_causa", False, False)
    multa = r["rubros_requiere_intimacion"]["multa_ley24013_art8"]
    assert multa["monto"] == 0
    assert "accion_requerida" in multa


def test_preaviso_nota_cerca_umbral_5_anios():
    """4 anios 10 meses -> 5 periodos art 245 pero preaviso 1 mes, con nota y escenario alternativo"""
    r = calcular_indemnizacion("2020-04-01", "2025-02-15", 1000000, "sin_causa", True, False)
    assert r["antiguedad"]["anos"] == 4
    assert r["antiguedad"]["periodos_indemnizatorios"] == 5
    preaviso = r["rubros_inmediatos"]["preaviso"]
    assert preaviso["monto"] == 1000000  # 1 mes, no 2
    assert "nota" in preaviso
    assert "231" in preaviso["nota"]
    # Escenario alternativo con 2 meses
    assert preaviso["monto_alternativo"] == 2000000
    assert preaviso["diferencia"] == 1000000


def test_art80_certificados_no_entregados():
    """Certificados no entregados -> multa de 3 sueldos"""
    r = calcular_indemnizacion(
        "2022-01-01", "2025-01-15", 1000000, "sin_causa", True, False,
        certificados_entregados=False,
    )
    assert "multa_art80_certificados" in r["rubros_inmediatos"]
    assert r["rubros_inmediatos"]["multa_art80_certificados"]["monto"] == 3000000
    assert "Art. 80" in r["rubros_inmediatos"]["multa_art80_certificados"]["fundamento"]


def test_totales_formateados():
    """Totales incluyen inmediatos_formateado"""
    r = calcular_indemnizacion("2022-01-01", "2025-01-15", 800000, "sin_causa", False, False)
    assert r["totales"]["inmediatos_formateado"] == f"${r['totales']['inmediatos']:,.0f}"


def test_no_contiene_resumen_ni_documentos():
    """El output no debe contener resumen pre-formateado ni secuencia de documentos"""
    r = calcular_indemnizacion("2022-01-01", "2025-01-15", 800000, "sin_causa", False, False)
    assert "resumen" not in r
    assert "documentos" not in r


def test_art80_certificados_entregados():
    """Certificados entregados -> no hay multa"""
    r = calcular_indemnizacion(
        "2022-01-01", "2025-01-15", 1000000, "sin_causa", True, False,
        certificados_entregados=True,
    )
    assert "multa_art80_certificados" not in r["rubros_inmediatos"]


def test_art80_certificados_no_informado():
    """Certificados no informados -> accion_requerida"""
    r = calcular_indemnizacion(
        "2022-01-01", "2025-01-15", 1000000, "sin_causa", True, False,
        certificados_entregados=None,
    )
    assert "multa_art80_certificados" in r["rubros_inmediatos"]
    assert r["rubros_inmediatos"]["multa_art80_certificados"]["monto"] == 0
    assert "accion_requerida" in r["rubros_inmediatos"]["multa_art80_certificados"]
