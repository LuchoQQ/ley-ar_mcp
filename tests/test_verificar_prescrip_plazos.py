from ley_ar.tools.verificar_prescrip import consultar_plazos_procesales


def test_listar_todos_plazos():
    r = consultar_plazos_procesales()
    assert "plazos" in r
    assert r["total"] > 0
    for p in r["plazos"]:
        assert "tipo" in p
        assert "dias" in p
        assert "fundamento" in p


def test_plazo_especifico():
    r = consultar_plazos_procesales("certificados_art80")
    assert "error" not in r
    assert r["tipo"] == "certificados_art80"
    assert r["dias"] == 30
    assert r["tipo_dias"] == "habiles"


def test_plazo_inexistente():
    r = consultar_plazos_procesales("inexistente")
    assert "error" in r


def test_plazo_intimacion_registro():
    r = consultar_plazos_procesales("intimacion_registro")
    assert r["dias"] == 30
    assert r["tipo_dias"] == "corridos"
    assert "Art. 11 Ley 24.013" in r["fundamento"]


def test_plazo_copia_telegrama_afip():
    r = consultar_plazos_procesales("copia_telegrama_afip")
    assert r["dias"] == 24
    assert r["tipo_dias"] == "horas"
