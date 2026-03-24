from ley_ar.tools.liquidacion_final import liquidacion_final


def test_renuncia_basica():
    r = liquidacion_final("2020-01-01", "2025-06-15", 1000000)
    assert "error" not in r
    assert r["motivo"] == "Renuncia del trabajador"
    assert r["rubros"]["dias_trabajados"]["monto"] > 0
    assert r["rubros"]["sac_proporcional"]["monto"] > 0
    assert r["rubros"]["vacaciones_proporcionales"]["monto"] > 0
    assert r["rubros"]["sac_sobre_vacaciones"]["monto"] > 0
    assert r["total"] > 0
    # Total debe ser la suma de todos los rubros
    suma = sum(rubro["monto"] for rubro in r["rubros"].values())
    assert abs(r["total"] - suma) < 0.01


def test_dias_trabajados_proporcional():
    """Dia 15 del mes -> 15/30 de sueldo"""
    r = liquidacion_final("2020-01-01", "2025-03-15", 900000)
    assert r["rubros"]["dias_trabajados"]["monto"] == 15 * (900000 / 30)


def test_sac_proporcional_primer_semestre():
    """SAC proporcional en primer semestre"""
    r = liquidacion_final("2020-01-01", "2025-03-15", 1000000)
    sac = r["rubros"]["sac_proporcional"]
    assert sac["monto"] > 0
    assert "Art. 123 LCT" in sac["fundamento"]


def test_vacaciones_con_gozadas():
    """Vacaciones descontando dias ya gozadas"""
    r_sin = liquidacion_final("2020-01-01", "2025-06-15", 1000000, dias_vacaciones_gozadas=0)
    r_con = liquidacion_final("2020-01-01", "2025-06-15", 1000000, dias_vacaciones_gozadas=10)
    assert r_con["rubros"]["vacaciones_proporcionales"]["monto"] < r_sin["rubros"]["vacaciones_proporcionales"]["monto"]


def test_fallecimiento_incluye_art248():
    """Fallecimiento incluye indemnizacion art. 248 (50% de art. 245)"""
    r = liquidacion_final("2020-01-01", "2025-06-15", 1000000, motivo="fallecimiento")
    assert "indemnizacion_fallecimiento" in r["rubros"]
    indem = r["rubros"]["indemnizacion_fallecimiento"]
    assert indem["monto"] > 0
    assert "Art. 248 LCT" in indem["fundamento"]


def test_jubilacion():
    r = liquidacion_final("2020-01-01", "2025-06-15", 1000000, motivo="jubilacion")
    assert r["motivo"] == "Jubilacion"
    assert "indemnizacion_fallecimiento" not in r["rubros"]


def test_motivo_invalido():
    r = liquidacion_final("2020-01-01", "2025-06-15", 1000000, motivo="invalido")
    assert "error" in r


def test_fecha_invalida():
    r = liquidacion_final("no-es-fecha", "2025-06-15", 1000000)
    assert "error" in r


def test_fecha_egreso_anterior():
    r = liquidacion_final("2025-06-15", "2020-01-01", 1000000)
    assert "error" in r


def test_remuneracion_negativa():
    r = liquidacion_final("2020-01-01", "2025-06-15", -100)
    assert "error" in r


def test_antiguedad_correcta():
    r = liquidacion_final("2020-01-01", "2025-06-15", 1000000)
    assert r["antiguedad"]["anos"] == 5
    assert r["antiguedad"]["meses"] == 5
