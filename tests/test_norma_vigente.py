import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ley_ar.services.legislation_store import LegislationStore
from ley_ar.tools.norma_vigente import norma_vigente

store = LegislationStore()


def test_lct_245():
    r = norma_vigente(store, "LCT", "245")
    assert "error" not in r
    assert r["articulo"] == "245"
    assert "despido" in r["texto"].lower()


def test_lct_178():
    r = norma_vigente(store, "LCT", "178")
    assert "error" not in r
    assert r["articulo"] == "178"


def test_alias_numero():
    r = norma_vigente(store, "20744", "245")
    assert "error" not in r
    assert r["articulo"] == "245"


def test_alias_ley_con_punto():
    r = norma_vigente(store, "ley 20.744", "1")
    assert "error" not in r


def test_lrt():
    r = norma_vigente(store, "LRT", "6")
    assert "error" not in r


def test_ley_25323():
    r = norma_vigente(store, "25323", "2")
    assert "error" not in r


def test_articulo_inexistente():
    r = norma_vigente(store, "LCT", "9999")
    assert "error" in r


def test_ley_inexistente():
    r = norma_vigente(store, "ZZZZ", "1")
    assert "error" in r
