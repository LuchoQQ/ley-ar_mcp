import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ley_ar.tools.calcular_indem import calcular_indemnizacion


def test_despido_menos_1_anio():
    """Antiguedad 8 meses -> 1 periodo (fraccion > 3 meses)"""
    r = calcular_indemnizacion("2024-06-01", "2025-02-15", 1000000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 1
    assert r["rubros"]["indemnizacion_antiguedad"]["monto"] == 1000000
    assert r["rubros"]["preaviso"]["monto"] == 1000000  # 1 mes (>= 3 meses, < 5 anos)


def test_despido_exacto_5_anios():
    """Antiguedad exacta 5 anos -> 5 periodos, preaviso 2 meses"""
    r = calcular_indemnizacion("2020-01-15", "2025-01-15", 1200000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 5
    assert r["rubros"]["preaviso"]["monto"] == 2400000  # 2 meses x $1.200.000


def test_despido_10_anios():
    """Antiguedad 10 anos -> 10 periodos, vacaciones 28 dias"""
    r = calcular_indemnizacion("2015-03-01", "2025-03-01", 900000, "sin_causa", True, False)
    assert r["antiguedad"]["periodos_indemnizatorios"] == 10
    assert r["rubros"]["indemnizacion_antiguedad"]["monto"] == 9000000


def test_despido_inicio_mes():
    """Despido el dia 3 -> integracion mes grande"""
    r = calcular_indemnizacion("2020-01-01", "2025-01-03", 1000000, "sin_causa", True, False)
    assert r["rubros"]["integracion_mes"]["monto"] > 0
    # 28 dias restantes x ($1.000.000 / 30) ~ $933.333
    assert r["rubros"]["integracion_mes"]["monto"] > 900000


def test_despido_fin_mes():
    """Despido el dia 31 -> integracion mes = 0"""
    r = calcular_indemnizacion("2020-01-01", "2025-01-31", 1000000, "sin_causa", True, False)
    assert r["rubros"]["integracion_mes"]["monto"] == 0


def test_despido_no_registrado():
    """Relacion no registrada -> multa art. 2 ley 25.323 = 50%"""
    r = calcular_indemnizacion("2022-01-01", "2025-01-15", 800000, "sin_causa", False, False)
    assert r["rubros"]["multa_ley25323_art2"]["monto"] > 0
    # Multa = 50% x (antiguedad + preaviso + integracion)
    antiguedad = r["rubros"]["indemnizacion_antiguedad"]["monto"]
    preaviso = r["rubros"]["preaviso"]["monto"]
    integracion = r["rubros"]["integracion_mes"]["monto"]
    expected = (antiguedad + preaviso + integracion) * 0.5
    assert abs(r["rubros"]["multa_ley25323_art2"]["monto"] - expected) < 1


def test_con_preaviso_otorgado():
    """Preaviso otorgado -> preaviso = 0, integracion = 0, SAC s/preaviso = 0"""
    r = calcular_indemnizacion("2020-01-01", "2025-06-15", 1000000, "sin_causa", True, True)
    assert r["rubros"]["preaviso"]["monto"] == 0
    assert r["rubros"]["integracion_mes"]["monto"] == 0
    assert r["rubros"]["sac_sobre_preaviso"]["monto"] == 0


def test_total_es_suma_de_rubros():
    """El total debe ser la suma de todos los rubros"""
    r = calcular_indemnizacion("2021-03-01", "2025-03-01", 1500000, "sin_causa", True, False)
    suma = sum(rubro["monto"] for rubro in r["rubros"].values())
    assert abs(r["total"] - suma) < 1


def test_periodo_prueba():
    """Antiguedad < 3 meses -> preaviso 15 dias (0.5 mes)"""
    r = calcular_indemnizacion("2025-01-01", "2025-02-15", 1000000, "sin_causa", True, False)
    assert r["rubros"]["preaviso"]["monto"] == 500000  # 0.5 x $1.000.000
