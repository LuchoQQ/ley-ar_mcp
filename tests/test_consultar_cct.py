from ley_ar.tools.consultar_cct import consultar_cct


def test_listar_ccts():
    """Sin parametro lista todos los CCTs"""
    r = consultar_cct()
    assert "convenios" in r
    assert r["total"] >= 0
    if r["total"] > 0:
        conv = r["convenios"][0]
        assert "cct" in conv
        assert "nombre" in conv
        assert "tope_245" in conv


def test_cct_especifico():
    """Consultar un CCT que exista"""
    r_lista = consultar_cct()
    if r_lista["total"] > 0:
        cct_id = r_lista["convenios"][0]["cct"]
        r = consultar_cct(cct_id)
        assert "error" not in r
        assert "cct" in r
        assert "nota_tope" in r


def test_cct_inexistente():
    """CCT inexistente devuelve error con lista de disponibles"""
    r = consultar_cct("999/99")
    assert "error" in r
    assert "disponibles" in r
