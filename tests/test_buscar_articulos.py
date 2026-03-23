"""
Tests de buscar_articulos con el sistema experto de situaciones legales.
Valida que cada situacion devuelva exactamente los articulos correctos
para los casos mas comunes en derecho laboral argentino.
"""

from ley_ar.services.legislation_store import LegislationStore
from ley_ar.tools.buscar_articulos import buscar_articulos

store = LegislationStore()


def _ids(result):
    """Extrae IDs (CODIGO_NUM) de los articulos devueltos."""
    return [a["id"] for a in result["articulos"]]


def _has(result, art_id):
    """Verifica que un articulo este en los resultados."""
    return art_id in _ids(result)


# --- Catalogo ---

def test_catalogo_sin_parametros():
    """Sin situacion debe devolver el catalogo completo."""
    r = buscar_articulos(store, None)
    assert r["tipo"] == "catalogo"
    assert r["total"] >= 30
    ids = [s["id"] for s in r["situaciones"]]
    assert "despido_sin_causa" in ids
    assert "accidente_trabajo" in ids


# --- Despido sin causa ---

def test_despido_sin_causa_primarios():
    """Debe incluir los 7 articulos primarios de despido sin causa."""
    r = buscar_articulos(store, "despido_sin_causa")
    assert _has(r, "LCT_245")
    assert _has(r, "LCT_231")
    assert _has(r, "LCT_232")
    assert _has(r, "LCT_233")
    assert _has(r, "LCT_123")
    assert _has(r, "LCT_156")
    assert _has(r, "LCT_80")
    # Solo primarios, sin condicionales
    tipos = {a["tipo"] for a in r["articulos"]}
    assert tipos == {"primario"}


def test_despido_sin_causa_no_registrado():
    """Con condicion no_registrado, agrega LdE y Ley 25.323."""
    r = buscar_articulos(store, "despido_sin_causa", ["no_registrado"])
    assert _has(r, "LEY-25323_1")
    assert _has(r, "LdE_8")
    assert _has(r, "LdE_15")
    # Verifica que los condicionales tienen el tipo correcto
    condicionales = [a for a in r["articulos"] if a["tipo"] == "condicional"]
    assert len(condicionales) == 3
    for c in condicionales:
        assert c["condicion"] == "no_registrado"


def test_despido_sin_causa_multiples_condiciones():
    """Multiples condiciones agregan articulos de cada una."""
    r = buscar_articulos(store, "despido_sin_causa", ["no_registrado", "falta_pago_post_intimacion"])
    assert _has(r, "LEY-25323_1")  # no_registrado
    assert _has(r, "LdE_8")        # no_registrado
    assert _has(r, "LEY-25323_2")  # falta_pago
    assert r["total_articulos"] == 11


def test_despido_sin_causa_condiciones_disponibles():
    """Debe informar condiciones disponibles no usadas."""
    r = buscar_articulos(store, "despido_sin_causa")
    assert "condiciones_disponibles" in r
    conds = r["condiciones_disponibles"]
    assert "no_registrado" in conds
    assert "falta_pago_post_intimacion" in conds


# --- Herencia ---

def test_despido_indirecto_hereda():
    """Despido indirecto hereda todos los articulos de despido sin causa + agrega Art. 246."""
    r = buscar_articulos(store, "despido_indirecto")
    # Propios
    assert _has(r, "LCT_246")
    assert _has(r, "LCT_242")
    # Heredados de despido_sin_causa
    assert _has(r, "LCT_245")
    assert _has(r, "LCT_232")
    assert _has(r, "LCT_80")


def test_despido_embarazo_hereda():
    """Despido por embarazo hereda despido sin causa + agrega Arts. 177, 178, 182."""
    r = buscar_articulos(store, "despido_embarazo")
    # Propios
    assert _has(r, "LCT_177")
    assert _has(r, "LCT_178")
    assert _has(r, "LCT_182")
    # Heredados
    assert _has(r, "LCT_245")
    assert _has(r, "LCT_232")


# --- Composicion ---

