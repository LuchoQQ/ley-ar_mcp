"""Tests de validacion de inputs para todas las tools que reciben fechas y enums."""

from ley_ar.tools.calcular_indem import calcular_indemnizacion
from ley_ar.tools.verificar_prescrip import verificar_prescripcion


# ── calcular_indemnizacion ──

def test_causa_invalida():
    r = calcular_indemnizacion("2020-01-01", "2025-01-01", 1000000, causa="banana")
    assert "error" in r
    assert "banana" in r["error"]


def test_fecha_ingreso_invalida():
    r = calcular_indemnizacion("no-fecha", "2025-01-01", 1000000)
    assert "error" in r
    assert "fecha_ingreso" in r["error"]


def test_fecha_egreso_invalida():
    r = calcular_indemnizacion("2020-01-01", "no-fecha", 1000000)
    assert "error" in r
    assert "fecha_egreso" in r["error"]


def test_egreso_anterior_a_ingreso():
    r = calcular_indemnizacion("2025-01-01", "2020-01-01", 1000000)
    assert "error" in r
    assert "posterior" in r["error"]


def test_remuneracion_cero():
    r = calcular_indemnizacion("2020-01-01", "2025-01-01", 0)
    assert "error" in r


def test_remuneracion_negativa():
    r = calcular_indemnizacion("2020-01-01", "2025-01-01", -500)
    assert "error" in r


def test_fecha_intimacion_invalida():
    r = calcular_indemnizacion(
        "2020-01-01", "2025-01-01", 1000000,
        registrado=False, fecha_intimacion="invalida",
    )
    assert "error" in r
    assert "fecha_intimacion" in r["error"]


def test_fecha_registro_falsa_invalida():
    r = calcular_indemnizacion(
        "2020-01-01", "2024-01-01", 1000000,
        registrado=False, fecha_registro_falsa="invalida",
    )
    assert "error" in r
    assert "fecha_registro_falsa" in r["error"]


# ── verificar_prescripcion ──

def test_prescripcion_fecha_invalida():
    r = verificar_prescripcion("despido", "no-fecha")
    assert "error" in r


def test_prescripcion_consulta_invalida():
    r = verificar_prescripcion("despido", "2025-01-01", "no-fecha")
    assert "error" in r
