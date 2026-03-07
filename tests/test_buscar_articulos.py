"""
Tests de buscar_articulos con casos laborales reales.
Valida que el sistema hibrido devuelva los articulos correctos
para las consultas mas comunes en derecho laboral argentino.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ley_ar.services.hybrid_retriever import HybridRetriever
from ley_ar.services.legislation_store import LegislationStore
from ley_ar.tools.buscar_articulos import buscar_articulos

store = LegislationStore()
retriever = HybridRetriever()


def _ids(result):
    """Extrae IDs (CODIGO_NUM) de los articulos devueltos."""
    return [f"{a['codigo']}_{a['articulo']}" for a in result["articulos"]]


def _has(result, art_id):
    """Verifica que un articulo este en los resultados."""
    return art_id in _ids(result)


# --- Despido ---

def test_despido_sin_causa():
    """Art. 245 LCT debe aparecer primero."""
    r = buscar_articulos(retriever, store, "despido sin causa", max_resultados=5)
    assert _has(r, "LCT_245"), f"LCT_245 no encontrado en {_ids(r)}"
    assert _ids(r)[0] == "LCT_245"


def test_despido_durante_embarazo():
    """Debe devolver art. 178 (presuncion por embarazo) y art. 182 (indem agravada)."""
    r = buscar_articulos(retriever, store, "despido durante embarazo", max_resultados=10)
    ids = _ids(r)
    assert _has(r, "LCT_178"), f"LCT_178 no encontrado en {ids}"
    assert _has(r, "LCT_245"), f"LCT_245 no encontrado en {ids}"


def test_despido_con_causa():
    """Art. 242 (justa causa) y 243 (comunicacion) deben aparecer."""
    r = buscar_articulos(retriever, store, "despido con justa causa", max_resultados=10)
    ids = _ids(r)
    assert _has(r, "LCT_242") or _has(r, "LCT_243"), f"Ni 242 ni 243 en {ids}"


def test_despido_discriminatorio():
    """Consulta sobre despido discriminatorio."""
    r = buscar_articulos(retriever, store, "despido discriminatorio", max_resultados=10)
    assert r["total_encontrados"] > 0


# --- Preaviso ---

def test_preaviso():
    """Arts. 231-232 deben aparecer para consulta de preaviso."""
    r = buscar_articulos(retriever, store, "preaviso de despido", max_resultados=10)
    ids = _ids(r)
    assert _has(r, "LCT_231") or _has(r, "LCT_232"), f"Ni 231 ni 232 en {ids}"


# --- Remuneracion ---

def test_horas_extras():
    """Art. 201 LCT sobre horas extras."""
    r = buscar_articulos(retriever, store, "horas extras", max_resultados=5)
    assert r["total_encontrados"] > 0


def test_aguinaldo_sac():
    """SAC / aguinaldo."""
    r = buscar_articulos(retriever, store, "aguinaldo", max_resultados=5)
    assert r["total_encontrados"] > 0


# --- Trabajo no registrado ---

def test_trabajo_en_negro():
    """Ley 24.013 arts. 8-10 para trabajo no registrado."""
    r = buscar_articulos(retriever, store, "trabajo en negro", max_resultados=10)
    assert r["total_encontrados"] > 0


# --- Accidentes ---

def test_accidente_de_trabajo():
    """LRT debe aparecer para accidentes laborales."""
    r = buscar_articulos(retriever, store, "accidente de trabajo", max_resultados=10)
    ids = _ids(r)
    lrt_arts = [i for i in ids if i.startswith("LRT_")]
    assert len(lrt_arts) > 0, f"Ningun articulo LRT en {ids}"


# --- Licencias ---

def test_licencia_por_enfermedad():
    r = buscar_articulos(retriever, store, "licencia por enfermedad", max_resultados=10)
    assert r["total_encontrados"] > 0


def test_licencia_por_maternidad():
    r = buscar_articulos(retriever, store, "licencia por maternidad", max_resultados=10)
    assert r["total_encontrados"] > 0


# --- Filtro por ley ---

def test_filtro_por_ley_lct():
    """Filtrar por LCT debe devolver solo articulos de LCT."""
    r = buscar_articulos(retriever, store, "despido", ley="LCT", max_resultados=10)
    ids = _ids(r)
    for art_id in ids:
        assert art_id.startswith("LCT_"), f"{art_id} no es LCT"


def test_filtro_por_ley_lrt():
    """Filtrar por LRT."""
    r = buscar_articulos(retriever, store, "accidente", ley="LRT", max_resultados=10)
    ids = _ids(r)
    for art_id in ids:
        assert art_id.startswith("LRT_"), f"{art_id} no es LRT"


# --- Calidad de respuesta ---

def test_devuelve_texto_completo():
    """Los articulos devueltos deben tener texto."""
    r = buscar_articulos(retriever, store, "indemnizacion por despido", max_resultados=3)
    for a in r["articulos"]:
        assert len(a["texto"]) > 50, f"Texto muy corto para {a['codigo']}_{a['articulo']}"
        assert a["ley"] != ""
        assert a["capitulo"] != "" or a["seccion"] != ""


def test_devuelve_descriptores():
    """Cada articulo debe tener descriptores asociados."""
    r = buscar_articulos(retriever, store, "despido sin causa", max_resultados=3)
    for a in r["articulos"]:
        assert len(a["descriptores"]) > 0


def test_max_resultados_respetado():
    r3 = buscar_articulos(retriever, store, "despido", max_resultados=3)
    r10 = buscar_articulos(retriever, store, "despido", max_resultados=10)
    assert len(r3["articulos"]) <= 3
    assert len(r10["articulos"]) <= 10
