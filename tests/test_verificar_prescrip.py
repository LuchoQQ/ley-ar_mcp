from ley_ar.tools.verificar_prescrip import verificar_prescripcion


def test_no_prescripto():
    r = verificar_prescripcion("despido", "2025-01-01", "2026-01-01")
    assert r["prescripto"] is False
    assert r["dias_restantes"] == 365


def test_prescripto():
    r = verificar_prescripcion("despido", "2023-01-01", "2026-01-01")
    assert r["prescripto"] is True
    assert r["dias_restantes"] == 0


def test_urgencia_menos_6_meses():
    r = verificar_prescripcion("despido", "2024-06-01", "2026-03-01")
    assert r["prescripto"] is False
    assert r["dias_restantes"] < 180
    assert "menos de 6 meses" in r["advertencia"]


def test_accidente():
    r = verificar_prescripcion("accidente", "2025-01-01", "2026-01-01")
    assert r["prescripto"] is False
    assert r["fundamento"] == "Art. 44 LRT"


def test_tipo_invalido():
    r = verificar_prescripcion("inexistente", "2025-01-01")
    assert "error" in r