def test_composicion_multiple_situaciones():
    """Combinar situaciones devuelve la union sin duplicados."""
    r = buscar_articulos(store, "despido_sin_causa,despido_embarazo")
    ids = _ids(r)
    # De despido_sin_causa
    assert "LCT_245" in ids
    # De despido_embarazo
    assert "LCT_178" in ids
    assert "LCT_182" in ids
    # Sin duplicados
    assert len(ids) == len(set(ids))


def test_composicion_con_condiciones():
    """Condiciones aplican a las situaciones que las tienen."""
    r = buscar_articulos(store, "despido_sin_causa,accidente_trabajo", ["no_registrado", "responsabilidad_civil_empleador"])
    assert _has(r, "LEY-25323_1")  # no_registrado (de despido_sin_causa)
    assert _has(r, "LRT_39")      # resp civil (de accidente_trabajo)
    assert _has(r, "LCT_75")      # resp civil (de accidente_trabajo)


# --- Despido con causa ---

def test_despido_con_causa():
    """Debe incluir Arts. 242, 243 y NO incluir Art. 245 por defecto."""
    r = buscar_articulos(store, "despido_con_causa")
    assert _has(r, "LCT_242")
    assert _has(r, "LCT_243")
    assert not _has(r, "LCT_245")  # No corresponde salvo causa no acreditada


def test_despido_con_causa_no_acreditada():
    """Si la causa no se acredita, agrega Art. 245."""
    r = buscar_articulos(store, "despido_con_causa", ["causa_no_acreditada"])
    assert _has(r, "LCT_242")
    assert _has(r, "LCT_245")


# --- Otras situaciones ---

def test_accidente_trabajo():
    """Debe devolver articulos de la LRT."""
    r = buscar_articulos(store, "accidente_trabajo")
    lrt = [a for a in r["articulos"] if a["id"].startswith("LRT_")]
    assert len(lrt) >= 4


def test_enfermedad_inculpable():
    """Debe devolver Arts. 208-213."""
    r = buscar_articulos(store, "enfermedad_inculpable")
    assert _has(r, "LCT_208")
    assert _has(r, "LCT_211")
    assert _has(r, "LCT_212")


def test_renuncia():
    """Renuncia: Art. 240 + SAC + vacaciones, sin Art. 245."""
    r = buscar_articulos(store, "renuncia")
    assert _has(r, "LCT_240")
    assert _has(r, "LCT_123")
    assert _has(r, "LCT_156")
    assert not _has(r, "LCT_245")


def test_prescripcion():
    """Prescripcion: Arts. 256-259."""
    r = buscar_articulos(store, "prescripcion")
    assert _has(r, "LCT_256")
    assert _has(r, "LCT_257")


# --- Texto completo ---

def test_articulos_tienen_texto():
    """Todos los articulos de LCT/LRT/LdE deben tener texto completo."""
    r = buscar_articulos(store, "despido_sin_causa")
    for a in r["articulos"]:
        assert a["texto"] is not None, f"{a['id']} no tiene texto"
        assert len(a["texto"]) > 50, f"Texto muy corto para {a['id']}"


def test_articulos_tienen_rol():
    """Cada articulo debe explicar su rol en la situacion."""
    r = buscar_articulos(store, "despido_sin_causa")
    for a in r["articulos"]:
        assert len(a["rol"]) > 20, f"Rol muy corto para {a['id']}"


# --- Errores ---

def test_situacion_invalida():
    """Situacion inexistente devuelve error con lista de disponibles."""
    r = buscar_articulos(store, "sarasa")
    assert "error" in r
    assert "situaciones_disponibles" in r


def test_notas_incluidas():
    """El resultado debe incluir notas legales relevantes."""
    r = buscar_articulos(store, "despido_sin_causa")
    assert "notas" in r
    assert len(r["notas"]) > 0


def test_situaciones_relacionadas():
    """Debe sugerir situaciones relacionadas."""
    r = buscar_articulos(store, "despido_sin_causa")
    assert "situaciones_relacionadas" in r
    assert "despido_indirecto" in r["situaciones_relacionadas"]
