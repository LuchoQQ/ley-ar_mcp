from ley_ar.services.intereses import calcular_intereses


def test_interes_basico():
    r = calcular_intereses(1000000, "2024-01-01", "2024-07-01")
    assert r["monto_base"] == 1000000
    assert r["monto_intereses"] > 0
    assert r["monto_con_intereses"] > 1000000
    assert r["dias_totales"] > 0
    assert len(r["detalle_periodos"]) > 0


def test_interes_cero_misma_fecha():
    r = calcular_intereses(1000000, "2024-01-01", "2024-01-01")
    assert r["monto_intereses"] == 0
    assert r["dias"] == 0


def test_fecha_hasta_anterior():
    r = calcular_intereses(1000000, "2025-01-01", "2024-01-01")
    assert r["monto_intereses"] == 0


def test_detalle_periodos():
    """Cada periodo debe tener dias, tna e interes"""
    r = calcular_intereses(500000, "2024-01-01", "2024-04-01")
    for p in r["detalle_periodos"]:
        assert "dias" in p
        assert "tna" in p
        assert "interes" in p
        assert p["dias"] > 0


def test_monto_con_intereses_suma():
    """monto_con_intereses = monto_base + monto_intereses"""
    r = calcular_intereses(1000000, "2023-01-01", "2024-01-01")
    assert abs(r["monto_con_intereses"] - (r["monto_base"] + r["monto_intereses"])) < 0.01


def test_interes_un_mes():
    """Interes de un solo mes"""
    r = calcular_intereses(1000000, "2024-01-01", "2024-02-01")
    assert len(r["detalle_periodos"]) == 1
    assert r["detalle_periodos"][0]["dias"] == 31


def test_tasa_default_futuro():
    """Fechas futuras usan tasa default"""
    r = calcular_intereses(1000000, "2030-01-01", "2030-07-01")
    assert r["monto_intereses"] > 0
